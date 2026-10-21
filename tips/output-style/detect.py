"""No output style at all. The saving is small (most output is thinking), so it is an estimate on visible text only."""
from tiplib import cost, main_turns, price_of

SHARE = 0.10  # Concise mostly drops the recap; assume a tenth of the output


def detect(calls, settings, **_):
    if settings.get('outputStyle'):
        return None  # a chosen style, or a misspelled one (output-style-case)
    out = sum(cost((0, c['t'][1], 0, 0, 0), price_of(c['model'])) for lst in main_turns(calls).values() for c in lst)
    save = out * SHARE
    if save < 1:
        return None
    return {
        'id': 'output-style', 'kind': 'fix', 'confidence': 'estimate',
        'title': 'Use the Concise output style',
        'saving': save, 'measured': out,
        'problem': f'You use the Default output style. Your sessions wrote ${out:.2f} of output, not counting subagents.',
        'how': 'Concise makes Claude answer first, without "Let me..." and without a recap at the end. You mostly save '
               'reading time; the cost effect is small.',
        'assumption': f'About {SHARE:.0%} less output. Most output is thinking, which a style does not change.',
        'change': 'Sets "outputStyle": "Concise" in ~/.claude/settings.json.',
        'actions': [{'op': 'json-merge', 'file': '~/.claude/settings.json', 'value': {'outputStyle': 'Concise'}}],
        'restart': True,
    }
