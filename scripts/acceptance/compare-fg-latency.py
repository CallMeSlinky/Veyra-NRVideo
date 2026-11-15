"""Compare software delay for duplicate 1440p60 input (30 unique fps -> 60)."""
from pathlib import Path
import csv
import ctypes
import hashlib
import json
import msvcrt
import os
import shutil
import statistics
import subprocess
import sys

ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
TASK = 'fg-latency-20261113'
TEST = ART / 'tests' / TASK
REPORT = ART / 'reports' / TASK
APP = ART / 'releases/anr-b15-20261113/Veyra-2.1.5-ANR-B15-win64-portable'
BUILD = ART / 'build/apex-anr-20261112'
FIXTURE = TEST / '1440p60-30unique.y4m'


def fixture():
    TEST.mkdir(parents=True, exist_ok=True)
    if FIXTURE.exists():
        return
    # Sparse monochrome fixture: exact duplicate pairs without gigabytes of
    # redundant physical storage. Decoding reads ordinary full-size frames.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    with FIXTURE.open('w+b') as f:
        returned = ctypes.c_uint32()
        if not kernel.DeviceIoControl(msvcrt.get_osfhandle(f.fileno()), 0x900C4,
                None, 0, None, 0, ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
        f.write(b'YUV4MPEG2 W2560 H1440 F60:1 Ip A1:1 Cmono\n')
        for i in range(60 * 25):
            f.write(b'FRAME\n')
            start = f.tell()
            x = 200 + ((i // 2) * 8) % 1800
            for y in range(500, 700):
                f.seek(start + y * 2560 + x)
                f.write(bytes([200]) * 120)
            f.seek(start + 2560 * 1440)
        f.truncate()
    print('Created sparse 1440p60 fixture, 30 unique fps', flush=True)


def run(label, backend, quality):
    output = REPORT / label
    if output.exists():
        raise FileExistsError('Preserve earlier evidence: ' + str(output))
    output.mkdir(parents=True)
    temp = ART / 'tmp' / TASK
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temp), TMP=str(temp), PATH=str(APP) + ';' + env.get('PATH', ''))
    for key in ('VEYRA_TEST_ANR_LEGACY_MOTION_SCALE', 'VEYRA_TEST_VIDEO_WORK_MS',
                'VEYRA_TEST_FIXED_CAPACITY_WAIT', 'VEYRA_TEST_VFG_NO_AUTO_REGULATE'):
        env.pop(key, None)
    with (output / 'console.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([str(APP / 'veyra_fg_latency_probe.exe'), str(FIXTURE),
            str(output), backend, str(quality), '12'], cwd=APP, env=env,
            stdout=log, stderr=subprocess.STDOUT, timeout=100)
    console = (output / 'console.log').read_text('utf-8', errors='replace')
    print(label, 'exit', result.returncode, console[-500:], flush=True)
    if result.returncode:
        raise RuntimeError('Probe failed; see ' + str(output))


def summarize():
    results = []
    for output in sorted(REPORT.iterdir()):
        if not output.is_dir() or not (output / 'samples.csv').exists():
            continue
        rows = list(csv.DictReader((output / 'samples.csv').open()))
        values = {}
        for key in ('softwareMean', 'softwareP95', 'enhancementMean', 'fgGpuMean',
                    'flowGpuMean', 'pairInterval', 'generatedFromA', 'generatedFromB', 'ageP95', 'submitFps'):
            valid = [float(r[key]) for r in rows if float(r[key]) >= 0 and float(r['wall']) >= 2]
            values[key] = dict(median=statistics.median(valid), min=min(valid), max=max(valid)) if valid else None
        first, last = rows[0], rows[-1]
        elapsed = float(last['wall']) - float(first['wall'])
        deltas = {key: int(last[key]) - int(first[key]) for key in (
            'frames', 'generated', 'realPresented', 'generatedPresented', 'xessPresented', 'xessGenerated',
            'fgSkipped', 'fgExpired', 'sourceSkipped')}
        results.append(dict(run=output.name, sampledWindowStatistics=values, deltas=deltas,
            seconds=elapsed, contentFps=int(last['contentFps']), limitedSamples=sum(int(r['limited']) for r in rows),
            providerOwned=int(last['providerOwned'])))
    report = dict(scope='Software only: paced file replay, not measured capture-card/input-to-photon latency. '
        'Medians summarize overlapping rolling 1-second windows, not pooled frame percentiles. '
        '1440p60 exact duplicate pairs, auto dedup, 30 unique fps, FG 2X. NR/SR off. '
        'NVIDIA low latency On; automatic display sync; VFG auto regulation disabled to hold each model fixed.',
        gpu='NVIDIA RTX 4090', display='2560x1440 at 240 Hz; automatic sync, windowed output',
        fixture='Sparse grayscale moving bar, 60 exact samples/sec in duplicate pairs; synthetic workload',
        xessCaveat='XeSS owns its swapchain and submits asynchronously. Its softwareMean measures '
            'the application-to-provider handoff, excluding unknown provider output delay; do not rank '
            'it against DXGI backends or call it input latency.',
        gpuTimingCaveat='Application-side GPU timestamps do not cover all provider-internal '
            'or Vulkan work. Do not compare fgGpuMean alone across providers.',
        results=results)
    identities = {}
    for p in [BUILD / 'veyra_fg_latency_probe.exe', APP / 'veyra_qml_ui.exe',
              APP / 'runtime/anr/nvngx_dlssg.dll']:
        with p.open('rb') as f:
            identities[str(p)] = hashlib.file_digest(f, 'sha256').hexdigest()
    report['identities'] = identities
    groups = {}
    for r in results:
        if not r['run'].startswith(('r1-', 'r2-')):
            continue
        key = r['run'][3:]
        groups.setdefault(key, []).append(r)
    report['comparison'] = {}
    for key, entries in groups.items():
        means = [r['sampledWindowStatistics']['softwareMean']['median'] for r in entries]
        tails = [r['sampledWindowStatistics']['softwareP95']['median'] for r in entries]
        report['comparison'][key] = dict(repeats=len(entries),
            runMedianSoftwareMeanMs=means, runMedianSoftwareP95Ms=tails,
            meanOfRunMediansMs=statistics.mean(means),
            softwareBoundaryComparable=key != 'xess',
            sourceFps=[r['deltas']['frames']/r['seconds'] for r in entries],
            generatedFps=[(r['deltas']['xessGenerated'] if key=='xess' else r['deltas']['generatedPresented'])/r['seconds'] for r in entries])
    (REPORT / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for key, row in report['comparison'].items():
        print(key, json.dumps(row), flush=True)


def cleanup():
    if FIXTURE.resolve().parent != TEST.resolve() or not TEST.resolve().is_relative_to((ART / 'tests').resolve()):
        raise ValueError('Fixture cleanup escapes the task directory')
    expected = len(b'YUV4MPEG2 W2560 H1440 F60:1 Ip A1:1 Cmono\n') + 1500 * (6 + 2560 * 1440)
    with FIXTURE.open('rb') as f:
        if f.readline() != b'YUV4MPEG2 W2560 H1440 F60:1 Ip A1:1 Cmono\n' or FIXTURE.stat().st_size != expected:
            raise ValueError('Fixture identity changed')
    FIXTURE.unlink()
    print('Removed generated sparse fixture; script and measured evidence retained')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    REPORT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ['cleanup']:
        cleanup()
    elif sys.argv[1:] == ['summary']:
        summarize()
    else:
        fixture()
        probe = APP / 'veyra_fg_latency_probe.exe'
        if probe.exists():
            raise FileExistsError(probe)
        shutil.copy2(BUILD / probe.name, probe)
        try:
            if sys.argv[1:] == ['pilot']:
                run('pilot-anr', 'anr', 1)
            else:
                cases = [('off', 'off', 1), ('dlss', 'dlss', 1), ('xess', 'xess', 1),
                         ('vfg-low', 'vfg', 0), ('vfg-medium', 'vfg', 1), ('vfg-high', 'vfg', 2), ('anr', 'anr', 1)]
                for repeat in range(2):
                    for label, backend, quality in (cases if repeat == 0 else list(reversed(cases))):
                        run(f'r{repeat + 1}-{label}', backend, quality)
            summarize()
        finally:
            if probe.resolve().parent != APP.resolve():
                raise ValueError('Probe cleanup escaped task application')
            probe.unlink()
