"""Validate replay's paused clock and actual pause/resume/idle MP4 output."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
REPORT = ART / 'reports/slinky-replay-pause-20261114'


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(ART / 'build/apex-anr-20261112/veyra_replay_buffer_tests.exe')],
                            capture_output=True, timeout=30)
    (REPORT / 'unit.log').write_bytes(result.stdout + result.stderr)
    if result.returncode: raise RuntimeError(result.stdout.decode())
    print(result.stdout.decode().splitlines()[-1], flush=True)
    spec = importlib.util.spec_from_file_location('replay_acceptance', ROOT / 'scripts/acceptance/test-replay-hdr.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.REPORT = REPORT
    sys.argv = [sys.argv[0], '--ui-only', '--pause']
    module.main()


if __name__ == '__main__':
    main()
