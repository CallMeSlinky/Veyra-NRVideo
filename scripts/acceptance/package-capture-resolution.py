"""Package the local capture-resolution fix using the verified 2.1.9 ZIP."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/capture-resolution-20261116'
OUT = BUILD / 'portable'
REPORT = ROOT / 'logs/capture-resolution-20261116/portable'
DONOR = Path('E:/Veyra-dev/Veyra/anr-artifacts/releases/fork-release-219-20261115/Veyra-2.1.9-win64-portable.zip')
APP = OUT / 'Veyra-2.1.9-win64-portable'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert not subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT).strip(), 'Commit source first'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert 'CMAKE_BUILD_TYPE:STRING=Release' in (BUILD/'CMakeCache.txt').read_text()
    expected = next(line.split()[0] for line in DONOR.with_name('SHA256SUMS.txt').read_text().splitlines() if line.rstrip().endswith(DONOR.name))
    assert sha(DONOR) == expected, 'Donor ZIP identity mismatch'
    APP.mkdir(parents=True, exist_ok=False)
    REPORT.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(DONOR) as z:
        manifest_name = next(n for n in z.namelist() if n.endswith('/package-manifest.json'))
        prefix = manifest_name.removesuffix('package-manifest.json')
        manifest = json.loads(z.read(manifest_name))
        assert not manifest['anrRuntimeIncluded']
        entries = {e['path']: e for e in manifest['files']}
        for info in z.infolist():
            name = PurePosixPath(info.filename)
            assert not name.is_absolute() and '..' not in name.parts and ':' not in info.filename and '\\' not in info.filename
            assert info.filename.startswith(prefix)
            relative = info.filename[len(prefix):]
            if not relative or info.is_dir() or relative == 'package-manifest.json':
                continue
            assert relative in entries, relative
            assert not relative.startswith(('user-data', 'logs/', 'runtime/anr/'))
            target = APP / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            assert target.stat().st_size == entries[relative]['size'] and sha(target) == entries[relative]['sha256'], relative
        assert all((APP/name).is_file() for name in entries)
    print('Verified donor extracted', flush=True)
    shutil.copy2(BUILD/'veyra_qml_ui.exe', APP/'veyra_qml_ui.exe')
    for name in ('qml', 'i18n', 'docs'):
        shutil.copytree(ROOT/name, APP/name, dirs_exist_ok=True)
    for path in (BUILD/'shaders').glob('*'):
        if path.is_file():
            shutil.copy2(path, APP/'shaders'/path.name)
    notes = ('Veyra 2.1.9 - capture resolution UI fix\n\n'
             'Extract the complete ZIP into a writable folder and run Start Veyra.cmd.\n'
             'Custom resolution is disabled until Enter a custom resolution is checked.\n'
             'Enabling editing copies the selected resolution. Check and select applies it.\n'
             'Unchecking only disables editing; the selected resolution is retained.\n'
             'Settings are stored in this copy\'s user-data folder.\n'
             'Optional ANR must be installed separately; see ANR-README.md.\n'
             f'Source commit: {commit}\n')
    (APP/'README-PORTABLE.txt').write_text(notes, encoding='utf-8')
    assert len(list(APP.glob('*.cmd'))) == 1
    assert not (APP/'runtime/anr').exists()
    assert not list(APP.rglob('*.nrx')) and not list(APP.rglob('nr_fg.ini'))
    temp = REPORT/'tmp'; temp.mkdir()
    env = os.environ.copy()
    for key in ('QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'CUDA_PATH'):
        env.pop(key, None)
    windows = Path(env.get('SystemRoot', 'C:/Windows'))
    env.update(PATH=f'{APP};{windows/"System32"};{windows}', TEMP=str(temp), TMP=str(temp),
               QML_DISK_CACHE_PATH=str(temp/'qmlcache'), VEYRA_LOG_FILE=str(REPORT/'engine.log'))
    probe = REPORT/'probe.qml'
    probe.write_text('''import QtQuick
Item {
 property var shell
 function find(item,name) { if(item.objectName===name)return item; for(const child of item.children||[]){const found=find(child,name);if(found)return found}return null }
 Timer { interval: 2200; running: true; onTriggered: { try {
  const dialog=parent.find(parent.shell.contentItem,"capture-dialog")
  if(!dialog)throw new Error("Capture dialog missing")
  const toggle=parent.find(dialog,"capture-custom-resolution-enable")
  const field=parent.find(dialog,"capture-custom-resolution")
  const apply=parent.find(dialog,"capture-custom-resolution-apply")
  if(!toggle||!field||!apply||toggle.checked||field.enabled||apply.enabled||field.text!=="")throw new Error("Incorrect default editing state")
  if(toggle.text!=="Enter a custom resolution")throw new Error("English translation missing: "+toggle.text)
  console.log("CAPTURE_PORTABLE_UI_PASS",veyra.version)
 } catch(error) { console.error("CAPTURE_PORTABLE_UI_FAIL",error.toString()) } Qt.quit() } }
}''', encoding='utf-8')
    main_qml = APP/'qml/Veyra/Main.qml'
    original = main_qml.read_bytes()
    text = original.decode('utf-8'); at = text.rfind('}')

    def run(label, extra):
        profile = REPORT/(label+'-profile'); profile.mkdir()
        (profile/'qml-preferences.v1.json').write_text(json.dumps(dict(language='en', autoResume=False, prewarmEnhancement=False)), encoding='utf-8')
        p = subprocess.run([str(APP/'veyra_qml_ui.exe'), '--data-dir', str(profile), '--page', 'pro', '--exit-after', '6000', *extra], cwd=APP, env=env, capture_output=True, timeout=45)
        output = p.stdout+p.stderr
        (REPORT/(label+'.log')).write_bytes(output)
        assert p.returncode == 0, (label, p.returncode, output[-2000:])
        return output

    try:
        main_qml.write_text(text[:at]+'\nLoader { source: '+json.dumps(probe.as_uri())+'; onLoaded: item.shell=root }\n'+text[at:], encoding='utf-8')
        output = run('ui', ['--motion-probe', 'dialog', '--reduced-motion'])
        assert b'CAPTURE_PORTABLE_UI_PASS' in output and b'CAPTURE_PORTABLE_UI_FAIL' not in output, output[-4000:]
    finally:
        main_qml.write_bytes(original)
    run('cold-start', [])
    print('Portable UI and minimal-PATH startup passed', flush=True)
    rows = []
    for path in sorted(APP.rglob('*')):
        if path.is_file():
            relative = path.relative_to(APP).as_posix()
            assert not relative.startswith(('user-data', 'logs/'))
            rows.append(dict(path=relative, size=path.stat().st_size, sha256=sha(path)))
    manifest = dict(version='2.1.9', revision='capture-resolution-20261116', sourceCommit=commit,
                    donorZipSha256=expected, anrRuntimeIncluded=False, exeSha256=sha(APP/'veyra_qml_ui.exe'), files=rows)
    (APP/'package-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    rows.append(dict(path='package-manifest.json', sha256=sha(APP/'package-manifest.json')))
    binary = OUT/(APP.name+'.zip')
    with zipfile.ZipFile(binary, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for row in rows:
            z.write(APP/row['path'], APP.name+'/'+row['path'])
    with zipfile.ZipFile(binary) as z:
        assert z.testzip() is None
        for row in rows:
            with z.open(APP.name+'/'+row['path']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256'], row['path']
    source_zip = OUT/'Veyra-2.1.9-source.zip'
    with source_zip.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=zip', '--prefix=Veyra-source/', commit], cwd=ROOT, stdout=stream, check=True, timeout=60)
    with zipfile.ZipFile(source_zip) as z:
        assert z.testzip() is None
    sums = ''.join(f'{sha(p)}  {p.name}\n' for p in (binary, source_zip))
    (OUT/'SHA256SUMS.txt').write_text(sums, encoding='ascii')
    result = dict(passed=True, sourceCommit=commit, portable=str(binary), bytes=binary.stat().st_size,
                  sha256=sha(binary), exeSha256=manifest['exeSha256'], files=len(rows),
                  sourceZip=str(source_zip), uiPassed=True, coldStartPassed=True, zipCrcAndAllFileHashesVerified=True)
    (REPORT/'FINAL.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
