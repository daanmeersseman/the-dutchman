"""A low CLAUDE_AUTOCOMPACT_PCT_OVERRIDE compacts every few minutes; a window size is the setting meant for it."""
WINDOW = 300_000


from tiplib import dget


def detect(sessions, settings, days, **_):
    pct = dget(settings, 'env', 'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE')
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return None
    if pct >= 50:
        return None
    autos = sum(1 for s in sessions.values() for _, trig in s['compactions'] if trig == 'auto')
    window = settings.get('autoCompactWindow')
    return {
        'id': 'autocompact-override', 'kind': 'fix', 'confidence': 'config',
        'title': f'Stop auto-compact from firing at {pct:g}%',
        'saving': None, 'measured': None,
        'problem': f'~/.claude/settings.json sets CLAUDE_AUTOCOMPACT_PCT_OVERRIDE to {pct:g}. Claude compacted on its own '
                   f'{autos} times in {days} days. Each compaction is a full model call over the conversation, and it '
                   'summarizes at a moment you did not choose.',
        'how': 'A low percentage makes Claude compact long before the window is full, and again soon after. '
               'autoCompactWindow sets one size in tokens at which Claude compacts, so a session compacts only once it '
               'gets that big.',
        'assumption': None,
        'change': 'Removes CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from env in ~/.claude/settings.json' +
                  ('.' if window else f' and sets "autoCompactWindow": {WINDOW}.'),
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': None},
                               **({} if window else {'autoCompactWindow': WINDOW})}}],
        'restart': True,
    }
