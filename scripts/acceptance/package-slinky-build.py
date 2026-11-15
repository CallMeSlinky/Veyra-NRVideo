"""Package the tested replay/HDR executable with verified existing runtimes."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
DONOR = ART / 'releases/slinky-build-2.1.6-20261114/Veyra-2.1.6-Slinky build-win64-portable.zip'
OUT = ART / 'releases/slinky-build-2.1.6-dialog-fix-20261114'
NAME = 'Veyra-2.1.6-Slinky-build-win64-portable'
APP = OUT / NAME
REPORT = ART / 'reports/slinky-dialog-fix-20261114/package'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def safe(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe package path: ' + name)
    return path.parts


def main(extra_docs=(), readme_suffix='', temporary=None):
    resume = '--resume' in sys.argv
    if OUT.exists() and not resume:
        raise FileExistsError('Refusing to overwrite an existing delivery: ' + str(OUT))
    if resume:
        existing = json.loads((APP / 'package-manifest.json').read_text())
        if existing.get('version') != '2.1.6-Slinky-build' or existing['exeSha256'] != sha(BUILD / 'veyra_qml_ui.exe'):
            raise ValueError('Existing output is not this task build')
        for row in existing['files']:
            if sha(APP.joinpath(*safe(row['path']))) != row['sha256']:
                raise ValueError('Existing task payload changed: ' + row['path'])
    expected = DONOR.with_suffix('.zip.sha256').read_text().split()[0]
    if sha(DONOR) != expected:
        raise ValueError('Donor archive SHA256 mismatch')
    assert (BUILD / 'qml/Veyra/Main.qml').read_bytes() == (ROOT / 'qml/Veyra/Main.qml').read_bytes()
    APP.mkdir(parents=True, exist_ok=resume)
    REPORT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DONOR) as archive:
        manifest_name = next(n for n in archive.namelist() if n.endswith('/package-manifest.json'))
        prefix = manifest_name.removesuffix('package-manifest.json')
        donor = json.loads(archive.read(manifest_name))
        for row in donor['files']:
            name = row['path']
            safe(name)
            if name == 'veyra_qml_ui.exe' or name.startswith(('qml/Veyra/', 'shaders/', 'i18n/')):
                continue
            data = archive.read(prefix + name)
            if len(data) != row['size'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Donor payload mismatch: ' + name)
            target = APP.joinpath(*safe(name))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    shutil.copy2(BUILD / 'veyra_qml_ui.exe', APP / 'veyra_qml_ui.exe')
    for folder in ('qml', 'shaders'):
        shutil.copytree(BUILD / folder, APP / folder, dirs_exist_ok=True)
    shutil.copytree(ROOT / 'i18n', APP / 'i18n', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', APP / 'THIRD_PARTY_NOTICES.md')
    for name in ('SLINKY_2.1.6_INTEGRATION_2026-11-14.md', 'RELEASE_NOTES_2.1.6.md', 'SLINKY_DIALOG_REPLAY_FIX_2026-11-14.md', *extra_docs):
        shutil.copy2(ROOT / 'docs' / name, APP / 'docs' / name)
    (APP / 'Start Veyra - Slinky build.cmd').write_text(
        '@echo off\ncd /d "%~dp0"\nstart "" "%~dp0veyra_qml_ui.exe" --data-dir "%~dp0user-data-slinky-2.1.6"\n',
        encoding='ascii')
    # Keep the familiar launcher, with the same isolated profile as the named launcher.
    shutil.copy2(APP / 'Start Veyra - Slinky build.cmd', APP / 'Start Veyra.cmd')
    (APP / 'Slinky build README.txt').write_text(
        'Veyra 2.1.6 - Slinky build - 14 November 2026\n\n'
        'Extract the whole ZIP, then run Start Veyra - Slinky build.cmd.\n'
        'Settings are kept in user-data-slinky-2.1.6 beside this copy.\n'
        'Includes all 2.1.6 application changes through upstream 20955b5c:\n'
        'automatic/60-to-30 duplicate removal, NVIDIA low latency Off/On,\n'
        'scheduling fixes, effect masks, instant replay, microphone controls, HDR UI and more.\n'
        'Preserves the local ANR B15 implementation and original FG dropdown labels.\n'
        'Upstream ANR provider implementation and quality-ranking labels are excluded.\n'
        'EXE version: 2.1.6.0; display label: 2.1.6-Slinky-build.\n'
        'Fixes mode-switch dialog text overflow and pauses replay while the source is paused/idle.\n'
        'Paused replay remains saveable; resumed replay omits the paused wall-clock interval.\n'
        'Optional PS5/Moonlight/Xbox and libass backends are not enabled in this build.\n'
        'Microphone hardware and physical HDR display output were not tested.\n'
        'This is a local personal build, not an official public release.\n'
        'See docs/SLINKY_2.1.6_INTEGRATION_2026-11-14.md for validation.\n' + readme_suffix, encoding='utf-8')
    rows = []
    for path in sorted(APP.rglob('*')):
        if path.is_file() and path.name != 'package-manifest.json':
            rows.append(dict(path=path.relative_to(APP).as_posix(), size=path.stat().st_size, sha256=sha(path)))
    for row in rows:
        name = row['path']
        if name.startswith(('user-data', 'logs/')) or name.endswith(('.log', '.dmp', 'tests.exe', 'probe.exe')):
            raise ValueError('Unwanted development artifact: ' + name)
    write(APP / 'package-manifest.json', dict(schema=1, version='2.1.6-Slinky-build',
        localOnly=True, published=False, sourceHasLocalChanges=True,
        exeSha256=sha(APP / 'veyra_qml_ui.exe'), donorSha256=expected, files=rows))
    archive_path = OUT / (NAME + '.zip')
    with zipfile.ZipFile(archive_path, 'w' if resume else 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows + [dict(path='package-manifest.json')]:
            archive.write(APP / row['path'], NAME + '/' + row['path'])
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip(): raise ValueError('ZIP CRC validation failed')
        for row in rows:
            with archive.open(NAME + '/' + row['path']) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                    raise ValueError('ZIP payload identity mismatch: ' + row['path'])
    digest = sha(archive_path)
    archive_path.with_suffix('.zip.sha256').write_text(digest + '  ' + archive_path.name + '\n', encoding='ascii')
    source = OUT / 'Veyra-2.1.6-Slinky-build-source.zip'
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(source, 'w' if resume else 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(set(names)):
            if not name or name.startswith(('deps/', '.vscode/', '.git/', 'build/', 'logs/', 'reports/', 'tests/data/')):
                continue
            path = ROOT.joinpath(*safe(name))
            if path.is_file(): archive.write(path, 'Veyra-Slinky-build-source/' + name)
    source.with_suffix('.zip.sha256').write_text(sha(source) + '  ' + source.name + '\n', encoding='ascii')
    print('ZIP payload verified:', len(rows), 'files', flush=True)
    temporary = temporary or ART / 'tmp/slinky-216-20261114'
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ('QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'CUDA_PATH'):
        env.pop(key, None)
    windows = Path(env.get('SystemRoot', 'C:/Windows'))
    env.update(PATH=f'{APP};{windows / "System32"};{windows}', TEMP=str(temporary), TMP=str(temporary),
               QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'),
               VEYRA_LOG_FILE=str(REPORT / 'cold-engine.log'))
    if (REPORT / 'cold-start.log').exists():
        shutil.copy2(REPORT / 'cold-start.log', REPORT / 'cold-start-first-attempt.log')
    with (REPORT / 'cold-start.log').open('w', encoding='utf-8') as log:
        done = subprocess.run([str(APP / 'veyra_qml_ui.exe'), '--data-dir', str(REPORT / 'cold-profile'),
                               '--page', 'pro', '--exit-after', '5000'], cwd=APP, env=env,
                              stdout=log, stderr=subprocess.STDOUT, timeout=40)
    if done.returncode: raise RuntimeError('Portable cold start failed; inspect cold-start.log')
    # Startup must not change any packaged payload.
    for row in rows:
        if sha(APP / row['path']) != row['sha256']:
            raise ValueError('Payload changed during cold start: ' + row['path'])
    write(REPORT / 'FINAL.json', dict(status='passed', archive=str(archive_path), sha256=digest,
        bytes=archive_path.stat().st_size, verifiedFiles=len(rows), source=str(source),
        sourceSha256=sha(source), coldStartExit=done.returncode, minimalPath=True,
        preexistingAnrRuntimePreserved=True, upstreamAnrChangesImported=False))
    print('Portable cold start passed\nZIP:', archive_path, '\nSHA256:', digest, flush=True)


if __name__ == '__main__':
    main()
