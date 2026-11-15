"""Short real-clip before/after exports; never touches the user's running app."""
import importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pkg',ROOT/'scripts/acceptance/package-apex-anr.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)
REPORT=pkg.ART/'reports/anr-quality-20261112'
TEST=pkg.ART/'tests/anr-quality-20261112'

def main():
    sys.stdout.reconfigure(encoding='utf-8');REPORT.mkdir(parents=True,exist_ok=True);TEST.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(PATH=str(pkg.APP)+';'+env.get('PATH',''),TEMP=str(pkg.ART/'tmp/apex-anr-20261112'),TMP=str(pkg.ART/'tmp/apex-anr-20261112'))
    probe=pkg.APP/'veyra_anr_motion_export_probe.exe';shutil.copy2(pkg.BUILD/'veyra_vfg_export_probe.exe',probe)
    results={}
    try:
        if 'holdout' in sys.argv:
            fixture=TEST/'gta-even-frames.y4m'
            subprocess.run([str(pkg.BUILD/'veyra_anr_quality_probe.exe'),'--decimate',str(TEST/'reference.mp4'),str(fixture)],env=env,check=True,timeout=120)
            for label,anr,legacy in [('holdout-legacy',True,True),('holdout-fixed',True,False),('holdout-vfg',False,False)]:
                child=env.copy();child['VEYRA_LOG_FILE']=str(REPORT/(label+'-engine.log'));child.pop('VEYRA_TEST_ANR_LEGACY_MOTION_SCALE',None)
                if legacy:child['VEYRA_TEST_ANR_LEGACY_MOTION_SCALE']='1'
                target=TEST/(label+'.mp4');command=[str(probe),str(fixture),str(target),'2','1','--frames','15']
                if anr:command.append('--anr')
                with (REPORT/(label+'.log')).open('w',encoding='utf-8') as log:
                    subprocess.run(command,env=child,cwd=pkg.APP,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
                results[label]=json.loads(subprocess.check_output([str(pkg.BUILD/'veyra_anr_quality_probe.exe'),'--holdout',str(TEST/'reference.mp4'),str(target)],env=env,timeout=120))
                print(label,json.dumps(results[label]),flush=True)
                pkg.write(REPORT/'holdout.json',results)
            return
        for label,multiplier,anr,legacy in [('reference',1,False,False),('legacy-2x',2,True,True),('legacy-3x',3,True,True),('fixed-2x',2,True,False),('fixed-3x',3,True,False),('vfg-2x',2,False,False)]:
            target=TEST/(label+'.mp4');child=env.copy();child['VEYRA_LOG_FILE']=str(REPORT/(label+'-engine.log'))
            child.pop('VEYRA_TEST_ANR_LEGACY_MOTION_SCALE',None)
            if legacy:child['VEYRA_TEST_ANR_LEGACY_MOTION_SCALE']='1'
            command=[str(probe),'C:/Users/Jack/Downloads/GTAVI_An_Extended_Look.mp4',str(target),str(multiplier),'1','--start','850','--frames','30']
            if anr:command.append('--anr')
            with (REPORT/(label+'.log')).open('w',encoding='utf-8') as log:
                done=subprocess.run(command,env=child,cwd=pkg.APP,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            if done.returncode:raise RuntimeError(label+': '+(REPORT/(label+'.log')).read_text('utf-8',errors='replace')[-5000:])
            if multiplier>1:
                comparison=subprocess.run([str(pkg.BUILD/'veyra_anr_quality_probe.exe'),str(TEST/'reference.mp4'),str(target),str(multiplier)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
                if comparison.returncode:raise RuntimeError(comparison.stderr.decode(errors='replace'))
                results[label]=json.loads(comparison.stdout)
                print(label,json.dumps(results[label]),flush=True)
                pkg.write(REPORT/'comparison.json',results)
            else:print('Reference 30-frame 4K segment exported',flush=True)
    finally:probe.unlink()
    pkg.write(REPORT/'input.json',{'path':'C:/Users/Jack/Downloads/GTAVI_An_Extended_Look.mp4','bytes':Path('C:/Users/Jack/Downloads/GTAVI_An_Extended_Look.mp4').stat().st_size,'startSeconds':850,'sourceFrames':30})

if __name__=='__main__':main()
