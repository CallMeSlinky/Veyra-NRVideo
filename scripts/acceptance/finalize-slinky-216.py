"""Record final, evidence-backed acceptance for the corrected Slinky delivery."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TASK = Path('E:/Veyra-dev/Veyra/anr-artifacts/reports/slinky-216-20261114')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    package = json.loads((TASK / 'package/FINAL.json').read_text())
    original = json.loads((TASK / 'original-files.json').read_text())
    for name in ('src/ngx/AnrFgBackend.cpp', 'include/veyra/ngx/AnrFgBackend.h'):
        assert digest(ROOT / name) == next(row['sha256'] for row in original if row['path'] == name)
    assert not (ROOT / 'src/ngx/AnrProvider.cpp').exists()
    assert not (ROOT / 'include/veyra/ngx/AnrProvider.h').exists()
    bridge = 'src/ui/bridge/FrameGeneration.cpp'
    with zipfile.ZipFile(TASK / 'original-local-changes.zip') as backup:
        before = backup.read(bridge).decode().replace('\r\n', '\n')
    after = (ROOT / bridge).read_text(encoding='utf-8')
    def choices(source):
        return source.split('QVariantList QmlPlayerBridge::fgBackendChoices() const {', 1)[1].split('QString QmlPlayerBridge::fgProviderText() const {', 1)[0]
    assert choices(before) == choices(after)
    validation = TASK / 'validation'
    units = []
    for folder, names in [('', ['live-timing', 'logger', 'preset-library', 'effect-chain']),
                          ('migration', ['vfg-settings']),
                          ('compatibility', ['anr-settings-migration']),
                          ('isolated', ['preset-roundtrip'])]:
        rows = json.loads((validation / folder / 'unit-results.json').read_text())
        for name in names:
            row = next(row for row in rows if row['check'] == name)
            assert row['exit'] == 0
            units.append(row)
    replay = validation / 'isolated/replay-hdr'
    actual = json.loads((replay / 'results.json').read_text())
    assert actual and all(row['exit'] == 0 for row in actual)
    quick = ET.parse(replay / 'quick.xml').getroot().attrib
    assert quick['failures'] == quick['errors'] == '0'
    gpu = json.loads((validation / 'gpu/results.json').read_text())
    assert len(gpu) == 6 and all(row['exit'] == 0 for row in gpu)
    app = Path(package['archive']).with_suffix('')
    manifest = json.loads((app / 'package-manifest.json').read_text())
    for row in manifest['files']:
        assert digest(app / row['path']) == row['sha256'], row['path']
    shaders = list((app / 'shaders').rglob('*.dxil'))
    receipt = dict(status='complete', upstream='20955b5c', version='2.1.6-Slinky-build',
                   numericVersion='2.1.6.0', package=package, unitChecks=units,
                   uiRecordingReplay=actual, qtQuick=quick, gpu=gpu, builtShaders=len(shaders),
                   preservedLocalAnrSource=True, preservedExactBackendChoiceFunction=True,
                   postGpuPackagedPayloadHashesVerified=True, publiclyPublished=False,
                   limits=['RTX 4090 only; no AMD/Intel hardware run',
                           'No physical capture-card latency, microphone hardware or HDR display check',
                           'Existing build disables optional PS5/Moonlight/Xbox and libass backends',
                           'Historical upstream performance data was not repeated locally'])
    (TASK / 'FINAL.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print('Complete:', package['archive'])
    print('Shader payloads:', len(shaders), 'All post-GPU package hashes retained')


if __name__ == '__main__':
    main()
