#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash distribution/run_ubuntu.sh [options]
  --confirm-dev5           Dev.4/dev.5/OpenCV, 128/256/512, 2 × 21 blocs de 30 ms.
  --quick                  Deux sessions, 7 blocs de 10 ms, 10 formes (défaut).
  --full                   Deux sessions, 21 blocs de 30 ms, 64 formes.
  --python EXECUTABLE      CPython 3.10–3.14 avec GIL (défaut : python3).
  --jobs N                 Compilations simultanées, hors timing (défaut : 2).
  --output DOSSIER         Nouveau dossier de résultats ; ne doit pas exister.
  --no-system-install      Ne jamais proposer apt ; échouer si dépendance absente.
  --no-process-guard       Désactiver la garde Python (la garde C reste active).
  --preflight              Vérifier l'hôte et les outils ; aucune installation.
  --help                   Afficher cette aide.
EOF
}

fail() { printf 'ERREUR : %s\n' "$*" >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
profile=quick
profile_given=
python_command=python3
jobs=2
output=
allow_system=1
process_guard=1
preflight=0
while (($#)); do
    case "$1" in
        --quick|--full|--confirm-dev5)
            [[ -z "$profile_given" ]] || fail 'Choisir un seul profil de comparaison.'
            profile=${1#--}; profile_given=1; shift ;;
        --python|--jobs|--output)
            (($# >= 2)) || fail "Argument manquant après $1."
            case "$1" in
                --python) python_command=$2 ;;
                --jobs) jobs=$2 ;;
                --output) output=$2 ;;
            esac
            shift 2 ;;
        --no-system-install) allow_system=0; shift ;;
        --no-process-guard) process_guard=0; shift ;;
        --preflight) preflight=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Option inconnue : $1" ;;
    esac
done
if [[ "$profile" == confirm-dev5 && "$(cat "$root/VERSION")" != 0.2.0-dev.5 ]]; then
    fail 'Le profil dev.5 exige son ZIP figé ; utiliser --quick ou --full pour cette version.'
fi
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || fail '--jobs doit être un entier positif.'
((jobs <= 64)) || fail '--jobs doit être inférieur ou égal à 64.'
[[ -n "$python_command" ]] || fail '--python est vide.'
[[ "$(uname -s)" == Linux ]] || fail 'Ce lanceur vise Ubuntu Linux ; voir le README pour les autres systèmes.'
[[ "$(uname -m)" == x86_64 ]] || fail 'Ce paquet de comparaison vise Ubuntu x86-64 (Intel ou AMD).'
[[ -r /etc/os-release ]] || fail '/etc/os-release est introuvable.'
. /etc/os-release
[[ "${ID:-}" == ubuntu && ( "${VERSION_ID:-}" == 22.04 || "${VERSION_ID:-}" == 24.04 ) ]] || fail 'Versions préparées : Ubuntu 22.04 et 24.04.'
command -v tar >/dev/null && command -v gzip >/dev/null || fail 'tar et gzip sont nécessaires pour conserver les résultats.'

missing=()
python_version=
check_dependencies() {
    missing=()
    command -v clang >/dev/null || missing+=(clang)
    command -v make >/dev/null || missing+=(make)
    command -v ar >/dev/null || missing+=(binutils)
    command -v flock >/dev/null || missing+=(util-linux)
    command -v ps >/dev/null || missing+=(procps)
    [[ -f /usr/include/stdio.h ]] || missing+=(libc6-dev)
    [[ -s /etc/ssl/certs/ca-certificates.crt ]] || missing+=(ca-certificates)
    if ! command -v "$python_command" >/dev/null; then
        [[ "$python_command" == python3 ]] || fail "Interpréteur demandé absent : $python_command"
        missing+=(python3 python3-venv python3-dev)
        return
    fi
    python_version=$("$python_command" - <<'PY'
import platform, struct, sys, sysconfig
if platform.python_implementation() != 'CPython' or not (3, 10) <= sys.version_info[:2] <= (3, 14):
    raise SystemExit('CPython 3.10 à 3.14 requis pour les dépendances épinglées.')
if sysconfig.get_config_var('Py_GIL_DISABLED') or struct.calcsize('P') != 8:
    raise SystemExit('CPython 64 bits avec GIL requis.')
print(f'{sys.version_info.major}.{sys.version_info.minor}')
PY
) || fail 'Version ou architecture Python incompatible.'
    "$python_command" -c 'import venv, ensurepip' >/dev/null 2>&1 || missing+=("python${python_version}-venv")
    "$python_command" -c 'from pathlib import Path; import sysconfig; assert (Path(sysconfig.get_paths()["include"])/"Python.h").is_file()' >/dev/null 2>&1 || missing+=("python${python_version}-dev")
}

if ((preflight)); then
    check_dependencies
    printf 'Hôte : Ubuntu %s, x86-64 ; Python : %s ; profil : %s.\n' "$VERSION_ID" "${python_version:-absent}" "$profile"
    if ((${#missing[@]})); then
        printf 'Paquets système manquants : %s\n' "${missing[*]}"
        exit 1
    fi
    printf 'Précontrôle réussi. Aucun paquet installé ; aucun test ou timing exécuté.\n'
    exit 0
fi

run_id="ubuntu-$(date -u +%Y%m%dT%H%M%SZ)-$$"
output=${output:-"$root/results/$run_id"}
[[ ! -e "$output" && ! -e "${output%/}.tar.gz" ]] || fail 'Le dossier ou son archive existe déjà ; choisir une nouvelle sortie.'
mkdir -p -- "$(dirname -- "$output")"
mkdir -- "$output"
output=$(cd -- "$output" && pwd -P)
mkdir "$output/logs" "$output/build-metadata"
work_relative=".ubuntu-work/$run_id"
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
        if [[ "$profile" == confirm-dev5 ]]; then
            "$summary_python" "$root/distribution/summarize_candidate.py" --results "$output" > "$output/logs/summary.log" 2>&1
        else
            "$summary_python" "$root/distribution/summarize.py" --results "$output" > "$output/logs/summary.log" 2>&1
        fi
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

check_dependencies
if ((${#missing[@]})); then
    printf 'Paquets système manquants : %s\n' "${missing[*]}"
    ((allow_system)) || fail 'Installation système désactivée. Installer ces paquets puis relancer.'
    [[ -t 0 ]] || fail 'Consentement interactif requis pour apt. Installer les paquets manuellement puis relancer.'
    printf 'Installer uniquement ces dépendances via apt (mise à jour des index comprise) ? [o/N] '
    read -r answer
    case "$answer" in o|O|oui|Oui|y|Y|yes) ;; *) fail 'Installation refusée ; aucun apt lancé.' ;; esac
    privilege=()
    if ((EUID != 0)); then
        command -v sudo >/dev/null || fail 'sudo absent ; demander à votre administrateur ces paquets.'
        sudo -v
        privilege=(sudo -n)
    fi
    run apt-update "${privilege[@]}" apt-get update
    run apt-install "${privilege[@]}" apt-get install --no-install-recommends --yes "${missing[@]}"
    check_dependencies
    ((${#missing[@]} == 0)) || fail "Dépendances encore absentes : ${missing[*]}. Vérifier l'interpréteur personnalisé."
fi
python_command=$(command -v "$python_command")
if [[ "$python_command" != /* ]]; then
    python_command="$(cd -- "$(dirname -- "$python_command")" && pwd -P)/$(basename -- "$python_command")"
fi

exec 9> "$root/.ubuntu-run.lock"
flock -n 9 || fail 'Une autre campagne utilise déjà ce dossier ; ne pas superposer les chronométrages.'
mkdir -p "$work"
cd "$root"
unset PYTHONPATH PYTHONHOME PYTHONOPTIMIZE CFLAGS CPPFLAGS CXXFLAGS LDFLAGS MAKEFLAGS MFLAGS
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CC=clang AR=ar
for required in Makefile python/benchmark_libraries.py python/benchmark.py bench/compare_small.py distribution/requirements-ubuntu.txt dataset/inputs.npz; do
    [[ -f "$required" ]] || fail "Paquet incomplet : $required absent."
done
cp distribution/requirements-ubuntu.txt "$output/requirements.txt"
cp distribution/run_ubuntu.sh "$output/run_ubuntu.sh"
cp VERSION "$output/VERSION"
if [[ -f SHA256SUMS ]]; then
    cp SHA256SUMS "$output/SHA256SUMS-source"
    run source-check sha256sum -c SHA256SUMS
else
    cp SOURCES.json "$output/SOURCES.json"
    run source-check "$python_command" tools/verify_source.py
fi
{
    printf 'started_utc=%s\nprofile=%s\ncompiler=clang\nbackend=auto\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$profile"
    cat /etc/os-release
    uname -a
    command -v lscpu >/dev/null && lscpu
    command -v free >/dev/null && free -h
    clang --version
    "$python_command" --version
} > "$output/host.txt" 2>&1

run create-venv "$python_command" -m venv "$work/venv"
python="$work/venv/bin/python"
run install-pip "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: pip==25.3
run install-dependencies "$python" -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: --report "$output/pip-install.json" -r distribution/requirements-ubuntu.txt
run pip-check "$python" -m pip check
"$python" -m pip freeze --all > "$output/pip-freeze.txt"
run generated-source-check "$python" tools/generate_small.py --check
run generated-avx2-check "$python" tools/generate_avx2.py --check
run build-and-c-checks make -j"$jobs" CC=clang AR=ar ARCH=x86_64 BACKEND=auto RUNTIME_SIMD=auto RUNNER= CFLAGS=-O3 EXTRA_FLAGS= BUILD="$work_relative/native" PYTHON="$python" check bench
run build-python "$python" python/build.py --core . --library "$work/native/libbridct.a" --output "$work/python" --cc clang
run python-environment "$python" python/runtime_info.py --module-dir "$work/python" --output "$output/python-environment.json"
run python-api-validation "$python" python/test_api.py --all-shapes --module-dir "$work/python" --output "$output/python-api-validation.json"
run build-allocator-test "$python" python/build_test_allocator.py --build-dir "$work/python"
run python-hardening "$python" python/test_hardening.py --module-dir "$work/python" --output "$output/python-hardening.json"
run dataset-check "$python" dataset/prepare.py
run numerical-corpus "$python" tests/verify_portability.py --runner "$work/native/test_runner_shared" --library "$work/native/libbridct.so" --output "$output/numerical-corpus" --execution 'Native Ubuntu x86-64; hardware described in host.txt'
if [[ "$profile" == confirm-dev5 ]]; then
    ((process_guard)) || fail 'La confirmation dev.5 exige la garde des processus.'
    run reconstruct-parent "$python" distribution/prepare_parent.py --output "$work/parent"
    cp "$work/parent/PARENT_RECONSTRUCTION.json" "$output/PARENT_RECONSTRUCTION.json"
    run build-parent make -C "$work/parent" -j"$jobs" CC=clang AR=ar ARCH=x86_64 BACKEND=auto RUNTIME_SIMD=auto RUNNER= CFLAGS=-O3 EXTRA_FLAGS= BUILD=build PYTHON="$python" check
    run build-parent-python "$python" python/build.py --core "$work/parent" --library "$work/parent/build/libbridct.a" --output "$work/parent-python" --cc clang
    run parent-api-validation "$python" python/test_api.py --all-shapes --module-dir "$work/parent-python" --output "$output/parent-api-validation.json"
    run parent-numerical-corpus "$python" "$work/parent/tests/verify_portability.py" --runner "$work/parent/build/test_runner_shared" --library "$work/parent/build/libbridct.so" --output "$output/parent-numerical-corpus" --execution 'Native Ubuntu x86-64; reconstructed dev.4 control, common toolchain'
    cp "$work/parent/build/config" "$output/build-metadata/parent-config"
    cp "$work/parent-python/build.json" "$output/build-metadata/parent-python.json"
    cp "$work/python/build.json" "$output/build-metadata/candidate-python.json"
    cp distribution/compare_candidate.py distribution/summarize_candidate.py "$output/"
    printf '\nDeux sessions appariées dev.4/dev.5/OpenCV ; éviter toute autre charge CPU.\n'
    for session in 1 2; do
        run "paired-session$session" "$python" distribution/compare_candidate.py --parent-extension "$work/parent-python" --candidate-extension "$work/python" --output "$output/paired-session$session" --session "$session" --blocks 21 --ms 30 --shapes 128x128 256x256 512x512
    done
    run paired-audit "$python" distribution/summarize_candidate.py --results "$output"
    stage=complete
    exit 0
fi

run native-controls-validation "$python" bench/compare_small.py --output "$output/native-controls-validation" --session 1 --validate-only --library "$work/native/libbridct.a" --cc clang --extra-flags=-march=native

blocks=7
ms=10
shape_args=()
if [[ "$profile" == full ]]; then blocks=21; ms=30; shape_args=(--all-shapes); fi
guard_args=()
((process_guard == 0)) || guard_args=(--guard-known-compute)
description="Native Ubuntu $VERSION_ID x86-64; user-managed host; isolation not guaranteed; profile=$profile"
printf '\nContrôles terminés. Début des deux sessions successives ; éviter toute autre charge CPU.\n'
for session in 1 2; do
    run "opencv-session$session" "$python" python/benchmark.py --extension "$work/python" --output "$output/opencv-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description "$description" "${shape_args[@]}" "${guard_args[@]}"
    run "libraries-session$session" "$python" python/benchmark_libraries.py --extension "$work/python" --output "$output/libraries-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --environment-description "$description" "${shape_args[@]}" "${guard_args[@]}"
    run "ooura-session$session" "$python" bench/compare_small.py --output "$output/ooura-session$session" --session "$session" --blocks "$blocks" --ms "$ms" --library "$work/native/libbridct.a" --control-build "$output/native-controls-validation/build" --cc clang
done
stage=complete
printf '\nCampagne terminée ; les sorties restent exploratoires et propres à cette machine.\n'
