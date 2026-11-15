# Veyra 2.1.6 — Slinky build

This supersedes the earlier 2.1.5 Slinky package, which imported only replay/HDR.
The user requested all 2.1.6 application changes while retaining the existing
local ANR implementation and original frame-generation dropdown labels.

## Included and excluded

Integrated upstream `20955b5c` (verified 2.1.6 publication), with application
version `2.1.6.0` and display label `2.1.6-Slinky-build`. Included the full release
changes: automatic/60→30 duplicate-removal controls and migration, cadence and
live-scheduler fixes, NVIDIA low latency Off/On and legacy Boost migration,
Reflex recovery, asynchronous logging, effect-exclusion masks and independent
NR nodes, refined optical flow, High GPU-priority/VFG regulation defaults,
replay/microphone recording, HDR folding, PSN account-lookup changes and the
remaining interface/persistence changes. See the upstream release notes for
historical measurements; those are not claimed as this machine's measurements.

Excluded upstream `AnrProvider.h/.cpp`, its changes to `DlssFgBackend`, and its
graph/provider integration. The pre-existing local `AnrFgBackend.h/.cpp` remains
byte-for-byte unchanged, with B15 runtimes retained from the verified local
donor. Shared 2.1.6 graph effects still run through the local backend. The
original backend dropdown list is retained: no quality-ranking strings, crown,
gold VFG flag or red ANR flag. Local TopDock capture controls are also preserved.

The old local ANR build used preset v37/library v21/session v16 before mainline
used those versions for effect masks. Readers first try current 2.1.6 data,
then accept the old layout only when the recovered data actually contains ANR.
Old `.anr` session sidecars remain readable; upgraded saves use the new sidecar,
preserving the old file. Frozen original fixtures cover this compatibility.

All local edits were backed up before integration, without copying dependencies
or the whole repository. Source remains an uncommitted working-tree integration;
no push, public upload, user profile modification or device configuration change.

## Build and validation

The existing E: build compiled the application and 13 related test targets with
two build jobs. The executable reports `2.1.6-Slinky-build` and PE product
version `2.1.6.0`.

Validation uses fresh task profiles and per-attempt TEMP directories. Raw results
and retained failures are under `E:/项目/Veyra/reports/slinky-216-20261114`.
The integration map, original edits, regression logs and package receipt are
kept there. `scripts/acceptance/test-slinky-216.py` runs timing/dedup, logging,
preset-library, effect-chain, preset round-trip, VFG settings and ANR migration
checks, followed by Qt Quick, translations, HDR and actual replay/recording UI
acceptance. The UI acceptance explicitly checks version, original FG labels,
duplicate-removal controls, low-latency choices and legacy value migration.

Passed: timing/dedup, asynchronous logger, preset-library, effect-chain and
preset round-trip tests; VFG settings 683/0; ANR settings/migration 48/0; replay
buffer 37/0; HDR and translation checks; game-hotkey state; Qt Quick 199 tests,
0 failures, 0 errors, 1 skip. Actual UI controls and simultaneous recording /
replay save passed; both MP4 outputs decoded independently with changing frames.
Final GPU verification also passed: 133 local ANR pixel checks and SDR/HDR mask
composition with the local ANR backend, plus no-FG and DLSS mask cases. All
packaged payload hashes remained unchanged after those checks. The portable ZIP
contains 88 nested built shaders and 1,693 verified payload files; minimal-PATH
startup passed. The completed receipt is `reports/slinky-216-20261114/FINAL.json`
under the E: artifact root.

The preset regression's invalid-backend test used enum value 5, which is now
valid ANR; it now checks the value after the last supported backend. An attempted
cadence-expectation change was reverted after diagnosis confirmed that the
legacy storage codec retains raw IDs and the UI/application path migrates them.
The first HDR test retry reused old test data; per-attempt TEMP isolation fixes
the harness. These failures remain recorded rather than erased.

## Portable delivery

`scripts/acceptance/package-slinky-build.py` verifies the immutable local B15
donor, includes all nested built shaders and Qt QML modules, updates the EXE/UI,
and creates the portable/source ZIPs with SHA256 sidecars. Every ZIP payload is
checked against its manifest, followed by a minimal-PATH startup.

Output: `E:/项目/Veyra/releases/slinky-build-2.1.6-20261114/`.
Extract `Veyra-2.1.6-Slinky build-win64-portable.zip` completely and launch
`Start Veyra - Slinky build.cmd`. Its separate profile is
`user-data-slinky-2.1.6`. The earlier 2.1.5 archive remains a previous delivery.

This is a private local build, not an official release. Optional PS5/Moonlight/
Xbox streaming and libass are not enabled by this machine's existing dependency
configuration. Source changes for those features are integrated, but their
runtime functionality cannot be claimed for this binary. Actual capture-card
latency, microphone hardware, physical HDR display output, long-run stability
and AMD/Intel hardware are not validated here.
