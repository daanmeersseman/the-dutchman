"""@imports in your personal CLAUDE.md load the whole file on every turn; a plain path lets Claude read it when needed."""
import os, re

from tiplib import MIN_USD, main_turns, read_price

IMPORT = re.compile(r'^@(\S+)\s*$', re.M)
ITEM = re.compile(r'^[\w.-]+$')  # actions.py only takes plain names as items


def detect(calls, home, days, **_):
    path = os.path.join(home, 'CLAUDE.md')
    try:
        text = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None
    found = []
    for ref in IMPORT.findall(text):
        f = os.path.normpath(os.path.join(os.path.dirname(path), os.path.expanduser(ref)))
        if ITEM.match(ref) and os.path.isfile(f):
            found.append((ref, os.path.getsize(f) // 4))  # shortcut: chars/4 token estimate
    if not found:
        return None
    toks = sum(t for _, t in found)
    turns = [c for lst in main_turns(calls).values() for c in lst]
    paid = sum(toks * read_price(c) for c in turns)
    if paid < MIN_USD:
        return None
    names = ', '.join(r for r, _ in found)
    return {
        'id': 'claude-md-import', 'kind': 'fix', 'category': 'Fixed cost', 'confidence': 'measured',
        'title': f'Your CLAUDE.md imports {names} into every turn',
        'saving': None, 'measured': paid,
        'problem': f'~/.claude/CLAUDE.md pulls in {names} with @, so about {toks:,} tokens load on every turn of every '
                   f'session: ${paid:.2f} in {days} days, read from cache.',
        'how': 'A line that names the file instead ("Read RTK.md when the task needs it.") costs a few tokens. Claude '
               'opens the file when it is relevant.',
        'assumption': 'Claude will not always open the file when it would have helped. Keep the @ for rules that must hold '
                      'on every turn.',
        'change': 'Replaces the @ line of each file you pick with "Read ~/.claude/<file> when the task needs it." in '
                  '~/.claude/CLAUDE.md.',
        'choose': {'question': 'Which imports may Claude read only when needed?', 'items': [r for r, _ in found]},
        'actions': [{'op': 'line-replace', 'file': path, 'find': '@{item}',
                     'replace': 'Read ~/.claude/{item} when the task needs it.'}],
        'restart': True, 'guide': '3.2',
    }
