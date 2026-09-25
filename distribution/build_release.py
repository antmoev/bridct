"""Build deterministic source/data packages from a reviewed allowlist."""
from pathlib import Path
import argparse
import hashlib
import json
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAMP = (2026, 9, 25, 0, 0, 0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def sums(files):
    return ''.join(f'{digest(data)}  {name}\n' for name, data in sorted(files.items())).encode()


def source_files(root):
    names = json.loads((root / 'distribution/files.json').read_text())
    if len(names) != len(set(names)):
        raise ValueError('Duplicate file in distribution/files.json')
    files = {}
    for name in names:
        path = root / name
        if not name or '\\' in name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError(f'Unsafe package path: {name}')
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Missing or redirected package file: {name}')
        files[name] = path.read_bytes()
    provenance = json.loads(files['PROVENANCE.json'])
    immutable = dict(provenance['sha256'])
    immutable.update(provenance.get('paper_implementation_sha256', {}))
    for name, expected in immutable.items():
        if name not in files or digest(files[name]) != expected:
            raise ValueError(f'Paper source changed: {name}; review and version the numerical implementation')
    corpus = json.loads(files['dataset/manifest.json'])
    if digest(files['dataset/inputs.npz']) != corpus['archive_sha256']:
        raise ValueError('Verification corpus differs from its immutable manifest')
    return files


def finish(files, platform):
    files = dict(files)
    start = 'README.md' if platform == 'repository' else f'distribution/README.{platform}.md'
    files['START_HERE.md'] = files[start]
    corpus = json.loads(files['dataset/manifest.json'])
    files['SOURCES.json'] = encoded({
        'version': files['VERSION'].decode().strip(),
        'packaging_version': files['PACKAGING_VERSION'].decode().strip(),
        'distribution': platform,
        'sha256': {name: digest(data) for name, data in sorted(files.items())},
        'generated_dataset': {'path': 'dataset/inputs.npz', 'sha256': corpus['archive_sha256']},
    })
    files['SHA256SUMS'] = sums(files)
    return files


def archive(path, files, prefix):
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)) << 16
            z.writestr(info, data)


def build(root, output):
    files = source_files(root)
    expected = finish(files, 'repository')
    for name in ('SOURCES.json', 'SHA256SUMS', 'START_HERE.md'):
        if (root / name).read_bytes() != expected[name]:
            raise ValueError(f'{name} is stale; review changes before --refresh-manifest')
    output.mkdir(parents=True, exist_ok=False)
    package = files['PACKAGING_VERSION'].decode().strip()
    if not package or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for c in package):
        raise ValueError('Unsafe packaging version')
    for platform in ('macos', 'ubuntu', 'windows'):
        archive(output / f'bridct-{package}-{platform}.zip', finish(files, platform), 'bridct/')
    dataset = {n.removeprefix('dataset/'): b for n, b in files.items() if n.startswith('dataset/')}
    dataset['SHA256SUMS'] = sums(dataset)
    archive(output / f'bridct-{package}-dataset.zip', dataset, 'bridct-dataset/')
    assets = {p.name: p.read_bytes() for p in sorted(output.iterdir())}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        clean = not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=root, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, clean = None, None
    release = {'version': files['VERSION'].decode().strip(), 'packaging_version': package,
               'source_commit': commit, 'clean_checkout': clean,
               'paper': 'https://arxiv.org/abs/2609.28519v1',
               'dataset_sha256': digest(files['dataset/inputs.npz']),
               'status': 'BUILT_NOT_PLATFORM_VALIDATED',
               'sha256': {n: digest(b) for n, b in assets.items()}}
    assets['RELEASE.json'] = encoded(release)
    (output / 'RELEASE.json').write_bytes(assets['RELEASE.json'])
    (output / 'SHA256SUMS').write_bytes(sums(assets))
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--refresh-manifest', action='store_true')
    mode.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.refresh_manifest:
        files = finish(source_files(ROOT), 'repository')
        for name in ('START_HERE.md', 'SOURCES.json', 'SHA256SUMS'):
            (ROOT / name).write_bytes(files[name])
        print('Refreshed packaging manifest; immutable paper sources and corpus checked.')
    else:
        print(json.dumps(build(ROOT, args.output.resolve()), indent=2))


if __name__ == '__main__':
    main()
