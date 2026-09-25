# Contributing

Use an issue or pull request to describe the problem, affected shapes and platform. Include the software version and compiler. Remove private paths and machine identifiers from logs before sharing.

The library preserves the Shao–Johnson factorization and the documented numerical contract. Ooura belongs only to the optional benchmark. Do not relax accuracy thresholds or add fast-math flags to make a test pass. Generated kernels must be changed through their generator and checked with `make check-generated PYTHON=python3`.

Run `make check` and the independent checks in `docs/RELEASING.md`. Keep core failures distinct from known boundary diagnostics. Performance claims require a stated machine, versions, call/allocation contracts and retained raw timing blocks. CI tests compilation and accuracy, not comparative performance.

Changes to a paper-frozen file require a new numerical software version and updated provenance. Documentation or packaging-only changes can retain the numerical version and increment `PACKAGING_VERSION`. Never replace the assets of an already cited release silently.
