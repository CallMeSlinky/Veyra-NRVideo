"""Check English badge bounds and capture normal/high-DPI dialog screenshots."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
REPORT = ART / 'reports/slinky-dialog-fix-20261114'


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    main_qml = BUILD / 'qml/Veyra/Main.qml'
    original = main_qml.read_bytes()
    source = original.decode('utf-8'); end = source.rfind('}')
    results = []
    try:
        for label, scale in [('normal', '1'), ('high-dpi', '1.5')]:
            temporary = REPORT / label / 'tmp'; temporary.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update(PATH=f'{ROOT / "deps/qt/6.8.3/msvc2022_64/bin"};E:/Veyra;{env.get("PATH", "")}',
                       TEMP=str(temporary), TMP=str(temporary), QT_SCALE_FACTOR=scale,
                       QT_PLUGIN_PATH=str(ROOT / 'deps/qt/6.8.3/msvc2022_64/plugins'),
                       QML2_IMPORT_PATH=str(ROOT / 'deps/qt/6.8.3/msvc2022_64/qml'),
                       QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'),
                       VEYRA_LOG_FILE=str(REPORT / (label + '-engine.log')))
            loader = '\nLoader { source: ' + json.dumps((ROOT / 'scripts/acceptance/mode-dialog-overflow.qml').as_uri())
            loader += '; onLoaded: item.screenshot=' + json.dumps(str(REPORT / (label + '.png'))) + ' }\n'
            main_qml.write_text(source[:end] + loader + source[end:], encoding='utf-8')
            result = subprocess.run([str(BUILD / 'veyra_qml_ui.exe'), '--data-dir', str(REPORT / label / 'profile'),
                                     '--page', 'pro', '--size', '800x600', '--reduced-motion', '--exit-after', '15000'],
                                    cwd=BUILD, env=env, capture_output=True, timeout=30)
            output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
            (REPORT / (label + '.log')).write_text(output, encoding='utf-8')
            if result.returncode or 'MODE_DIALOG_PASS' not in output or 'MODE_DIALOG_FAIL' in output:
                raise RuntimeError(label + ': ' + output[-3000:])
            results.append(dict(scale=scale, passed=True))
            print(label, 'passed', flush=True)
    finally:
        main_qml.write_bytes(original)
    (REPORT / 'layout-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
