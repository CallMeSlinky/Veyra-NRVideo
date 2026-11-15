"""Bounded checks for all 2.1.6 changes and the preserved local ANR backend."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
REPORT = ART / 'reports/slinky-216-20261114/validation'


def main():
    global REPORT
    if '--attempt' in sys.argv:
        REPORT = REPORT / sys.argv[sys.argv.index('--attempt') + 1]
    REPORT.mkdir(parents=True, exist_ok=True)
    temporary = REPORT / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temporary), TMP=str(temporary),
               PATH=f'{ROOT / "deps/qt/6.8.3/msvc2022_64/bin"};E:/Veyra;{env.get("PATH", "")}',
               VEYRA_LOG_FILE=str(REPORT / 'engine.log'), QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'))
    results = []
    checks = [
        ('live-timing', ['veyra_live_timing_tests.exe']),
        ('logger', ['veyra_logger_tests.exe', REPORT / 'logger']),
        ('preset-library', ['veyra_preset_library_tests.exe']),
        ('effect-chain', ['veyra_effect_chain_tests.exe']),
        ('preset-roundtrip', ['veyra_repair_preset_tests.exe', REPORT / 'presets.dat']),
        ('vfg-settings', ['veyra_vfg_settings_tests.exe', REPORT / 'vfg']),
        ('anr-settings-migration', ['veyra_anr_settings_tests.exe', REPORT / 'anr', ROOT / 'tests/fixtures/legacy-slinky-anr']),
    ]
    if '--checks' in sys.argv:
        selected = sys.argv[sys.argv.index('--checks') + 1].split(',')
        checks = [(label, args) for label, args in checks if label in selected]
    for label, args in checks:
        command = [str(BUILD / args[0]), *map(str, args[1:])]
        result = subprocess.run(command, cwd=BUILD, env=env, capture_output=True, timeout=300)
        output = result.stdout + result.stderr
        (REPORT / (label + '.log')).write_bytes(output)
        results.append(dict(check=label, exit=result.returncode))
        (REPORT / 'unit-results.json').write_text(json.dumps(results, indent=2))
        if result.returncode:
            raise RuntimeError(label + ': ' + output.decode('utf-8', errors='replace')[-5000:])
        print(label, 'passed', flush=True)
    if '--skip-ui' in sys.argv:
        return
    spec = importlib.util.spec_from_file_location('replay_acceptance', ROOT / 'scripts/acceptance/test-replay-hdr.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.REPORT = REPORT / 'replay-hdr'
    module.main()


def gpu():
    app = ART / 'releases/slinky-build-2.1.6-20261114/Veyra-2.1.6-Slinky build-win64-portable'
    output = REPORT / 'gpu'
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / 'tmp'; temporary.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(PATH=f'{app};{env.get("PATH", "")}', TEMP=str(temporary), TMP=str(temporary),
               VEYRA_LOG_FILE=str(output / 'engine.log'))
    runtime = app / 'runtime/experimental'
    checks = [('anr-pixels', [BUILD / 'veyra_anr_gpu_tests.exe', runtime])]
    for mode, provider in [('exclusion', 'off'), ('exclusion-hdr', 'off'),
                           ('exclusion', 'anr'), ('exclusion-hdr', 'anr'),
                           ('exclusion', 'dlss')]:
        label = mode + '-' + provider
        checks.append((label, [BUILD / 'veyra_repair_fg_tests.exe', mode, output / label, runtime, provider]))
    results = []
    for label, args in checks:
        result = subprocess.run(list(map(str, args)), cwd=app, env=env, capture_output=True, timeout=300)
        (output / (label + '.log')).write_bytes(result.stdout + result.stderr)
        results.append(dict(check=label, exit=result.returncode))
        (output / 'results.json').write_text(json.dumps(results, indent=2))
        if result.returncode:
            raise RuntimeError(label + ': ' + (result.stdout + result.stderr).decode('utf-8', errors='replace')[-5000:])
        print(label, 'passed', flush=True)


if __name__ == '__main__':
    gpu() if '--gpu' in sys.argv else main()
