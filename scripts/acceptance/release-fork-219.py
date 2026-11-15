"""Prepare, verify and publish the user's fork release; never package ANR assets."""
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[2]
ART=Path('E:/Veyra-dev/Veyra/anr-artifacts')
REPORT=ART/'reports/fork-release-219-20261115'
OUT=ART/'releases/fork-release-219-20261115'
BUILD=ART/'build/apex-anr-20261112'
REPO='CallMeSlinky/Veyra-NRVideo'
TAG='v2.1.9'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def prepare():
    REPORT.mkdir(parents=True,exist_ok=False)
    names=git('ls-files','--modified','--others','--exclude-standard','-z').decode().split('\0')
    rows=[]
    with zipfile.ZipFile(REPORT/'before-release-source-edits.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in sorted(set(names)):
            if not name or name.startswith(('deps/','.vscode/')):continue
            path=ROOT/name
            if path.is_file():
                z.write(path,name)
                rows.append(dict(path=name,sha256=sha(path)))
    write(REPORT/'before-release-files.json',rows)
    (REPORT/'before-release.diff').write_bytes(git('diff','--binary'))
    write(REPORT/'revisions.json',{r:git('rev-parse',r).decode().strip() for r in ['HEAD','origin/main','v2.1.9^{}']})
    # These later upstream commits only change publication documentation and badges.
    for name in ['README.md','README_CN.md','README_EN.md','assets/veyra-trending-cpp.svg',
                 'assets/veyra-trending-global.svg','docs/RELEASE_2.1.9_EXECUTION_2026-11-15.md']:
        data=git('show','origin/main:'+name)
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    for name in ['README.md','README_EN.md']:
        path=ROOT/name
        intro=('> **CallMeSlinky fork — Veyra 2.1.9**\n> Adds AV1 recording/replay/export, capture shortcuts, dialog and replay fixes, '
               'and optional user-installed ANR support. [Download](https://github.com/'+REPO+'/releases/latest) · '
               '[English / 简体中文 release notes](docs/FORK_RELEASE_2.1.9.md) · [ANR installation](docs/INSTALL_ANR.md).\n\n')
        path.write_text(intro+path.read_text(encoding='utf-8'),encoding='utf-8')
    path=ROOT/'README_CN.md'
    path.write_text('> **CallMeSlinky 分支 — Veyra 2.1.9**\n> 新增 AV1 录制／回放／导出、截图与录制快捷入口、对话框与回放修复，以及可选的用户自装 ANR 支持。'
        '[下载](https://github.com/'+REPO+'/releases/latest) · [更新说明](docs/FORK_RELEASE_2.1.9.md) · [ANR 安装](docs/INSTALL_ANR.md)。\n\n'
        +path.read_text(encoding='utf-8'),encoding='utf-8')
    print('Source backup saved; latest upstream README content retained with fork download links.')


def commit_source():
    branch='slinky/release-2.1.9'
    subprocess.run(['git','switch','-c',branch],cwd=ROOT,check=True)
    subprocess.run(['git','-c','core.safecrlf=false','add','-u'],cwd=ROOT,check=True)
    names=git('ls-files','--others','--exclude-standard','-z').decode().split('\0')
    forbidden={'.dll','.exe','.lib','.pdb','.zip','.nrx','.mp3','.pem','.pfx','.key'}
    added=[]
    for name in names:
        if not name or name.startswith(('deps/','.vscode/','.agents/','.codex/')):continue
        assert Path(name).suffix.lower() not in forbidden,name
        assert not Path(name).name.startswith('.env'),name
        added.append(name)
    for offset in range(0,len(added),40):
        subprocess.run(['git','-c','core.safecrlf=false','add','--',*added[offset:offset+40]],cwd=ROOT,check=True)
    staged=git('diff','--cached','--name-only','-z').decode().split('\0')
    for name in staged:
        if not name:continue
        assert not name.startswith(('deps/','.vscode/','runtime/','runtime_local/')),name
        assert Path(name).suffix.lower() not in forbidden,name
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    subprocess.run(['git','commit','-m','Add custom AV1, capture controls, replay fixes and optional ANR support'],cwd=ROOT,check=True)
    snapshot=git('rev-parse','HEAD').decode().strip()
    # The verified tree already contains the upstream release code plus reviewed
    # later publication docs. Record upstream ancestry without replaying that
    # previously resolved source merge or overwriting the custom ANR adapter.
    subprocess.run(['git','merge','--strategy=ours','--no-ff','origin/main','-m',
        'Integrate upstream v2.1.9 history with the verified custom source tree'],cwd=ROOT,check=True)
    source=git('rev-parse','HEAD').decode().strip()
    subprocess.run(['git','switch','main'],cwd=ROOT,check=True)
    subprocess.run(['git','merge','--ff-only',branch],cwd=ROOT,check=True)
    write(REPORT/'SOURCE.json',dict(commit=source,snapshotCommit=snapshot,upstream=git('rev-parse','origin/main').decode().strip(),
        branch='main',stagedFiles=len([n for n in staged if n]),anrAssetsIncluded=False))
    print('Source ready:',source)


def package():
    source=json.loads((REPORT/'SOURCE.json').read_text())['commit']
    assert git('rev-parse','HEAD').decode().strip()==source
    assert not git('diff','--name-only','HEAD').strip(),'Source changed after commit'
    assert 'VEYRA_DISPLAY_VERSION:STRING=2.1.9\n' in (BUILD/'CMakeCache.txt').read_text()
    app=OUT/'Veyra-2.1.9-win64-portable'
    app.mkdir(parents=True,exist_ok=False)
    donor=ART/'releases/slinky-219-20261115/Veyra-2.1.9-Slinky-build-win64-portable'
    donor_manifest=json.loads((donor/'package-manifest.json').read_text())
    assert not donor_manifest['anrRuntimeIncluded']
    for row in donor_manifest['files']:
        name=row['path']
        assert sha(donor/name)==row['sha256'],name
        if name.startswith(('docs/','assets/','qml/','shaders/','i18n/')) or name.endswith('.cmd') or name in (
            'README.md','README_EN.md','README_CN.md','THIRD_PARTY_NOTICES.md','RELEASE_NOTES.md','ANR-README.txt','Slinky build README.txt','veyra_qml_ui.exe'):continue
        target=app/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(donor/name,target)
    for name in ('qml','shaders'):
        shutil.copytree(BUILD/name,app/name)
    tracked=git('ls-tree','-r','--name-only','HEAD','docs','assets','i18n').decode().splitlines()
    for name in tracked:
        target=app/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for name in ('README.md','README_EN.md','README_CN.md','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,app/name)
    shutil.copy2(BUILD/'veyra_qml_ui.exe',app/'veyra_qml_ui.exe')
    shutil.copy2(ROOT/'docs/FORK_RELEASE_2.1.9.md',app/'RELEASE_NOTES.md')
    shutil.copy2(ROOT/'docs/INSTALL_ANR.md',app/'ANR-README.md')
    (app/'Start Veyra.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0veyra_qml_ui.exe" --data-dir "%~dp0user-data" %*\r\n')
    (app/'README-PORTABLE.txt').write_text('Veyra 2.1.9\nExtract the complete ZIP into a new writable folder and run Start Veyra.cmd.\n'
        'Settings are stored in user-data beside this copy. Existing installations are not modified.\n'
        'See RELEASE_NOTES.md and ANR-README.md for English and Simplified Chinese instructions.\n'
        'ANR runtimes and the upstream startup music asset are not included.\n',encoding='utf-8')
    assert not (app/'runtime/anr').exists() and not list(app.rglob('*.nrx')) and not list(app.rglob('nr_fg.ini'))
    assert len(list(app.glob('*.cmd')))==1
    # Check the relinked version and capture/codec UI in the assembled app.
    temp=ART/'tmp/fork-release-219-20261115';temp.mkdir(parents=True,exist_ok=True)
    ui=REPORT/'release-ui.qml'
    ui.write_text('''import QtQuick
Item {
 property var appWindow: Window.window
 function find(item,name) { if(item.objectName===name)return item; for(const child of item.children||[]){const found=find(child,name);if(found)return found}return null }
 Timer { interval: 1200; running: true; repeat: false; onTriggered: { try {
  if(veyra.version!=="2.1.9")throw new Error("wrong version: "+veyra.version)
  if(!parent.find(parent.appWindow.contentItem,"dock-screenshot")||!parent.find(parent.appWindow.contentItem,"dock-record"))throw new Error("capture controls missing")
  if(!veyra.fgBackendChoices.find(c=>c.id==="anr")||!veyra.fgBackendChoices.find(c=>c.id==="amdfrc"))throw new Error("FG options missing")
  if(!veyra.setPreference("recordCodec",2)||veyra.recordingCodec!==2)throw new Error("record codec")
  veyra.exportCodec=2;if(veyra.exportCodec!==2)throw new Error("export codec")
  console.log("FORK_RELEASE_UI_PASS")
 } catch(error) { console.error("FORK_RELEASE_UI_FAIL",error.toString()) } Qt.quit() } }
}
''',encoding='utf-8')
    main=app/'qml/Veyra/Main.qml';original=main.read_bytes();text=original.decode('utf-8');at=text.rfind('}')
    env=os.environ.copy()
    for key in ('QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH','CUDA_PATH'):env.pop(key,None)
    windows=Path(env.get('SystemRoot','C:/Windows'))
    env.update(PATH=f'{app};{windows/"System32"};{windows}',TEMP=str(temp),TMP=str(temp),
        QML_DISK_CACHE_PATH=str(temp/'qmlcache'),VEYRA_LOG_FILE=str(REPORT/'release-engine.log'))
    def run(label,extra):
        result=subprocess.run([str(app/'veyra_qml_ui.exe'),'--data-dir',str(REPORT/(label+'-profile')),
            '--page','pro','--exit-after','6000',*extra],cwd=app,env=env,capture_output=True,timeout=45)
        (REPORT/(label+'.log')).write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,label
        return result.stdout+result.stderr
    try:
        main.write_text(text[:at]+'\nLoader { source: '+json.dumps(ui.as_uri())+' }\n'+text[at:],encoding='utf-8')
        result=run('release-ui',['--reduced-motion'])
        assert b'FORK_RELEASE_UI_PASS' in result and b'FORK_RELEASE_UI_FAIL' not in result,result[-3000:]
    finally:main.write_bytes(original)
    run('cold-start',[])
    rows=[]
    for path in sorted(app.rglob('*')):
        if not path.is_file():continue
        name=path.relative_to(app).as_posix()
        assert not name.startswith(('user-data','logs/','runtime/anr/'))
        rows.append(dict(path=name,size=path.stat().st_size,sha256=sha(path)))
    manifest=dict(version='2.1.9',repository=REPO,sourceCommit=source,anrRuntimeIncluded=False,
        exeSha256=sha(app/'veyra_qml_ui.exe'),files=rows)
    write(app/'package-manifest.json',manifest)
    rows.append(dict(path='package-manifest.json',sha256=sha(app/'package-manifest.json')))
    binary=OUT/'Veyra-2.1.9-win64-portable.zip'
    print('Compressing portable:',len(rows),'files',flush=True)
    with zipfile.ZipFile(binary,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in rows:z.write(app/row['path'],app.name+'/'+row['path'])
    with zipfile.ZipFile(binary) as z:
        assert z.testzip() is None
        for row in rows:
            with z.open(app.name+'/'+row['path']) as stream:
                assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256'],row['path']
    source_zip=OUT/'Veyra-2.1.9-source.zip'
    with source_zip.open('xb') as stream:
        subprocess.run(['git','archive','--format=zip','--prefix=Veyra-2.1.9-source/',source],cwd=ROOT,stdout=stream,check=True,timeout=300)
    with zipfile.ZipFile(source_zip) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert not name.startswith(('Veyra-2.1.9-source/deps/','Veyra-2.1.9-source/.vscode/'))
            assert PurePosixPath(name).suffix.lower() not in {'.dll','.exe','.lib','.pdb','.nrx','.mp3'},name
    assets=[dict(path=str(p),name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in (binary,source_zip)]
    sums=OUT/'SHA256SUMS.txt'
    sums.write_text(''.join(row['sha256']+'  '+row['name']+'\n' for row in assets),encoding='ascii')
    assets.append(dict(path=str(sums),name=sums.name,bytes=sums.stat().st_size,sha256=sha(sums)))
    write(REPORT/'PACKAGE.json',dict(status='passed',sourceCommit=source,app=str(app),assets=assets,
        exeSha256=manifest['exeSha256'],anrRuntimeIncluded=False,uiPassed=True,coldStartExit=0,payloadFiles=len(rows)))
    print('Package and corresponding source verified.',flush=True)


def token():
    env=os.environ.copy();env.update(GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0')
    result=subprocess.run(['git','credential','fill'],cwd=ROOT,input='protocol=https\nhost=github.com\n\n',
        env=env,text=True,capture_output=True,timeout=30,check=True)
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    return fields['password']


def api(path,method='GET',data=None):
    request=urllib.request.Request('https://api.github.com/'+path,method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json',
            'Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Veyra-fork-release'})
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)


def publish():
    package=json.loads((REPORT/'PACKAGE.json').read_text())
    assert package['status']=='passed'
    source=package['sourceCommit']
    assert git('rev-parse','HEAD').decode().strip()==source and not git('diff','--name-only','HEAD').strip()
    for row in package['assets']:assert sha(Path(row['path']))==row['sha256']
    assert not git('ls-remote','--tags','origin','refs/tags/'+TAG).strip(),'Tag already exists; refusing to move it'
    subprocess.run(['git','tag','-a',TAG,source,'-m','Veyra 2.1.9 - CallMeSlinky fork'],cwd=ROOT,check=True)
    subprocess.run(['git','push','--atomic','origin','HEAD:refs/heads/main','refs/tags/'+TAG],cwd=ROOT,check=True,timeout=300)
    body=(ROOT/'docs/FORK_RELEASE_2.1.9.md').read_text(encoding='utf-8')
    for name in ('INSTALL_ANR.md','FORK_BUILD_2.1.9.md'):
        body=body.replace(']('+name+')','](https://github.com/'+REPO+'/blob/'+TAG+'/docs/'+name+')')
    release=api('repos/'+REPO+'/releases','POST',dict(tag_name=TAG,target_commitish=source,name='Veyra 2.1.9',body=body,draft=True,prerelease=False))
    write(REPORT/'DRAFT.json',dict(id=release['id'],html_url=release['html_url'],tag=TAG))
    for row in package['assets']:
        url=urllib.parse.urlsplit(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(row['name']))
        connection=http.client.HTTPSConnection(url.hostname,timeout=180)
        connection.putrequest('POST',url.path+'?'+url.query)
        connection.putheader('Authorization','Bearer '+token())
        connection.putheader('User-Agent','Veyra-fork-release')
        connection.putheader('Content-Type','application/zip' if row['name'].endswith('.zip') else 'text/plain')
        connection.putheader('Content-Length',str(row['bytes']));connection.endheaders()
        print('Uploading',row['name'],flush=True)
        with Path(row['path']).open('rb') as stream:
            while block:=stream.read(4*1024*1024):connection.send(block)
        response=connection.getresponse();data=json.loads(response.read());connection.close()
        assert response.status==201,(response.status,data.get('message'))
        assert data['size']==row['bytes'] and data.get('digest')=='sha256:'+row['sha256'],row['name']
    assets=api('repos/'+REPO+'/releases/'+str(release['id'])+'/assets')
    assert len(assets)==len(package['assets'])
    for row in package['assets']:
        asset=next(a for a in assets if a['name']==row['name'])
        assert asset['state']=='uploaded' and asset['digest']=='sha256:'+row['sha256']
    release=api('repos/'+REPO+'/releases/'+str(release['id']),'PATCH',dict(draft=False,make_latest='true'))
    assert not release['draft']
    write(REPORT/'PUBLISHED.json',dict(id=release['id'],url=release['html_url'],assets=assets,sourceCommit=source))
    verify()


def verify():
    package=json.loads((REPORT/'PACKAGE.json').read_text())
    release=api('repos/'+REPO+'/releases/tags/'+TAG)
    assert not release['draft'] and release['name']=='Veyra 2.1.9'
    assert api('repos/'+REPO+'/releases/latest')['id']==release['id']
    downloads=[]
    for row in package['assets']:
        asset=next(a for a in release['assets'] if a['name']==row['name'])
        assert asset['size']==row['bytes'] and asset['digest']=='sha256:'+row['sha256']
        request=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'Veyra-release-verification'})
        digest=hashlib.sha256();size=0
        with urllib.request.urlopen(request,timeout=120) as response:
            while block:=response.read(4*1024*1024):digest.update(block);size+=len(block)
        assert digest.hexdigest()==row['sha256'] and size==row['bytes']
        downloads.append(dict(name=row['name'],sha256=digest.hexdigest(),bytes=size,anonymousDownload=True))
        print('Public download verified:',row['name'],flush=True)
    write(REPORT/'FINAL.json',dict(status='published-and-verified',url=release['html_url'],tag=TAG,
        sourceCommit=package['sourceCommit'],exeSha256=package['exeSha256'],anrRuntimeIncluded=False,
        app=package['app'],downloads=downloads,notesLanguages=['English','Simplified Chinese']))
    print('Published and verified:',release['html_url'],flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    phases={'prepare':prepare,'commit':commit_source,'package':package,'publish':publish,'verify':verify}
    if len(sys.argv)!=2 or sys.argv[1] not in phases:raise SystemExit('Select a supported release phase')
    phases[sys.argv[1]]()
