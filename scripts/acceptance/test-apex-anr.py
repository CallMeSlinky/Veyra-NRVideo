"""Bounded actual GPU, UI, restart and graph/NVENC export acceptance."""
import importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('anr_package',ROOT/'scripts/acceptance/package-apex-anr.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)
APP=pkg.APP;ART=pkg.ART;BUILD=pkg.BUILD;REPORT=pkg.REPORT
TEST=ART/'tests/anr-quality-20261112'

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    env=os.environ.copy();env.update(TEMP=str(ART/'tmp/apex-anr-20261112'),TMP=str(ART/'tmp/apex-anr-20261112'),
        VEYRA_LOG_FILE=str(REPORT/'product.log'))
    env['PATH']=str(APP)+';'+env.get('PATH','')
    env['QT_PLUGIN_PATH']=str(APP);env['QML2_IMPORT_PATH']=str(APP/'qml')
    for directory in (REPORT/'screenshots',REPORT/'recordings'):
        directory.mkdir(parents=True,exist_ok=True)
    results=[]
    def run(label,command,cwd=APP,timeout=180,extra=None):
        child=env.copy();child.update(extra or {})
        with (REPORT/(label+'.log')).open('w',encoding='utf-8') as log:
            done=subprocess.run([str(x) for x in command],cwd=cwd,env=child,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        text=(REPORT/(label+'.log')).read_text('utf-8',errors='replace')
        results.append({'test':label,'returncode':done.returncode});pkg.write(REPORT/'acceptance.json',results)
        if done.returncode:raise RuntimeError(label+' failed: '+text[-5000:])
        print(label,'exit',done.returncode,flush=True);return text
    if 'unit' in sys.argv:
        run('anr-settings',[BUILD/'veyra_anr_settings_tests.exe',TEST/'settings-final'])
        run('vfg-settings',[BUILD/'veyra_vfg_settings_tests.exe',TEST/'vfg-settings-final'])
        return
    if 'quick' in sys.argv:
        shutil.copytree(ROOT/'tests/qml/quick',BUILD/'qml-tests',dirs_exist_ok=True)
        run('qml-quick',[BUILD/'veyra_qml_quick_tests.exe','-o',str(REPORT/'qml-quick.xml')+',junitxml'],cwd=BUILD,timeout=300,
            extra={'PATH':str(ROOT/'deps/qt/6.8.3/msvc2022_64/bin')+';'+env['PATH'],
                   'QT_PLUGIN_PATH':str(ROOT/'deps/qt/6.8.3/msvc2022_64/plugins'),
                   'QML2_IMPORT_PATH':str(ROOT/'deps/qt/6.8.3/msvc2022_64/qml'),'QT_QUICK_BACKEND':'software'})
        return
    def y4m(path,frames):
        if path.exists():return
        w,h=640,360
        with path.open('wb') as out:
            out.write(f'YUV4MPEG2 W{w} H{h} F24:1 Ip A1:1 C420jpeg\n'.encode())
            for frame in range(frames):
                y=bytearray(30+(x//16+row//16)%24 for row in range(h) for x in range(w))
                left=70+(frame*5)%420
                for row in range(120,240):y[row*w+left:row*w+left+80]=bytes([210])*80
                out.write(b'FRAME\n'+y+bytes([110])*(w*h//4)+bytes([150])*(w*h//4))
    media=TEST/'anr-motion.y4m';y4m(media,240)
    mainQml=APP/'qml/Veyra/Main.qml';original=mainQml.read_bytes();source=original.decode('utf-8');at=source.rfind('}')
    try:
        phases=('dock',) if 'dock' in sys.argv else ('missing',) if 'missing' in sys.argv else ('run','restore')
        for phase in phases:
            loader='\nLoader { source: '+json.dumps((ROOT/'scripts/acceptance/apex-anr-ui.qml').as_uri())+'; onLoaded: {item.media='+json.dumps(str(media))+';item.evidence='+json.dumps(str(REPORT))+';item.phase='+json.dumps(phase)+'} }\n'
            mainQml.write_text(source[:at]+loader+source[at:],encoding='utf-8')
            runtime=APP/'runtime/anr';held=APP/'runtime/anr-acceptance-held'
            if phase=='missing':
                for path in (runtime,held):
                    if not path.resolve().is_relative_to(APP.resolve()):raise ValueError('Runtime move escapes task application')
                if held.exists():raise FileExistsError(held)
                runtime.rename(held)
            try:
                text=run('ui-'+phase,[APP/'veyra_qml_ui.exe','--page','pro','--tab','fg','--dock-pinned','--size','1280x900','--reduced-motion','--data-dir',TEST/('ui-missing-profile' if phase=='missing' else 'ui-profile'),'--exit-after','140000'],extra={'VEYRA_LOG_FILE':str(REPORT/('ui-'+phase+'-engine.log'))})
            finally:
                if phase=='missing':held.rename(runtime)
            marker={'run':'ANR_UI_PASS','restore':'ANR_UI_RESTORE_PASS','missing':'ANR_UI_MISSING_PASS','dock':'ANR_DOCK_CAPTURE_PASS'}[phase]
            if marker not in text or 'ANR_UI_FAIL' in text:raise RuntimeError(text[-7000:])
    finally:mainQml.write_bytes(original)
    if 'missing' in sys.argv:return
    if 'dock' in sys.argv:
        files=list((REPORT/'screenshots').glob('*.png'))+list((REPORT/'recordings').glob('*.mp4'))
        if len(files)<4:raise RuntimeError('Expected windowed and fullscreen screenshots/recordings')
        for index,file in enumerate(files):
            data=json.loads(subprocess.check_output([str(BUILD/'veyra_anr_media_probe.exe'),str(file)],env=env,timeout=30))
            if data['frames']<1 or data['width']<320:raise RuntimeError('Invalid capture artifact')
            pkg.write(REPORT/f'dock-capture-{index}.json',{'file':str(file),'decoded':data})
        print('Dock screenshots and recording files decoded successfully');return
    probe=APP/'veyra_vfg_export_probe.exe';shutil.copy2(BUILD/probe.name,probe)
    try:
        short=TEST/'anr-short.y4m';y4m(short,12)
        for multiplier in (2,4):
            target=TEST/f'anr-export-{multiplier}x.mp4'
            run(f'export-{multiplier}x',[probe,short,target,str(multiplier),'1','--anr'])
            data=json.loads(subprocess.check_output([str(BUILD/'veyra_anr_media_probe.exe'),str(target)],env=env,timeout=30))
            if data['frames']!=12*multiplier or data['distinctLumaFrames']<12:raise RuntimeError('Encoded frame count/content mismatch')
            pkg.write(REPORT/f'export-{multiplier}x-probe.json',data)
    finally:probe.unlink()
    print('ANR playback, dropdown, restart and export acceptance passed')

if __name__=='__main__':main()
