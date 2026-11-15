"""Prove the phase-position regression detects the old adapter and passes the fix."""
import importlib.util,os,subprocess,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pkg',ROOT/'scripts/acceptance/package-apex-anr.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)

def main():
    sys.stdout.reconfigure(encoding='utf-8');results={}
    for label,legacy in [('legacy-phase',True),('fixed-phase',False)]:
        env=os.environ.copy();env.update(TEMP=str(pkg.ART/'tmp/apex-anr-20261112'),TMP=str(pkg.ART/'tmp/apex-anr-20261112'))
        env.pop('VEYRA_TEST_ANR_LEGACY_MOTION_SCALE',None)
        if legacy:env['VEYRA_TEST_ANR_LEGACY_MOTION_SCALE']='1'
        with (pkg.REPORT/(label+'.log')).open('w',encoding='utf-8') as log:
            done=subprocess.run([str(pkg.BUILD/'veyra_anr_gpu_tests.exe'),str(pkg.ART/'tests/apex-anr-20261112/runtime/experimental')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        text=(pkg.REPORT/(label+'.log')).read_text('utf-8')
        match=re.search(r'ANR GPU checks=(\d+) failed=(\d+)',text)
        if not match:raise RuntimeError(text[-5000:])
        checks,failed=map(int,match.groups())
        if legacy and (done.returncode==0 or failed==0):raise RuntimeError('Old motion conversion escaped regression')
        if not legacy and (done.returncode!=0 or failed!=0):raise RuntimeError(text[-5000:])
        results[label]={'returncode':done.returncode,'checks':checks,'failed':failed}
        print(label,results[label],flush=True)
    pkg.write(pkg.REPORT/'motion-regression.json',results)

if __name__=='__main__':main()
