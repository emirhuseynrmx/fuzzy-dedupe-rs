//! The algorithms, with no Python in sight, so they can be tested with `cargo test`.
//!
//! Rule: two names are duplicates when `edit_distance / longer_length <= threshold`,
//! after normalization. Every search strategy here must return exactly the pairs
//! the brute-force search returns; the tests check that.

use rayon::prelude::*;
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Legal-form words dropped from the end of a name by `strip_suffixes`, compared
/// after lowercasing and removing '.' and ','. Kept in step with `reference.py`.
pub const LEGAL_SUFFIXES: &[&str] = &[
    "limited",
    "ltd",
    "llc",
    "llp",
    "lp",
    "plc",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "ag",
    "kg",
    "sa",
    "sas",
    "sarl",
    "srl",
    "spa",
    "bv",
    "nv",
    "oy",
    "ab",
    "as",
    "pty",
    "pvt",
    "aş",
    "şti",
    "ltdşti",
];

/// How names are cleaned before comparison.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Norm {
    /// Sort the words, so "Ltd Acme" == "Acme Ltd".
    pub token_sort: bool,
    /// Drop legal-form words at the end ("Ltd", "Limited", "GmbH", "A.Ş."), repeatedly,
    /// as long as at least one word is left.
    pub strip_suffixes: bool,
}

fn is_legal_suffix(word: &str) -> bool {
    let bare: String = word.chars().filter(|&c| c != '.' && c != ',').collect();
    LEGAL_SUFFIXES.contains(&bare.as_str())
}

/// Lowercase, collapse whitespace, and apply the options in `norm`.
pub fn normalize_with(name: &str, norm: Norm) -> Vec<char> {
    let lowered = name.to_lowercase();
    let mut words: Vec<&str> = lowered.split_whitespace().collect();
    if norm.strip_suffixes {
        while words.len() > 1 && is_legal_suffix(words[words.len() - 1]) {
            words.pop();
        }
    }
    if norm.token_sort {
        words.sort_unstable();
    }
    words.join(" ").chars().collect()
}

/// Lowercase, collapse whitespace, and optionally sort the words, so that
/// "ACME  Ltd" == "acme ltd" and, with `token_sort`, "Ltd Acme" == "Acme Ltd".
pub fn normalize(name: &str, token_sort: bool) -> Vec<char> {
    normalize_with(
        name,
        Norm {
            token_sort,
            strip_suffixes: false,
        },
    )
}

/// A character-frequency sketch: counts of characters hashed into 32 buckets.
///
/// One edit changes the counts by at most 2 in total (a substitution moves one
/// character out and one in; an insertion or deletion moves one), so
/// `edit_distance >= L1(counts_a - counts_b) / 2`. Bucketing and saturation only
/// make the sum smaller, so it stays a lower bound (the frequency-distance bound
/// of Kahveci and Singh, VLDB 2001). It rejects most far-apart pairs before any
/// dynamic programming, and never rejects a match.
pub type Sketch = [u8; 32];

pub fn sketch(s: &[char]) -> Sketch {
    let mut out = [0u8; 32];
    for &c in s {
        let b = ((c as u32).wrapping_mul(2_654_435_761) >> 27) as usize;
        out[b] = out[b].saturating_add(1);
    }
    out
}

/// Lower bound on the edit distance from two sketches.
#[inline]
pub fn sketch_bound(a: &Sketch, b: &Sketch) -> usize {
    let l1: u32 = a
        .iter()
        .zip(b.iter())
        .map(|(&x, &y)| x.abs_diff(y) as u32)
        .sum();
    (l1 as usize).div_ceil(2)
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

/// Myers' algorithm for patterns longer than 64 characters: the pattern is cut
/// into 64-bit blocks and the horizontal delta at each block's last row is
/// carried into the next block (Myers 1999, section 5; Hyyrö 2003). Cost per
/// text character is one pass over the blocks, i.e. O(n * m / 64) for the pair.
pub struct BlockPattern {
    blocks: usize,
    ascii: Vec<u64>,
    other: HashMap<char, Vec<u64>>,
    len: usize,
}

impl BlockPattern {
    pub fn new(pattern: &[char]) -> Self {
        let blocks = pattern.len().div_ceil(64).max(1);
        let mut ascii = vec![0u64; 128 * blocks];
        let mut other: HashMap<char, Vec<u64>> = HashMap::new();
        for (i, &c) in pattern.iter().enumerate() {
            let (b, bit) = (i / 64, 1u64 << (i % 64));
            if (c as u32) < 128 {
                ascii[c as usize * blocks + b] |= bit;
            } else {
                other.entry(c).or_insert_with(|| vec![0; blocks])[b] |= bit;
            }
        }
        BlockPattern {
            blocks,
            ascii,
            other,
            len: pattern.len(),
        }
    }

    /// Bits of the pattern's match mask for `c` in 64-bit word `word`.
    #[inline]
    fn word(&self, word: usize, c: char) -> u64 {
        if (c as u32) < 128 {
            self.ascii[c as usize * self.blocks + word]
        } else {
            self.other.get(&c).map_or(0, |v| v[word])
        }
    }

    /// Edit distance if it is at most `max`, otherwise some value above `max`.
    ///
    /// Only cells within `max` of the diagonal can hold a value <= max, so a
    /// 64-bit window of `2 * max + 1` rows is enough. The window slides down one
    /// row per text character; the score is followed along the diagonal until the
    /// window reaches the last row, then along the last row, and the search stops
    /// once it can no longer end within `max` (Hyyrö 2003, the banded variant;
    /// same scheme as RapidFuzz's small-band kernel). Needs `2 * max + 1 <= 64`,
    /// `len > max` and a length difference of at most `max`.
    pub fn distance_band(&self, text: &[char], max: usize) -> usize {
        let (m, n) = (self.len, text.len());
        debug_assert!(2 * max < 64 && m > max && m.abs_diff(n) <= max);
        let mut vp: u64 = !0u64 << (63 - max);
        let mut vn: u64 = 0;
        let mut dist = max;
        let diagonal: u64 = 1 << 63;
        let mut horizontal: u64 = 1 << 62;
        let mut start = max as isize + 1 - 64;
        // The score can fall along the last row but never along the diagonal.
        let break_score = max + n - (m - max);
        for (i, &c) in text.iter().enumerate() {
            let pm = if start < 0 {
                self.word(0, c) << (-start) as u32
            } else {
                let (w, off) = (start as usize / 64, start as usize % 64);
                let mut x = self.word(w, c) >> off;
                if off != 0 && w + 1 < self.blocks {
                    x |= self.word(w + 1, c) << (64 - off);
                }
                x
            };
            let d0 = (((pm & vp).wrapping_add(vp)) ^ vp) | pm | vn;
            let hp = vn | !(d0 | vp);
            let hn = d0 & vp;
            if i < m - max {
                dist += usize::from(d0 & diagonal == 0);
            } else {
                dist += usize::from(hp & horizontal != 0);
                dist -= usize::from(hn & horizontal != 0);
                horizontal >>= 1;
            }
            if dist > break_score {
                return max + 1;
            }
            vp = hn | !((d0 >> 1) | hp);
            vn = (d0 >> 1) & hp;
            start += 1;
        }
        if dist <= max {
            dist
        } else {
            max + 1
        }
    }

    pub fn distance(&self, text: &[char]) -> usize {
        let (m, nb) = (self.len, self.blocks);
        if m == 0 {
            return text.len();
        }
        let zeros = vec![0u64; nb];
        let mut pv = vec![!0u64; nb];
        let mut mv = vec![0u64; nb];
        let top_last = 1u64 << ((m - 1) % 64);
        let mut score = m as isize;
        for &c in text {
            let eqs: &[u64] = if (c as u32) < 128 {
                &self.ascii[c as usize * nb..(c as usize + 1) * nb]
            } else {
                self.other.get(&c).map(Vec::as_slice).unwrap_or(&zeros)
            };
            // Global distance: the top row grows by one per column, so +1 enters block 0.
            let mut hin: i32 = 1;
            for b in 0..nb {
                let top = if b + 1 == nb { top_last } else { 1u64 << 63 };
                let (p, mm) = (pv[b], mv[b]);
                let mut eq = eqs[b];
                let xv = eq | mm;
                if hin < 0 {
                    eq |= 1;
                }
                let xh = ((eq & p).wrapping_add(p) ^ p) | eq;
                let mut ph = mm | !(xh | p);
                let mut mh = p & xh;
                let hout = if ph & top != 0 {
                    1
                } else if mh & top != 0 {
                    -1
                } else {
                    0
                };
                ph <<= 1;
                mh <<= 1;
                match hin.cmp(&0) {
                    std::cmp::Ordering::Less => mh |= 1,
                    std::cmp::Ordering::Greater => ph |= 1,
                    std::cmp::Ordering::Equal => {}
                }
                pv[b] = mh | !(xv | ph);
                mv[b] = ph & xv;
                hin = hout;
            }
            score += hin as isize;
        }
        score as usize
    }
}

/// A string prepared once as a Myers pattern, then compared against many others.
/// Building the match masks is the expensive part, so it is done per name, not per pair.
// The 1 KB mask table stays inline: a Prepared is built once per name and never moved in a loop.
#[allow(clippy::large_enum_variant)]
pub enum Prepared {
    Empty,
    Word(Pattern),
    Blocks(BlockPattern),
}

impl Prepared {
    pub fn new(s: &[char]) -> Self {
        match Pattern::new(s) {
            Some(p) => Prepared::Word(p),
            None if s.is_empty() => Prepared::Empty,
            None => Prepared::Blocks(BlockPattern::new(s)),
        }
    }

    /// Edit distance if it is at most `max`, otherwise some value above `max`. Uses the
    /// banded kernel for long strings when the band fits in one word.
    #[inline]
    pub fn distance_within(&self, text: &[char], max: usize) -> usize {
        match self {
            Prepared::Blocks(p)
                if 2 * max < 64 && p.len > max && p.len.abs_diff(text.len()) <= max =>
            {
                p.distance_band(text, max)
            }
            _ => self.distance(text),
        }
    }

    /// Edit distance between the prepared string and `text` (Myers is symmetric in effect:
    /// the global distance doesn't depend on which side is the pattern).
    #[inline]
    pub fn distance(&self, text: &[char]) -> usize {
        match self {
            Prepared::Empty => text.len(),
            Prepared::Word(p) => p.distance(text),
            Prepared::Blocks(p) => p.distance(text),
        }
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
        None => BlockPattern::new(short).distance(long),
    }
}

/// Edit distance if it is at most `k`, otherwise `None`. The length
/// difference is a lower bound, so hopeless pairs are rejected before any work.
pub fn levenshtein_bounded(a: &[char], b: &[char], k: usize) -> Option<usize> {
    if a.len().abs_diff(b.len()) > k {
        return None;
    }
    let d = levenshtein(a, b);
    (d <= k).then_some(d)
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

/// The threshold as a table: how many edits a pair may have, by longer length.
/// `max_edits` involves float division, and pairs are counted in millions.
pub struct Rule {
    threshold: f64,
    k: Vec<usize>,
}

impl Rule {
    pub fn new(threshold: f64, max_len: usize) -> Self {
        Rule {
            threshold,
            k: (0..=max_len).map(|l| max_edits(l, threshold)).collect(),
        }
    }

    pub fn for_names<'a>(threshold: f64, names: impl IntoIterator<Item = &'a Vec<char>>) -> Self {
        Rule::new(
            threshold,
            names.into_iter().map(Vec::len).max().unwrap_or(0),
        )
    }

    #[inline]
    pub fn k(&self, len: usize) -> usize {
        match self.k.get(len) {
            Some(&k) => k,
            None => max_edits(len, self.threshold),
        }
    }
}

/// Score one pair the way the reference does, or `None` if it isn't a duplicate.
/// `pa` is `a` prepared as a pattern; `sa`, `sb` are the sketches of `a` and `b`.
#[inline]
pub(crate) fn score(
    pa: &Prepared,
    a: &[char],
    sa: &Sketch,
    b: &[char],
    sb: &Sketch,
    rule: &Rule,
) -> Option<f64> {
    let longest = a.len().max(b.len());
    if longest == 0 {
        return Some(0.0);
    }
    // k is the largest d with d / longest <= threshold, so every test below is exact:
    // the length gap and the sketch bound are lower bounds on d, and d <= k is the rule itself.
    let k = rule.k(longest);
    if a.len().abs_diff(b.len()) > k || sketch_bound(sa, sb) > k {
        return None;
    }
    let d = pa.distance_within(b, k);
    (d <= k).then(|| d as f64 / longest as f64)
}

/// Compare every pair. O(n^2), but the reference every other strategy is checked against.
pub fn pairs_brute(names: &[Vec<char>], threshold: f64) -> Vec<Pair> {
    let sk: Vec<Sketch> = names.par_iter().map(|n| sketch(n)).collect();
    let sk = &sk;
    let rule = Rule::for_names(threshold, names);
    let rule = &rule;
    (0..names.len())
        .into_par_iter()
        .flat_map_iter(|i| {
            let a = &names[i];
            let pa = Prepared::new(a);
            ((i + 1)..names.len()).filter_map(move |j| {
                score(&pa, a, &sk[i], &names[j], &sk[j], rule).map(|s| (i, j, s))
            })
        })
        .collect()
}

/// Where segment `seg` of `k + 1` starts and how long it is, for a string of length `len`
/// (PASS-JOIN's even partition: the last `len % (k+1)` segments are one longer).
#[inline]
pub(crate) fn segment(len: usize, k: usize, seg: usize) -> (usize, usize) {
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
pub(crate) fn key(len: usize, k: usize, seg: usize, chars: &[char]) -> u64 {
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
    indexed_join(names, threshold, |_, _| true, &AtomicUsize::new(0))
}

/// Like `pairs_indexed`, and also how many candidate pairs the filter let
/// through to verification (the work an exact search can't avoid).
pub fn pairs_indexed_stats(names: &[Vec<char>], threshold: f64) -> (Vec<Pair>, usize) {
    if threshold >= 0.5 || names.len() < 2 {
        let n = names.len();
        return (pairs_brute(names, threshold), n * n.saturating_sub(1) / 2);
    }
    let verified = AtomicUsize::new(0);
    let pairs = indexed_join(names, threshold, |_, _| true, &verified);
    (pairs, verified.into_inner())
}

/// Should `auto` compare all pairs instead of using the index? The index does
/// about (k+1)^3 hash lookups per name, where k is the number of edits the name
/// can absorb, so it loses on long strings at high thresholds (titles at 0.3:
/// k ~ 18) while all-pairs cost grows with n^2. Measured cross-over on this
/// project's benchmarks; the answer is the same either way, only the speed differs.
pub fn prefer_brute(lengths: &[usize], threshold: f64) -> bool {
    if threshold >= 0.5 || lengths.len() < 2 {
        return true;
    }
    let mut ls = lengths.to_vec();
    let mid = ls.len() / 2;
    let (_, median, _) = ls.select_nth_unstable(mid);
    max_edits(*median, threshold) >= 16 && lengths.len() <= 20_000
}

/// The PASS-JOIN search over `names`, reporting only pairs for which `keep(r, s)` holds.
/// Each qualifying pair is found exactly once, when the longer name (or, at equal
/// length, the later one) is probed.
fn indexed_join<F>(
    names: &[Vec<char>],
    threshold: f64,
    keep: F,
    verified: &AtomicUsize,
) -> Vec<Pair>
where
    F: Fn(usize, usize) -> bool + Sync,
{
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
    let sk: Vec<Sketch> = names.par_iter().map(|n| sketch(n)).collect();
    let rule = Rule::new(threshold, max_len);
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
                        if keep(r, s) {
                            found.push((r, s, 0.0));
                        }
                    }
                    // Two empty names are compared trivially; count them as verified too.
                    verified.fetch_add(found.len(), Ordering::Relaxed);
                    return found;
                }
                let k = k_of[big];
                cands.clear();
                let stamp = s as u32;
                let mut add = |r: usize, cands: &mut Vec<u32>| {
                    let shorter = names[r].len() < big;
                    if r != s && (shorter || r < s) && seen[r] != stamp && keep(r, s) {
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
                verified.fetch_add(cands.len(), Ordering::Relaxed);
                let pt = Prepared::new(text);
                for &r in cands.iter() {
                    let r = r as usize;
                    if let Some(sc) = score(&pt, text, &sk[s], &names[r], &sk[r], &rule) {
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

/// Pairs `(i, j, score)` between two lists: `left[i]` matches `right[j]`.
/// All pairs, compared directly: the reference for `link_indexed`.
pub fn link_brute(left: &[Vec<char>], right: &[Vec<char>], threshold: f64) -> Vec<Pair> {
    let sr: Vec<Sketch> = right.par_iter().map(|n| sketch(n)).collect();
    let sr = &sr;
    let rule = Rule::for_names(threshold, left.iter().chain(right.iter()));
    let rule = &rule;
    (0..left.len())
        .into_par_iter()
        .flat_map_iter(|i| {
            let a = &left[i];
            let (pa, sa) = (Prepared::new(a), sketch(a));
            right
                .iter()
                .enumerate()
                .filter_map(move |(j, b)| score(&pa, a, &sa, b, &sr[j], rule).map(|s| (i, j, s)))
        })
        .collect()
}

/// PASS-JOIN across two lists (the paper's R-S join): both lists go into one
/// index and only cross-list pairs are verified. Equals `link_brute`.
pub fn link_indexed(left: &[Vec<char>], right: &[Vec<char>], threshold: f64) -> Vec<Pair> {
    if threshold >= 0.5 || left.is_empty() || right.is_empty() {
        return link_brute(left, right, threshold);
    }
    let n = left.len();
    let all: Vec<Vec<char>> = left.iter().chain(right.iter()).cloned().collect();
    let mut out: Vec<Pair> = indexed_join(
        &all,
        threshold,
        |r, s| (r < n) != (s < n),
        &AtomicUsize::new(0),
    )
    .into_iter()
    .map(|(a, b, sc)| (a.min(b), a.max(b) - n, sc))
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
    fn strip_suffixes_drops_legal_forms() {
        let n = |s: &str| -> String {
            normalize_with(
                s,
                Norm {
                    token_sort: false,
                    strip_suffixes: true,
                },
            )
            .into_iter()
            .collect()
        };
        assert_eq!(n("Acme Ltd."), "acme");
        assert_eq!(n("ACME  LIMITED"), "acme");
        assert_eq!(n("Şişecam A.Ş."), "şişecam");
        assert_eq!(n("Kuzey Gıda Ltd. Şti."), "kuzey gıda");
        assert_eq!(n("Limited"), "limited"); // never strip the last word
        assert_eq!(n("Ltd Acme"), "ltd acme"); // only at the end
    }

    #[test]
    fn band_on_edited_long_strings() {
        // Long strings with a known number of random edits, across every band width.
        let alphabet: Vec<char> = "abcdeşğıö ".chars().collect();
        let mut seed = 99u64;
        let mut rnd = |n: usize| -> usize {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (seed >> 33) as usize % n
        };
        let mut checked = 0;
        for len in [65, 80, 100, 127, 128, 129, 150] {
            for edits in 0..36 {
                let a: Vec<char> = (0..len).map(|_| alphabet[rnd(alphabet.len())]).collect();
                let mut b = a.clone();
                for _ in 0..edits {
                    let pos = rnd(b.len().max(1));
                    match rnd(3) {
                        0 if !b.is_empty() => {
                            b.remove(pos);
                        }
                        1 => b.insert(pos, alphabet[rnd(alphabet.len())]),
                        _ if !b.is_empty() => b[pos] = alphabet[rnd(alphabet.len())],
                        _ => {}
                    }
                }
                let d = levenshtein_dp(&a, &b);
                let p = BlockPattern::new(&a);
                for max in 0..32 {
                    if a.len() > max && a.len().abs_diff(b.len()) <= max {
                        let got = p.distance_band(&b, max);
                        assert!(
                            if d <= max { got == d } else { got > max },
                            "len={len} edits={edits} max={max} d={d} got={got}"
                        );
                        checked += 1;
                    }
                }
            }
        }
        assert!(
            checked > 3000,
            "only {checked} cases reached the band kernel"
        );
    }

    #[test]
    fn block_boundaries() {
        // Pattern lengths around the 64-bit block edges, against dynamic programming.
        let alphabet: Vec<char> = "abcşğ ".chars().collect();
        let mut seed = 12345u64;
        let mut next = |n: usize| -> Vec<char> {
            (0..n)
                .map(|_| {
                    seed = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    alphabet[(seed >> 33) as usize % alphabet.len()]
                })
                .collect()
        };
        for m in [63, 64, 65, 127, 128, 129, 200] {
            for n in [m - 3, m, m + 5] {
                let (a, b) = (next(m), next(n));
                assert_eq!(levenshtein(&a, &b), levenshtein_dp(&a, &b), "m={m} n={n}");
            }
        }
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

    // Around and past 64 characters, similar strings, to exercise the banded kernel.
    fn band_name() -> impl Strategy<Value = String> {
        prop::string::string_regex("(abcabçab){5,17}[abç]{0,12}").unwrap()
    }

    // Past 64 characters, to exercise the banded fallback.
    fn long_name() -> impl Strategy<Value = String> {
        prop::string::string_regex("[abç]{0,140}").unwrap()
    }

    proptest! {
        // Default config, so PROPTEST_CASES (set in CI) controls the number of cases.
        #![proptest_config(ProptestConfig::default())]

        #[test]
        fn myers_equals_dp(a in name(), b in name()) {
            let (a, b) = (chars(&a), chars(&b));
            prop_assert_eq!(levenshtein(&a, &b), levenshtein_dp(&a, &b));
        }

        #[test]
        fn sketch_is_a_lower_bound(a in long_name(), b in long_name()) {
            let (a, b) = (chars(&a), chars(&b));
            prop_assert!(sketch_bound(&sketch(&a), &sketch(&b)) <= levenshtein_dp(&a, &b));
        }

        #[test]
        fn band_agrees_with_dp(a in band_name(), b in band_name(), max in 0usize..32) {
            let (a, b) = (chars(&a), chars(&b));
            let d = levenshtein_dp(&a, &b);
            let p = BlockPattern::new(&a);
            if a.len() > max && a.len().abs_diff(b.len()) <= max {
                let got = p.distance_band(&b, max);
                if d <= max {
                    prop_assert_eq!(got, d);
                } else {
                    prop_assert!(got > max);
                }
            }
        }

        #[test]
        fn bounded_agrees_with_dp(a in long_name(), b in long_name(), k in 0usize..40) {
            let (a, b) = (chars(&a), chars(&b));
            let d = levenshtein_dp(&a, &b);
            prop_assert_eq!(levenshtein_bounded(&a, &b, k), (d <= k).then_some(d));
        }

        #[test]
        fn link_indexed_equals_brute(
            left in prop::collection::vec(name(), 0..40),
            right in prop::collection::vec(name(), 0..40),
            t in 0.0f64..0.45,
        ) {
            let l: Vec<Vec<char>> = left.iter().map(|n| normalize(n, false)).collect();
            let r: Vec<Vec<char>> = right.iter().map(|n| normalize(n, false)).collect();
            prop_assert_eq!(link_indexed(&l, &r, t), link_brute(&l, &r, t));
        }

        #[test]
        fn indexed_equals_brute(names in prop::collection::vec(name(), 0..60), t in 0.0f64..0.45) {
            let cleaned: Vec<Vec<char>> = names.iter().map(|n| normalize(n, false)).collect();
            prop_assert_eq!(pairs_indexed(&cleaned, t), pairs_brute(&cleaned, t));
        }
    }
}
