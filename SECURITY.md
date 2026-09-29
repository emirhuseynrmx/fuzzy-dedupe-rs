# Security policy

Please report vulnerabilities privately through GitHub's
[security advisories](https://github.com/emirhuseynrmx/fuzzy-dedupe-rs/security/advisories/new)
rather than a public issue. You'll get a reply within a week.

fuzzy-dedupe reads the input you give it and does no network access at runtime.
The benchmark scripts in `bench/` download public datasets over HTTPS on first use.
