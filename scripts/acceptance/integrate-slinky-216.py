"""Prepare reviewable 2.1.6 candidates while retaining the local ANR backend."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TASK = Path('E:/Veyra-dev/Veyra/anr-artifacts/reports/slinky-216-20261114')
UPSTREAM = '20955b5c'
ANR = 'bc4cbfa8'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob(revision, path):
    result = subprocess.run(['git', 'show', revision + ':' + path], cwd=ROOT, capture_output=True)
    return result.stdout.replace(b'\r\n', b'\n') if result.returncode == 0 else b''


def merge(current, base, other, label):
    folder = TASK / 'merge-inputs'
    folder.mkdir(exist_ok=True)
    for name, data in [('local', current), ('base', base), ('upstream', other)]:
        (folder / name).write_bytes(data)
    result = subprocess.run(['git', 'merge-file', '-p', '-L', 'LOCAL', '-L', 'BASE', '-L', label,
                             str(folder / 'local'), str(folder / 'base'), str(folder / 'upstream')],
                            cwd=ROOT, capture_output=True)
    if result.returncode > 127: raise RuntimeError(result.stderr.decode())
    return result.stdout, result.returncode


def main():
    if '--apply' in sys.argv:
        apply_candidates()
        return
    if TASK.exists(): raise FileExistsError(TASK)
    TASK.mkdir(parents=True)
    names = git('diff', '--name-only', 'HEAD', UPSTREAM).decode().splitlines()
    anr_names = set(git('diff', '--name-only', ANR + '^', ANR).decode().splitlines())
    original_names = git('ls-files', '--modified', '--others', '--exclude-standard', '-z').decode().split('\0')
    protected = []
    with zipfile.ZipFile(TASK / 'original-local-changes.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(original_names)):
            if not name or name.startswith(('deps/', '.vscode/')): continue
            path = ROOT / name
            if path.is_file():
                data = path.read_bytes()
                archive.writestr(name, data)
                protected.append(dict(path=name, sha256=hashlib.sha256(data).hexdigest()))
    (TASK / 'original.diff').write_bytes(git('diff', '--binary'))
    (TASK / 'original-files.json').write_text(json.dumps(protected, indent=2))
    report = []
    for name in names:
        if name in ('AGENTS.md', 'docs/WORKLOG.md', 'tests/unit/AnrSettingsTests.cpp') or name.startswith(('include/veyra/ngx/AnrProvider', 'src/ngx/AnrProvider')):
            report.append(dict(path=name, action='excluded-upstream-ANR-or-local-history'))
            continue
        local = (ROOT / name).read_bytes().replace(b'\r\n', b'\n') if (ROOT / name).exists() else b''
        upstream = blob(UPSTREAM, name)
        filtered = upstream
        filtering_conflicts = 0
        if name in anr_names and not name.startswith('docs/') and name != 'i18n/catalog.json':
            filtered, filtering_conflicts = merge(upstream, blob(ANR, name), blob(ANR + '^', name), 'REMOVE_UPSTREAM_ANR')
        if filtering_conflicts:
            status = 'filter-conflict'
            merged = filtered
        elif name == 'i18n/catalog.json':
            upstream_json = json.loads(upstream)
            local_json = json.loads(local)
            # Keep the local translations for FG choices and all local ANR text.
            before = json.loads(blob(ANR + '^', name))
            after = json.loads(blob(ANR, name))
            old_keys = {e['zh'] for e in before['entries']}
            anr_keys = {e['zh'] for e in after['entries']} - old_keys
            upstream_json['entries'] = [e for e in upstream_json['entries'] if e['zh'] not in anr_keys and '顶级补帧质量' not in e['zh'] and '极差质量' not in e['zh']]
            present = {e['zh'] for e in upstream_json['entries']}
            for entry in local_json['entries']:
                if entry['zh'] not in present:
                    upstream_json['entries'].append(entry); present.add(entry['zh'])
            merged = (json.dumps(upstream_json, ensure_ascii=False, indent=1) + '\n').encode()
            status = 'merged-catalog-preserve-local-FG-labels'
        else:
            if name == 'src/ui/bridge/FrameGeneration.cpp':
                # Drop the later quality rankings as well as the original ANR addition.
                old = blob('2271bc97^', name)
                new = blob('2271bc97', name)
                # These two lines are the only implementation change in that commit.
                new_lines = new.decode().splitlines()
                old_lines = old.decode().splitlines()
                for new_line, old_line in zip(new_lines, old_lines):
                    if new_line != old_line:
                        filtered = filtered.replace(new_line.encode(), old_line.encode())
            merged, conflicts = merge(local, blob('HEAD', name), filtered, 'UPSTREAM_2_1_6')
            status = 'merge-conflict' if conflicts else 'ready'
        target = TASK / 'candidates' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(merged)
        report.append(dict(path=name, action=status))
    (TASK / 'integration-map.json').write_text(json.dumps(report, indent=2))
    print('Candidates:', len(report), 'conflicts:')
    for row in report:
        if 'conflict' in row['action']: print(row['action'], row['path'])


def apply_candidates():
    if (TASK / 'applied.json').exists():
        raise FileExistsError('Integration already applied; refusing to overwrite subsequent work')
    candidates = TASK / 'candidates'
    # Keep our adapter/license description and stock upstream persistence and
    # test interfaces. Neither preset codec contains the upstream provider.
    (candidates / 'THIRD_PARTY_NOTICES.md').write_bytes((ROOT / 'THIRD_PARTY_NOTICES.md').read_bytes())
    for name in ('src/engine/PresetLibrary.cpp', 'src/engine/PresetStore.cpp', 'tests/integration/RepairFgTests.cpp'):
        (candidates / name).write_bytes(blob(UPSTREAM, name))
    name = 'src/ui/bridge/FrameGeneration.cpp'
    source = (candidates / name).read_text(encoding='utf-8')
    start = source.index('<<<<<<< LOCAL\n')
    end = source.index('>>>>>>> REMOVE_UPSTREAM_ANR\n', start) + len('>>>>>>> REMOVE_UPSTREAM_ANR\n')
    source = source[:start] + source[end:]
    original = (ROOT / name).read_text(encoding='utf-8')
    begin = 'QVariantList QmlPlayerBridge::fgBackendChoices() const {'
    finish = 'QString QmlPlayerBridge::fgProviderText() const {'
    source = source[:source.index(begin)] + original[original.index(begin):original.index(finish)] + source[source.index(finish):]
    merged, conflicts = merge(original.encode(), blob('HEAD', name), source.encode(), 'UPSTREAM_2_1_6')
    # Choices were already restored above, so retain the known local block if
    # the three-way merge sees the same local ANR addition in both inputs.
    if conflicts: raise ValueError('Unresolved frame-generation bridge conflict')
    (candidates / name).write_bytes(merged)
    report = json.loads((TASK / 'integration-map.json').read_text())
    applied = []
    for row in report:
        if row['action'].startswith('excluded-'): continue
        name = row['path']
        data = (candidates / name).read_bytes()
        if b'<<<<<<< LOCAL' in data or b'>>>>>>> UPSTREAM' in data or b'>>>>>>> REMOVE_' in data:
            raise ValueError('Unresolved conflict: ' + name)
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        applied.append(name)
    (TASK / 'applied.json').write_text(json.dumps(applied, indent=2))
    print('Applied', len(applied), 'reviewed files')


if __name__ == '__main__':
    main()
