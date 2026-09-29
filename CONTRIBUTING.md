# Contributing

Thanks for helping. The one rule of this project: **every strategy must return exactly the pairs the brute-force search returns.** A change that makes it faster but changes a single pair is a bug.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install maturin pytest hypothesis
maturin develop --release
```

## Before opening a pull request

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo clippy --all-targets --features python -- -D warnings
PROPTEST_CASES=2000 cargo test --release
pytest -q
```

- New search logic needs a property test comparing it with `pairs_brute` / `link_brute` (Rust) and with the Python reference (Hypothesis).
- Performance claims need a command from `bench/` and its output. Don't add numbers you haven't measured.
- Keep the pure-Python reference in `python/fuzzy_dedupe/reference.py` in step with the Rust rules.
