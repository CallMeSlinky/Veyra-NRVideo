"""Create one portable app without ANR payloads and with exactly one launcher."""
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
REPORT = ART / 'reports/slinky-219-20261115'
DONOR = ART / 'releases/anr-b16-20261114/Veyra-2.1.6-Slinky-ANR-B16-win64-portable.zip'
APP = ART / 'releases/slinky-219-20261115/Veyra-2.1.9-Slinky-build-win64-portable'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    accepted = json.loads((REPORT / 'validation/codecs/FINAL.json').read_text())
    assert accepted['passed'] and accepted['scope'] == 'full'
    b18 = json.loads((REPORT / 'b18/FINAL.json').read_text())
    assert b18['passed'] and b18['exeSha256'] == sha(BUILD / 'veyra_qml_ui.exe')
    expected = DONOR.with_suffix('.zip.sha256').read_text().split()[0]
    assert sha(DONOR) == expected, 'Donor identity mismatch'
    resume = '--resume' in sys.argv
    APP.mkdir(parents=True, exist_ok=resume)
    if resume:
        previous = json.loads((APP / 'package-manifest.json').read_text())
        missing_launchers = []
        for row in previous['files']:
            path = APP / row['path']
            if not path.exists() and row['path'].startswith('Start Veyra') and path.suffix == '.cmd':
                missing_launchers.append(row['path'])
                continue
            assert sha(path) == row['sha256'], 'Concurrent change: ' + row['path']
        retired = APP / 'runtime/anr'
        assert retired.resolve().is_relative_to(APP.resolve())
        assert not os.path.isjunction(APP / 'runtime') and not os.path.isjunction(retired)
        for path in retired.rglob('*'):
            assert not path.is_symlink() and not os.path.isjunction(path), path
        if retired.exists():shutil.rmtree(retired)
        for path in APP.glob('Start Veyra*.cmd'):
            if path.name != 'Start Veyra - Slinky build.cmd':
                assert any(r['path'] == path.name for r in previous['files'])
                path.unlink()
        (REPORT / 'stage-revision.json').write_text(json.dumps(dict(
            reason='User requests no ANR redistribution and one launcher',
            removedRuntime=str(retired), missingInheritedLaunchers=missing_launchers,
            previousColdStartExit=0, previousVerification='failed on missing duplicate launchers'), indent=2))
    with zipfile.ZipFile(DONOR) as archive:
        assert archive.testzip() is None
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            assert not name.is_absolute() and '..' not in name.parts and ':' not in entry.filename and '\\' not in entry.filename
            relative = Path(*name.parts[1:])
            if not relative.parts or entry.is_dir():
                continue
            if relative.as_posix().startswith('runtime/anr/') or relative.name == 'package-manifest.json' or relative.suffix == '.cmd':
                continue
            if resume:
                continue
            assert not relative.parts[0].startswith(('user-data', 'logs'))
            target = APP / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
        manifest_name = next(n for n in archive.namelist() if n.endswith('/package-manifest.json'))
        donor_manifest = json.loads(archive.read(manifest_name))
        prefix = manifest_name.removesuffix('package-manifest.json')
        for row in donor_manifest['files']:
            assert hashlib.sha256(archive.read(prefix + row['path'])).hexdigest() == row['sha256'], row['path']
    shutil.copy2(BUILD / 'veyra_qml_ui.exe', APP / 'veyra_qml_ui.exe')
    for name in ('qml', 'shaders', 'i18n', 'docs', 'assets'):
        source = BUILD / name if name in ('qml', 'shaders') else ROOT / name
        shutil.copytree(source, APP / name, dirs_exist_ok=True)
    for name in ('README.md', 'README_EN.md', 'README_CN.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, APP / name)
    shutil.copy2(ROOT / 'docs/RELEASE_NOTES_2.1.9.md', APP / 'RELEASE_NOTES.md')
    # Exactly one launcher, addressing this copy's private 2.1.9 profile.
    launcher = '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0veyra_qml_ui.exe" --data-dir "%~dp0user-data-slinky-2.1.9" %*\r\n'
    (APP / 'Start Veyra - Slinky build.cmd').write_bytes(launcher.encode('ascii'))
    (APP / 'Slinky build README.txt').write_text(
        'Veyra 2.1.9 Slinky build.\nRun Start Veyra - Slinky build.cmd.\n'
        'Retains custom AV1/HEVC, capture buttons, badge wrapping, replay fixes and optional ANR integration.\n'
        'Settings use a new user-data-slinky-2.1.9 directory; prior profiles are untouched.\n'
        'AMD FRC requires the AMD driver runtime; not tested on this NVIDIA PC.\n'
        'Startup music is optional and absent unless you supply an authorized media/startup-music.mp3.\n'
        'Known concurrent HEVC HDR recording/replay failure remains unresolved.\n'
        'No ANR binaries/models/config are included. Download ANR directly from its author if desired.\n'
        'See docs/SLINKY_2.1.9_INTEGRATION_2026-11-15.md for current validation.\n', encoding='utf-8')
    (APP / 'ANR-README.txt').write_text(
        'Optional ANR installation (download directly from its author):\n'
        'https://github.com/apex-compute/ANR/releases/download/FG-V.B18/anr-fg-V.B18-full.zip\n\n'
        'Close Veyra. Create runtime/anr beside the executable. Extract the ZIP contents there.\n'
        'The provider will be at runtime/anr/game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/nvngx_dlssg.dll.\n'
        'Keep all subfolders together. Do not run install.cmd; do not copy game/dxgi.dll beside Veyra.\n'
        'Restart Veyra and select Apex ANR - Beta. Legacy flat provider installs remain supported.\n'
        'This package contains no ANR provider DLLs, models or program packs.\n', encoding='utf-8')
    assert not (APP / 'runtime/anr').exists(), 'ANR payload must not be distributed'
    assert len(list(APP.glob('*.cmd'))) == 1
    files = [dict(path=p.relative_to(APP).as_posix(), size=p.stat().st_size, sha256=sha(p))
             for p in sorted(APP.rglob('*')) if p.is_file() and p.name != 'package-manifest.json']
    manifest = dict(version='2.1.9-Slinky-build', published=False, anrRuntimeIncluded=False,
                    donorSha256=expected, exeSha256=sha(APP / 'veyra_qml_ui.exe'), files=files)
    (APP / 'package-manifest.json').write_text(json.dumps(manifest, indent=2))
    temporary = ART / 'tmp/slinky-219-20261115'
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ('QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'CUDA_PATH'):
        env.pop(key, None)
    windows = Path(env.get('SystemRoot', 'C:/Windows'))
    env.update(PATH=f'{APP};{windows / "System32"};{windows}', TEMP=str(temporary), TMP=str(temporary),
               QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'), VEYRA_LOG_FILE=str(REPORT / 'cold-engine.log'))
    result = subprocess.run([str(APP / 'veyra_qml_ui.exe'), '--data-dir', str(REPORT / 'cold-profile'),
                             '--page', 'pro', '--exit-after', '6000'], cwd=APP, env=env,
                            capture_output=True, timeout=45)
    (REPORT / 'cold-start.log').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, 'Cold start failed'
    for row in files:
        assert sha(APP / row['path']) == row['sha256'], row['path']
    (REPORT / 'STAGE.json').write_text(json.dumps(dict(app=str(APP), files=len(files), coldStartExit=0,
        exeSha256=manifest['exeSha256'], donorSha256=expected, publicUpload=False,
        anrRuntimeIncluded=False, launcher='Start Veyra - Slinky build.cmd'), indent=2))
    print('Portable stage verified:', APP, len(files), 'files')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
