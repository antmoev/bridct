#!/usr/bin/env bash
set -euo pipefail
root=$(pwd -P)
python_boot=$(cygpath -u "$BRIDCT_PYTHON_WINDOWS")
output=$(cygpath -u "$BRIDCT_OUTPUT_WINDOWS")
work=$(cygpath -u "$BRIDCT_WORK_WINDOWS")
work_relative=".windows-work/$(basename "$work")"
jobs=$BRIDCT_JOBS
unset PYTHONPATH PYTHONHOME PYTHONOPTIMIZE CFLAGS CPPFLAGS CXXFLAGS LDFLAGS MAKEFLAGS MFLAGS
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
run() {
    local name=$1
    shift
    printf '%s\n' "$name" > "$output/pipeline-stage.txt"
    printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$name"
    printf '%q ' "$@" >> "$output/commands.log"
    printf '\n' >> "$output/commands.log"
    "$@" > "$output/logs/$name.log" 2>&1 || { local code=$?; tail -n 30 "$output/logs/$name.log"; return "$code"; }
}
finish() {
    local code=$?
    trap - EXIT
    set +e
    for file in "$work/native/config" "$work/python/build.json" "$work/python/build.log" "$work/python/import-check.log"; do
        [[ ! -f "$file" ]] || cp "$file" "$output/build-metadata/$(basename "$file")"
    done
    printf '%s\n' "$code" > "$output/pipeline-exit.txt"
    exit "$code"
}
trap finish EXIT
pacman -Q > "$output/msys2-packages.txt"
clang --version > "$output/compiler.txt"
cp distribution/requirements-ubuntu.txt "$output/requirements.txt"
cp distribution/windows_pipeline.sh "$output/windows_pipeline.sh"
cp SOURCES.json "$output/SOURCES.json"
run source-check "$python_boot" tools/verify_source.py
run create-venv "$python_boot" -m venv "$work/venv"
python="$work/venv/Scripts/python.exe"
run pip-upgrade "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: pip==25.3
run dependencies "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: --report "$output/pip-install.json" -r distribution/requirements-ubuntu.txt
run pip-check "$python" -m pip check
"$python" -m pip freeze --all > "$output/pip-freeze.txt"
run generated-small "$python" tools/generate_small.py --check
run generated-avx2 "$python" tools/generate_avx2.py --check
run build-and-c-checks make -j"$jobs" CC=clang AR=llvm-ar ARCH=x86_64 BACKEND=auto RUNTIME_SIMD=auto RUNNER= CFLAGS=-O3 EXTRA_FLAGS= BUILD="$work_relative/native" PYTHON="$python" check bench
run build-python "$python" python/build.py --core . --library "$work/native/libbridct.a" --output "$work/python" --cc clang
run python-environment "$python" python/runtime_info.py --module-dir "$work/python" --output "$output/python-environment.json"
run python-api "$python" python/test_api.py --all-shapes --module-dir "$work/python" --output "$output/python-api-validation.json"
run allocator-build "$python" python/build_test_allocator.py --build-dir "$work/python"
run python-hardening "$python" python/test_hardening.py --module-dir "$work/python" --output "$output/python-hardening.json"
run corpus "$python" tests/verify_portability.py --runner "$work/native/test_runner_shared.exe" --library "$work/native/bridct.dll" --output "$output/numerical-corpus" --execution 'Native Windows x86-64; see host.json for CPU/OS and CI status'
run native-controls "$python" bench/compare_small.py --output "$output/native-controls-validation" --session 1 --validate-only --library "$work/native/libbridct.a" --cc clang --extra-flags=-march=native
if [[ "$BRIDCT_PROFILE" == Verify ]]; then
    printf 'complete-validation-only\n' > "$output/pipeline-stage.txt"
    exit 0
fi
blocks=7; ms=10; shapes=()
if [[ "$BRIDCT_PROFILE" == Full ]]; then blocks=21; ms=30; shapes=(--all-shapes); fi
for session in 1 2; do
    run "opencv-session$session" "$python" python/benchmark.py --extension "$work/python" --output "$output/opencv-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description 'Windows x86-64; see host.json; isolation not guaranteed' "${shapes[@]}" --guard-known-compute
    run "libraries-session$session" "$python" python/benchmark_libraries.py --extension "$work/python" --output "$output/libraries-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description 'Windows x86-64; see host.json; isolation not guaranteed' "${shapes[@]}" --guard-known-compute
    run "ooura-session$session" "$python" bench/compare_small.py --output "$output/ooura-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --library "$work/native/libbridct.a" --control-build "$output/native-controls-validation/build" --cc clang
 done
printf 'complete\n' > "$output/pipeline-stage.txt"
