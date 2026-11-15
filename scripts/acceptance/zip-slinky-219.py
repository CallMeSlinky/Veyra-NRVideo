"""ZIP only the verified portable payload, excluding user data and ANR assets."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ART = Path('E:/Veyra-dev/Veyra/anr-artifacts')
REPORT = ART / 'reports/slinky-219-20261115'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    stage = json.loads((REPORT / 'STAGE.json').read_text())
    final = json.loads((REPORT / 'FINAL.json').read_text())
    assert final['status'] == 'passed' and not stage['anrRuntimeIncluded']
    app = Path(stage['app'])
    manifest_path = app / 'package-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert not manifest['anrRuntimeIncluded']
    assert manifest['exeSha256'] == stage['exeSha256'] == sha(app / 'veyra_qml_ui.exe')
    rows = list(manifest['files'])
    assert [r['path'] for r in rows if r['path'].endswith('.cmd')] == [stage['launcher']]
    for row in rows:
        name = row['path']
        parts = PurePosixPath(name)
        assert not parts.is_absolute() and '..' not in parts.parts and ':' not in name and '\\' not in name
        assert not name.startswith(('runtime/anr/', 'user-data', 'logs/'))
        assert not name.endswith('.nrx') and parts.name != 'nr_fg.ini'
        assert sha(app / name) == row['sha256'], name
    rows.append(dict(path='package-manifest.json', sha256=sha(manifest_path)))
    archive_path = app.parent / (app.name + '.zip')
    partial = archive_path.with_suffix('.zip.partial')
    if archive_path.exists() or partial.exists():
        raise FileExistsError('Refusing to replace an existing archive or unfinished attempt')
    print('Packaging', len(rows), 'verified files', flush=True)
    with zipfile.ZipFile(partial, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            archive.write(app / row['path'], app.name + '/' + row['path'])
    print('Checking ZIP CRC and every payload SHA256', flush=True)
    with zipfile.ZipFile(partial) as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) == len(rows)
        for row in rows:
            with archive.open(app.name + '/' + row['path']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256'], row['path']
    partial.rename(archive_path)
    digest = sha(archive_path)
    archive_path.with_suffix('.zip.sha256').write_text(digest + '  ' + archive_path.name + '\n', encoding='ascii')
    result = dict(status='passed', archive=str(archive_path), bytes=archive_path.stat().st_size,
        sha256=digest, payloadFiles=len(rows), exeSha256=stage['exeSha256'],
        anrRuntimeIncluded=False, launcher=stage['launcher'], publicUpload=False,
        validation='ZIP CRC and every archived payload SHA256 verified against accepted portable manifest')
    (REPORT / 'ZIP.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
