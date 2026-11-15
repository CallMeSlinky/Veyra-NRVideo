# AV1 and H.265 / HEVC recording, replay and export

H.265 / HEVC was already implemented. This change retains that implementation,
labels it explicitly as H.265 / HEVC, and adds AV1 to the three-codec selectors
in Settings -> Playback -> Recording and Export -> Video encoding.
Instant replay follows the recording codec. Existing `recordHevc` preferences
and boolean C++ entry points remain supported. New recording preferences use
`recordCodec`: 0 H.264, 1 HEVC, 2 AV1. Export batches freeze the codec and carry
it through queueing, the version-16 worker protocol, and recovery restarts.

AV1 uses sequence-header OBUs, periodic keyframes and FFmpeg MP4/Matroska muxing.
On this RTX 4090/driver, native D3D12 NVENC initialized but failed to retrieve its
first AV1 packet (`NV_ENC_ERR_INVALID_PARAM`). The delivered AV1 path therefore
uses a native D3D11 NVENC compatibility transport on the same adapter. A bounded
D3D12 copy ring feeds shared NV12/P010 textures; shared GPU fences order the copy
and encoder without pixel readback or a CPU wait for the copy. Registered
completion events bound the encoder worker's output wait. Both recording and
export share this transport. It costs an additional GPU copy and shared texture
per input slot; no performance improvement is claimed. H.264/HEVC retain the
native D3D12 transport. HEVC continues to use its
existing codec configuration. SDR uses 8-bit NV12; HDR uses 10-bit P010 with
BT.2020/PQ signalling. An explicit AV1 selection stays AV1 in HDR and at large
dimensions; legacy H.264 recording requests still promote to HEVC for HDR or
dimensions above 4096. Neither codec changes enhancement or FG algorithms.

AV1 support is checked against the opened NVENC device's codec GUID list, and
10-bit support is checked before initialization. An unsupported request fails
explicitly. AV1 encoding on AMD/Intel is not implemented by this change; their
existing Media Foundation H.264/HEVC paths remain available. No silent switch
from AV1 to H.264 is allowed. AV1 decode support is independent of encode support.

## Dependencies for running

No additional codec pack, CUDA Toolkit, x265, libaom or SVT-AV1 installation is
needed by this hardware encoding path.

| Dependency | Source | Where it belongs |
|---|---|---|
| NVIDIA display driver supporting NVENC API 13.0 (570 or newer per the pinned headers) | [Official driver download](https://www.nvidia.com/en-us/drivers/) | Install with NVIDIA's installer. The encoder is loaded from `%WINDIR%\System32\nvEncodeAPI64.dll`; do not copy a downloaded DLL into the app. |
| GPU with the requested hardware encoder | [NVIDIA support matrix](https://developer.nvidia.com/video-encode-decode-support-matrix) | Hardware requirement. GeForce RTX 40/50 series support AV1 encoding; check the exact GPU in the matrix. HEVC has wider support. |
| Veyra's matching patched FFmpeg runtime | Existing Veyra portable package; [upstream FFmpeg](https://ffmpeg.org/download.html) for reference | Existing matching `avcodec-63.dll`, `avformat-63.dll`, `avutil-61.dll`, `swresample-7.dll` and other deployed runtime dependencies beside `veyra_qml_ui.exe`. Keep the package's complete matching set. |

The existing local dependencies already provide the headers and FFmpeg libraries
needed for this implementation. No dependency download or driver change was made.
Microsoft Store HEVC/AV1 playback extensions are not required for Veyra's NVENC
encoding or bundled FFmpeg decoding. External players/editors have their own
codec support requirements.

## Dependencies for rebuilding this checkout

| Dependency | Link / version | Location and CMake setting |
|---|---|---|
| NVENC headers | [nv-codec-headers n13.0.19.0](https://github.com/FFmpeg/nv-codec-headers/releases/tag/n13.0.19.0) | Current checkout: `deps/nvidia/nv-codec-headers-13.0.19.0/include/ffnvcodec/nvEncodeAPI.h`. Set `VEYRA_NVENC_HEADERS_ROOT` to the directory containing `include`. |
| Existing patched FFmpeg development prefix | Project's preserved patched 9.0.1 source/build, not an unpatched replacement | This host: `E:/Veyra-dev/Veyra/deps/ffmpeg-9.0.1-veyra`; set `VEYRA_FFMPEG_ROOT` to that prefix (`include`, `lib`, `bin`). |
| Existing compiler and Qt | MSVC 2022 C++20 and Qt 6.8.3, as already configured | Reuse the existing build cache and Qt prefix. AV1 adds no Qt dependency. |

If staging headers on a new machine, use
`E:/项目/Veyra/deps/nvidia/nv-codec-headers-13.0.19.0`, with
`include/ffnvcodec/nvEncodeAPI.h` directly under it, and point
`VEYRA_NVENC_HEADERS_ROOT` there. The build already pins the 13.0 ABI; do not
replace the headers with another SDK major version independently of the code.
Direct3D 11/12 and DXGI are Windows components; the bridge adds no redistributable.
The full NVIDIA Video Codec SDK is optional for reference/samples, not needed
in addition to these headers.

## Verification and artifacts

Reproducible entry point: `scripts/acceptance/verify-video-codecs.py` (build),
then `--check` (isolated synthetic fixtures, profiles and logs). Build concurrency
is two, build timeout 900 seconds; each acceptance child has a 180-second limit.
The build and tests use the existing E: artifact root. The source checkout and
the running user's portable application are not deployment targets.

Build: `E:/Veyra-dev/Veyra/anr-artifacts/build/apex-anr-20261112`.
Evidence: `E:/项目/Veyra/reports/video-codecs-20261114`.
Actual results, decoded codec/bit depth/colour metadata/keyframe counts and
limitations are recorded in that task's `FINAL.json`; failed attempts remain.

One simultaneous HEVC HDR recording/replay fixture encountered device removal
`0x887A0006` and process exit `0xC0000005` in attempt `20261114-204228`. An earlier
concurrent HDR run passed. The final HDR harness records and buffers replay
separately; this does not establish that the concurrent failure is fixed. SDR
recording/replay concurrency is covered for all three codecs. Physical HDR
display output, capture cards, long-duration stability and AMD/Intel hardware
are outside these synthetic checks.

Local update ZIP: `E:/项目/Veyra/releases/video-codecs-20261114/`.
`Veyra-2.1.6-Slinky-AV1-HEVC-update.zip` is an overlay for the complete existing
2.1.6 Slinky portable package, not a standalone distribution. Extract a fresh
copy of that package into a new folder, then extract this update beside its
EXE. Run `Start Veyra - AV1 HEVC test.cmd` for a separate
`runtime_local/user-data-av1-hevc-test` profile. The update includes the rebuilt
EXE, UI, i18n and all matching built shaders, but no model/driver/runtime DLLs
and no user settings. Every ZIP payload is checked against a SHA256 manifest.

References: [NVENC 13.0 programming guide](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-video-encoder-api-prog-guide/index.html),
[FFmpeg NVENC implementation](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/nvenc.c),
[Microsoft D3D11/D3D12 fence interop](https://learn.microsoft.com/en-us/windows/win32/direct3d11/direct3d-11-4-features),
[upstream report of the same first-packet failure](https://github.com/NortheBridge/luminalshine/releases/tag/26.11.1).
The bridge is original project code using Windows/NVENC APIs; no upstream
implementation was copied and no SDK/driver binaries were changed.
No commit, push, public upload, driver update or replacement of the running app.
