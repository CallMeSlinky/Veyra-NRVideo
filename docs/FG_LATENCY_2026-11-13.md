# Frame-generation software latency comparison — 2026-11-13

For the user's clarified setup, the test input is **2560×1440 at 60 samples/s,
with every image repeated twice**. Automatic duplicate removal recovers 30 unique
frames/s; each frame-generation backend uses 2X for nominal 60 fps output.
NR, SR, antialiasing and other optional processing are off. This is a synthetic
grayscale moving-bar fixture, not a representative gameplay quality test.

The local RTX 4090 runs the actual current Veyra enhancement graph and live
scheduler, using the existing paced-file-as-card diagnostic mode. No capture
device is opened. The input is paced with the existing 800 ppm simulated card
clock drift, without injected timing jitter. Exact duplicate removal is confirmed
by production `content-dedup` logs: 60 observed, 30 kept, 30 repeated per second,
with the full image compared and zero difference on repeated frames.

## Results

These numbers measure **software arrival of a real input frame to return from
its application presentation call**, excluding controller/game latency, HDMI/USB
transport, capture-card buffering and actual display scanout/pixel response.

The statistic is the median of sampled rolling one-second mean latencies within
each run, after excluding the first two measurement seconds. Two 12-second
measurement runs were performed per setting, in forward/reverse backend order,
following warmup past 90 processed unique frames. These are not pooled
frame-level medians or pooled P95s.

| Backend / quality | Run 1 software delay | Run 2 software delay |
|---|---:|---:|
| No generation, 30 unique fps | 6.27 ms | 7.25 ms |
| VFG Medium, 2X | 25.93 ms | 25.95 ms |
| VFG Low, 2X | 27.24 ms | 30.24 ms |
| DLSS FG, 2X | 29.58 ms | 32.14 ms |
| VFG High, 2X | 31.93 ms | 31.94 ms |
| ANR V.B15, 2X | 33.78 ms | 36.52 ms |
| XeSS FG, 2X | 3.16 ms handoff only | 3.23 ms handoff only |

**XeSS cannot be ranked by this table.** Its provider owns the swapchain and
queues output internally; return from the application's presentation call is an
earlier boundary than the DXGI backends' output submission. Its ~3.2 ms value
does not include unknown provider output delay. Existing source intentionally
does not report DXGI display-latency statistics for XeSS. Its SDK reported about
30 real + 30 generated submissions/s, which establishes submissions, not scanout
or controller-to-photon latency.

All 14 comparison runs passed. About 30 unique input frames/s were processed
and about 30 generated frames/s were submitted with FG enabled. The completed
comparison recorded zero pre-evaluation FG skips; one generated frame expired
during the second VFG Medium measurement. Other repeated samples were discarded
as intended, not treated as missing unique gameplay frames. VFG auto regulation
was disabled in the diagnostic so each requested Low/Medium/High model stayed
fixed; the product's default remains unchanged. SDK logs confirm requested VFG
quality IDs 0/1/2. Low's delay varied more between runs than Medium's; the label
alone does not establish the lowest complete software latency.

VFG High flagged budget limitation in one sampled snapshot in each pass, without
recorded FG skips or expired generated frames during either measurement.

Application-side GPU timestamps are not a fair standalone provider comparison:
ANR uses separate Vulkan work and XeSS runs internal work outside those spans.
Zero or small GPU stage measurements do not mean zero computation.

## Recommendation and limits

**For this measured software path, VFG Medium at 2X is the first setting to try
for smooth 30→60 output.** It had the lowest measured delay among the comparable
DXGI paths, about 19 ms above the no-generation baseline. This short synthetic
test does not establish that it beats XeSS's actual visible output or wins on
other GPUs, real game scenes or display configurations.

Duplicate removal avoids interpolating repeated pictures. It does not make the
game deliver fresh input responses at 60 fps. Interpolating between unique A and
B still requires B, which arrives about 33.36 ms after A in this test. Different
presentation strategies distribute that delay differently between generated
and real frames, so this interval must not simply be added again to the table.

The desktop was 2560×1440 at 240 Hz, with a windowed presenter, Automatic display
sync, VRR off, output cap off, and NVIDIA Low Latency On requested. XeSS retained
its own pacing ownership; native NVIDIA pacing was not layered on it. A 60 Hz
display's queuing/scanout and a real card's capture path can change visible delay.
No real Elgato 4K S, controller-input trigger, high-speed camera or photodiode
was available for this test. Therefore there is **no measured overall
input-to-photon winner across all four backends**.

For absolute minimum delay, HDMI passthrough to the display avoids the PC preview
and Veyra processing path. Elgato describes the 4K S's passthrough as zero latency;
its USB preview is a separate path:
<https://www.elgato.com/en-UK/p/game-capture-4k-s>.

## Reproduction and evidence

- Probe source: `tests/integration/FgLatencyProbe.cpp`.
- Build: `python -X utf8 -B scripts/acceptance/build-apex-anr.py veyra_fg_latency_probe`.
- Harness: `scripts/acceptance/compare-fg-latency.py`; `pilot` runs ANR first,
  no argument runs the two-pass comparison, and `summary` refreshes the report.
  Existing run directories are protected against overwrite.
- Evidence: `E:/项目/Veyra/reports/fg-latency-20261113/results.json`, plus each
  run's raw `samples.csv`, `console.log` and production `engine.log`.
- Fixture specification is in the harness. Its sparse file has approximately
  5.53 GB logical length; that is not its allocated physical size. It can be
  regenerated and is retired after verification.

All diagnostic output, TEMP and test data are on E:. The probe executable is
temporarily placed beside the verified B15 application to resolve the exact
same runtime dependencies, then removed in `finally`. Product files are verified
against the existing package manifest afterward. No user profile, installed
application executable, display mode, driver, runtime model or public release
is changed. The build only adds a diagnostic target; it does not change product
behavior.
