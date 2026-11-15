"""Stage and verify B16 in a separate latest Slinky AV1/HEVC portable app."""
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')  # junction to E:/项目/Veyra
TASK = 'anr-b16-20261114'
OUT = ART / 'releases' / TASK
APP = OUT / 'Veyra-2.1.6-Slinky-ANR-B16-win64-portable'
REPORT = ART / 'reports' / TASK
TEST = ART / 'tests' / TASK
BUILD = ART / 'build/apex-anr-20261112'
DOWNLOAD = ART / 'downloads' / TASK / 'anr-fg-V.B16-full.zip'
DONOR = ART / 'releases/slinky-av1-hevc-full-20261114/Veyra-2.1.6-Slinky-build-win64-portable.zip'
URL = 'https://github.com/apex-compute/ANR/releases/download/FG-V.B16/anr-fg-V.B16-full.zip'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def safe(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe archive path: ' + name)
    return p.parts


def stage():
    if APP.exists():
        raise FileExistsError('Use the existing task stage; do not overwrite it')
    expected = DONOR.with_suffix('.zip.sha256').read_text().split()[0]
    if sha(DONOR) != expected:
        raise ValueError('Donor ZIP identity mismatch')
    rows = []
    with zipfile.ZipFile(DONOR) as z:
        manifest_name = next(n for n in z.namelist() if n.endswith('/package-manifest.json'))
        prefix = manifest_name.removesuffix('package-manifest.json')
        manifest = json.loads(z.read(manifest_name))
        for row in manifest['files']:
            name = row['path']
            parts = safe(name)
            if name.startswith('runtime/anr/'):
                continue
            data = z.read(prefix + name)
            if len(data) != row['size'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Donor payload mismatch: ' + name)
            target = APP.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append(row)
    prefix = 'game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/'
    with zipfile.ZipFile(DOWNLOAD) as z:
        meta = json.loads(z.read('nr_fg_package.json'))
        if meta['version'] != 'V.B16':
            raise ValueError('Unexpected upstream version')
        for name in z.namelist():
            if name.startswith(prefix) and not name.endswith('/'):
                target = APP / 'runtime/anr'
                target = target.joinpath(*safe(name[len(prefix):]))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        runtime = APP / 'runtime/anr'
        (runtime / 'nr_fg_package.json').write_bytes(z.read('nr_fg_package.json'))
        if sha(runtime / 'nvngx_dlssg.dll') != meta['provider_sha256']:
            raise ValueError('Provider differs from upstream metadata')
        (runtime / 'UPSTREAM-README.txt').write_bytes(z.read('README.txt'))
    (APP / 'runtime/experimental').mkdir(exist_ok=True)
    # Preserve the donor's existing notices and corresponding source archive.
    shutil.copy2(ROOT / 'docs/ANR_B16_2026-11-14.md', APP / 'docs/ANR_B16_2026-11-14.md')
    (APP / 'ANR-README.txt').write_text(
        'Veyra 2.1.6 Slinky ANR B16 (AV1/HEVC application, updated runtime)\n\n'
        'Run Start Veyra.cmd; select Apex ANR - Beta. Supports 2X/3X/4X/6X.\n'
        'Settings use the separate user-data-anr-b16 folder beside this copy.\n'
        'The pixel-space motion correction and latest AV1/HEVC application are retained.\n'
        'Only runtime/anr is upgraded; OptiScaler and dxgi.dll are not installed.\n'
        'Upstream: ' + URL + '\n'
        'See docs/ANR_B16_2026-11-14.md. Local personal candidate; not published.\n', encoding='utf-8')
    (APP / 'Start Veyra - ANR B16.cmd').write_text('@echo off\ncd /d \"%~dp0\"\nstart \"\" \"%~dp0veyra_qml_ui.exe\" --data-dir \"%~dp0user-data-anr-b16\"\n', encoding='ascii')
    shutil.copy2(APP / 'Start Veyra - ANR B16.cmd', APP / 'Start Veyra.cmd')
    write(REPORT / 'stage.json', dict(upstreamUrl=URL, archiveSha256=sha(DOWNLOAD),
        upstreamMetadata=meta, donor=str(DONOR), donorSha256=sha(DONOR),
        exeSha256=sha(APP / 'veyra_qml_ui.exe'), verifiedDonorFiles=len(rows),
        unchangedApplication=True))
    print('Staged', APP, flush=True)


def tests():
    REPORT.mkdir(parents=True, exist_ok=True)
    TEST.mkdir(parents=True, exist_ok=True)
    temp = ART / 'tmp' / TASK
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temp), TMP=str(temp), PATH=str(APP)+';'+env.get('PATH', ''),
               VEYRA_LOG_FILE=str(REPORT / 'gpu-engine.log'))
    env.pop('VEYRA_TEST_ANR_LEGACY_MOTION_SCALE', None)
    with (REPORT / 'gpu.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([str(BUILD / 'veyra_anr_gpu_tests.exe'), str(APP / 'runtime/experimental')],
            cwd=APP, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    text = (REPORT / 'gpu.log').read_text('utf-8', errors='replace')
    if result.returncode or 'ANR GPU checks=133 failed=0' not in text:
        raise RuntimeError(text[-8000:])
    print('B16 GPU: 133 checks, 0 failures', flush=True)
    spec = importlib.util.spec_from_file_location('acceptance', ROOT / 'scripts/acceptance/test-apex-anr.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.APP, mod.REPORT, mod.TEST = APP, REPORT, TEST
    mod.ART = ART / 'tmp' / TASK / 'harness'
    (mod.ART / 'tmp/apex-anr-20261112').mkdir(parents=True, exist_ok=True)
    # Redirect the existing acceptance harness without changing historical scripts.
    mod.pkg.APP, mod.pkg.REPORT = APP, REPORT
    sys.argv = [str(__file__)]
    mod.main()


def seal():
    if 'ANR GPU checks=133 failed=0' not in (REPORT / 'gpu.log').read_text('utf-8'):
        raise ValueError('GPU acceptance missing')
    results = json.loads((REPORT / 'acceptance.json').read_text())
    if len(results) != 4 or any(row['returncode'] for row in results):
        raise ValueError('UI/export acceptance missing')
    stage_info = json.loads((REPORT / 'stage.json').read_text())
    if sha(APP / 'veyra_qml_ui.exe') != stage_info['exeSha256']:
        raise ValueError('Application changed')
    with zipfile.ZipFile(DOWNLOAD) as z:
        prefix = 'game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/'
        for name in z.namelist():
            if name.startswith(prefix) and not name.endswith('/'):
                target = APP / 'runtime/anr' / name[len(prefix):]
                if sha(target) != hashlib.sha256(z.read(name)).hexdigest():
                    raise ValueError('Upstream file changed during tests: ' + name)
    with zipfile.ZipFile(DONOR) as z:
        name = next(n for n in z.namelist() if n.endswith('/package-manifest.json'))
        for row in json.loads(z.read(name))['files']:
            if row['path'].startswith('runtime/anr/') or row['path'] in ('ANR-README.txt', 'Start Veyra.cmd'):
                continue
            if sha(APP / row['path']) != row['sha256']:
                raise ValueError('Retained donor file changed: ' + row['path'])
    shutil.copy2(ROOT / 'docs/ANR_B16_2026-11-14.md', APP / 'docs/ANR_B16_2026-11-14.md')
    readme = APP / 'ANR-README.txt'
    readme.write_text(readme.read_text(encoding='utf-8').replace(
        'user-data-anr folder', 'user-data-anr-b16 folder'), encoding='utf-8')
    rows = []
    for file in sorted(APP.rglob('*')):
        if not file.is_file():
            continue
        name = file.relative_to(APP).as_posix()
        if name.startswith(('user-data', 'logs/')) or name.endswith(('.log', '.dmp')):
            continue
        if name in ('package-manifest.json', 'runtime/anr/anr-vkloader.dll'):
            continue
        rows.append(dict(path=name, size=file.stat().st_size, sha256=sha(file)))
    write(APP / 'package-manifest.json', dict(schema=1, version='2.1.6-Slinky-anr-B16',
        anrVersion='FG-V.B16', localOnly=True, published=False,
        exeSha256=stage_info['exeSha256'], sourceHasLocalChanges=True,
        sourceArchive=str(DONOR.parent / 'Veyra-2.1.6-Slinky-build-source.zip'), files=rows))
    archive = OUT / (APP.name + '.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for row in rows + [dict(path='package-manifest.json')]:
            z.write(APP / row['path'], APP.name + '/' + row['path'])
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise ValueError('ZIP CRC failure')
        for row in rows:
            if hashlib.sha256(z.read(APP.name + '/' + row['path'])).hexdigest() != row['sha256']:
                raise ValueError('Archived identity mismatch: ' + row['path'])
    digest = sha(archive)
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n', encoding='ascii')
    write(REPORT / 'FINAL.json', dict(status='passed', portable=str(archive), sha256=digest,
        upstream=stage_info, gpuChecks=133, gpuFailures=0, acceptance=results,
        limits=['RTX 4090 only; AMD and Intel untested',
                'No long-duration VRAM-growth measurement', 'Local personal package; not published']))
    print('Verified portable:', archive, '\nSHA256:', digest, flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'stage': stage, 'test': tests, 'seal': seal}[sys.argv[1]]()
