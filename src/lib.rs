//! fuzzy-dedupe: find near-duplicate names fast, with exactly the answers of a
//! brute-force search. The algorithms live in [`core`] and [`index`]; the Python
//! module is built only with the `python` feature, so `cargo test` needs no Python.

pub mod core;
pub mod index;

#[cfg(feature = "python")]
mod python {
    use crate::core::{self, Norm, PairRules};
    use crate::index;
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    fn check_threshold(threshold: f64) -> PyResult<()> {
        if (0.0..=1.0).contains(&threshold) {
            Ok(())
        } else {
            Err(PyValueError::new_err("threshold must be between 0 and 1"))
        }
    }

    fn rules(
        numbers_must_match: bool,
        word_threshold: Option<f64>,
        turkish: bool,
    ) -> PyResult<PairRules> {
        if let Some(wt) = word_threshold {
            if !(0.0..=1.0).contains(&wt) {
                return Err(PyValueError::new_err(
                    "word_threshold must be between 0 and 1",
                ));
            }
        }
        Ok(PairRules {
            numbers_must_match,
            word_threshold,
            turkish,
        })
    }

    fn cleaned(names: &[String], norm: Norm) -> Vec<Vec<char>> {
        names
            .iter()
            .map(|n| core::normalize_with(n, norm))
            .collect()
    }

    /// `true` to compare all pairs, `false` to use the index.
    fn use_brute(
        method: &str,
        lens: impl Iterator<Item = usize>,
        threshold: f64,
    ) -> PyResult<bool> {
        match method {
            "auto" => Ok(core::prefer_brute(&lens.collect::<Vec<_>>(), threshold)),
            "indexed" => Ok(false),
            "brute" => Ok(true),
            other => Err(PyValueError::new_err(format!(
                "unknown method {other:?}; use 'auto', 'indexed' or 'brute'"
            ))),
        }
    }

    fn search(names: &[Vec<char>], threshold: f64, method: &str) -> PyResult<Vec<core::Pair>> {
        check_threshold(threshold)?;
        Ok(
            if use_brute(method, names.iter().map(Vec::len), threshold)? {
                core::pairs_brute(names, threshold)
            } else {
                core::pairs_indexed(names, threshold)
            },
        )
    }

    /// All pairs (i, j, score) with i < j whose normalized edit distance is <= threshold.
    #[allow(clippy::too_many_arguments)]
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false, strip_suffixes = false, turkish = false, numbers_must_match = false, word_threshold = None, method = "auto"))]
    fn find_duplicates(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
        strip_suffixes: bool,
        turkish: bool,
        numbers_must_match: bool,
        word_threshold: Option<f64>,
        method: &str,
    ) -> PyResult<Vec<core::Pair>> {
        let names = cleaned(
            &names,
            Norm {
                token_sort,
                strip_suffixes,
                turkish,
            },
        );
        let rules = rules(numbers_must_match, word_threshold, turkish)?;
        // No Python objects are touched from here on, so other Python threads keep running.
        py.allow_threads(|| {
            let pairs = search(&names, threshold, method)?;
            Ok(core::filter_pairs(pairs, &names, &names, &rules))
        })
    }

    /// Groups of names linked by any chain of duplicate pairs, each a sorted list of positions.
    #[allow(clippy::too_many_arguments)]
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false, strip_suffixes = false, turkish = false, numbers_must_match = false, word_threshold = None, method = "auto"))]
    fn cluster(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
        strip_suffixes: bool,
        turkish: bool,
        numbers_must_match: bool,
        word_threshold: Option<f64>,
        method: &str,
    ) -> PyResult<Vec<Vec<usize>>> {
        let names = cleaned(
            &names,
            Norm {
                token_sort,
                strip_suffixes,
                turkish,
            },
        );
        let rules = rules(numbers_must_match, word_threshold, turkish)?;
        py.allow_threads(|| {
            let pairs = search(&names, threshold, method)?;
            let pairs = core::filter_pairs(pairs, &names, &names, &rules);
            Ok(core::clusters(names.len(), &pairs))
        })
    }

    /// Pairs (i, j, score) where left[i] and right[j] are within the threshold.
    // The arguments mirror the Python signature one to one.
    #[allow(clippy::too_many_arguments)]
    #[pyfunction]
    #[pyo3(signature = (left, right, threshold = 0.2, *, token_sort = false, strip_suffixes = false, turkish = false, numbers_must_match = false, word_threshold = None, method = "auto"))]
    fn link(
        py: Python<'_>,
        left: Vec<String>,
        right: Vec<String>,
        threshold: f64,
        token_sort: bool,
        strip_suffixes: bool,
        turkish: bool,
        numbers_must_match: bool,
        word_threshold: Option<f64>,
        method: &str,
    ) -> PyResult<Vec<core::Pair>> {
        check_threshold(threshold)?;
        let norm = Norm {
            token_sort,
            strip_suffixes,
            turkish,
        };
        let (left, right) = (cleaned(&left, norm), cleaned(&right, norm));
        let brute = use_brute(
            method,
            left.iter().chain(right.iter()).map(Vec::len),
            threshold,
        )?;
        let rules = rules(numbers_must_match, word_threshold, turkish)?;
        Ok(py.allow_threads(|| {
            let pairs = if brute {
                core::link_brute(&left, &right, threshold)
            } else {
                core::link_indexed(&left, &right, threshold)
            };
            core::filter_pairs(pairs, &left, &right, &rules)
        }))
    }

    /// Search statistics: pairs found and candidate pairs verified by the index.
    #[allow(clippy::too_many_arguments)]
    #[pyfunction]
    #[pyo3(signature = (names, threshold = 0.2, *, token_sort = false, strip_suffixes = false, turkish = false, numbers_must_match = false, word_threshold = None))]
    fn stats(
        py: Python<'_>,
        names: Vec<String>,
        threshold: f64,
        token_sort: bool,
        strip_suffixes: bool,
        turkish: bool,
        numbers_must_match: bool,
        word_threshold: Option<f64>,
    ) -> PyResult<(usize, usize, usize)> {
        check_threshold(threshold)?;
        let names = cleaned(
            &names,
            Norm {
                token_sort,
                strip_suffixes,
                turkish,
            },
        );
        let rules = rules(numbers_must_match, word_threshold, turkish)?;
        let n = names.len();
        let (pairs, verified) = py.allow_threads(|| {
            let (pairs, verified) = core::pairs_indexed_stats(&names, threshold);
            (core::filter_pairs(pairs, &names, &names, &rules), verified)
        });
        Ok((pairs.len(), verified, n * n.saturating_sub(1) / 2))
    }

    /// Edit distance between two strings, as characters (not bytes).
    #[pyfunction]
    fn levenshtein(a: &str, b: &str) -> usize {
        let (a, b): (Vec<char>, Vec<char>) = (a.chars().collect(), b.chars().collect());
        core::levenshtein(&a, &b)
    }

    /// A persistent, incremental index of names (see `fuzzy_dedupe.Index`).
    #[pyclass(subclass, name = "Index", module = "fuzzy_dedupe._native")]
    pub struct PyIndex {
        inner: index::Index,
    }

    #[pymethods]
    impl PyIndex {
        #[new]
        #[allow(clippy::too_many_arguments)]
        #[pyo3(signature = (threshold = 0.2, *, token_sort = false, strip_suffixes = false, turkish = false, numbers_must_match = false, word_threshold = None))]
        fn new(
            threshold: f64,
            token_sort: bool,
            strip_suffixes: bool,
            turkish: bool,
            numbers_must_match: bool,
            word_threshold: Option<f64>,
        ) -> PyResult<Self> {
            check_threshold(threshold)?;
            Ok(PyIndex {
                inner: index::Index::with_rules(
                    threshold,
                    Norm {
                        token_sort,
                        strip_suffixes,
                        turkish,
                    },
                    rules(numbers_must_match, word_threshold, turkish)?,
                ),
            })
        }

        /// Add names; returns the id given to the first one (ids are consecutive).
        fn add(&mut self, py: Python<'_>, names: Vec<String>) -> usize {
            let inner = &mut self.inner;
            py.allow_threads(|| inner.add(&names))
        }

        /// Stored names matching `name`, as `[(id, score)]` sorted by id.
        fn query(&self, py: Python<'_>, name: String) -> Vec<(usize, f64)> {
            let inner = &self.inner;
            py.allow_threads(|| inner.query(&name))
        }

        /// `query` for many names, in parallel.
        fn query_many(&self, py: Python<'_>, names: Vec<String>) -> Vec<Vec<(usize, f64)>> {
            let inner = &self.inner;
            py.allow_threads(|| inner.query_many(&names))
        }

        /// The stored names, as given (id i is names()[i]).
        fn names(&self) -> Vec<String> {
            self.inner.raw_names().to_vec()
        }

        #[getter]
        fn threshold(&self) -> f64 {
            self.inner.threshold()
        }

        #[getter]
        fn token_sort(&self) -> bool {
            self.inner.norm().token_sort
        }

        #[getter]
        fn strip_suffixes(&self) -> bool {
            self.inner.norm().strip_suffixes
        }

        #[getter]
        fn turkish(&self) -> bool {
            self.inner.norm().turkish
        }

        #[getter]
        fn numbers_must_match(&self) -> bool {
            self.inner.rules().numbers_must_match
        }

        #[getter]
        fn word_threshold(&self) -> Option<f64> {
            self.inner.rules().word_threshold
        }

        fn __len__(&self) -> usize {
            self.inner.len()
        }
    }

    #[pymodule]
    fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;
        m.add_function(wrap_pyfunction!(cluster, m)?)?;
        m.add_function(wrap_pyfunction!(link, m)?)?;
        m.add_function(wrap_pyfunction!(stats, m)?)?;
        m.add_function(wrap_pyfunction!(levenshtein, m)?)?;
        m.add_class::<PyIndex>()?;
        Ok(())
    }
}
