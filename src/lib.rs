//! fuzzy-dedupe: find near-duplicate names fast, with exactly the answers of a
//! brute-force search. The algorithms live in [`core`]; the Python module is
//! built only with the `python` feature, so `cargo test` needs no Python.

pub mod core;

#[cfg(feature = "python")]
mod python {
    use crate::core;
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    fn cleaned(names: &[String], token_sort: bool) -> Vec<Vec<char>> {
        names
            .iter()
            .map(|n| core::normalize(n, token_sort))
            .collect()
    }

    fn search(names: &[Vec<char>], threshold: f64, method: &str) -> PyResult<Vec<core::Pair>> {
        if !(0.0..=1.0).contains(&threshold) {
            return Err(PyValueError::new_err("threshold must be between 0 and 1"));
        }
        match method {
            "auto" => {
                let lens: Vec<usize> = names.iter().map(Vec::len).collect();
                Ok(if core::prefer_brute(&lens, threshold) {
                    core::pairs_brute(names, threshold)
                } else {
                    core::pairs_indexed(names, threshold)
                })
            }
            "indexed" => Ok(core::pairs_indexed(names, threshold)),
            "brute" => Ok(core::pairs_brute(names, threshold)),
            other => Err(PyValueError::new_err(format!(
                "unknown method {other:?}; use 'auto', 'indexed' or 'brute'"
            ))),
        }
    }

    /// All pairs (i, j, score) with i < j whose normalized edit distance is <= threshold.
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false, method = "auto"))]
    fn find_duplicates(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
        method: &str,
    ) -> PyResult<Vec<core::Pair>> {
        let names = cleaned(&names, token_sort);
        // No Python objects are touched from here on, so other Python threads keep running.
        py.allow_threads(|| search(&names, threshold, method))
    }

    /// Groups of names linked by any chain of duplicate pairs, each a sorted list of positions.
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false, method = "auto"))]
    fn cluster(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
        method: &str,
    ) -> PyResult<Vec<Vec<usize>>> {
        let names = cleaned(&names, token_sort);
        py.allow_threads(|| {
            let pairs = search(&names, threshold, method)?;
            Ok(core::clusters(names.len(), &pairs))
        })
    }

    /// Pairs (i, j, score) where left[i] and right[j] are within the threshold.
    #[pyfunction]
    #[pyo3(signature = (left, right, threshold = 0.2, *, token_sort = false, method = "auto"))]
    fn link(
        py: Python<'_>,
        left: Vec<String>,
        right: Vec<String>,
        threshold: f64,
        token_sort: bool,
        method: &str,
    ) -> PyResult<Vec<core::Pair>> {
        let (left, right) = (cleaned(&left, token_sort), cleaned(&right, token_sort));
        if !(0.0..=1.0).contains(&threshold) {
            return Err(PyValueError::new_err("threshold must be between 0 and 1"));
        }
        let brute = match method {
            "auto" => {
                let lens: Vec<usize> = left.iter().chain(right.iter()).map(Vec::len).collect();
                core::prefer_brute(&lens, threshold)
            }
            "indexed" => false,
            "brute" => true,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown method {other:?}; use 'auto', 'indexed' or 'brute'"
                )))
            }
        };
        Ok(py.allow_threads(|| {
            if brute {
                core::link_brute(&left, &right, threshold)
            } else {
                core::link_indexed(&left, &right, threshold)
            }
        }))
    }

    /// Search statistics: pairs found and candidate pairs verified by the index.
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false))]
    fn stats(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
    ) -> PyResult<(usize, usize, usize)> {
        if !(0.0..=1.0).contains(&threshold) {
            return Err(PyValueError::new_err("threshold must be between 0 and 1"));
        }
        let names = cleaned(&names, token_sort);
        let n = names.len();
        let (pairs, verified) = py.allow_threads(|| core::pairs_indexed_stats(&names, threshold));
        Ok((pairs.len(), verified, n * n.saturating_sub(1) / 2))
    }

    /// Edit distance between two strings, as characters (not bytes).
    #[pyfunction]
    fn levenshtein(a: &str, b: &str) -> usize {
        let (a, b): (Vec<char>, Vec<char>) = (a.chars().collect(), b.chars().collect());
        core::levenshtein(&a, &b)
    }

    #[pymodule]
    fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;
        m.add_function(wrap_pyfunction!(cluster, m)?)?;
        m.add_function(wrap_pyfunction!(link, m)?)?;
        m.add_function(wrap_pyfunction!(stats, m)?)?;
        m.add_function(wrap_pyfunction!(levenshtein, m)?)?;
        Ok(())
    }
}
