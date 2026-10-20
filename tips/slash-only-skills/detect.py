"""User skills Claude never picked itself in the window, with their description still in every turn."""
import glob, os, re

SKILL_DESC = re.compile(r'^description:\s*(.+?)(?=^\w[\w-]*:|\Z)', re.S | re.M)


def detect(sessions, home, days, **_):
    used = set().union(*(s['skills_used'] for s in sessions.values())) if sessions else set()
    idle = []
    for path in glob.glob(os.path.join(home, 'skills', '*', 'SKILL.md')):
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        head = text.split('---', 2)[1] if text.startswith('---') else ''
        if re.search(r'^disable-model-invocation:\s*true', head, re.M):
            continue
        name = os.path.basename(os.path.dirname(path))
        if name in used:
            continue
        m = SKILL_DESC.search(head)
        idle.append((name, len(m.group(1)) // 4 if m else 0))  # shortcut: chars/4 token estimate, fine for ranking
    if len(idle) < 2:
        return None
    idle.sort(key=lambda x: -x[1])
    toks = sum(t for _, t in idle)
    names = ', '.join(n for n, _ in idle)
    return {
        'id': 'slash-only-skills', 'kind': 'fix', 'category': 'Fixed cost', 'confidence': 'measured',
        'title': f'{len(idle)} skills sit in every turn but Claude never uses them',
        'saving': None, 'measured': None,
        'problem': f'Claude keeps the description of every skill in its context, so it can pick one when it fits. '
                   f'In {days} days it never picked {names}. Together that is about {toks:,} tokens on every turn.',
        'how': 'A skill marked "only when I type /name" leaves the context and still works with /name. Claude then '
               'never starts it by itself.',
        'assumption': None,
        'change': 'Adds "disable-model-invocation: true" to the frontmatter of the SKILL.md of the skills you pick, '
                  'in ~/.claude/skills/.',
        'choose': {'question': 'Which of these skills do you only start yourself with /name?',
                   'items': [n for n, _ in idle]},
        'actions': [{'op': 'frontmatter-set', 'file': os.path.join(home, 'skills', '{item}', 'SKILL.md'),
                     'key': 'disable-model-invocation', 'value': 'true'}],
        'restart': True, 'guide': '3.4',
    }
