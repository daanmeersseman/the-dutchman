"""Bash output that enters the context unfiltered. Measured from the tool results in the logs."""
import shutil

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
        'id': 'rtk', 'kind': 'check', 'confidence': 'config',
        'title': 'Condense command output before it enters the context',
        'saving': None, 'measured': None,
        'problem': f'{calls:,} Bash commands put about {toks:,} tokens of output into your conversations (builds, '
                   'tests, git, grep). Every later turn of that session reads it again.',
        'how': 'RTK is a hook that condenses that output before Claude sees it. It keeps errors and signal and drops '
               'the noise. In a measured test it cut command output by 73%.',
        'assumption': 'In that test each output was read again about 30 times. The saving depends on your commands.',
        'change': None, 'actions': [], 'restart': False,
        'next': 'Run: rtk init -g' if installed else 'Install RTK, then run: rtk init -g',
    }
