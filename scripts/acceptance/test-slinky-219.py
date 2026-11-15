"""Bounded v2.1.9/custom-feature regression with isolated E: artifacts."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
REPORT = ART / 'reports/slinky-219-20261115/validation'


def main():
    REPORT.mkdir(parents=True, exist_ok=False)
    temporary = REPORT / 'tmp'
    temporary.mkdir()
    qt = ROOT / 'deps/qt/6.8.3/msvc2022_64'
    env = os.environ.copy()
    env.update(TEMP=str(temporary), TMP=str(temporary),
               PATH=f'{qt / "bin"};E:/Veyra;{env.get("PATH", "")}',
               QT_PLUGIN_PATH=str(qt / 'plugins'), QML2_IMPORT_PATH=str(qt / 'qml'),
               QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'),
               VEYRA_LOG_FILE=str(REPORT / 'engine.log'), QT_QUICK_BACKEND='software')
    checks = [
        ('timing', ['veyra_live_timing_tests.exe']),
        ('replay', ['veyra_replay_buffer_tests.exe']),
        ('anr-settings', ['veyra_anr_settings_tests.exe', REPORT / 'anr', ROOT / 'tests/fixtures/legacy-slinky-anr']),
        ('fg-settings', ['veyra_vfg_settings_tests.exe', REPORT / 'vfg']),
        ('vrr-policy', ['veyra_vrr_profile_tests.exe']),
        ('capture-monitor-off', ['veyra_capture_audio_tests.exe', '--record-monitor-off']),
        ('optional-startup-music', ['veyra_startup_music_tests.exe', 'missing', REPORT / 'absent.mp3']),
        ('qml-quick', ['veyra_qml_quick_tests.exe', '-o', str(REPORT / 'quick.xml') + ',junitxml']),
    ]
    shutil.copytree(ROOT / 'tests/qml/quick', BUILD / 'qml-tests', dirs_exist_ok=True)
    results = []
    for name, arguments in checks:
        result = subprocess.run([str(BUILD / arguments[0]), *map(str, arguments[1:])],
                                cwd=BUILD, env=env, capture_output=True, timeout=300)
        output = result.stdout + result.stderr
        (REPORT / (name + '.log')).write_bytes(output)
        results.append(dict(check=name, exit=result.returncode))
        (REPORT / 'results.json').write_text(json.dumps(results, indent=2))
        print(name, result.returncode, flush=True)
        if result.returncode:
            raise RuntimeError(output.decode('utf-8', errors='replace')[-4000:])
    # Verify untouched custom implementation files against the original backup.
    original = json.loads((REPORT.parent / 'original-files.json').read_text())
    protected = ['include/veyra/ngx/AnrFgBackend.h',
                 'include/veyra/sink/VideoCodec.h', 'src/sink/NvencCodec.h',
                 'src/sink/NvencD3D11Bridge.h', 'qml/Veyra/VTag.qml',
                 'src/engine/ReplayBuffer.cpp', 'include/veyra/engine/ReplayTimeline.h']
    for name in protected:
        expected = next(row['sha256'] for row in original if row['path'] == name)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    (REPORT / 'protected-files.json').write_text(json.dumps(protected, indent=2))
    spec = importlib.util.spec_from_file_location('codecs', ROOT / 'scripts/acceptance/verify-video-codecs.py')
    codecs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codecs)
    codecs.REPORT = REPORT / 'codecs'
    codecs.REPORT.mkdir()
    sys.argv = [sys.argv[0], '--aligned-fixture']
    if codecs.check():
        raise RuntimeError('Codec acceptance failed')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
