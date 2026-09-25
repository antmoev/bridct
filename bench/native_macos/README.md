# Optional native macOS comparisons

This helper reproduces the final native comparison against Apple vDSP, FFTW, general and specialized Ooura, libjxl, and libjpeg-turbo. It is separate from the simpler platform launcher and Python-library benchmarks. It needs native Apple Silicon macOS because the reference wrappers use Accelerate and NEON; BRiDCT itself remains portable.

Use a Python environment containing NumPy and SciPy, the Xcode Command Line Tools (`xcode-select --install` if absent), and CMake for building libjpeg-turbo from source. Set `BRIDCT_ROOT` to the extracted package and `NATIVE_DEPS` to a folder outside it. None of the following commands installs a system library.

```sh
BRIDCT_ROOT="$PWD"
NATIVE_DEPS="$HOME/bridct-native-dependencies"
mkdir -p "$NATIVE_DEPS"
cd "$NATIVE_DEPS"
```

Obtain the pinned reference sources. Download checksums are in `DEPENDENCIES.json`; verify them before extraction:

```sh
curl -fL https://www.fftw.org/fftw-3.3.11.tar.gz -o fftw.tar.gz
curl -fL https://codeload.github.com/libjxl/libjxl/tar.gz/7741c8ce9998cbaffabec5cadd051b1b68afa3e2 -o libjxl.tar.gz
curl -fL https://codeload.github.com/google/highway/tar.gz/457c891775a7397bdb0376bb1031e6e027af1c48 -o highway.tar.gz
printf '%s\n' \
 '5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1  fftw.tar.gz' \
 '68f755ab2735efaac0e3424bf3ca491c6eb1586ad31860c9cda160011128a280  libjxl.tar.gz' \
 '5124b0501c98d9930dbb065bfa1a5bbbd59ce0f12facb7e1e33aaef01a5f1f1a  highway.tar.gz' | shasum -a 256 -c -
tar -xzf fftw.tar.gz
tar -xzf libjxl.tar.gz
tar -xzf highway.tar.gz
```

Build FFTW in single precision with NEON and no threads. Setup and planning are outside the timed transform:

```sh
cd "$NATIVE_DEPS/fftw-3.3.11"
CC="$(xcrun --find clang)" CFLAGS="-O3 -std=gnu11 -isysroot $(xcrun --show-sdk-path)" \
 ./configure --enable-float --enable-neon --disable-fortran --disable-shared
make -j2
```

libjxl and Highway need no separate build: the helper compiles their DCT headers and Highway's small support file directly. For libjpeg-turbo, supply an existing **3.2.0** static `libjpeg.a`, or build that release:

```sh
cd "$NATIVE_DEPS"
git clone --depth 1 --branch 3.2.0 https://github.com/libjpeg-turbo/libjpeg-turbo.git jpeg-turbo-3.2.0
cmake -S jpeg-turbo-3.2.0 -B jpeg-build -DCMAKE_BUILD_TYPE=Release \
 -DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DWITH_SIMD=ON
cmake --build jpeg-build --parallel 2
```

The recorded campaign used the Homebrew 3.2.0 arm64 bottle. A source build of the same release need not reproduce its binary bytes or timings. Build provenance and the actual linked archive hash are recorded for each run. The harness measures `jpeg_fdct_float` only, with its output converted to the common orthonormal convention; integer codec approximations are not included.

Build the helper, using `python` from the chosen NumPy/SciPy environment:

```sh
cd "$BRIDCT_ROOT/bench/native_macos"
python build.py \
 --fftw-root "$NATIVE_DEPS/fftw-3.3.11" \
 --libjxl-root "$NATIVE_DEPS/libjxl-7741c8ce9998cbaffabec5cadd051b1b68afa3e2" \
 --highway-root "$NATIVE_DEPS/highway-457c891775a7397bdb0376bb1031e6e027af1c48" \
 --jpeg-library "$NATIVE_DEPS/jpeg-build/libjpeg.a" > build.log 2>&1
python run.py validate --output validation > validation.log 2>&1
```

Require `validation/verification.json` to report `PASS` before measuring. Read `PROTOCOL.md`: each transform call handles **one array**, including libjxl. Four rotating input arrays form a timing pool, not a four-array batch. Timings include all wrapper copies and normalization, exclude setup, and subtract no overhead.

With other benchmarks and compilers stopped, run two sessions serially:

```sh
python run.py timing --session 1 --output session1 > session1.log 2> session1-fftw-plans.txt
python run.py timing --session 2 --output session2 > session2.log 2> session2-fftw-plans.txt
python analyze.py session1 session2 --output analysis
```

Expect roughly 4–6 minutes per session on the measured Mac, with longer times possible elsewhere. Existing output directories are never overwritten. To repeat, choose fresh `--output` paths and pass their names to `analyze.py`; use `--verification` when the validation folder has another name.

Keep `build/manifest.json`, `validation/`, both session folders and FFTW plan logs, and `analysis/`. The build manifest records compiler commands, reference pins, source/library hashes and BRiDCT version. Analysis emits microseconds per complete array and same-session reference/BRiDCT ratios. Review logs before sharing: process snapshots and local build paths describe the machine running the benchmark.

These files contain no manuscript build system. `NOTICE.md` documents reference attribution and separate licensing.
