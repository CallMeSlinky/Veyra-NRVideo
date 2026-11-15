# Complete Slinky 2.1.6 portable with AV1 / HEVC

User requested a full ZIP named `Veyra-2.1.6-Slinky-build-win64-portable.zip`.

Delivery: `E:/项目/Veyra/releases/slinky-av1-hevc-full-20261114/`.
Extract the whole portable ZIP into a new folder and run
`Start Veyra - Slinky build.cmd`. The complete runtime, Qt modules, models,
licenses, UI and matching shaders are included. No overlay installation is
required. Settings use `user-data-slinky-2.1.6` beside this extracted copy.

- Portable ZIP: 724,362,370 bytes.
- SHA256: `65c3fd2b2131600ff1e4038b277434ab7ba0c637d43afc6812b707167a7f64e7`.
- Matching source ZIP and SHA256 sidecars are in the same delivery directory.
- Rebuilt EXE matches the full codec acceptance receipt:
  `a5df72e1d5b21c8637f4a6288ef3067a507c9c090ffd9e81c6e18fbf8cc3830f`.

The packager verifies the immutable prior Slinky donor ZIP and its runtime
payloads, overlays the accepted EXE/UI/i18n/all built shaders, and verifies all
1,695 packaged payloads by SHA256 plus ZIP CRC. Startup from the assembled
portable passed with PATH restricted to the app and Windows system folders,
using a private data directory and task-specific TEMP/logs. Product codec GPU
tests were not repeated during packaging; this executable is the exact one
accepted by `reports/video-codecs-20261114/FINAL.json`.

Reproducible packaging entry point:
`python -B scripts/acceptance/package-slinky-codecs-full.py`.
Packaging receipt: `E:/项目/Veyra/reports/slinky-av1-hevc-full-20261114/FINAL.json`.

AV1 requires supported NVIDIA hardware. H.264/HEVC retain their existing
Media Foundation path on AMD/Intel. The known simultaneous HEVC HDR
recording/replay device-removal failure remains unresolved; separate HDR and
all three SDR codec paths passed the codec acceptance. Physical HDR displays,
capture cards and long-duration stability were not validated here.

Existing ANR B15 assets are preserved from the user's private Slinky donor;
this is a local personal package, not a public release. Existing packages,
application directories, profiles and dependencies were not replaced. No
commit, push, public upload, driver change or new dependency download.
