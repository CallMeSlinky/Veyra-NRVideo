"""Extract supplied SDKs on E:, never into the source tree or system directories."""
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parents[2]
DEST=Path('E:/Veyra-dev/Veyra/anr-artifacts/deps/apex-anr-20261112')

def extract(archive,destination,prefix='',keep=lambda name:True):
    count=0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir() or not item.filename.startswith(prefix):continue
            name=item.filename[len(prefix):]
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
                raise ValueError('Unsafe archive path: '+name)
            if not keep(name):continue
            target=destination.joinpath(*path.parts)
            if target.exists() and target.stat().st_size==item.file_size:continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,target.open('wb') as out:
                import shutil
                shutil.copyfileobj(src,out)
            count+=1
    print(archive.name, 'extracted',count,'files to',destination)

if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    incoming=ROOT/'deps/incoming'
    extract(incoming/'FidelityFX-SDK-v1.1.4.zip',DEST/'fidelityfx-1.1.4',keep=lambda n:n.startswith('sdk/') or 'license' in n.lower())
    extract(incoming/'XeSS_SDK_3.0.2.zip',DEST/'xess-3.0.2',keep=lambda n:n.startswith(('inc/','lib/')) or 'license' in n.lower())
    for archive in incoming.glob('*.zip'):
        with zipfile.ZipFile(archive) as z:
            header=next((n for n in z.namelist() if n.endswith('Kits/FidelityFX/framegeneration/include/dx12/ffx_api_framegeneration_dx12.h')),None)
        if header:
            prefix=header.split('Kits/')[0]
            extract(archive,DEST/'fidelityfx-2.3.0',prefix,keep=lambda n:n.startswith('Kits/') or 'license' in n.lower())
