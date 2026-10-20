"""Project rules without paths: load on every turn. Priced from the turns of this project."""
import glob, os, re

from tiplib import main_turns, price_of

MIN_TOKENS = 2_000


def detect(calls, cwd, **_):
    rules = []
    for path in sorted(glob.glob(os.path.join(cwd, '.claude', 'rules', '*.md'))):
        name = os.path.basename(path)
        if name.lower() == 'readme.md':
            continue
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        head = text.split('---', 2)[1] if text.startswith('---') else ''
        if not re.search(r'^paths:', head, re.M):
            rules.append((name, len(text) // 4))  # shortcut: chars/4 token estimate
    toks = sum(t for _, t in rules)
    if toks < MIN_TOKENS:
        return None
    rules.sort(key=lambda r: -r[1])
    # what those tokens cost per turn, as a cache read, over this project's main turns
    turns = [c for lst in main_turns(calls).values() for c in lst if c.get('cwd') == os.path.normcase(os.path.normpath(cwd))]
    measured = sum(toks * price_of(c['model'])[2] / 1e6 for c in turns) or None
    names = ', '.join(f'{n} (~{t:,})' for n, t in rules[:6]) + (' and more' if len(rules) > 6 else '')
    return {
        'id': 'always-on-rules', 'kind': 'check', 'category': 'Fixed cost', 'confidence': 'estimate',
        'title': f'{len(rules)} rules in this repo load on every turn',
        'saving': None, 'measured': measured,
        'problem': f'{len(rules)} files in .claude/rules have no paths: header, so they load at startup like CLAUDE.md: '
                   f'about {toks:,} tokens on every turn. Largest: {names}.',
        'how': 'A rule with a paths: header loads only when Claude reads or edits a matching file. A rule that only '
               'matters for, say, Blazor pages then costs nothing in an API session. Rules that apply everywhere '
               '(security, secrets) stay always-on.',
        'assumption': 'Tokens estimated as characters / 4; the amount is that many tokens as a cache read on each turn '
                      'in this project. These files are shared with the team, so this tip changes nothing itself.',
        'change': None, 'actions': [], 'restart': False, 'guide': '3.3',
    }
