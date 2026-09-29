//! The algorithms, with no Python in sight, so they can be tested with `cargo test`.
//!
//! Rule: two names are duplicates when `edit_distance / longer_length <= threshold`,
//! after normalization. Every search strategy here must return exactly the pairs
//! the brute-force search returns; the tests check that.

use rayon::prelude::*;
use std::collections::HashMap;

/// Lowercase, collapse whitespace, and optionally sort the words, so that
/// "ACME  Ltd" == "acme ltd" and, with `token_sort`, "Ltd Acme" == "Acme Ltd".
pub fn normalize(name: &str, token_sort: bool) -> Vec<char> {
    let lowered = name.to_lowercase();
    let mut words: Vec<&str> = lowered.split_whitespace().collect();
    if token_sort {
        words.sort_unstable();
    }
    words.join(" ").chars().collect()
}

/// Classic dynamic-programming edit distance, one row of memory.
pub fn levenshtein_dp(a: &[char], b: &[char]) -> usize {
    let (a, b) = if a.len() < b.len() { (b, a) } else { (a, b) };
    let mut row: Vec<usize> = (0..=b.len()).collect();
    for (i, ca) in a.iter().enumerate() {
        let mut diagonal = row[0];
        row[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let above = row[j + 1];
            row[j + 1] = (above + 1)
                .min(row[j] + 1)
                .min(diagonal + usize::from(ca != cb));
            diagonal = above;
        }
    }
    row[b.len()]
}

/// Match masks for Myers' algorithm: bit `i` of `mask(c)` is set when `pattern[i] == c`.
pub struct Pattern {
    ascii: [u64; 128],
    other: HashMap<char, u64>,
    len: usize,
}

impl Pattern {
    /// Only patterns of up to 64 characters fit in one machine word.
    pub fn new(pattern: &[char]) -> Option<Self> {
        if pattern.is_empty() || pattern.len() > 64 {
            return None;
        }
        let mut ascii = [0u64; 128];
        let mut other = HashMap::new();
        for (i, &c) in pattern.iter().enumerate() {
            let bit = 1u64 << i;
            if (c as u32) < 128 {
                ascii[c as usize] |= bit;
            } else {
                *other.entry(c).or_insert(0) |= bit;
            }
        }
        Some(Pattern {
            ascii,
            other,
            len: pattern.len(),
        })
    }

    #[inline]
    fn mask(&self, c: char) -> u64 {
        if (c as u32) < 128 {
            self.ascii[c as usize]
        } else {
            self.other.get(&c).copied().unwrap_or(0)
        }
    }

    /// Edit distance from this pattern to `text`, using Myers' bit-vector
    /// algorithm in the formulation of Hyyrö (2001): one column of the DP
    /// table per text character, as a handful of word operations.
    pub fn distance(&self, text: &[char]) -> usize {
        let m = self.len;
        let last = 1u64 << (m - 1);
        let mut pv: u64 = if m == 64 { !0 } else { (1u64 << m) - 1 };
        let mut mv: u64 = 0;
        let mut score = m;
        for &c in text {
            let eq = self.mask(c);
            let xv = eq | mv;
            let xh = ((eq & pv).wrapping_add(pv) ^ pv) | eq;
            let mut ph = mv | !(xh | pv);
            let mut mh = pv & xh;
            if ph & last != 0 {
                score += 1;
            } else if mh & last != 0 {
                score -= 1;
            }
            // Global distance: the top row of the table grows by one per column.
            ph = (ph << 1) | 1;
            mh <<= 1;
            pv = mh | !(xv | ph);
            mv = ph & xv;
        }
        score
    }
}

/// Edit distance, bit-parallel when one side fits in 64 characters.
pub fn levenshtein(a: &[char], b: &[char]) -> usize {
    if a.is_empty() {
        return b.len();
    }
    if b.is_empty() {
        return a.len();
    }
    let (short, long) = if a.len() <= b.len() { (a, b) } else { (b, a) };
    match Pattern::new(short) {
        Some(p) => p.distance(long),
        None => levenshtein_dp(a, b),
    }
}

/// The largest edit distance `d` a pair with this longer length can have and
/// still match, using the same float comparison as the Python reference.
pub fn max_edits(longest: usize, threshold: f64) -> usize {
    if longest == 0 {
        return 0;
    }
    let mut d = (threshold * longest as f64).floor().max(0.0) as usize;
    while d > 0 && d as f64 / longest as f64 > threshold {
        d -= 1;
    }
    while (d + 1) as f64 / longest as f64 <= threshold && d < longest {
        d += 1;
    }
    d
}

pub type Pair = (usize, usize, f64);

/// Score one pair the way the reference does, or `None` if it isn't a duplicate.
#[inline]
fn score(a: &[char], b: &[char], threshold: f64) -> Option<f64> {
    let longest = a.len().max(b.len());
    if longest == 0 {
        return Some(0.0);
    }
    if a.len().abs_diff(b.len()) as f64 / longest as f64 > threshold {
        return None;
    }
    let s = levenshtein(a, b) as f64 / longest as f64;
    (s <= threshold).then_some(s)
}

/// Compare every pair. O(n^2), but the reference every other strategy is checked against.
pub fn pairs_brute(names: &[Vec<char>], threshold: f64) -> Vec<Pair> {
    (0..names.len())
        .into_par_iter()
        .flat_map_iter(|i| {
            let a = &names[i];
            ((i + 1)..names.len())
                .filter_map(move |j| score(a, &names[j], threshold).map(|s| (i, j, s)))
        })
        .collect()
}

/// Where segment `seg` of `k + 1` starts and how long it is, for a string of length `len`
/// (PASS-JOIN's even partition: the last `len % (k+1)` segments are one longer).
#[inline]
fn segment(len: usize, k: usize, seg: usize) -> (usize, usize) {
    let parts = k + 1;
    let base = len / parts;
    let longer = len % parts;
    let shorter = parts - longer;
    if seg < shorter {
        (seg * base, base)
    } else {
        (shorter * base + (seg - shorter) * (base + 1), base + 1)
    }
}

#[inline]
fn key(len: usize, k: usize, seg: usize, chars: &[char]) -> u64 {
    // FNV-1a. A collision only adds a candidate, which verification then rejects.
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for v in [len as u64, k as u64, seg as u64]
        .into_iter()
        .chain(chars.iter().map(|&c| c as u64))
    {
        h ^= v;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// PASS-JOIN (Li, Deng, Wang, Feng, VLDB 2011) adapted to a threshold relative
/// to the longer string. If `r` (length l) and `s` (length L >= l) are within
/// k = max_edits(L) edits, then cutting `r` into k+1 segments leaves at least
/// one segment untouched by the edits, and it appears in `s` shifted by at most
/// k positions. So we index every segment and only verify strings that share one.
/// No pair is lost: the result equals `pairs_brute`.
pub fn pairs_indexed(names: &[Vec<char>], threshold: f64) -> Vec<Pair> {
    // Wide thresholds leave segments too short to filter anything.
    if threshold >= 0.5 || names.len() < 2 {
        return pairs_brute(names, threshold);
    }
    let max_len = names.iter().map(Vec::len).max().unwrap_or(0);
    let mut by_len: Vec<Vec<usize>> = vec![Vec::new(); max_len + 1];
    for (i, n) in names.iter().enumerate() {
        by_len[n.len()].push(i);
    }
    let k_of: Vec<usize> = (0..=max_len).map(|l| max_edits(l, threshold)).collect();

    // Which segmentations each length needs: one per k of a longer string it can pair with.
    let mut ks_for: Vec<Vec<usize>> = vec![Vec::new(); max_len + 1];
    for big in 1..=max_len {
        if by_len[big].is_empty() {
            continue;
        }
        let k = k_of[big];
        for small in big.saturating_sub(k).max(1)..=big {
            if !by_len[small].is_empty() && small > k && !ks_for[small].contains(&k) {
                ks_for[small].push(k);
            }
        }
    }

    let mut index: HashMap<u64, Vec<u32>> = HashMap::new();
    for (l, ks) in ks_for.iter().enumerate() {
        for &k in ks {
            for &i in &by_len[l] {
                for seg in 0..=k {
                    let (start, len) = segment(l, k, seg);
                    index
                        .entry(key(l, k, seg, &names[i][start..start + len]))
                        .or_default()
                        .push(i as u32);
                }
            }
        }
    }

    let empties = &by_len[0];
    let mut out: Vec<Pair> = (0..names.len())
        .into_par_iter()
        .map_init(
            || (Vec::<u32>::new(), vec![u32::MAX; names.len()]),
            |(cands, seen), s| {
                let text = &names[s];
                let big = text.len();
                let mut found = Vec::new();
                if big == 0 {
                    // Two empty names are identical; pair each with the empties before it.
                    for &r in empties.iter().take_while(|&&r| r < s) {
                        found.push((r, s, 0.0));
                    }
                    return found;
                }
                let k = k_of[big];
                cands.clear();
                let stamp = s as u32;
                let mut add = |r: usize, cands: &mut Vec<u32>| {
                    let shorter = names[r].len() < big;
                    if r != s && (shorter || r < s) && seen[r] != stamp {
                        seen[r] = stamp;
                        cands.push(r as u32);
                    }
                };
                let lo_len = big.saturating_sub(k);
                for (small, group) in by_len.iter().enumerate().take(big + 1).skip(lo_len) {
                    if small == 0 {
                        // An empty name is within k edits of `text` only if k >= big.
                        if k >= big {
                            for &r in empties {
                                add(r, cands);
                            }
                        }
                        continue;
                    }
                    if group.is_empty() {
                        continue;
                    }
                    if small <= k {
                        // Too short to cut into k+1 non-empty segments: check them all.
                        for &r in group.iter() {
                            add(r, cands);
                        }
                        continue;
                    }
                    // Multi-match-aware window (PASS-JOIN, Lemma 3): segment `seg` can only
                    // match where both the edits before it (<= seg) and after it (<= k - seg)
                    // are affordable, given the length difference `delta`.
                    let delta = (big - small) as isize;
                    for seg in 0..=k {
                        let (start, len) = segment(small, k, seg);
                        let (st, sg, rest) = (start as isize, seg as isize, (k - seg) as isize);
                        let lo = (st - sg).max(st + delta - rest).max(0);
                        let hi = (st + sg).min(st + delta + rest).min((big - len) as isize);
                        if lo > hi {
                            continue;
                        }
                        let (lo, hi) = (lo as usize, hi as usize);
                        for pos in lo..=hi {
                            if let Some(ids) = index.get(&key(small, k, seg, &text[pos..pos + len]))
                            {
                                for &r in ids {
                                    add(r as usize, cands);
                                }
                            }
                        }
                    }
                }
                for &r in cands.iter() {
                    let r = r as usize;
                    if let Some(sc) = score(&names[r], text, threshold) {
                        found.push((r.min(s), r.max(s), sc));
                    }
                }
                found
            },
        )
        .flatten()
        .collect();
    out.sort_unstable_by_key(|&(i, j, _)| (i, j));
    out
}

/// Group names that are linked by any chain of duplicate pairs (connected
/// components, via union-find). Returns groups of two or more, each sorted,
/// ordered by their first member.
pub fn clusters(n: usize, pairs: &[Pair]) -> Vec<Vec<usize>> {
    let mut parent: Vec<usize> = (0..n).collect();
    fn find(parent: &mut [usize], mut x: usize) -> usize {
        while parent[x] != x {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        x
    }
    for &(i, j, _) in pairs {
        let (a, b) = (find(&mut parent, i), find(&mut parent, j));
        if a != b {
            parent[a.max(b)] = a.min(b);
        }
    }
    let mut groups: HashMap<usize, Vec<usize>> = HashMap::new();
    for i in 0..n {
        let root = find(&mut parent, i);
        groups.entry(root).or_default().push(i);
    }
    let mut out: Vec<Vec<usize>> = groups.into_values().filter(|g| g.len() > 1).collect();
    out.sort_unstable_by_key(|g| g[0]);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn chars(s: &str) -> Vec<char> {
        s.chars().collect()
    }

    #[test]
    fn known_distances() {
        assert_eq!(levenshtein(&chars("kitten"), &chars("sitting")), 3);
        assert_eq!(levenshtein(&chars(""), &chars("abc")), 3);
        assert_eq!(levenshtein(&chars("şişecam"), &chars("sisecam")), 2);
        let long: Vec<char> = "a".repeat(80).chars().collect();
        assert_eq!(levenshtein(&long, &chars("b")), 80);
    }

    #[test]
    fn max_edits_matches_the_float_rule() {
        for len in 1..200 {
            for t in [0.0, 0.1, 0.15, 0.2, 0.25, 1.0 / 3.0, 0.45] {
                let k = max_edits(len, t);
                assert!(k as f64 / len as f64 <= t);
                assert!(k == len || (k + 1) as f64 / len as f64 > t);
            }
        }
    }

    #[test]
    fn segments_cover_the_string() {
        for len in 1..40 {
            for k in 0..len {
                let mut next = 0;
                for seg in 0..=k {
                    let (start, l) = segment(len, k, seg);
                    assert_eq!(start, next);
                    assert!(l > 0);
                    next = start + l;
                }
                assert_eq!(next, len);
            }
        }
    }

    fn name() -> impl Strategy<Value = String> {
        prop::string::string_regex("[abcçdeşğ ]{0,70}").unwrap()
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(300))]

        #[test]
        fn myers_equals_dp(a in name(), b in name()) {
            let (a, b) = (chars(&a), chars(&b));
            prop_assert_eq!(levenshtein(&a, &b), levenshtein_dp(&a, &b));
        }

        #[test]
        fn indexed_equals_brute(names in prop::collection::vec(name(), 0..60), t in 0.0f64..0.45) {
            let cleaned: Vec<Vec<char>> = names.iter().map(|n| normalize(n, false)).collect();
            prop_assert_eq!(pairs_indexed(&cleaned, t), pairs_brute(&cleaned, t));
        }
    }
}
