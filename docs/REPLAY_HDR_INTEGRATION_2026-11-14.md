# Selective recording/replay and HDR integration — 2026-11-14

Applied locally on `main`, based on `8332c8a8`, without a full upstream merge:

- `6061d901`: instant replay buffer, parallel recording/replay capture, F9 save
  shortcut, microphone selection and optional separate microphone track.
- `e0aab788`: recording/replay fixes and regression tests only. Excluded the
  release version bump, packaging, unrelated frame-generation test and release
  documentation.
- `3fba266621a46f6d3d31dbd69c694c56bbbbda8e`: replay toggle beside recording,
  replay save control, HDR brightness/metadata controls collapsed initially,
  and the Expand translation. Excluded release packaging and upstream reports.

The workspace already contained uncommitted ANR code when this task started.
That work is preserved. No upstream ANR implementation, frame-generation
scheduling changes, GPU-priority changes or release version changes were imported.
No commit, push or publication was performed.

## Verification

Built `veyra_qml_ui`, `veyra_replay_buffer_tests`,
`veyra_game_passthrough_tests`, `veyra_hdr_tuning_tests`,
`veyra_qml_quick_tests`, and `veyra_ui_i18n_tests`, using the existing
E: build and dependencies, concurrency 2 and the existing build label.

- Replay buffer: 37 passed, 0 failed, including capacity limits, GOP boundaries,
  audio arrival while video pauses, clip selection and audio fanout.
- HDR tuning and translation tests: passed.
- Game hotkey state tests: passed, including replay binding and repeat handling.
- Qt Quick: 175 tests, 0 failures, 0 errors, 1 skipped raster check.
- Actual application with a private profile and synthetic SDR video: replay
  toggle updates the bridge, HDR expands/collapses while retaining settings,
  simultaneous recording and replay save succeed, replay remains active after
  save, and both MP4 outputs independently decode with changing image content:
  recording 118 frames, replay 212 frames, all distinct, 320×180 at 30 fps.

Two existing optional-backend QML bindings logged undefined-to-bool warnings in
`Ps5SourceDialog.qml` and `XboxSourceDialog.qml`. Those files were not changed;
this local build does not enable the corresponding remote-play backends.

The first application attempt could not start because the acceptance harness
referenced an unavailable runtime path (Windows exit `0xC0000135`). Corrected
the read-only runtime search path to `E:/Veyra` and repeated only that check;
the failed attempt is retained in the results. Build-copy `Main.qml` is restored
in `finally`; source QML and existing application packages are not instrumented.

Run `python -X utf8 -B scripts/acceptance/test-replay-hdr.py` after the build.
`--ui-only` repeats only the actual application/decode checks. The harness uses
the existing local build at `E:/Veyra-dev/Veyra/anr-artifacts/build/apex-anr-20261112`,
whose name predates this integration. Reports, clips and private profile are in
`E:/项目/Veyra/reports/replay-hdr-20261114`.

Microphone hardware/privacy failures, separate microphone-track output, actual
capture-card recording, optical HDR display output and long-duration replay
memory use were not validated by this run. Existing unit checks cover HDR tuning;
the linked upstream commit changes HDR interface visibility, not HDR processing.

## Slinky build portable delivery

The user requested a ZIP containing “Slinky build” in its name. Packaging uses
the tested executable above and hash-verified payloads from the existing local
ANR B15 archive, with the current QML, translations and all nested built shaders.
Qt's deployed QML modules are retained alongside the application's own module.
The internal EXE version remains `2.1.5-anr-beta2`; the delivery name identifies
this custom build without replacing or relabeling an official release.

Output: `E:/项目/Veyra/releases/slinky-build-20261114/`:

- `Veyra-2.1.5-Slinky build-win64-portable.zip`
- `Veyra-2.1.5-Slinky build-source.zip`
- SHA256 sidecars and the extracted portable application.

Extract the entire portable ZIP and run `Start Veyra - Slinky build.cmd`.
It uses `user-data-slinky` beside that copy, leaving other profiles untouched.
The package script verifies every archived payload and performs a minimal-PATH
startup with a private profile; authoritative outcome and digests are in
`E:/项目/Veyra/reports/slinky-build-20261114/FINAL.json`.
The first portable check caught missing deployed Qt QML modules; its failure log
is retained and the package was rebuilt with those modules before delivery.
