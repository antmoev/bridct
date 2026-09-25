#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash distribution/run_macos.sh [options]
  --verify                 Build and verify; no timing (default).
  --quick                  Verify, then two sessions: 7 blocks, 10 ms, 10 shapes.
  --full                   Verify, then two sessions: 21 blocks, 30 ms, 64 shapes.
  --python EXECUTABLE      Native 64-bit CPython 3.10–3.14 with GIL (default python3).
  --jobs N                 Parallel compilation jobs, never timing (default 2).
  --output DIRECTORY       New results directory; must not already exist.
  --offline                New venv with inherited system packages; no network.
  --preflight              Check tools and host only; no installation or build.
  --help                   Show this help.
Dependencies are installed only inside a new venv. No system packages are installed.
EOF
}
fail() {
    printf 'ERROR: %s\n' "$*" >&2
    if [[ -n "${output:-}" && -d "$output/logs" ]]; then
        printf 'ERROR: %s\n' "$*" >> "$output/logs/failure.log"
    fi
    exit 1
}
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
profile=verify
profile_given=
python_command=python3
jobs=2
output=
offline=0
preflight=0
lock_owned=
while (($#)); do
    case "$1" in
        --verify|--quick|--full)
            [[ -z "$profile_given" ]] || fail 'Choose one profile.'
            profile=${1#--}; profile_given=1; shift ;;
        --python|--jobs|--output)
            (($# >= 2)) || fail "Missing argument after $1."
            case "$1" in
                --python) python_command=$2 ;;
                --jobs) jobs=$2 ;;
                --output) output=$2 ;;
            esac
            shift 2 ;;
        --offline) offline=1; shift ;;
        --preflight) preflight=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || fail '--jobs must be a positive integer.'
((jobs <= 64)) || fail '--jobs must be <= 64.'
[[ "$(uname -s)" == Darwin ]] || fail 'This launcher requires macOS.'
arch=$(uname -m)
[[ "$arch" == arm64 || "$arch" == x86_64 ]] || fail 'Supported CPU architectures: arm64 and x86_64.'
[[ "$(sysctl -in sysctl.proc_translated 2>/dev/null || true)" != 1 ]] || fail 'Use a native terminal and Python, not Rosetta.'
command -v tar >/dev/null && command -v gzip >/dev/null || fail 'tar and gzip are required.'
check_dependencies() {
    command -v xcrun >/dev/null || fail 'Install Apple Command Line Tools with xcode-select --install.'
    compiler=$(xcrun --find clang) || fail 'Install Apple Command Line Tools with xcode-select --install.'
    archiver=$(xcrun --find ar) || fail 'Apple ar is unavailable.'
    sdk=$(xcrun --sdk macosx --show-sdk-path) || fail 'macOS SDK is unavailable.'
    command -v make >/dev/null || fail 'make is unavailable; install Apple Command Line Tools.'
    command -v "$python_command" >/dev/null || fail 'Install native CPython 3.10–3.14 and select it with --python.'
    "$python_command" - "$arch" <<'PYTHON'
import platform, struct, sys, sysconfig, venv, ensurepip
from pathlib import Path
if platform.python_implementation() != 'CPython' or not (3, 10) <= sys.version_info[:2] <= (3, 14):
    raise SystemExit('CPython 3.10–3.14 required.')
if sysconfig.get_config_var('Py_GIL_DISABLED') or struct.calcsize('P') != 8:
    raise SystemExit('64-bit CPython with GIL required.')
if platform.machine() != sys.argv[1]:
    raise SystemExit('Python architecture differs from the terminal architecture.')
if not (Path(sysconfig.get_paths()['include'])/'Python.h').is_file():
    raise SystemExit('Python development headers are unavailable.')
print('CPython', platform.python_version(), platform.machine())
PYTHON
}
if ((preflight)); then
    check_dependencies
    printf 'Preflight passed; profile=%s, architecture=%s. No installation or build.\n' "$profile" "$arch"
    exit 0
fi
run_id="macos-$(date -u +%Y%m%dT%H%M%SZ)-$$"
output=${output:-"$root/results/$run_id"}
[[ ! -e "$output" && ! -e "${output%/}.tar.gz" ]] || fail 'Le dossier ou son archive existe déjà ; choisir une nouvelle sortie.'
mkdir -p -- "$(dirname -- "$output")"
mkdir -- "$output"
output=$(cd -- "$output" && pwd -P)
mkdir "$output/logs" "$output/build-metadata"
work_relative=".macos-work/$run_id"
work="$root/$work_relative"
stage=preparation
child_pid=
archive="$output.tar.gz"
finish() {
    local code=$?
    trap - EXIT INT TERM
    set +e
    if [[ -n "$child_pid" ]]; then
        kill -TERM "$child_pid" 2>/dev/null
        wait "$child_pid" 2>/dev/null
    fi
    printf 'exit_code=%s\nlast_stage=%s\nprofile=%s\nfinished_utc=%s\n' "$code" "$stage" "$profile" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$output/status.txt"
    mkdir -p "$output/build-metadata"
    for name in config; do
        [[ ! -f "$work/native/$name" ]] || cp "$work/native/$name" "$output/build-metadata/native-$name"
    done
    for name in build.json build.log import-check.log test-allocator-build.json test-allocator-build.log; do
        [[ ! -f "$work/python/$name" ]] || cp "$work/python/$name" "$output/build-metadata/$name"
    done
    local summary_python=${python:-$python_command}
    if [[ -f "$root/distribution/summarize.py" ]] && command -v "$summary_python" >/dev/null; then
        "$summary_python" "$root/distribution/summarize.py" --results "$output" > "$output/logs/summary.log" 2>&1
        printf 'summary_exit_code=%s\n' "$?" >> "$output/status.txt"
    fi
    tar --exclude='*/build' --exclude='*/__pycache__' -czf "$archive" -C "$(dirname "$output")" -- "$(basename "$output")"
    local archive_code=$?
    if ((archive_code == 0)); then
        printf '\nArchive à transmettre : %s\n' "$archive"
    else
        printf '\nArchivage incomplet ; conserver le dossier : %s\n' "$output" >&2
        ((code != 0)) || code=$archive_code
    fi
    [[ -z "$lock_owned" ]] || rmdir "$root/.macos-run.lock" 2>/dev/null
    exit "$code"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

run() {
    stage=$1
    shift
    printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$stage"
    printf '%q ' "$@" >> "$output/commands.log"
    printf '\n' >> "$output/commands.log"
    "$@" > "$output/logs/$stage.log" 2>&1 &
    child_pid=$!
    local code=0
    wait "$child_pid" || code=$?
    child_pid=
    if ((code)); then
        tail -n 40 "$output/logs/$stage.log" >&2
        return "$code"
    fi
}

{
    printf 'started_utc=%s\nprofile=%s\narchitecture=%s\noffline=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$profile" "$arch" "$offline"
    sw_vers
    for key in hw.model hw.memsize hw.physicalcpu hw.logicalcpu machdep.cpu.brand_string; do
        sysctl "$key" 2>/dev/null || true
    done
} > "$output/host.txt" 2>&1
[[ ! -f "$root/VERSION" ]] || cp "$root/VERSION" "$output/VERSION"
check_dependencies
"$compiler" --version >> "$output/host.txt"
"$python_command" --version >> "$output/host.txt" 2>&1
python_command=$(command -v "$python_command")
if [[ "$python_command" != /* ]]; then
    python_command="$(cd -- "$(dirname -- "$python_command")" && pwd -P)/$(basename -- "$python_command")"
fi
mkdir "$root/.macos-run.lock" 2>/dev/null || fail 'Another run owns .macos-run.lock; do not overlap campaigns. Remove a stale lock only after checking no run remains active.'
lock_owned=1
mkdir -p "$work"
cd "$root"
unset PYTHONPATH PYTHONHOME PYTHONOPTIMIZE CFLAGS CPPFLAGS CXXFLAGS LDFLAGS MAKEFLAGS MFLAGS
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CC="$compiler" AR="$archiver" SDKROOT="$sdk"
for required in Makefile python/benchmark_libraries.py python/benchmark.py bench/compare_small.py distribution/requirements-ubuntu.txt dataset/inputs.npz; do
    [[ -f "$required" ]] || fail "Incomplete package: $required absent."
done
cp distribution/requirements-ubuntu.txt "$output/requirements.txt"
cp distribution/run_macos.sh "$output/run_macos.sh"
cp VERSION "$output/VERSION"
if [[ -f SHA256SUMS ]]; then
    cp SHA256SUMS "$output/SHA256SUMS-source"
    run source-check shasum -a 256 -c SHA256SUMS
else
    cp SOURCES.json "$output/SOURCES.json"
    run source-check "$python_command" tools/verify_source.py
fi
if ((offline)); then
    run create-venv "$python_command" -m venv --system-site-packages "$work/venv"
    "$python_command" - "$work/venv" > "$output/logs/offline-inheritance.log" <<'PYTHON'
from pathlib import Path
import site, sys
root = Path(sys.argv[1])
paths = [Path(p).resolve() for p in site.getsitepackages() if Path(p).is_dir()]
target = root/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'/'bridct_offline_inheritance.pth'
target.write_text(''.join(str(p)+'\n' for p in paths))
print('Explicit offline package inheritance:')
for path in paths:
    print(path)
PYTHON
else
    run create-venv "$python_command" -m venv "$work/venv"
fi
python="$work/venv/bin/python"
if ((offline)); then
    run check-offline-dependencies "$python" -m pip --isolated install --no-index --no-deps --only-binary=:all: -r distribution/requirements-ubuntu.txt
else
    run install-pip "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: pip==25.3
    run install-dependencies "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: --report "$output/pip-install.json" -r distribution/requirements-ubuntu.txt
fi
run pip-check "$python" -m pip check
"$python" -m pip freeze --all > "$output/pip-freeze.txt"
run generated-source-check "$python" tools/generate_small.py --check
run generated-avx2-check "$python" tools/generate_avx2.py --check
run build-and-c-checks make -j"$jobs" CC="$compiler" AR="$archiver" ARCH="$arch" BACKEND=auto RUNTIME_SIMD=auto RUNNER= CFLAGS=-O3 EXTRA_FLAGS= BUILD="$work_relative/native" PYTHON="$python" check bench
run build-python "$python" python/build.py --core . --library "$work/native/libbridct.a" --output "$work/python" --cc "$compiler"
run python-environment "$python" python/runtime_info.py --module-dir "$work/python" --output "$output/python-environment.json"
run python-api-validation "$python" python/test_api.py --all-shapes --module-dir "$work/python" --output "$output/python-api-validation.json"
run build-allocator-test "$python" python/build_test_allocator.py --build-dir "$work/python"
run python-hardening "$python" python/test_hardening.py --module-dir "$work/python" --output "$output/python-hardening.json"
run dataset-check "$python" dataset/prepare.py
run numerical-corpus "$python" tests/verify_portability.py --runner "$work/native/test_runner_shared" --library "$work/native/libbridct.dylib" --output "$output/numerical-corpus" --execution "Native macOS $arch; hardware described in host.txt"
run native-controls-validation "$python" bench/compare_small.py --output "$output/native-controls-validation" --session 1 --validate-only --library "$work/native/libbridct.a" --cc "$compiler"
if [[ "$profile" == verify ]]; then
    stage=complete
    printf '\nVerification completed; no benchmark timings were collected.\n'
    exit 0
fi
blocks=7
ms=10
shape_args=(--shapes 8x8 16x16 32x32 64x64 128x128 256x256 512x512 1024x1024 16x32 8x64)
if [[ "$profile" == full ]]; then blocks=21; ms=30; shape_args=(--all-shapes); fi
description="Native macOS $arch; user-managed host; isolation not guaranteed; profile=$profile"
printf '\nValidation completed. Two consecutive sessions; avoid other CPU workloads.\n'
for session in 1 2; do
    run "opencv-session$session" "$python" python/benchmark.py --extension "$work/python" --output "$output/opencv-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description "$description" "${shape_args[@]}" --guard-known-compute
    run "libraries-session$session" "$python" python/benchmark_libraries.py --extension "$work/python" --output "$output/libraries-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description "$description" "${shape_args[@]}" --guard-known-compute
    run "ooura-session$session" "$python" bench/compare_small.py --output "$output/ooura-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --library "$work/native/libbridct.a" --control-build "$output/native-controls-validation/build" --cc "$compiler"
done
stage=complete
printf '\nCampaign completed; results are exploratory and specific to this machine.\n'
