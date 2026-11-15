"""Full private Slinky portable from the verified donor and accepted codec EXE."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
ART=Path('E:/Veyra-dev/Veyra/anr-artifacts')


def main():
    spec=importlib.util.spec_from_file_location('slinky_packager',ROOT / 'scripts/acceptance/package-slinky-build.py')
    pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)
    codec_report=ART / 'reports/video-codecs-20261114/FINAL.json'
    receipt=json.loads(codec_report.read_text(encoding='utf-8'))
    if not receipt['passed'] or receipt['scope']!='full' or pack.sha(pack.BUILD / 'veyra_qml_ui.exe')!=receipt['exeSha256']:
        raise ValueError('Build does not match the full codec acceptance receipt')
    pack.DONOR=ART / 'releases/slinky-build-2.1.6-dialog-fix-20261114/Veyra-2.1.6-Slinky-build-win64-portable.zip'
    pack.OUT=ART / 'releases/slinky-av1-hevc-full-20261114'
    pack.APP=pack.OUT / pack.NAME
    pack.REPORT=ART / 'reports/slinky-av1-hevc-full-20261114'
    pack.main(extra_docs=('VIDEO_CODECS_2026-11-14.md',),
              temporary=ART / 'tmp/slinky-av1-hevc-full-20261114',
              readme_suffix='\nAV1 / H.265 update:\n'
              'Includes the accepted AV1/HEVC recording, replay and export changes.\n'
              'AV1 uses NVIDIA NVENC through a shared-texture D3D11 compatibility transport.\n'
              'No additional codec pack or CUDA Toolkit installation is needed for encoding.\n'
              'AV1 requires supported NVIDIA hardware; AMD/Intel AV1 encoding is not implemented.\n'
              'Known issue: one simultaneous HEVC HDR recording/replay test hit GPU device removal.\n'
              'Separate HDR recording/replay tests passed; the simultaneous failure is unresolved.\n'
              'Dependency links and locations: docs/VIDEO_CODECS_2026-11-14.md\n')
    result=json.loads((pack.REPORT / 'FINAL.json').read_text())
    result.update(codecAcceptance=str(codec_report),exeSha256=receipt['exeSha256'],
                  knownLimitations=receipt['knownLimitations'],standalone=True)
    pack.write(pack.REPORT / 'FINAL.json',result)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
