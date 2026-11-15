# Slinky 2.1.9 integration

Integrated the upstream v2.1.6 (`20955b5c`) to v2.1.9 (`d442b4e5`)
release delta into the existing custom working tree. The local Git HEAD is
still `8332c8a8`; this remains an uncommitted source integration, with no push
or public release. Upstream main may contain subsequent documentation changes;
this task specifically targets the v2.1.9 release tag.

The original 218 changed/untracked source and documentation files are backed
up with SHA256 identities under `E:/项目/Veyra/reports/slinky-219-20261115`.
Dependencies, editor settings, user profiles and existing portable deliveries
were not included in the backup or overwritten.

## Changes

Included the dusk theme/intro and optional startup audio implementation,
editable exclusion outlines, virtual desktop capture, G-SYNC profile controls,
capture audio/monitor separation, bounded provider statistics and XeSS resize
counter repair, AMD FRC, RX9000 FSR4 defaults/fallback, and associated tests,
assets and documentation. Release-note performance claims are upstream history,
not measurements on this PC.

Preserved the custom AV1/HEVC/H.264 recording, replay and export selectors,
NVENC compatibility transport, top-dock screenshot/record controls, wrapping
badges and dialog sizing, paused replay timeline and legacy ANR preset/session
compatibility. The local ANR inference adapter is retained; its directory
discovery now also supports the exact B18 full ZIP's nested provider layout.
No upstream AnrProvider implementation was introduced. Original FG dropdown
labels remain, with AMD FRC added and without quality rankings/crowns.

AMF SDK v1.5.3 public headers were fetched from the official MIT-licensed
GPUOpen-LibrariesAndSDKs/AMF repository at
`57ee0cfb0e1a08d9041f77435653794c1b012be0`, under
`E:/项目/Veyra/deps/amf-sdk-1.5.3-20261115/amf/public`.
The build uses this directory for `VEYRA_AMF_SDK_ROOT`. Runtime AMF comes from
the AMD graphics driver; this PC has no System32/amfrt64.dll, so real AMD FRC
playback cannot be validated here. No driver or runtime DLL was installed.
Startup music is optional; the upstream MP3 is not in Git and was not downloaded.

## Reproduction and validation

`scripts/acceptance/integrate-slinky-219.py` records the source backup, merge
candidates, explicit conflict resolutions and applied file hashes.
`build-apex-anr.py --label 2.1.9-Slinky-build` uses the existing E: build
and at most two jobs. `test-slinky-219.py` checks timing, replay, ANR migration,
FG settings, VRR policy, muted-monitor capture audio, optional music, Qt Quick
and decoded recording/replay/export codecs. `test-slinky-219-ui.py` adds actual
custom-control/version/dropdown and pause/resume replay checks. Each process is
bounded and uses a task-specific profile, TEMP and logs.

Detailed current results and any failures are retained in the task report
directory. The final validation status is recorded in FINAL.json; earlier
2.1.6 acceptance is not substituted for this task's results.

Passed: application and regression builds, 53 replay checks, 48 ANR
settings/migration checks, 683 FG settings checks, 62 VRR policy assertions
(no driver writes), timing, muted-monitor audio, optional-music absence,
translation extraction with zero missing translations/placeholder errors,
and Qt Quick 209 tests/0 failures/0 errors/1 skip. Full codec acceptance
independently decodes 18 SDR/HDR recording/replay/export/queued/Matroska
files, including three-codec persistence across restart and unsupported
Media Foundation AV1 rejection. HDR uses separate recording/replay checks.

An initial build invocation used the wrong Qt Quick target name and stopped
before compilation. The corrected target and subsequent builds passed;
the original failure remains in the build log. One translation-check invocation
hit the console's cp1252 encoding; rerunning with Python UTF-8 mode passed.

## Delivery and boundaries

`stage-slinky-219.py` creates one separate portable folder under
`E:/项目/Veyra/releases/slinky-219-20261115`, using the SHA-verified existing
ANR B16 portable ZIP as its runtime donor, excluding all `runtime/anr` payloads.
It replaces the application, UI,
translations, assets and matching built shaders, verifies the donor payloads
and checks isolated startup with a minimal PATH. All launchers use this copy's
new `user-data-slinky-2.1.9` profile; existing profiles remain untouched.
There is exactly one launcher: `Start Veyra - Slinky build.cmd`.

This delivery contains no ANR binaries, models, program packs or configuration.
The ANR B16/B18 archives and test installations remain in private test/download
directories outside the portable folder. Physical capture hardware, AMD/Intel hardware,
physical HDR display output, optical latency and long-duration stability
are untested. The prior simultaneous HEVC HDR recording/replay device-removal
failure remains unresolved; regression checks exercise those HDR paths
separately. Optional PS5/Moonlight/Xbox and libass retain their existing build
configuration. No public upload or GitHub release is performed.

Actual UI validation passed the custom 2.1.9 version, both capture buttons,
local FG labels and added AMD FRC choice. Pausing longer than the replay
buffer, saving while paused, resuming and saving after stop passed, with five
outputs independently decoded and no paused-time gap. ANR B16 GPU checks
passed 133/0; SDR/HDR exclusion masks with ANR and SDR masks with DLSS passed.

The portable entry point is
`E:/项目/Veyra/releases/slinky-219-20261115/Veyra-2.1.9-Slinky-build-win64-portable/Start Veyra - Slinky build.cmd`.
Packaging/startup identities are in STAGE.json; final status is in FINAL.json.

## Optional user-installed ANR B18

1. Close Veyra. Download the author's exact
   [anr-fg-V.B18-full.zip](https://github.com/apex-compute/ANR/releases/download/FG-V.B18/anr-fg-V.B18-full.zip).
2. Create `runtime/anr` beside `veyra_qml_ui.exe` and extract the ZIP **contents**
   into it, preserving the archive's directories.
3. The DLL should be at
   `runtime/anr/game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/nvngx_dlssg.dll`.
   Keep the complete model/program directories together. Existing flat provider
   installations directly under `runtime/anr` remain supported and take precedence.
4. Restart Veyra and select `Apex ANR · Beta`. No installer is needed; do not
   run the archive's install.cmd or copy game/dxgi.dll beside Veyra.

The exact full ZIP includes OptiScaler files as well as ANR. Veyra loads only
the ANR DLL from the detected provider directory and never loads that proxy or
runs the installers. Archive SHA256:
`ed70eef1dc92ba71685daad59f1d9ef1d9897b46df009f04b1dc51c4933cd300`.
Provider SHA256 matches the author's metadata:
`be9a9c4f21c89cbae993f1c2f5df0685e3f530bf9f2e565e22958dd062c9c12c`.

The untouched extracted layout passed 7 layout assertions, 133 B18 GPU
checks, and SDR/HDR ANR exclusion composition checks on this NVIDIA PC.
Evidence: `reports/slinky-219-20261115/b18`. The codec/UI regressions above
precede this loader-only change; ANR GPU/layout checks cover the rebuilt EXE.
No AMD/Intel B18 hardware claim is made. The first portable startup exited 0,
but its manifest check detected missing duplicate launcher files. That failed
verification is retained; the revised delivery uses only the single requested
launcher and excludes ANR payloads.
