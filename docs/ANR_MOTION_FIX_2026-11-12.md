# ANR beta2: video motion input correction

The user reported that ANR 2X/3X looked like the original GTA VI video while
NVIDIA VFG looked smoother. Their log confirmed ANR was creating, submitting
and presenting frames without provider errors. Those counters did not prove
correct temporal interpolation.

The initial adapter incorrectly passed the NGX-core DLSS consumer's reversed,
normalized motion scales to the **direct ANR provider**. Veyra's shared flow
texture is already current→previous in working-resolution pixels. ANR needs
that texture with scale **+1, +1**. The correction is confined to
`AnrFgBackend::evaluate`; DLSS, VFG, shared flow computation, presentation,
configuration defaults and runtime binaries are unchanged.

`VEYRA_TEST_ANR_LEGACY_MOTION_SCALE=1` restores the old conversion in a test
child process for reproducible before/after comparisons. Product launchers do
not set it. All tests use task-specific outputs and private settings; the
user's running application and source MP4 are untouched.

## Regression evidence

The original GPU test only checked nonblack/distinct pixels. It could pass
incorrect temporal motion. The revised test also measures the centroid of an
object moving exactly eight pixels per input frame. At 2X, for example, the
expected intermediate location is x=487.5: the old conversion gave about
x=489.0, whereas pixel-scale ANR gave x=487.4932. Other phases match their
expected positions within the 0.3-pixel assertion tolerance.

ANR's native bridge schedules work at command submission. Diagnostic input
upload, evaluation and readback are therefore separate submissions; reading
the generated texture inside its evaluation list observed the previous
output. These CPU waits/readbacks exist only in the test. The product already
submits color production before generation and consumes generated textures
in subsequent submissions; no new production wait was introduced.

The revised GPU suite covers SDR/HDR and 2X/3X/4X/6X, and explicitly runs against
both legacy and corrected adapters. Results are in
`reports/anr-quality-20261112/motion-regression.json` with per-frame positions
in the corresponding logs.

## The user's GTA VI clip

Input: `C:/Users/Jack/Downloads/GTAVI_An_Extended_Look.mp4` (14,115,273,308 bytes).
The source was opened read-only, not copied or modified. Thirty 4K frames
starting at 850 seconds were exported with legacy ANR 2X/3X, corrected ANR
2X/3X and VFG 2X. Independent decoding confirmed 60/90-frame outputs, with
source-frame alignment checked separately. See `comparison.json`.

For a temporal quality check, the 30-frame reference was converted to a
960×540 grayscale diagnostic fixture with alternate frames omitted, at
15 fps. Each provider reconstructed the missing frames at 2X. Fourteen
generated positions were compared against the real withheld source frames;
the startup/final hold was excluded. Mean absolute grayscale error (0–255):

| Method | Error against actual withheld frames |
|---|---:|
| Repeat previous source frame | 17.9348 |
| Simple linear blend | 14.8451 |
| Initial ANR adapter | 14.6153 |
| Corrected ANR adapter | 9.7167 |
| NVIDIA VFG | 7.3752 |

The corrected adapter reduces error by approximately **33.5%** relative to the
initial ANR adapter in this sample. VFG still performs better in this test.
This is one short grayscale sample, not a general quality ranking, a claim
of native game motion/depth, or proof that ANR matches VFG on every scene.
Actual 30→60/90 fps 4K exports are retained separately from this diagnostic.

## Delivery

Separate **2.1.5-anr-beta2** portable and corresponding application source
archives are under `E:/项目/Veyra/releases/apex-anr-motion-fix-20261112`.
The original beta archive is preserved. The user-installed running copy at
`E:/Veyra-2.1.5-ANR-beta-win64-portable` is not overwritten or stopped.

Build and test entry points:

```powershell
python -X utf8 -B scripts/acceptance/build-apex-anr.py veyra_qml_ui veyra_anr_gpu_tests veyra_vfg_export_probe veyra_anr_quality_probe
python -X utf8 -B scripts/acceptance/test-apex-anr-quality.py
python -X utf8 -B scripts/acceptance/test-apex-anr-quality.py holdout
python -X utf8 -B scripts/acceptance/test-apex-anr-motion-regression.py
python -X utf8 -B scripts/acceptance/test-apex-anr.py
```

The frame generation dropdown and aligned screenshot/record dock icons remain.
ANR still uses estimated optical flow and proxy depth; choose **Optical flow**
for video interpolation. The original dependency/build exclusions and ANR
runtime redistribution boundary in `APEX_ANR_2026-11-12.md` still apply.
No public release, upload, driver change or user-settings modification is made.
