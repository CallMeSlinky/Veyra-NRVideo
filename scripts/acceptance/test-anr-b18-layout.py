"""Validate the user's exact B18 full ZIP privately; never stage it for distribution."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
ART=Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD=ART/'build/apex-anr-20261112'
REPORT=ART/'reports/slinky-219-20261115/b18'
TEST=ART/'tests/slinky-219-20261115/b18'
URL='https://github.com/apex-compute/ANR/releases/download/FG-V.B18/anr-fg-V.B18-full.zip'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    REPORT.mkdir(parents=True,exist_ok=False)
    TEST.mkdir(parents=True,exist_ok=False)
    archive=ART/'downloads/anr-b18-20261115/anr-fg-V.B18-full.zip'
    target=TEST/'runtime/anr'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        meta=json.loads(z.read('nr_fg_package.json'))
        assert meta['version']=='V.B18' and meta['kind']=='full'
        for entry in z.infolist():
            parts=PurePosixPath(entry.filename)
            assert not parts.is_absolute() and '..' not in parts.parts and ':' not in entry.filename and '\\' not in entry.filename
            if entry.is_dir():continue
            path=target.joinpath(*parts.parts)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(z.read(entry))
    provider=target/'game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/nvngx_dlssg.dll'
    assert sha(provider)==meta['provider_sha256']
    temp=TEST/'tmp';temp.mkdir()
    donor=ART/'releases/anr-b16-20261114/Veyra-2.1.6-Slinky-ANR-B16-win64-portable'
    env=os.environ.copy()
    env.update(PATH=f'{donor};{env.get("PATH", "")}',TEMP=str(temp),TMP=str(temp),
               VEYRA_LOG_FILE=str(REPORT/'engine.log'))
    checks=[('layout',['veyra_anr_runtime_layout_tests.exe',TEST/'layout-fixtures']),
            ('b18-pixels',['veyra_anr_gpu_tests.exe',TEST/'runtime/experimental'])]
    for mode in ('exclusion','exclusion-hdr'):
        checks.append((mode,['veyra_repair_fg_tests.exe',mode,TEST/mode,TEST/'runtime/experimental','anr']))
    results=[]
    for name,args in checks:
        result=subprocess.run([str(BUILD/args[0]),*map(str,args[1:])],cwd=donor,env=env,capture_output=True,timeout=300)
        output=result.stdout+result.stderr
        (REPORT/(name+'.log')).write_bytes(output)
        results.append(dict(check=name,exit=result.returncode))
        (REPORT/'results.json').write_text(json.dumps(results,indent=2))
        assert result.returncode==0,output.decode('utf-8',errors='replace')[-4000:]
        if name=='b18-pixels':assert b'ANR GPU checks=133 failed=0' in output
        print(name,'passed',flush=True)
    (REPORT/'FINAL.json').write_text(json.dumps(dict(passed=True,upstreamUrl=URL,
        archiveSha256=sha(archive),providerSha256=sha(provider),metadata=meta,checks=results,
        exeSha256=sha(BUILD/'veyra_qml_ui.exe'),layout='untouched full ZIP extracted into runtime/anr',
        optiscalerInstalled=False,distributionContainsAnr=False),indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
