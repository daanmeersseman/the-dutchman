"""outputStyle is case-sensitive; "concise" silently falls back to Default."""


def detect(settings, **_):
    style = settings.get('outputStyle')
    if not isinstance(style, str) or style == 'Concise' or style.lower() != 'concise':
        return None
    return {
        'id': 'output-style-case', 'kind': 'fix', 'confidence': 'config',
        'title': 'Fix the spelling of your Concise output style',
        'saving': None, 'measured': None,
        'problem': f'~/.claude/settings.json has "outputStyle": "{style}". The name is case-sensitive, so Claude Code '
                   'silently uses the Default style.',
        'how': 'Concise makes Claude answer first, without "Let me..." and without a recap at the end.',
        'assumption': None,
        'change': 'Changes it to "outputStyle": "Concise" in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json', 'value': {'outputStyle': 'Concise'}}],
        'restart': True,
    }
