# fuzzy-dedupe

Find near-duplicate names in a list: "Acme Ltd", "ACME  ltd" and "Acme Ltd." are the same customer.

The same function exists twice in this repo: once in plain Python, the way most teams start, and once in Rust, called from Python through PyO3. Same inputs, same outputs, same rules. The Rust one is **113x faster on one core and 560x faster on twelve** for a 3,000-name list.

This is a small, complete example of the kind of job I do: take the slow part of a Python codebase, rewrite it in Rust, and hand it back as a normal `pip install` package that your existing code calls the same way.

## Results

Measured with `python bench/bench.py 3000` on a Windows laptop (AMD, 12 logical cores, Python 3.13):

| Version | Time | Speed-up |
|---|---|---|
| Pure Python | 36.21 s | 1x |
| Rust (PyO3), 1 thread | 0.317 s | 113x |
| Rust (PyO3 + rayon), 12 threads | 0.065 s | 560x |

4,498,500 pairs compared, 87,525 duplicates found, and both versions returned exactly the same list. Full output in [`bench/results.md`](bench/results.md). Your numbers will differ with your machine and your data. Run the script to see them.

Where the speed comes from:

- **Native code:** the inner loop compares characters in memory instead of Python objects. That alone is the 113x.
- **All cores:** rows are split across threads with rayon. The Python version can't do this with threads because of the GIL; the Rust version releases the GIL while it works.

## Use it

```python
from fuzzy_dedupe import find_duplicates

names = ["Acme Ltd", "ACME  ltd", "Acme Ltd.", "Globex"]
find_duplicates(names, threshold=0.2)
# [(0, 1, 0.0), (0, 2, 0.1111111111111111), (1, 2, 0.1111111111111111)]
```

Each result is `(i, j, score)`: the positions of the two names and their edit distance divided by the longer name's length. `0.0` means identical after lowercasing and collapsing spaces.

The pure-Python version is `fuzzy_dedupe.find_duplicates_python`, with the same signature.

## Build

You need Python 3.9+ and a Rust toolchain.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install maturin pytest
maturin develop --release
pytest -q
python bench/bench.py 3000
```

## How it is checked

- `tests/test_same_answers.py` runs both versions on 80 randomly generated messy lists (typos, case, extra spaces, Turkish characters) at four thresholds and requires identical output, plus edge cases like empty names.
- CI runs the tests on Linux, macOS and Windows, on Python 3.9 and 3.13, then builds wheels for all three.

## Layout

```
src/lib.rs                       Rust version (PyO3 + rayon)
python/fuzzy_dedupe/reference.py Pure-Python version
tests/test_same_answers.py       Both must agree
bench/bench.py                   Timing script behind the table above
```

## License

MIT
