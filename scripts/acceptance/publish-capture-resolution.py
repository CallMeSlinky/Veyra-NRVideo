"""Publish the verified local portable as a new fork release; retain prior releases."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT/'logs/capture-resolution-20261116/github'
OUT = ROOT/'build/capture-resolution-20261116/portable'
REPO = 'CallMeSlinky/Veyra-NRVideo'
TAG = 'v2.1.9-slinky-r2'
spec = importlib.util.spec_from_file_location('release_helpers', Path(__file__).with_name('release-fork-219.py'))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def write(name, data):
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT/name).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, timeout=120).decode().strip()


def preflight():
    assert not git('status', '--porcelain'), 'Commit local changes first'
    package = json.loads((ROOT/'logs/capture-resolution-20261116/portable/FINAL.json').read_text())
    assert package['passed'] and package['zipCrcAndAllFileHashesVerified'] and package['uiPassed'] and package['coldStartPassed']
    assert helper.sha(Path(package['portable'])) == package['sha256']
    subprocess.run(['git', 'merge-base', '--is-ancestor', package['sourceCommit'], 'HEAD'], cwd=ROOT, check=True)
    changes = git('diff', '--name-only', package['sourceCommit'], 'HEAD').splitlines()
    assert all(p.startswith(('docs/', 'scripts/')) for p in changes), changes
    with zipfile.ZipFile(package['sourceZip']) as z:
        assert z.testzip() is None
        entry = next(n for n in z.namelist() if n.endswith('/qml/Veyra/CaptureSourceDialog.qml'))
        archived = z.read(entry)
        committed = subprocess.check_output(['git', 'show', package['sourceCommit']+':qml/Veyra/CaptureSourceDialog.qml'], cwd=ROOT)
        # git archive applies this Windows checkout's CRLF conversion; git show
        # returns the repository's LF blob. Normalize only that transport change.
        assert archived.replace(b'\r\n', b'\n') == committed.replace(b'\r\n', b'\n')
    sums = dict((line.split()[1], line.split()[0]) for line in (OUT/'SHA256SUMS.txt').read_text().splitlines())
    assets = []
    for name in ('Veyra-2.1.9-win64-portable.zip', 'Veyra-2.1.9-source.zip', 'SHA256SUMS.txt'):
        path = OUT/name
        digest = helper.sha(path)
        if name in sums:
            assert digest == sums[name], name
        assets.append(dict(name=name, path=str(path), bytes=path.stat().st_size, sha256=digest))
    write('PACKAGE.json', dict(sourceCommit=package['sourceCommit'], mainCommit=git('rev-parse', 'HEAD'), assets=assets))
    return package, assets


def upload(release, row):
    url = urllib.parse.urlsplit(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(row['name']))
    connection = http.client.HTTPSConnection(url.hostname, timeout=180)
    connection.putrequest('POST', url.path+'?'+url.query)
    connection.putheader('Authorization', 'Bearer '+helper.token())
    connection.putheader('User-Agent', 'Veyra-capture-release')
    connection.putheader('Content-Type', 'application/zip' if row['name'].endswith('.zip') else 'text/plain')
    connection.putheader('Content-Length', str(row['bytes']))
    connection.endheaders()
    print('Uploading '+row['name'], flush=True)
    sent = 0
    milestone = 128*1024*1024
    with Path(row['path']).open('rb') as stream:
        while block := stream.read(4*1024*1024):
            connection.send(block)
            sent += len(block)
            if sent >= milestone:
                print(f'Uploaded {sent // (1024*1024)} MiB', flush=True)
                milestone += 128*1024*1024
    response = connection.getresponse()
    result = json.loads(response.read())
    connection.close()
    assert response.status == 201, (response.status, result.get('message'))
    assert result['size'] == row['bytes'] and result['digest'] == 'sha256:'+row['sha256'], row['name']


def publish():
    package, assets = preflight()
    subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=ROOT, check=True, timeout=120)
    subprocess.run(['git', 'merge-base', '--is-ancestor', 'origin/main', 'HEAD'], cwd=ROOT, check=True)
    existing = git('tag', '--list', TAG)
    if existing:
        assert git('rev-parse', TAG+'^{}') == package['sourceCommit']
    else:
        assert not git('ls-remote', '--tags', 'origin', 'refs/tags/'+TAG), 'Remote release tag already exists'
        subprocess.run(['git', 'tag', '-a', TAG, package['sourceCommit'], '-m', 'Veyra 2.1.9 - capture settings update'], cwd=ROOT, check=True)
    subprocess.run(['git', 'push', '--atomic', 'origin', 'HEAD:refs/heads/main', 'refs/tags/'+TAG], cwd=ROOT, check=True, timeout=180)
    if (REPORT/'DRAFT.json').exists():
        saved = json.loads((REPORT/'DRAFT.json').read_text())
        release = helper.api(f'repos/{REPO}/releases/{saved["id"]}')
        assert release['tag_name'] == TAG
    else:
        notes = (ROOT/'docs/FORK_RELEASE_2.1.9_R2.md').read_text('utf-8')
        release = helper.api(f'repos/{REPO}/releases', 'POST', dict(tag_name=TAG, target_commitish=package['sourceCommit'],
            name='Veyra 2.1.9 — Capture settings update', body=notes, draft=True, prerelease=False))
        write('DRAFT.json', dict(id=release['id'], url=release['html_url'], tag=TAG))
    for row in assets:
        present = next((a for a in release['assets'] if a['name'] == row['name']), None)
        if present:
            assert present['size'] == row['bytes'] and present['digest'] == 'sha256:'+row['sha256'], 'Existing asset differs'
        else:
            assert release['draft'], 'Refusing to alter an already published release'
            upload(release, row)
    uploaded = helper.api(f'repos/{REPO}/releases/{release["id"]}/assets')
    assert len(uploaded) == len(assets)
    for row in assets:
        asset = next(a for a in uploaded if a['name'] == row['name'])
        assert asset['state'] == 'uploaded' and asset['size'] == row['bytes'] and asset['digest'] == 'sha256:'+row['sha256']
    release = helper.api(f'repos/{REPO}/releases/{release["id"]}', 'PATCH', dict(draft=False, make_latest='true'))
    assert not release['draft']
    write('PUBLISHED.json', dict(id=release['id'], url=release['html_url'], tag=TAG, sourceCommit=package['sourceCommit']))
    verify()


def verify():
    package = json.loads((REPORT/'PACKAGE.json').read_text())
    release = helper.api(f'repos/{REPO}/releases/tags/{TAG}')
    assert not release['draft'] and not release['prerelease']
    assert helper.api(f'repos/{REPO}/releases/latest')['id'] == release['id']
    assert helper.api(f'repos/{REPO}/releases/tags/v2.1.9-slinky')['id'] == 446437559
    assert git('ls-remote', 'origin', 'refs/heads/main').split()[0] == package['mainCommit']
    assert git('ls-remote', 'origin', 'refs/tags/'+TAG+'^{}').split()[0] == package['sourceCommit']
    downloads = []
    for row in package['assets']:
        asset = next(a for a in release['assets'] if a['name'] == row['name'])
        assert asset['size'] == row['bytes'] and asset['digest'] == 'sha256:'+row['sha256']
        request = urllib.request.Request(asset['browser_download_url'], headers={'User-Agent': 'Veyra-anonymous-verification'})
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(request, timeout=120) as response:
            while block := response.read(4*1024*1024):
                digest.update(block)
                size += len(block)
        assert digest.hexdigest() == row['sha256'] and size == row['bytes'], row['name']
        downloads.append(dict(name=row['name'], sha256=row['sha256'], bytes=size, anonymousDownloadVerified=True))
        print('Anonymous download verified: '+row['name'], flush=True)
    write('FINAL.json', dict(status='published-and-verified', url=release['html_url'], tag=TAG,
        sourceCommit=package['sourceCommit'], mainCommit=package['mainCommit'], downloads=downloads, previousReleaseRetained=True))
    print('Published and verified: '+release['html_url'], flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'publish': publish, 'verify': verify}[sys.argv[1]]()
