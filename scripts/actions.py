"""Apply or undo a tip's actions. Every file is backed up first; undo puts it back.

Usage: python actions.py apply <tip-id> [--items a,b] [--dry]    (the tip's actions as JSON on stdin)
       python actions.py undo <tip-id>
Prints JSON: {"ok": bool, "message": str}. With --dry nothing is written; the message is the diff it would make.

Actions (paths absolute or with ~; "{item}" is replaced by each chosen item):
  {"op": "json-merge", "file", "value"}             deep-merge an object into a JSON file
  {"op": "json-list", "file", "key", "add", "remove"} add/remove strings in a top-level list
  {"op": "copy-file", "src", "dest"}                 copy a file, creating folders
  {"op": "frontmatter-set", "file", "key", "value"}  set a key in a Markdown file's YAML frontmatter
"""
import argparse, difflib, hashlib, json, os, re, shutil, sys, tempfile

BACKUPS = os.path.expanduser(os.path.join('~', '.claude', 'burndown', 'backups'))
ITEM = re.compile(r'^[\w.-]+$')  # items become path parts: no separators, no ..


def norm(path):
    return os.path.normpath(os.path.expanduser(path))


def sha(path):
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        text = f.read()
    return json.loads(text) if text.strip() else {}  # invalid JSON raises: nothing is written


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def frontmatter_set(path, key, value):
    with open(path, encoding='utf-8', newline='') as f:
        text = f.read()
    m = re.match(r'---\r?\n(.*?)\r?\n---', text, re.S)
    if not m:
        raise ValueError(f'{path} has no frontmatter')
    eol = '\r\n' if '\r\n' in text else '\n'
    head, line = m.group(1), f'{key}: {value}'
    rx = re.compile(rf'^{re.escape(key)}:.*?(?=\r?$)', re.M)
    head = rx.sub(line, head) if rx.search(head) else head + eol + line
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text[:m.start(1)] + head + text[m.end(1):])


def run(a):
    op = a['op']
    if op == 'json-merge':
        f = norm(a['file'])
        write_json(f, merge(read_json(f), a['value']))
    elif op == 'json-list':
        f = norm(a['file'])
        data = read_json(f)
        lst = [x for x in data.get(a['key']) or [] if x not in a.get('remove', [])]
        lst += [x for x in a.get('add', []) if x not in lst]
        data[a['key']] = lst
        write_json(f, data)
    elif op == 'copy-file':
        dest = norm(a['dest'])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(norm(a['src']), dest)
    elif op == 'frontmatter-set':
        frontmatter_set(norm(a['file']), a['key'], a['value'])
    else:
        raise ValueError(f'unknown action {op}')


def expand(actions, items):
    for it in items:
        if not ITEM.match(it):
            raise ValueError(f'invalid item {it!r}')
    out = []
    for a in actions:
        s = json.dumps(a)
        if '{item}' in s:
            out += [json.loads(s.replace('{item}', it)) for it in items]
        else:
            out.append(a)
    return out


def target(a):
    return norm(a.get('file') or a['dest'])


def restore(manifest, d):
    for m in manifest:
        if m['backup']:
            shutil.copyfile(os.path.join(d, m['backup']), m['file'])
        elif os.path.exists(m['file']):
            os.remove(m['file'])
            try:
                os.rmdir(os.path.dirname(m['file']))  # only when empty, e.g. a skill folder we created
            except OSError:
                pass


def folder(tip_id, backups):
    return os.path.join(backups, re.sub(r'[^\w.-]', '_', tip_id))


def text(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read().splitlines(keepends=True)


def preview(steps, files):
    """Run the steps on temporary copies and return the unified diff."""
    tmp = tempfile.mkdtemp(prefix='burndown-')
    try:
        copies = {f: os.path.join(tmp, str(i), os.path.basename(f)) for i, f in enumerate(files)}
        for f, c in copies.items():
            os.makedirs(os.path.dirname(c))
            if os.path.exists(f):
                shutil.copyfile(f, c)
        for a in steps:
            a = dict(a)
            a['file' if 'file' in a else 'dest'] = copies[target(a)]
            run(a)
        return ''.join(''.join(difflib.unified_diff(text(f), text(c), f, f + ' (after)')) for f, c in copies.items())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply(tip_id, actions, items=(), backups=BACKUPS, dry=False):
    d = folder(tip_id, backups)
    if os.path.exists(os.path.join(d, 'manifest.json')):
        return {'ok': False, 'message': 'This tip is already applied. Undo it first.'}
    try:
        steps = expand(actions, list(items))
    except ValueError as e:
        return {'ok': False, 'message': f'Nothing changed: {e}'}
    files = list(dict.fromkeys(target(a) for a in steps))
    if dry:
        try:
            return {'ok': True, 'message': preview(steps, files) or 'No change: already in place.'}
        except Exception as e:
            return {'ok': False, 'message': f'Would fail: {e}'}
    os.makedirs(d, exist_ok=True)
    manifest = []
    for i, f in enumerate(files):
        backup = str(i) if os.path.exists(f) else None
        if backup:
            shutil.copyfile(f, os.path.join(d, backup))
        manifest.append({'file': f, 'backup': backup})
    try:
        for a in steps:
            run(a)
    except Exception as e:  # leave nothing half-done
        restore(manifest, d)
        shutil.rmtree(d, ignore_errors=True)
        return {'ok': False, 'message': f'Nothing changed: {e}'}
    for m in manifest:
        m['after'] = sha(m['file'])
    with open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    return {'ok': True, 'message': 'Changed: ' + ', '.join(files)}


def undo(tip_id, backups=BACKUPS):
    d = folder(tip_id, backups)
    try:
        with open(os.path.join(d, 'manifest.json'), encoding='utf-8') as f:
            manifest = json.load(f)
    except OSError:
        return {'ok': False, 'message': 'No backup of this tip, so nothing to undo.'}
    changed = [m['file'] for m in manifest if sha(m['file']) != m['after']]
    if changed:  # restoring would throw away edits made after the tip
        return {'ok': False, 'message': f'Not undone: {", ".join(changed)} changed since. The backup is in {d}.'}
    restore(manifest, d)
    shutil.rmtree(d, ignore_errors=True)
    return {'ok': True, 'message': 'Restored: ' + ', '.join(m['file'] for m in manifest)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['apply', 'undo'])
    ap.add_argument('tip')
    ap.add_argument('--items', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if a.cmd == 'apply':
        res = apply(a.tip, json.loads(sys.stdin.read()), [x for x in a.items.split(',') if x], dry=a.dry)
    else:
        res = undo(a.tip)
    print(json.dumps(res, ensure_ascii=False))
