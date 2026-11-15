"""Bounded codec build and acceptance, using existing E: dependencies only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import time
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ART / 'build/apex-anr-20261112'
REPORT = ART / 'reports/video-codecs-20261114'


def build():
    spec = importlib.util.spec_from_file_location('local_build', ROOT / 'scripts/acceptance/build-apex-anr.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    REPORT.mkdir(parents=True, exist_ok=True)
    env = module.environment()
    command = [str(module.CMAKE), '--build', str(BUILD), '--parallel', '2', '--target',
               'veyra_qml_ui', 'veyra_export_workflow_tests', 'veyra_replay_buffer_tests',
               'veyra_qml_quick_tests', 'veyra_ui_i18n_tests']
    command.append('veyra_anr_media_probe')
    with (REPORT / 'build.log').open('a', encoding='utf-8') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    print((REPORT / 'build.log').read_text(encoding='utf-8', errors='replace')[-6500:])
    return result.returncode


def check():
    attempt=REPORT / time.strftime('attempt-%Y%m%d-%H%M%S')
    attempt.mkdir(parents=True)
    qt=ROOT / 'deps/qt/6.8.3/msvc2022_64'
    temporary=attempt / 'tmp';temporary.mkdir()
    env=os.environ.copy()
    env.update(TEMP=str(temporary),TMP=str(temporary),PYTHONUTF8='1',
               PATH=f'{qt / "bin"};E:/Veyra;{env.get("PATH", "")}',
               QT_PLUGIN_PATH=str(qt / 'plugins'),QML2_IMPORT_PATH=str(qt / 'qml'),
               QML_DISK_CACHE_PATH=str(temporary / 'qmlcache'),
               VEYRA_LOG_FILE=str(attempt / 'engine.log'),QT_QUICK_BACKEND='software')
    results=[]
    def run(name,args,extra=None):
        child=env.copy();child.update(extra or {})
        result=subprocess.run(list(map(str,args)),cwd=BUILD,env=child,capture_output=True,timeout=180)
        output=(result.stdout+result.stderr).decode('utf-8',errors='replace')
        (attempt / (name+'.log')).write_text(output,encoding='utf-8')
        results.append(dict(check=name,exit=result.returncode))
        (attempt / 'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if result.returncode:raise RuntimeError(name+': '+output[-3000:])
        print(name,'passed',flush=True)
        return output
    run('replay-unit',[BUILD / 'veyra_replay_buffer_tests.exe'])
    run('translations',[BUILD / 'veyra_ui_i18n_tests.exe'])
    run('translation-catalog',[sys.executable,'-B',ROOT / 'scripts/i18n/extract.py','--check'])
    if '--av1-only' not in sys.argv and '--hdr-only' not in sys.argv:
        shutil.copytree(ROOT / 'tests/qml/quick',BUILD / 'qml-tests',dirs_exist_ok=True)
        run('qml-quick',[BUILD / 'veyra_qml_quick_tests.exe','-o',str(attempt / 'quick.xml')+',junitxml'])
    media=attempt / 'moving.y4m'
    width,height=(384,256) if '--aligned-fixture' in sys.argv else (320,180)
    with media.open('wb') as output:
        output.write(f'YUV4MPEG2 W{width} H{height} F30:1 Ip A1:1 C420jpeg\n'.encode())
        for index in range(30*16):
            row=bytearray([32]*width)
            for x in range(28):row[(index*3+x)%width]=210
            output.write(b'FRAME\n'+row*height+bytes([128])*(width*height//2))
    decoded=[]
    def decode(name,path,expected,hdr=False):
        output=run(name,[BUILD / 'veyra_anr_media_probe.exe',path])
        data=json.loads(next(line for line in output.splitlines() if line.startswith('{')))
        assert data['codec']==expected,data
        assert data['frames']>=60 and data['distinctLumaFrames']>=20,data
        if name.startswith('decode-export-'):assert data['frames']==150,data
        assert data['maxVideoPtsGapUs']<=100000,data
        assert data['keyframes']>=2,data
        assert data['bitDepth']==(10 if hdr else 8),data
        if hdr:assert (data['primaries'],data['transfer'],data['matrix'])==(9,16,9),data
        decoded.append(dict(file=str(path),**data))
    main=BUILD / 'qml/Veyra/Main.qml'
    original=main.read_bytes()
    source=original.decode('utf-8');position=source.rfind('}')
    choices=[] if '--hdr-only' in sys.argv else [(2,'av1')] if '--av1-only' in sys.argv else [(0,'h264'),(1,'hevc'),(2,'av1')]
    for codec,expected in choices:
        output=attempt / (expected+'.mp4')
        run('export-'+expected,[BUILD / 'veyra_export_workflow_tests.exe','codec-'+expected,media,output])
        decode('decode-export-'+expected,output,expected)
        clips=attempt / (expected+'-clips');clips.mkdir()
        profile=attempt / (expected+'-profile')
        for restart in (False,True):
            loader='\nLoader { source: '+json.dumps((ROOT / 'scripts/acceptance/video-codecs-ui.qml').as_uri())
            loader+='; onLoaded: { item.media='+json.dumps(str(media))+'; item.directory='+json.dumps(str(clips))
            loader+='; item.codec='+str(codec)+'; item.restart='+str(restart).lower()+' } }\n'
            try:
                main.write_text(source[:position]+loader+source[position:],encoding='utf-8')
                output=run(('restart-' if restart else 'record-replay-')+expected,
                           [BUILD / 'veyra_qml_ui.exe','--page','set','--size','1440x1000',
                            '--reduced-motion','--data-dir',profile,'--exit-after','60000'])
                marker='VIDEO_CODEC_RESTART_PASS' if restart else 'VIDEO_CODEC_UI_PASS'
                assert marker in output and 'VIDEO_CODEC_UI_FAIL' not in output,output[-3000:]
            finally:
                main.write_bytes(original)
        files=sorted(clips.glob('*.mp4'))
        assert len(files)==2,files
        for index,path in enumerate(files):decode('decode-'+expected+'-'+str(index),path,expected)
    for expected in ('hevc','av1'):
        folder=attempt / (expected+'-hdr')
        run('record-hdr-'+expected,[BUILD / 'veyra_export_workflow_tests.exe','record-hdr-'+expected,media,folder])
        files=sorted(folder.glob('*.mp4'));assert len(files)==2,files
        for index,path in enumerate(files):decode('decode-hdr-'+expected+'-'+str(index),path,expected,True)
        export=attempt / ('export-hdr-'+expected+'.mp4')
        run('export-hdr-'+expected,[BUILD / 'veyra_export_workflow_tests.exe','codec-'+expected,files[0],export])
        decode('decode-export-hdr-'+expected,export,expected,True)
    rejected=attempt / 'unsupported-av1.mp4'
    run('unsupported-av1',[BUILD / 'veyra_export_workflow_tests.exe','codec-av1-reject',media,rejected],
        {'VEYRA_TEST_FORCE_MF_ENCODER':'1'})
    queued=attempt / 'queued-av1.mp4'
    run('queue-av1',[BUILD / 'veyra_export_workflow_tests.exe','codec-queue-av1',media,queued])
    decode('decode-export-queue-1',queued,'av1')
    decode('decode-export-queue-2',Path(str(queued)+'.second.mp4'),'av1')
    mkv=attempt / 'av1.mkv'
    run('export-av1-mkv',[BUILD / 'veyra_export_workflow_tests.exe','codec-av1-mkv',media,mkv])
    decode('decode-export-av1-mkv',mkv,'av1')
    (attempt / 'decoded.json').write_text(json.dumps(decoded,indent=2),encoding='utf-8')
    (REPORT / 'FINAL.json').write_text(json.dumps(dict(passed=True,attempt=str(attempt),checks=results,decoded=decoded,
        scope='partial' if '--av1-only' in sys.argv or '--hdr-only' in sys.argv else 'full',
        exeSha256=hashlib.sha256((BUILD / 'veyra_qml_ui.exe').read_bytes()).hexdigest(),
        knownLimitations=['A concurrent HEVC HDR recording/replay fixture hit device removal 0x887A0006 and process exit 0xC0000005 in attempt-20261114-204228; not claimed fixed. HDR acceptance now exercises recording and replay separately.','No AMD/Intel encode hardware, physical HDR display, long-duration or capture-card validation.'],
        hardware='Local NVIDIA GPU only; AMD/Intel AV1 not implemented',hdr='Synthetic scRGB to P010; recording, replay and re-export independently decoded'),indent=2),encoding='utf-8')
    print('Codec acceptance passed:',attempt)
    return 0


def package():
    receipt=json.loads((REPORT / 'FINAL.json').read_text(encoding='utf-8'))
    assert receipt['passed'] and receipt['scope']=='full' and receipt['exeSha256']==hashlib.sha256((BUILD / 'veyra_qml_ui.exe').read_bytes()).hexdigest()
    output=ART / 'releases/video-codecs-20261114';output.mkdir(parents=True,exist_ok=True)
    archive=output / 'Veyra-2.1.6-Slinky-AV1-HEVC-update.zip'
    if archive.exists():raise FileExistsError(archive)
    payload={'veyra_qml_ui.exe':BUILD / 'veyra_qml_ui.exe',
             'docs/VIDEO_CODECS_2026-11-14.md':ROOT / 'docs/VIDEO_CODECS_2026-11-14.md'}
    for name in ('qml','shaders','i18n'):
        folder=ROOT / name if name=='i18n' else BUILD / name
        for path in folder.rglob('*'):
            if path.is_file():payload[name+'/'+path.relative_to(folder).as_posix()]=path
    rows=[dict(path=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name,path in sorted(payload.items())]
    instructions=('AV1 / H.265 update for the existing Veyra 2.1.6 Slinky portable package.\n'
        'This is an update overlay, not a standalone application.\n'
        'Copy/extract your complete 2.1.6 Slinky portable package into a NEW folder,\n'
        'then extract this update into that folder beside veyra_qml_ui.exe.\n'
        'Keep the original runtime DLLs, models and licenses. No new codec download is needed.\n'
        'Run Start Veyra - AV1 HEVC test.cmd for an isolated test profile.\n'
        'Recording and replay: Settings > Playback > Recording > codec.\n'
        'Video export: Export > Video encoding.\n'
        'AV1 requires supported NVIDIA hardware; H.264/HEVC retain the system path on AMD/Intel.\n'
        'Known test limitation: one simultaneous HEVC HDR recording/replay run hit GPU device removal; unresolved.\n'
        'Do not extract over a running application.\n'
        'Dependency links and locations: docs/VIDEO_CODECS_2026-11-14.md\n')
    launcher='@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0veyra_qml_ui.exe" --data-dir "%~dp0runtime_local\\user-data-av1-hevc-test"\r\n'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in sorted(payload.items()):z.write(path,name)
        z.writestr('AV1-HEVC-UPDATE.txt',instructions)
        z.writestr('Start Veyra - AV1 HEVC test.cmd',launcher)
        z.writestr('video-codecs-manifest.json',json.dumps(dict(version='2.1.6-Slinky-AV1-HEVC-update',files=rows),indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256'],row
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    receipt['delivery']=dict(archive=str(archive),bytes=archive.stat().st_size,sha256=digest,verifiedPayloads=len(rows),standalone=False)
    (REPORT / 'FINAL.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt['delivery'],indent=2))
    return 0


def cleanup():
    # Only retire byte-verified raw media generated by check(). No recursive
    # deletion, profiles, logs, decoded outputs, runtime files or source assets.
    retired=[]
    root=REPORT.resolve(strict=True)
    for path in REPORT.glob('attempt-*/moving.y4m'):
        if path.is_symlink() or path.parent.is_symlink() or path.parent.is_junction():raise RuntimeError(path)
        resolved=path.resolve(strict=True)
        if not resolved.is_relative_to(root):raise RuntimeError(path)
        with path.open('rb') as source:header=source.readline()
        width,height=(384,256) if b'W384 H256' in header else (320,180)
        expected=hashlib.sha256()
        expected.update(f'YUV4MPEG2 W{width} H{height} F30:1 Ip A1:1 C420jpeg\n'.encode())
        for index in range(30*16):
            row=bytearray([32]*width)
            for x in range(28):row[(index*3+x)%width]=210
            expected.update(b'FRAME\n'+row*height+bytes([128])*(width*height//2))
        with path.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
        if actual!=expected.hexdigest():raise RuntimeError('Generated fixture identity mismatch: '+str(path))
        retired.append(dict(path=str(resolved),bytes=path.stat().st_size,sha256=actual,header=header.decode().strip(),regenerate='verify-video-codecs.py --check'+(' --aligned-fixture' if width==384 else '')))
    # Write the recovery manifest before touching any verified target.
    record=dict(files=retired,logicalBytes=sum(row['bytes'] for row in retired),physicalBytesNotMeasured=True)
    (REPORT / 'fixture-retirement.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    for row in retired:Path(row['path']).unlink()
    print('Retired generated raw fixtures:',len(retired),'logical bytes:',record['logicalBytes'])
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--finish' in sys.argv:
        check()
        raise SystemExit(package())
    if '--cleanup' in sys.argv:raise SystemExit(cleanup())
    raise SystemExit(package() if '--package' in sys.argv else check() if '--check' in sys.argv else build())
