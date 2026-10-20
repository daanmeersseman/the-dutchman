"""A top-level effortLevel is ignored for Opus 5.5. Configuration fix, no amount."""


def detect(calls, settings, **_):
    if 'effortLevel' not in settings or (settings.get('modelSettings') or {}).get('claude-opus-5-5'):
        return None
    if not any('opus-5-5' in c['model'] for c in calls):
        return None
    lvl = settings['effortLevel']
    return {
        'id': 'effort-model-settings', 'kind': 'fix', 'category': 'Models', 'confidence': 'config',
        'title': f'Your effort setting "{lvl}" is ignored by Opus 5.5',
        'saving': None, 'measured': None,
        'problem': f'~/.claude/settings.json has "effortLevel": "{lvl}" at the top level. Opus 5.5 only reads effort per '
                   'model, so it runs at its own default and ignores your choice.',
        'how': 'Effort sets how long the model thinks before answering. Thinking is billed as output and is most of '
               'the output. Setting it per model makes your choice take effect.',
        'assumption': None,
        'change': f'Adds "modelSettings": {{"claude-opus-5-5": {{"effortLevel": "{lvl}"}}}} to ~/.claude/settings.json. '
                  'The top-level effortLevel stays for the other models.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json',
                     'value': {'modelSettings': {'claude-opus-5-5': {'effortLevel': lvl}}}}],
        'min_version': '2.1.251', 'restart': True, 'guide': '6.4',
    }
