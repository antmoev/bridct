# Build and verify software packages

`distribution/build_release.py` builds the macOS, Ubuntu and Windows source ZIPs and a standalone dataset ZIP. Use it when you need to package the software yourself. To run BRiDCT, follow the main README or the platform instructions.

Package construction uses only the Python standard library and does not download dependencies.

`VERSION` identifies the numerical implementation. `PACKAGING_VERSION` identifies a distribution revision. `distribution/files.json` is the explicit allowlist of package files. `PROVENANCE.json` retains the paper snapshot's immutable source hashes.

After reviewed documentation/packaging changes:

```sh
python3 distribution/build_release.py --refresh-manifest
python3 distribution/build_release.py --output dist
python3 tests/test_release.py
```

The output directory must not already exist. The builder checks immutable provenance and dataset hashes before refreshing the manifest; it does not silently bless changes to paper kernels. It produces three platform ZIPs, a standalone dataset ZIP, `SHA256SUMS` and `RELEASE.json`. Only the platform starting instructions and their manifests differ between the three code packages. Archive timestamps and permissions are fixed for deterministic bytes.

## Check an extracted package

Extract the ZIP into a fresh directory outside the checkout. From its `bridct` folder:

```sh
python3 tools/verify_source.py
python3 dataset/verify.py
make -j2 check
make check-generated PYTHON=python3
python3 tests/verify_portability.py --runner build/test_runner_shared --library build/libbridct.dylib --output build/numerical --execution 'Native macOS ARM64 validation'
make -C python check-full PYTHON=python3
make -C python check-hardening PYTHON=python3
```

Use `build/libbridct.so` on Linux. On Windows use the documented launcher with `-Profile Verify`, which records the actual toolchain and performs C/Python/dataset checks. NumPy and SciPy are required for the independent Python checks; the C-only build does not need them. Boundary diagnostics are retained separately and must not be confused with required failures.

The GitHub workflow validates extracted platform packages without measuring performance. Its Windows job uses the actual Windows launcher; its Unix jobs build and validate the extracted sources with an isolated Python environment. A workflow pass is not evidence of a speedup on shared runners.
