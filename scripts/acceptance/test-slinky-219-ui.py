"""Reuse the replay clock regression with v2.1.9 and custom-control assertions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path('E:/Veyra-dev/Veyra/anr-artifacts/reports/slinky-219-20261115/ui')


def main():
    REPORT.mkdir(parents=True, exist_ok=False)
    source = (ROOT / 'scripts/acceptance/replay-hdr-ui.qml').read_text(encoding='utf-8')
    source = source.replace('veyra.version.indexOf("2.1.6") >= 0, "application reports 2.1.6"',
                            'veyra.version === "2.1.9-Slinky-build", "application reports custom 2.1.9"')
    anchor = 'const choices = veyra.fgBackendChoices'
    source = source.replace(anchor, '''test.check(test.find(test.appWindow.contentItem, "dock-screenshot"), "custom screenshot button retained")
                test.check(test.find(test.appWindow.contentItem, "dock-record"), "custom recording button retained")
                const choices = veyra.fgBackendChoices
                test.check(choices.find(c => c.id === "amdfrc"), "upstream AMD FRC choice integrated")''')
    script = REPORT / 'replay-ui.qml'
    script.write_text(source, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('replay', ROOT / 'scripts/acceptance/test-replay-hdr.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    replay.REPORT, replay.UI_SCRIPT = REPORT, script
    sys.argv = [sys.argv[0], '--ui-only', '--pause']
    replay.main()
    donor = replay.ART / 'releases/anr-b16-20261114/Veyra-2.1.6-Slinky-ANR-B16-win64-portable'
    runtime = donor / 'runtime/experimental'
    env = os.environ.copy()
    env.update(PATH=f'{donor};{env.get("PATH", "")}', TEMP=str(REPORT / 'tmp'),
               TMP=str(REPORT / 'tmp'), VEYRA_LOG_FILE=str(REPORT / 'gpu-engine.log'))
    checks = [('anr-b16-pixels', [replay.BUILD / 'veyra_anr_gpu_tests.exe', runtime])]
    for mode, backend in [('exclusion', 'anr'), ('exclusion-hdr', 'anr'), ('exclusion', 'dlss')]:
        checks.append((mode + '-' + backend,
            [replay.BUILD / 'veyra_repair_fg_tests.exe', mode, REPORT / (mode + '-' + backend), runtime, backend]))
    results = []
    for name, args in checks:
        result = subprocess.run(list(map(str, args)), cwd=donor, env=env, capture_output=True, timeout=300)
        (REPORT / (name + '.log')).write_bytes(result.stdout + result.stderr)
        results.append(dict(check=name, exit=result.returncode))
        (REPORT / 'gpu-results.json').write_text(json.dumps(results, indent=2))
        assert result.returncode == 0, name + ': ' + result.stderr.decode('utf-8', errors='replace')[-2000:]
        print(name, 'passed', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
