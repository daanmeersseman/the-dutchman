"""Bash output that enters the context unfiltered. Measured from the tool results in the logs."""
import json, shutil

from tiplib import has_hook


def detect(sessions, settings, **_):
    if has_hook(settings, 'rtk'):
        return None
    chars = sum(s.get('bash_chars', 0) for s in sessions.values())
    calls = sum(s.get('bash_calls', 0) for s in sessions.values())
    toks = chars // 4  # shortcut: chars/4 token estimate
    if toks < 200_000:
        return None
    installed = shutil.which('rtk') is not None
    return {
        'id': 'rtk', 'kind': 'check', 'category': 'Context', 'confidence': 'measured',
        'title': 'Condense command output before it enters the context',
        'saving': None, 'measured': None,
        'problem': f'{calls:,} Bash commands put about {toks:,} tokens of output into your conversations (builds, '
                   'tests, git, grep). Every later turn of that session reads it again.',
        'how': 'RTK is a hook that condenses that output (errors and signal kept, noise dropped) before Claude sees '
               'it. Measured for the guide: command output -73%.',
        'assumption': 'Re-read about 30 times on average for the guide; the saving depends on your commands.',
        'change': None, 'actions': [], 'restart': False, 'guide': '7.1',
        'next': 'Run: rtk init -g' if installed else 'Install RTK, then run: rtk init -g',
    }
