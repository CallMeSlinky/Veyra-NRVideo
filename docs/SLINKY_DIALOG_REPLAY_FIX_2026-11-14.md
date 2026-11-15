# Slinky 2.1.6 dialog and replay pause fixes

The mode-switch confirmation's long translated message used a single-line
badge. `VTag.wrapText` now optionally wraps text within its assigned width and
grows vertically. Only the mode-switch cards opt in, and both cards share the
row height. No message was truncated or removed. Actual English dialog bounds
and screenshots passed at 100% and 150% DPI.

Instant replay now follows the source's playback state. A shared replay-only
timeline freezes outside playback and omits paused wall time on resume. Video,
audio/microphone stamps, segment end and replay-save requests use that mapping.
Paused redraws and audio callbacks do not enter replay, and audio encoding is
bounded by available video rather than continuing to fill silence while video
is stationary. Idle/source-end and still-image states leave replay suspended.
Ordinary recording retains its independent wall-clock behavior.

Verified in the rebuilt application with a fresh profile and synthetic moving
video, with replay audio enabled:

- Replay buffer/timeline tests: 47 passed, 0 failed.
- A 20-second pause, longer than the selected 15-second buffer, did not change
  replay frame count, buffered duration or memory after pending work drained.
- Saves before pause, while paused, after resume and after source stop all
  independently decoded with moving video. No video timestamp gap exceeded
  300 ms, and the paused wall-clock interval did not extend clip duration.
- Turning replay off/on while already paused captured no video or audio.
- Ordinary recording alongside replay also produced a playable video.
- The translated mode-switch dialog fits its cards at both tested DPI scales.

Evidence: `reports/slinky-replay-pause-20261114` and
`reports/slinky-dialog-fix-20261114` under the E: artifact root.
Real microphone hardware, capture-card input and arbitrary source formats were
not tested by this synthetic regression. Prior 2.1.6 ANR/pipeline acceptance
remains historical; these changes do not modify ANR or FG dropdown labels.

Output name: `Veyra-2.1.6-Slinky-build-win64-portable` (hyphenated as requested).
The ZIP and matching source ZIP are under
`E:/项目/Veyra/releases/slinky-build-2.1.6-dialog-fix-20261114`.
Extract the full ZIP and run `Start Veyra - Slinky build.cmd`.
