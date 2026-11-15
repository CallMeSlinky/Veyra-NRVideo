"""Bounded replay/HDR checks using existing E: dependencies and an isolated profile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
RUNTIME = Path('E:/Veyra')
REPORT = ART / 'reports/replay-hdr-20261114'
QT = ROOT / 'deps/qt/6.8.3/msvc2022_64'
UI_SCRIPT = ROOT / 'scripts/acceptance/replay-hdr-ui.qml'


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / 'clips').mkdir(exist_ok=True)
    temporary = REPORT / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temporary), TMP=str(temporary),
               QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'),
               PATH=f'{QT / "bin"};{RUNTIME};{env.get("PATH", "")}',
               QT_PLUGIN_PATH=str(QT / 'plugins'),
               QML2_IMPORT_PATH=str(QT / 'qml'),
               VEYRA_LOG_FILE=str(REPORT / 'engine.log'))
    results_path = REPORT / 'results.json'
    results = json.loads(results_path.read_text()) if results_path.exists() else []

    def run(name, args, extra=None):
        child = env.copy(); child.update(extra or {})
        result = subprocess.run([str(x) for x in args], cwd=BUILD, env=child,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        output = result.stdout.decode('utf-8', errors='replace')
        log = REPORT / (name + '.log')
        if log.exists():
            log = REPORT / (name + '-' + str(len(results)) + '.log')
        log.write_text(output, encoding='utf-8')
        results.append({'check': name, 'exit': result.returncode})
        (REPORT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        if result.returncode:
            raise RuntimeError(name + ': ' + output[-5000:])
        print(name, 'passed', flush=True)
        return output

    if '--ui-only' not in sys.argv:
        for target in ('replay_buffer', 'hdr_tuning', 'ui_i18n'):
            run(target, [BUILD / f'veyra_{target}_tests.exe'])
        run('game-hotkey-state', [BUILD / 'veyra_game_passthrough_tests.exe', '--state-only'])
        shutil.copytree(ROOT / 'tests/qml/quick', BUILD / 'qml-tests', dirs_exist_ok=True)
        run('qml-quick', [BUILD / 'veyra_qml_quick_tests.exe', '-o', str(REPORT / 'quick.xml') + ',junitxml'],
            {'QT_QUICK_BACKEND': 'software'})

    media = REPORT / 'moving.y4m'
    if not media.exists():
        width, height = 320, 180
        with media.open('wb') as out:
            out.write(f'YUV4MPEG2 W{width} H{height} F30:1 Ip A1:1 C420jpeg\n'.encode())
            for index in range(30 * 60):
                row = bytearray([32] * width)
                for x in range(20): row[(index * 3 + x) % width] = 210
                out.write(b'FRAME\n' + row * height + bytes([128]) * (width * height // 2))
    prior_clips = set((REPORT / 'clips').glob('*.mp4'))
    main_qml = BUILD / 'qml/Veyra/Main.qml'
    original = main_qml.read_bytes()
    source = original.decode('utf-8'); at = source.rfind('}')
    loader = '\nLoader { source: ' + json.dumps(UI_SCRIPT.as_uri())
    loader += '; onLoaded: { item.media=' + json.dumps(str(media))
    loader += '; item.evidence=' + json.dumps(str(REPORT)) + ' } }\n'
    if '--pause' in sys.argv:
        loader = loader.replace(' } }\n', '; item.exercisePause=true } }\n')
    try:
        main_qml.write_text(source[:at] + loader + source[at:], encoding='utf-8')
        output = run('ui', [BUILD / 'veyra_qml_ui.exe', '--page', 'pro', '--size', '1440x1000',
                            '--reduced-motion', '--data-dir', REPORT / f'profile-{len(results)}', '--exit-after', '100000'])
        if 'REPLAY_HDR_UI_PASS' not in output or 'REPLAY_HDR_UI_FAIL' in output:
            raise RuntimeError(output[-5000:])
        if '--pause' in sys.argv and 'REPLAY_PAUSE_PASS' not in output:
            raise RuntimeError(output[-5000:])
    finally:
        main_qml.write_bytes(original)
    clips = sorted(set((REPORT / 'clips').glob('*.mp4')) - prior_clips)
    if len(clips) < 2: raise RuntimeError('Expected recording and replay MP4 files')
    for index, clip in enumerate(clips):
        decoded = run(f'decode-{index}', [BUILD / 'veyra_anr_media_probe.exe', clip])
        data = json.loads(decoded)
        if data['frames'] < 30 or data['distinctLumaFrames'] < 10:
            raise RuntimeError(f'Insufficient decoded motion: {clip}: {data}')
        if '--pause' in sys.argv and (data['maxVideoPtsGapUs'] > 300000 or data['durationSeconds'] > 20):
            raise RuntimeError(f'Pause created a video gap: {clip}: {data}')
    print('Replay/HDR acceptance passed; evidence:', REPORT)
    retire_fixture()


def retire_fixture():
    media = REPORT / 'moving.y4m'
    if not media.exists(): return
    assert media.resolve().parent == REPORT.resolve()
    with media.open('rb') as source:
        assert source.readline() == b'YUV4MPEG2 W320 H180 F30:1 Ip A1:1 C420jpeg\n'
        source.seek(0)
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    (REPORT / 'retired-fixture.json').write_text(json.dumps({
        'path': str(media), 'bytes': media.stat().st_size, 'sha256': digest,
        'reason': 'Generated synthetic input; regenerate with this harness.'
    }, indent=2), encoding='utf-8')
    media.unlink()


if __name__ == '__main__':
    if '--retire-fixture' in sys.argv:
        retire_fixture()
    else:
        main()
