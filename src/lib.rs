//! The Rust version of `fuzzy_dedupe.reference.find_duplicates`, with the same
//! inputs, the same outputs and the same rules. Two differences make it fast:
//! it compares characters instead of Python objects, and it splits the rows
//! across all CPU cores with rayon.

use pyo3::prelude::*;
use rayon::prelude::*;

fn normalize(name: &str) -> Vec<char> {
    let lowered = name.to_lowercase();
    let joined = lowered.split_whitespace().collect::<Vec<_>>().join(" ");
    joined.chars().collect()
}

/// Edit distance over two character slices, keeping one row of the table.
fn levenshtein(a: &[char], b: &[char], row: &mut Vec<usize>) -> usize {
    let (a, b) = if a.len() < b.len() { (b, a) } else { (a, b) };
    row.clear();
    row.extend(0..=b.len());
    for (i, ca) in a.iter().enumerate() {
        let mut diagonal = row[0];
        row[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let above = row[j + 1];
            let substitution = diagonal + usize::from(ca != cb);
            row[j + 1] = (above + 1).min(row[j] + 1).min(substitution);
            diagonal = above;
        }
    }
    row[b.len()]
}

/// All pairs (i, j, score) with i < j whose normalized distance is <= threshold.
#[pyfunction]
#[pyo3(signature = (names, threshold = 0.2))]
fn find_duplicates(py: Python<'_>, names: Vec<String>, threshold: f64) -> Vec<(usize, usize, f64)> {
    let cleaned: Vec<Vec<char>> = names.iter().map(|n| normalize(n)).collect();
    // Release the GIL: the rest touches no Python objects, so other Python threads keep running.
    py.allow_threads(|| {
        (0..cleaned.len())
            .into_par_iter()
            .map_init(Vec::new, |row, i| {
                let a = &cleaned[i];
                let mut found = Vec::new();
                for (j, b) in cleaned.iter().enumerate().skip(i + 1) {
                    let longest = a.len().max(b.len());
                    if longest == 0 {
                        found.push((i, j, 0.0));
                        continue;
                    }
                    let gap = a.len().abs_diff(b.len()) as f64 / longest as f64;
                    if gap > threshold {
                        continue;
                    }
                    let score = levenshtein(a, b, row) as f64 / longest as f64;
                    if score <= threshold {
                        found.push((i, j, score));
                    }
                }
                found
            })
            .flatten()
            .collect()
    })
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;
    Ok(())
}
