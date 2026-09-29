//! A persistent, incremental index: build once, add names later, and ask
//! "which stored names match this one?" without rescanning the list.
//!
//! Every stored name `r` of length `l` is cut into `k + 1` segments for each
//! `k` it may need: `k = max_edits(L)` for every length `L >= l` that could still
//! pair with it (`L - k(L) <= l`). That set depends only on `l` and the
//! threshold, so names added later never force old ones to be re-indexed.
//!
//! A query `q` then looks up, for each compatible stored length, its own
//! substrings at the positions a surviving segment could occupy. The pigeonhole
//! argument of PASS-JOIN holds whichever string is longer: with at most `k`
//! edits between `q` and `r`, one of `r`'s `k + 1` segments is untouched and
//! appears in `q` shifted by at most `k`. So a query returns exactly what
//! comparing it with every stored name would.

use crate::core::{self, key, max_edits, segment, sketch, Norm, Prepared, Rule, Sketch};
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};

pub struct Index {
    threshold: f64,
    norm: Norm,
    raw: Vec<String>,
    names: Vec<Vec<char>>,
    sketches: Vec<Sketch>,
    by_len: Vec<Vec<u32>>,
    segments: HashMap<u64, Vec<u32>>,
    ks_cache: HashMap<usize, Vec<usize>>,
}

impl Index {
    pub fn new(threshold: f64, norm: Norm) -> Self {
        Index {
            threshold,
            norm,
            raw: Vec::new(),
            names: Vec::new(),
            sketches: Vec::new(),
            by_len: Vec::new(),
            segments: HashMap::new(),
            ks_cache: HashMap::new(),
        }
    }

    pub fn threshold(&self) -> f64 {
        self.threshold
    }

    pub fn norm(&self) -> Norm {
        self.norm
    }

    pub fn len(&self) -> usize {
        self.names.len()
    }

    pub fn is_empty(&self) -> bool {
        self.names.is_empty()
    }

    pub fn raw_names(&self) -> &[String] {
        &self.raw
    }

    /// Wide thresholds make segments too short to filter; such an index just scans.
    fn scans(&self) -> bool {
        self.threshold >= 0.5
    }

    /// The segmentations a stored name of length `l` needs (only those with non-empty segments).
    fn ks_for_len(&mut self, l: usize) -> Vec<usize> {
        if let Some(ks) = self.ks_cache.get(&l) {
            return ks.clone();
        }
        let mut ks = Vec::new();
        // threshold < 0.5 means L - k(L) >= L / 2, so no L beyond 2l + 1 can pair with l.
        for big in l.max(1)..=(2 * l + 1) {
            let k = max_edits(big, self.threshold);
            if big - k <= l && l > k && !ks.contains(&k) {
                ks.push(k);
            }
        }
        self.ks_cache.insert(l, ks.clone());
        ks
    }

    /// Add names; returns the id of the first one (ids are consecutive).
    pub fn add(&mut self, names: &[String]) -> usize {
        let first = self.names.len();
        let cleaned: Vec<Vec<char>> = names
            .par_iter()
            .map(|n| core::normalize_with(n, self.norm))
            .collect();
        for (offset, (raw, name)) in names.iter().zip(cleaned).enumerate() {
            let id = (first + offset) as u32;
            let l = name.len();
            if self.by_len.len() <= l {
                self.by_len.resize(l + 1, Vec::new());
            }
            self.by_len[l].push(id);
            if !self.scans() {
                for k in self.ks_for_len(l) {
                    for seg in 0..=k {
                        let (start, len) = segment(l, k, seg);
                        self.segments
                            .entry(key(l, k, seg, &name[start..start + len]))
                            .or_default()
                            .push(id);
                    }
                }
            }
            self.sketches.push(sketch(&name));
            self.names.push(name);
            self.raw.push(raw.clone());
        }
        first
    }

    /// Stored names matching `query`: `(id, score)` sorted by id.
    pub fn query(&self, query: &str) -> Vec<(usize, f64)> {
        let q = core::normalize_with(query, self.norm);
        let (pq, sq) = (Prepared::new(&q), sketch(&q));
        let t = self.threshold;
        let rule = Rule::new(t, q.len().max(self.by_len.len()));
        let check = |r: usize| {
            core::score(&pq, &q, &sq, &self.names[r], &self.sketches[r], &rule).map(|s| (r, s))
        };
        if self.scans() {
            return (0..self.names.len()).filter_map(check).collect();
        }
        let lq = q.len();
        let max_len = self.by_len.len().saturating_sub(1);
        let mut cands: HashSet<u32> = HashSet::new();
        if lq == 0 {
            if let Some(empties) = self.by_len.first() {
                cands.extend(empties.iter().copied());
            }
        } else {
            // Stored names no longer than q allow k(lq) edits; longer ones allow k(lr).
            let lower = lq.saturating_sub(max_edits(lq, t));
            let mut lr = lower.max(1);
            while lr <= max_len {
                let k = if lr <= lq {
                    max_edits(lq, t)
                } else {
                    max_edits(lr, t)
                };
                if lr > lq && lr - k > lq {
                    break;
                }
                let group = &self.by_len[lr];
                if !group.is_empty() {
                    if lr <= k {
                        cands.extend(group.iter().copied());
                    } else {
                        for seg in 0..=k {
                            let (start, len) = segment(lr, k, seg);
                            if len > lq {
                                continue;
                            }
                            let lo = start.saturating_sub(k);
                            let hi = (start + k).min(lq - len);
                            if lo > hi {
                                continue;
                            }
                            for pos in lo..=hi {
                                if let Some(ids) =
                                    self.segments.get(&key(lr, k, seg, &q[pos..pos + len]))
                                {
                                    cands.extend(ids.iter().copied());
                                }
                            }
                        }
                    }
                }
                lr += 1;
            }
        }
        let mut out: Vec<(usize, f64)> = cands
            .into_iter()
            .filter_map(|r| check(r as usize))
            .collect();
        out.sort_unstable_by_key(|&(r, _)| r);
        out
    }

    /// `query` for many names at once, in parallel.
    pub fn query_many(&self, queries: &[String]) -> Vec<Vec<(usize, f64)>> {
        queries.par_iter().map(|q| self.query(q)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn name() -> impl Strategy<Value = String> {
        prop::string::string_regex("[abcçdeşğ ]{0,40}").unwrap()
    }

    fn brute(stored: &[String], q: &str, t: f64, norm: Norm) -> Vec<(usize, f64)> {
        let qc = core::normalize_with(q, norm);
        let (pq, sq) = (Prepared::new(&qc), sketch(&qc));
        stored
            .iter()
            .enumerate()
            .filter_map(|(i, s)| {
                let sc = core::normalize_with(s, norm);
                core::score(&pq, &qc, &sq, &sc, &sketch(&sc), &Rule::new(t, 0)).map(|x| (i, x))
            })
            .collect()
    }

    proptest! {
        #![proptest_config(ProptestConfig::default())]

        #[test]
        fn query_equals_scanning_everything(
            first in prop::collection::vec(name(), 0..40),
            later in prop::collection::vec(name(), 0..20),
            queries in prop::collection::vec(name(), 1..8),
            t in 0.0f64..0.6,
            strip in any::<bool>(),
        ) {
            let norm = Norm { token_sort: false, strip_suffixes: strip };
            let mut idx = Index::new(t, norm);
            idx.add(&first);
            idx.add(&later); // incremental: added after the first batch was indexed
            let stored: Vec<String> = first.iter().chain(later.iter()).cloned().collect();
            for q in &queries {
                prop_assert_eq!(idx.query(q), brute(&stored, q, t, norm));
            }
        }
    }
}
