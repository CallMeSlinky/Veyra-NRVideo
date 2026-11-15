"""Record final source/build/package identities and redistribution checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ART=Path('E:/Veyra-dev/Veyra/anr-artifacts')
REPORT=ART/'reports/slinky-219-20261115'
BUILD=ART/'build/apex-anr-20261112'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    stage=json.loads((REPORT/'STAGE.json').read_text())
    app=Path(stage['app'])
    manifest=json.loads((app/'package-manifest.json').read_text())
    assert stage['coldStartExit']==0 and not stage['anrRuntimeIncluded']
    assert [p.name for p in app.glob('*.cmd')]==['Start Veyra - Slinky build.cmd']
    assert not (app/'runtime/anr').exists()
    assert not list(app.rglob('*.nrx')) and not list(app.rglob('nr_fg.ini'))
    for row in manifest['files']:
        assert sha(app/row['path'])==row['sha256'],row['path']
    assert sha(ROOT/'qml/Veyra/Main.qml')==sha(BUILD/'qml/Veyra/Main.qml')==sha(app/'qml/Veyra/Main.qml')
    b18=json.loads((REPORT/'b18/FINAL.json').read_text())
    assert b18['passed'] and b18['exeSha256']==stage['exeSha256']==sha(BUILD/'veyra_qml_ui.exe')
    codecs=json.loads((REPORT/'validation/codecs/FINAL.json').read_text())
    assert codecs['passed'] and codecs['scope']=='full'
    results=json.loads((REPORT/'validation/results.json').read_text())
    assert all(row['exit']==0 for row in results)
    gpu=json.loads((REPORT/'ui/gpu-results.json').read_text())
    assert all(row['exit']==0 for row in gpu)
    assert 'REPLAY_PAUSE_PASS' in (REPORT/'ui/ui.log').read_text(encoding='utf-8')
    quick=ET.parse(REPORT/'validation/quick.xml').getroot().attrib
    assert quick['failures']=='0' and quick['errors']=='0'
    # The sole adapter change after codec/UI acceptance is runtime discovery.
    with zipfile.ZipFile(REPORT/'original-local-changes.zip') as original:
        old=original.read('src/ngx/AnrFgBackend.cpp').replace(b'\r\n',b'\n')
    current=(ROOT/'src/ngx/AnrFgBackend.cpp').read_bytes().replace(b'\r\n',b'\n')
    assert old.split(b'bool AnrFgBackend::initialize',1)[1]==current.split(b'bool AnrFgBackend::initialize',1)[1]
    diff=subprocess.run(['git','-c','core.safecrlf=false','diff','--check'],cwd=ROOT,capture_output=True)
    assert diff.returncode==0,diff.stdout.decode(errors='replace')
    final=dict(status='passed',upstreamTag='v2.1.9',
        upstreamCommit=subprocess.check_output(['git','rev-parse','v2.1.9^{}'],cwd=ROOT).decode().strip(),
        sourceState='Uncommitted custom working-tree integration; no push or public release',
        app=stage['app'],launcher=stage['launcher'],exeSha256=stage['exeSha256'],
        packageFiles=stage['files'],anrRuntimeIncluded=False,optionalAnrDownload=b18['upstreamUrl'],
        b18=b18,quick=quick,checks=results,earlierB16Gpu=gpu,
        codecAcceptance=codecs,codecAcceptancePrecedesLoaderOnlyChange=True,
        anrInferenceCodeUnchanged=True,matchingShaders=len(list((app/'shaders').rglob('*.dxil'))),
        protectedFiles=json.loads((REPORT/'validation/protected-files.json').read_text()),
        startupMusicIncluded=False,amfHeadersEnabled=True,amdRuntimeInstalled=False,
        limitations=['AMD FRC/AMD/Intel hardware not tested; no AMD runtime on this PC.',
            'Known simultaneous HEVC HDR recording/replay device-removal issue remains unresolved.',
            'No physical capture card, physical HDR display, optical latency or long-duration validation.',
            'Upstream startup MP3 is not included; music remains optional.'],
        originalSourceBackup=str(REPORT/'original-local-changes.zip'),
        retainedFailures=['Wrong initial Qt Quick build target; corrected build passed.',
            'First translation check hit cp1252 console encoding; UTF-8 check passed.',
            'Initial stage manifest check detected missing duplicate launchers after successful startup; revised stage has one launcher.'])
    (REPORT/'FINAL.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
    print('Verified 2.1.9 delivery:',stage['app'])
    print('One launcher; no ANR payload; exact B18 full archive extraction verified.')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
