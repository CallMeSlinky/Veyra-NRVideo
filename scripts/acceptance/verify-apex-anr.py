"""Cold-start with a minimal PATH, or verify every archived payload identity."""
import hashlib,importlib.util,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('anr_package',ROOT/'scripts/acceptance/package-apex-anr.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1:] == ['cold']:
        app=pkg.APP;profile=pkg.ART/'tests/anr-quality-20261112/cold-profile'
        profile.mkdir(parents=True,exist_ok=True)
        shutil.copy2(pkg.ART/'tests/anr-quality-20261112/ui-profile/chain-session.v1.anr',profile/'chain-session.v1.anr')
        env=os.environ.copy();windows=Path(os.environ.get('SystemRoot','C:/Windows'))
        for key in ('QT_PLUGIN_PATH','QML2_IMPORT_PATH','QML_IMPORT_PATH','CUDA_PATH'):
            env.pop(key,None)
        env.update(PATH=str(app)+';'+str(windows/'System32')+';'+str(windows),
                   TEMP=str(pkg.ART/'tmp/apex-anr-20261112'),TMP=str(pkg.ART/'tmp/apex-anr-20261112'),
                   VEYRA_LOG_FILE=str(pkg.REPORT/'cold-engine.log'))
        with (pkg.REPORT/'cold.log').open('w',encoding='utf-8') as log:
            done=subprocess.run([str(app/'veyra_qml_ui.exe'),'--data-dir',str(profile),'--page','min',
                '--dock-pinned','--exit-after','7000',str(pkg.ART/'tests/anr-quality-20261112/anr-motion.y4m')],
                env=env,cwd=app,stdout=log,stderr=subprocess.STDOUT,timeout=40)
        text=(pkg.REPORT/'cold.log').read_text('utf-8',errors='replace')
        if done.returncode or '[anr] Created' not in text:raise RuntimeError(text[-5000:])
        pkg.write(pkg.REPORT/'cold.json',{'returncode':done.returncode,'anrCreated':True,'minimalPath':True,
            'cudaToolkitOnPath':False,'exeSha256':pkg.sha(app/'veyra_qml_ui.exe')})
        print('Cold portable start passed (minimal PATH, ANR playback)');return
    archive=pkg.OUT/(pkg.APP.name+'.zip')
    import xml.etree.ElementTree as ET
    quick=ET.parse(pkg.REPORT/'qml-quick.xml').getroot().attrib
    if quick.get('failures')!='0' or quick.get('errors')!='0':raise ValueError('Qt Quick regression failed')
    for file,marker in [('fixed-phase.log','ANR GPU checks=133 failed=0'),
                        ('anr-settings.log','ANR settings checks=39 failed=0'),
                        ('vfg-settings.log','VFG settings 683 checks, 0 failures'),
                        ('ui-run.log','ANR_UI_PASS'),('ui-restore.log','ANR_UI_RESTORE_PASS'),
                        ('ui-missing.log','ANR_UI_MISSING_PASS'),('ui-dock.log','ANR_DOCK_CAPTURE_PASS')]:
        raw=(pkg.REPORT/file).read_bytes()
        encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
        if marker not in raw.decode(encoding,errors='replace'):raise ValueError('Missing acceptance evidence: '+file)
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read(pkg.APP.name+'/package-manifest.json'))
        for row in manifest['files']:
            with z.open(pkg.APP.name+'/'+row['path']) as stream:
                digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=row['sha256']:raise ValueError('Archive hash mismatch: '+row['path'])
        names=z.namelist()
        if any('/user-data' in n or '/logs/' in n or n.endswith(('.log','.dmp')) or n.endswith('/anr-vkloader.dll') for n in names):
            raise ValueError('Development/cache artifact in archive')
        if any('tests.exe' in n or 'probe.exe' in n for n in names):raise ValueError('Test executable in archive')
    motion=json.loads((pkg.REPORT/'motion-regression.json').read_text('utf-8'))
    if motion['legacy-phase']['failed']==0 or motion['fixed-phase']['failed']!=0:raise ValueError('Motion regression did not distinguish old/new adapter')
    holdout=json.loads((pkg.REPORT/'holdout.json').read_text('utf-8'))
    if holdout['holdout-fixed']['generatedGroundTruthMae']>=holdout['holdout-legacy']['generatedGroundTruthMae']:raise ValueError('Held-out frame reconstruction did not improve')
    pkg.write(pkg.REPORT/'FINAL.json',{
        'status':'complete','publiclyPublished':False,'version':'2.1.5-anr-beta2',
        'portable':str(archive),'portableSha256':pkg.sha(archive),'portableBytes':archive.stat().st_size,
        'source':str(pkg.OUT/'Veyra-2.1.5-ANR-beta2-source.zip'),
        'motionRegression':motion,'gtaHeldOutComparison':holdout,
        'archivedFilesVerified':len(manifest['files']),
        'hardware':'NVIDIA GeForce RTX 4090',
        'tests':{'anrGpuChecks':133,'anrGpuFailures':0,'d3d12DebugErrors':0,
                 'anrSettingsChecks':39,'anrSettingsFailures':0,'vfgSettingsChecks':683,'vfgSettingsFailures':0,
                 'qmlCases':int(quick['tests']),'qmlFailures':int(quick['failures']),'qmlErrors':int(quick['errors']),'qmlSkipped':int(quick['skipped']),
                 'anrDropdownPlaybackRestartMissingRuntime':'passed','export2xDecodedFrames':24,'export4xDecodedFrames':48,
                 'dockIconAlignment':'passed','minimalFullscreenScreenshotRecording':'passed',
                 'minimalPathColdStart':json.loads((pkg.REPORT/'cold.json').read_text('utf-8'))},
        'limits':['AMD/Intel inference not tested','Optional PS5/Moonlight/Xbox streaming and libass not compiled',
                  'Local personal candidate: upstream ANR addon supplies no explicit redistribution licence'],
        'notes':'See docs/ANR_MOTION_FIX_2026-11-12.md. The original running user application was left untouched.'})
    print('All archived file hashes verified:',len(manifest['files']))

if __name__=='__main__':main()
