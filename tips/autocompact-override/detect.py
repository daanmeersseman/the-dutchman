"""A low CLAUDE_AUTOCOMPACT_PCT_OVERRIDE compacts every few minutes; a window size is the setting meant for it."""
WINDOW = 300_000


def detect(sessions, settings, days, **_):
    pct = (settings.get('env') or {}).get('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE')
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return None
    if pct >= 50:
        return None
    autos = sum(1 for s in sessions.values() for _, trig in s['compactions'] if trig == 'auto')
    window = settings.get('autoCompactWindow')
    return {
        'id': 'autocompact-override', 'kind': 'fix', 'category': 'Sessions', 'confidence': 'config',
        'title': f'Auto-compact fires at {pct:g}% of the window',
        'saving': None, 'measured': None,
        'problem': f'~/.claude/settings.json sets CLAUDE_AUTOCOMPACT_PCT_OVERRIDE to {pct:g}. Claude compacted on its own '
                   f'{autos} times in {days} days. Each compaction is a full model call over the conversation, and it '
                   'summarises at a moment you did not choose.',
        'how': 'autoCompactWindow sets the size at which Claude compacts, in tokens. It does what a low percentage was '
               'meant for, without compacting again right after.',
        'assumption': None,
        'change': 'Removes CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from env in ~/.claude/settings.json' +
                  ('.' if window else f' and sets "autoCompactWindow": {WINDOW}.'),
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': None},
                               **({} if window else {'autoCompactWindow': WINDOW})}}],
        'restart': True, 'guide': '4',
    }
