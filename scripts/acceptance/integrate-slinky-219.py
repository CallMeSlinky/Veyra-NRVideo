"""Merge the upstream 2.1.6 -> 2.1.9 delta into the existing custom tree.

Prepare candidates and a byte-exact backup first; apply only conflict-free,
reviewed candidates. Dependencies and editor settings are never included.
"""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TASK = Path('E:/项目/Veyra/reports/slinky-219-20261115')
BASE = '20955b5c'
TARGET = 'v2.1.9'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob(revision, name):
    result = subprocess.run(['git', 'show', revision + ':' + name], cwd=ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else b''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare():
    TASK.mkdir(parents=True, exist_ok=False)
    original_names = git('ls-files', '--modified', '--others', '--exclude-standard', '-z').decode().split('\0')
    manifest = []
    with zipfile.ZipFile(TASK / 'original-local-changes.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(original_names)):
            if not name or name.startswith(('deps/', '.vscode/')):
                continue
            path = ROOT / name
            if path.is_file():
                data = path.read_bytes()
                archive.writestr(name, data)
                manifest.append(dict(path=name, sha256=digest(data)))
    (TASK / 'original-files.json').write_text(json.dumps(manifest, indent=2))
    (TASK / 'original.diff').write_bytes(git('diff', '--binary'))
    (TASK / 'revisions.json').write_text(json.dumps({r: git('rev-parse', r).decode().strip() for r in ['HEAD', BASE, TARGET]}, indent=2))
    rows = []
    scratch = TASK / 'merge-inputs'
    scratch.mkdir()
    for name in git('diff', '--name-only', BASE, TARGET).decode().splitlines():
        if name == 'AGENTS.md':
            rows.append(dict(path=name, action='preserve-local-instructions'))
            continue
        path = ROOT / name
        current = path.read_bytes() if path.is_file() else b''
        base, other = blob(BASE, name), blob(TARGET, name)
        normalize = lambda data: data.replace(b'\r\n', b'\n')
        if normalize(current) == normalize(other):
            action, merged = 'already-current', current
        elif normalize(current) == normalize(base):
            action, merged = 'upstream', other
        elif b'\0' in current + base + other:
            action, merged = 'binary-conflict', current
        else:
            for label, data in [('local', current), ('base', base), ('upstream', other)]:
                (scratch / label).write_bytes(normalize(data))
            result = subprocess.run(['git', 'merge-file', '-p', '-L', 'SLINKY', '-L', 'UPSTREAM_2_1_6', '-L', 'UPSTREAM_2_1_9',
                str(scratch / 'local'), str(scratch / 'base'), str(scratch / 'upstream')], cwd=ROOT, capture_output=True)
            if result.returncode < 0 or result.returncode >= 128:
                raise RuntimeError(result.stderr.decode(errors='replace'))
            action, merged = ('conflict' if result.returncode else 'merged'), result.stdout
        candidate = TASK / 'candidates' / name
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(merged)
        rows.append(dict(path=name, action=action, original_sha256=digest(current)))
    (TASK / 'integration-map.json').write_text(json.dumps(rows, indent=2))
    for row in rows:
        if 'conflict' in row['action']:
            print(row['action'], row['path'])
    print('Prepared', len(rows), 'candidates; backup contains', len(manifest), 'files')


def apply():
    if (TASK / 'applied.json').exists():
        raise FileExistsError('Already applied')
    rows = json.loads((TASK / 'integration-map.json').read_text())
    pending = []
    for row in rows:
        if row['action'] in ('preserve-local-instructions', 'already-current'):
            continue
        name = row['path']
        current = (ROOT / name).read_bytes() if (ROOT / name).is_file() else b''
        if digest(current) != row['original_sha256']:
            raise RuntimeError('Concurrent edit: ' + name)
        data = (TASK / 'candidates' / name).read_bytes()
        if any(marker in data for marker in [b'<<<<<<< SLINKY', b'=======\n', b'>>>>>>> UPSTREAM_2_1_9']):
            # Only flag separator lines when the candidate actually has a conflict start.
            if b'<<<<<<< SLINKY' in data or b'>>>>>>> UPSTREAM_2_1_9' in data:
                raise RuntimeError('Unresolved conflict: ' + name)
        if row['action'] == 'binary-conflict':
            raise RuntimeError('Unresolved binary conflict: ' + name)
        pending.append((name, data))
    for name, data in pending:
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (TASK / 'applied.json').write_text(json.dumps([dict(path=n, sha256=digest(d)) for n, d in pending], indent=2))
    print('Applied', len(pending), 'reviewed candidates')


def resolve():
    """Explicit resolutions retain local ANR and add upstream AMD FRC alongside it."""
    resolutions = {}
    pattern = re.compile(r'<<<<<<< SLINKY\n(.*?)=======\n(.*?)>>>>>>> UPSTREAM_2_1_9\n', re.S)
    folder = TASK / 'candidates'
    rows = json.loads((TASK / 'integration-map.json').read_text())
    for row in rows:
        if row['action'] != 'conflict':
            continue
        name = row['path']
        path = folder / name
        text = path.read_text(encoding='utf-8')
        choices = []
        def choose(match):
            local, upstream = match.group(1), match.group(2)
            if name == 'docs/WORKLOG.md':
                result = local + '\n' + upstream
            elif name == 'THIRD_PARTY_NOTICES.md':
                result = local + upstream[upstream.index('## AMD Advanced Media Framework'):]
            elif name.endswith('EnhancementSettings.h'):
                result = local + '    case FrameGenerationBackend::AmdFrc: return "AMD-FRC";\n'
            elif name.endswith('ExportFeaturePolicy.h') or name == 'qml/Veyra/NodePage.qml':
                result = upstream
            elif name == 'src/pipeline/EnhanceGraph.cpp':
                if '(!desc.noNgx' in upstream:
                    result = upstream.replace('||desc.frameGenerationBackend==engine::FrameGenerationBackend::Anr', '')
                elif 'needNgxCore' in local:
                    result = local.replace(') || desc_.convertVideoHdr()', ' && !amfFrc_) || desc_.convertVideoHdr()')
                elif 'fgCapsAvailable_' in local:
                    result = local.replace('!anrBackend_)', '!anrBackend_&&!amfFrc_)')
                elif 'return (anrBackend_' in local:
                    result = local.replace('|| fsrActive()', '|| amfFrcActive() || fsrActive()')
                else:
                    assert 'shutdown()' in local
                    result = local + upstream
            elif name == 'src/ui/PlayerUiFacade.cpp':
                result = upstream.replace('||requestedFgBackend_==veyra::engine::FrameGenerationBackend::Anr', '')
            elif name == 'src/ui/bridge/FrameGeneration.cpp':
                if 'QVariantMap' in local:
                    result = local.replace('        QVariantMap{{"id","vfg"}', '        QVariantMap{{"id","amdfrc"},{"label",tr("AMD FRC · 视频补帧 · 2X")}},\n        QVariantMap{{"id","vfg"}')
                elif '未知补帧后端' in local:
                    result = upstream
                elif 'value == QLatin1String' in local:
                    result = local + upstream
                else:
                    assert 'return 6;' in local
                    result = local.splitlines(keepends=True)[0] + upstream
            elif name == 'src/ui/bridge/Hardware.cpp':
                result = '#include "veyra/gfx/AmfFrcBackend.h"\n'
            elif name == 'src/ui/bridge/Preferences.cpp':
                result = '#include "veyra/gfx/AmfFrcBackend.h"\n' if '#include' in upstream else upstream[upstream.index('    // AMD FRC:'):]
            elif name == 'src/ui/bridge/Status.cpp':
                result = '\n'.join(line for line in upstream.splitlines() if 'FrameGenerationBackend::Anr' not in line) + '\n'
            elif name == 'tests/unit/AnrSettingsTests.cpp':
                result = local.replace('FrameGenerationBackend(6)', 'FrameGenerationBackend(7)').replace('caps.anr=false;', 'caps.anr=false;caps.fsr4=false;')
            else:
                raise RuntimeError('Unexpected conflict: ' + name)
            choices.append(dict(local=local, upstream=upstream, resolved=result))
            return result
        if name == 'i18n/catalog.json':
            local = json.loads((ROOT / name).read_text(encoding='utf-8'))
            base = json.loads(blob(BASE, name))
            upstream = json.loads(blob(TARGET, name))
            old = {e['zh']: e for e in base['entries']}
            custom = {e['zh']: e for e in local['entries']}
            merged = []
            for entry in upstream['entries']:
                key = entry['zh']
                if '顶级补帧质量' in key or '极差质量' in key:
                    continue
                merged.append(custom[key] if key in custom and custom[key] != old.get(key) else entry)
            present = {e['zh'] for e in merged}
            merged.extend(e for e in local['entries'] if e['zh'] not in present)
            local['entries'] = merged
            text = json.dumps(local, ensure_ascii=False, indent=1) + '\n'
        else:
            text = pattern.sub(choose, text)
        assert '<<<<<<< SLINKY' not in text, name
        path.write_text(text, encoding='utf-8', newline='\n')
        resolutions[name] = choices
    (TASK / 'resolutions.json').write_text(json.dumps(resolutions, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Resolved', len(resolutions), 'files')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--resolve' in sys.argv:
        resolve()
    elif '--apply' in sys.argv:
        apply()
    else:
        prepare()
