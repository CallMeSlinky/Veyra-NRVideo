"""Stage/seal a local personal portable candidate from verified runtime files."""
from pathlib import Path, PurePosixPath
import hashlib,json,os,shutil,subprocess,sys,zipfile

ROOT=Path(__file__).resolve().parents[2]
ART=Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD=ART/'build/apex-anr-20261112'
OUT=ART/'releases/apex-anr-motion-fix-20261112'
APP=OUT/'Veyra-2.1.5-ANR-beta2-win64-portable'
REPORT=ART/'reports/anr-quality-20261112'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def stage():
    donor=Path('E:/Veyra')
    manifest=json.loads((donor/'package-manifest.json').read_text('utf-8-sig'))
    records=[]
    for row in manifest['files']:
        name=row['path'];relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name:raise ValueError(name)
        if name=='veyra_qml_ui.exe' or name.startswith(('qml/Veyra/','shaders/','i18n/')):continue
        source=donor.joinpath(*relative.parts)
        if sha(source)!=row['sha256']:raise ValueError('Donor identity changed: '+name)
        target=APP.joinpath(*relative.parts);target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists() or sha(target)!=row['sha256']:shutil.copy2(source,target)
        records.append(row)
    shutil.copy2(BUILD/'veyra_qml_ui.exe',APP/'veyra_qml_ui.exe')
    shutil.copytree(BUILD/'shaders',APP/'shaders',dirs_exist_ok=True)
    shutil.copytree(ROOT/'qml/Veyra',APP/'qml/Veyra',dirs_exist_ok=True)
    shutil.copytree(ROOT/'i18n',APP/'i18n',dirs_exist_ok=True)
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',APP/'THIRD_PARTY_NOTICES.md')
    addon=ART/'downloads/apex-anr-20261112/addon'
    shutil.copytree(addon/'Apex Neural Rendering FG/dlssg',APP/'runtime/anr',dirs_exist_ok=True)
    shutil.copy2(addon/'nr_fg_package.json',APP/'runtime/anr/nr_fg_package.json')
    (APP/'Start Veyra.cmd').write_text('@echo off\ncd /d "%~dp0"\nstart "" "%~dp0veyra_qml_ui.exe" --data-dir "%~dp0user-data-anr"\n',encoding='ascii')
    (APP/'ANR-README.txt').write_text(
        'Veyra 2.1.5 ANR beta2 - corrected pixel-space motion input\n\n'
        'Run Start Veyra.cmd. In Frame Generation choose Apex ANR - Beta, then 2X/3X/4X/6X.\n'
        'Settings stay in user-data-anr beside the program. No CUDA toolkit is needed on the destination PC.\n'
        'ANR is loaded from runtime/anr, independently of the original NVIDIA DLSS-G runtime.\n'
        'ANR uses estimated video motion and proxy depth, not native game engine inputs.\n'
        'Official ANR FG V.B14: https://github.com/apex-compute/ANR/releases/tag/FG-V.B14\n'
        'The external ANR beta runtime remains Apex Compute software; no ANR source or redistribution license\n'
        'was supplied in its addon. This local personal package has not been published.\n'
        'The build enables FSR, XeSS, VFG and NVIDIA enhancement backends. Optional PS5/Moonlight/Xbox\n'
        'streaming and libass subtitle rendering are not compiled in this local dependency configuration.\n'
        'See docs/APEX_ANR_2026-11-12.md for test results and known limits.\n',encoding='utf-8')
    write(REPORT/'donor-verification.json',{'donor':'E:/Veyra','manifestSha256':sha(donor/'package-manifest.json'),'verifiedFiles':len(records),'files':records})
    print('Staged',APP)

def seal():
    for name in ('veyra_anr_gpu_tests.exe','veyra_vfg_export_probe.exe','veyra_qml_quick_tests.exe'):
        if (APP/name).exists():raise ValueError('Test executable in delivery: '+name)
    shutil.copy2(ROOT/'docs/APEX_ANR_2026-11-12.md',APP/'docs/APEX_ANR_2026-11-12.md')
    shutil.copy2(ROOT/'docs/ANR_MOTION_FIX_2026-11-12.md',APP/'docs/ANR_MOTION_FIX_2026-11-12.md')
    rows=[]
    for file in sorted(APP.rglob('*')):
        if not file.is_file():continue
        name=file.relative_to(APP).as_posix()
        if name.startswith(('logs/','user-data','qml-tests/')) or name.endswith(('.log','.dmp')):continue
        if name=='runtime/anr/anr-vkloader.dll':continue # provider-generated copy of the system Vulkan loader
        if name=='package-manifest.json':continue
        rows.append({'path':name,'size':file.stat().st_size,'sha256':sha(file)})
    # Do not misrepresent the original release's source commit or executable.
    write(APP/'package-manifest.json',{'schema':1,'version':'2.1.5-anr-beta2','localOnly':True,
        'published':False,'baseSourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'sourceHasLocalChanges':True,'exeSha256':sha(APP/'veyra_qml_ui.exe'),'anrVersion':'FG-V.B14','files':rows})
    archive=OUT/(APP.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in rows+ [{'path':'package-manifest.json'}]:
            file=APP/row['path'];z.write(file,APP.name+'/'+row['path'])
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC validation failed')
    digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    source=source_archive()
    write(REPORT/'package.json',{'portable':str(archive),'sha256':digest,'size':archive.stat().st_size,'source':str(source),'sourceSha256':sha(source),'fileCount':len(rows)+1})
    print('Sealed',archive,'SHA256',digest)

def source_archive():
    # Application corresponding source, including this uncommitted integration.
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    extras=['include/veyra/ngx/AnrFgBackend.h','src/ngx/AnrFgBackend.cpp',
        'tests/integration/AnrGpuTests.cpp','tests/integration/AnrMediaProbe.cpp','tests/integration/AnrQualityProbe.cpp','tests/unit/AnrSettingsTests.cpp','docs/APEX_ANR_2026-11-12.md','docs/ANR_MOTION_FIX_2026-11-12.md']
    extras += [p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts/acceptance').glob('*apex-anr*')]
    source=OUT/'Veyra-2.1.5-ANR-beta2-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(set(tracked+extras)):
            if name and (ROOT/name).is_file():z.write(ROOT/name,'Veyra-2.1.5-ANR-beta2-source/'+name)
    source.with_suffix('.zip.sha256').write_text(sha(source)+'  '+source.name+'\n',encoding='ascii')
    if (REPORT/'package.json').exists():
        data=json.loads((REPORT/'package.json').read_text('utf-8'))
        data.update(source=str(source),sourceSha256=sha(source));write(REPORT/'package.json',data)
    print('Source archive',source);return source

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'stage':stage,'seal':seal,'source':source_archive}[sys.argv[1]]()
