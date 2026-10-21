"""Hand-computed checks for analyze.py. Run: python test_analyze.py"""
import datetime as dt, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze
from tiplib import norm

NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)
X = 3  # the fixture's logs cover 10 days; amounts are per 30


def line(mid, model, stamp, sid, inp=0, out=0, read=0, w5=0, w1=0, side=False):
    return json.dumps({'type': 'assistant', 'timestamp': stamp, 'sessionId': sid, 'isSidechain': side, 'message': {
        'id': mid, 'model': model, 'content': [], 'usage': {
            'input_tokens': inp, 'output_tokens': out, 'cache_read_input_tokens': read,
            'cache_creation': {'ephemeral_5m_input_tokens': w5, 'ephemeral_1h_input_tokens': w1}}}})


class AnalyzeTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        proj = os.path.join(self.home, 'projects', 'p')
        os.makedirs(os.path.join(proj, 's1', 'subagents'))
        with open(os.path.join(proj, 's1.jsonl'), 'w', encoding='utf-8') as f:
            # 10 days of history, so tips are allowed
            f.write(line('old', 'claude-haiku-5-5', '2026-10-10T09:00:00Z', 's0', inp=1000) + '\n')
            # two main turns 20 minutes apart, each a full 1M-token rewrite on Opus
            f.write(line('a', 'claude-opus-5-5', '2026-10-19T10:00:00Z', 's1', w5=1_000_000) + '\n')
            f.write(line('b', 'claude-opus-5-5', '2026-10-19T10:20:00Z', 's1', w5=1_000_000) + '\n')
            # streaming duplicate of 'b' with more output: counted once, with the larger output
            f.write(line('b', 'claude-opus-5-5', '2026-10-19T10:20:00Z', 's1', w5=1_000_000, out=1000) + '\n')
        sub = os.path.join(proj, 's1', 'subagents', 'agent-x')
        with open(sub + '.jsonl', 'w', encoding='utf-8') as f:
            f.write(line('s', 'claude-opus-5-5', '2026-10-19T10:05:00Z', 's1', inp=1_000_000, side=True) + '\n')
        with open(sub + '.meta.json', 'w', encoding='utf-8') as f:
            json.dump({'agentType': 'general-purpose'}, f)
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'outputStyle': 'concise'}, f)

    def run_it(self):
        r = analyze.analyze(self.home, self.home, 30, now=NOW)
        return r, {t['id']: t for t in r['tips']}

    def test_dedupe_and_spend(self):
        r, _ = self.run_it()
        self.assertEqual(r['calls'], 4)
        # haiku 1000*0.1 + 2 * 1M*5 + 1000*20 + subagent 1M*4, per 1M
        self.assertAlmostEqual(r['spend'], (100 + 10_000_000 + 20_000 + 4_000_000) / 1e6, places=2)

    def test_subagent_saving_is_opus_minus_sonnet(self):
        _, tips = self.run_it()
        self.assertAlmostEqual(tips['subagent-model']['saving'], (4.0 - 2.0) * X, places=2)

    def test_amounts_are_per_30_days_of_logs(self):
        r, tips = self.run_it()
        self.assertEqual(r['history_days'], 10)
        # a window of 90 days with the same 10 days of logs gives the same amounts
        r90 = analyze.analyze(self.home, self.home, 90, now=NOW)
        self.assertEqual({t['id']: t['saving'] for t in r90['tips']}, {t['id']: t['saving'] for t in r['tips']})

    def test_cache_backtest(self):
        _, tips = self.run_it()
        # now: 5 + 5 + 0.02 output. 1h: first write 8, second becomes a read 0.2, output 0.02
        self.assertAlmostEqual(tips['cache-ttl-1h']['saving'], (10.02 - 8.22) * X, places=2)
        # the reminder about the same rewrites is not offered next to it
        self.assertNotIn('cache-expiry', tips)

    def test_config_tip(self):
        _, tips = self.run_it()
        self.assertIn('output-style-case', tips)

    def test_no_tips_without_history(self):
        r = analyze.analyze(self.home, self.home, 30, now=dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc))
        self.assertEqual(r['tips'], [])

    def test_long_sessions_is_a_reminder_with_skill(self):
        _, tips = self.run_it()
        t = tips['long-sessions']
        # both 1M-token Opus turns are past 250k; only the part above counts: 3/4 of 5 + 5.02
        self.assertAlmostEqual(t['measured'], 10.02 * 0.75 * X, places=2)
        self.assertEqual(t['kind'], 'reminder')
        self.assertEqual(t['reminder']['at'], 250_000)
        self.assertEqual(t['actions'][0]['op'], 'copy-file')

    def test_long_sessions_follows_the_chosen_limit(self):
        r = analyze.analyze(self.home, self.home, 30, now=NOW, context_limit=0)
        self.assertNotIn('long-sessions', {t['id'] for t in r['tips']})
        r = analyze.analyze(self.home, self.home, 30, now=NOW, context_limit=400_000)
        t = {t['id']: t for t in r['tips']}['long-sessions']
        self.assertEqual(t['reminder']['at'], 400_000)
        self.assertIn('400k', t['title'])

    def test_long_sessions_with_frugalitas_installs_nothing(self):
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'enabledPlugins': {'frugalitas@frugalitas': True}}, f)
        _, tips = self.run_it()
        self.assertEqual(tips['long-sessions']['actions'], [])
        self.assertIn('/frugal restart', tips['long-sessions']['reminder']['text'])

    def test_opusplan_saves_eleven_percent_of_opus(self):
        _, tips = self.run_it()
        # main sessions: 10.02 on Opus, all of it
        self.assertAlmostEqual(tips['opusplan']['saving'], 10.02 * 0.11 * X, places=2)
        # a sonnet default does not hide it when the logs show Opus
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'model': 'sonnet'}, f)
        self.assertIn('opusplan', self.run_it()[1])

    def test_cache_expiry_counts_rewrite_after_gap(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('ce', os.path.join(analyze.TIPS, 'cache-expiry', 'detect.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        calls, sessions = analyze.read_calls(self.home, '2026-10-01')
        # 20 min gap > 5 min TTL, second turn wrote 1M: 5 (write) - 0.2 (read) = 4.8, under the $5 floor
        self.assertIsNone(mod.detect(calls=calls, settings={}))
        main = [c for c in calls if not c['side'] and 'opus' in c['model']][-1]
        calls += [dict(main, ts='2026-10-19T11:00:00Z')]  # one more such turn: 9.6
        self.assertAlmostEqual(mod.detect(calls=calls, settings={})['measured'], 9.6, places=2)
        # the user's own stake: $20 hides it, 0 turns it off; over 15 days 9.6 is 19.2 per 30
        self.assertIsNone(mod.detect(calls=calls, settings={}, cache_stake=20))
        self.assertIsNone(mod.detect(calls=calls, settings={}, cache_stake=0))
        self.assertIsNotNone(mod.detect(calls=calls, settings={}, days=15, cache_stake=19))

    def test_every_tip_has_a_kind(self):
        _, tips = self.run_it()
        for t in tips.values():
            self.assertIn(t['kind'], ('fix', 'reminder', 'check'))
            self.assertEqual(t['change'] is None, t['actions'] == [] and 'reminder' not in t, t['id'])

    def test_settings_already_done(self):
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'promptCacheTtl': '1h', 'env': {'CLAUDE_CODE_SUBAGENT_MODEL': 'claude-sonnet-5-5'}}, f)
        _, tips = self.run_it()
        self.assertNotIn('cache-ttl-1h', tips)
        # set to Sonnet, yet the fixture's subagent ran on Opus this week: a check, nothing to apply
        self.assertEqual(tips['subagent-model']['kind'], 'check')
        self.assertEqual(tips['subagent-model']['actions'], [])
        # set to Opus on purpose: no tip
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'env': {'CLAUDE_CODE_SUBAGENT_MODEL': 'claude-opus-5-5'}}, f)
        self.assertNotIn('subagent-model', self.run_it()[1])

    def test_odd_log_lines_and_settings_hide_nothing(self):
        with open(os.path.join(self.home, 'projects', 'p', 's1.jsonl'), 'a', encoding='utf-8') as f:
            f.write('["timestamp"]\n"timestamp"\n{"timestamp": 1\n')
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8-sig') as f:
            json.dump({'env': 'x', 'modelSettings': [], 'permissions': 'y', 'enabledPlugins': None, 'hooks': 3}, f)
        r, tips = self.run_it()
        self.assertEqual(r['errors'], [])
        self.assertIn('opusplan', tips)

    def test_bom_settings_are_read(self):
        with open(os.path.join(self.home, 'settings.json'), 'w', encoding='utf-8-sig') as f:
            json.dump({'promptCacheTtl': '1h'}, f)
        self.assertNotIn('cache-ttl-1h', self.run_it()[1])

    def load(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, os.path.join(analyze.TIPS, name, 'detect.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_cold_resume_counts_only_gaps_of_an_hour(self):
        mod = self.load('cold-resume')
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        self.assertIsNone(mod.detect(calls=calls, settings={}, days=30))  # 20 min apart: cache-expiry, not this
        main = [c for c in calls if not c['side'] and 'opus' in c['model']][-1]
        calls += [dict(main, ts='2026-10-19T12:00:00Z'), dict(main, ts='2026-10-19T14:00:00Z')]
        # two resumes of a 1M write on Opus: 2 * (5 - 0.2)
        self.assertAlmostEqual(mod.detect(calls=calls, settings={}, days=30)['measured'], 9.6, places=2)
        self.assertTrue(mod.detect(calls=calls, settings={}, days=30)['reminder']['on_resume'])

    def test_autocompact_override_moves_to_window(self):
        mod = self.load('autocompact-override')
        self.assertIsNone(mod.detect(sessions={}, settings={'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': '80'}}, days=30))
        t = mod.detect(sessions={}, settings={'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': '30'}}, days=30)
        self.assertEqual(t['actions'][0]['value'], {'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': None}, 'autoCompactWindow': 300_000})

    def test_output_style_is_a_tenth_of_main_output(self):
        mod = self.load('output-style')
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        self.assertIsNone(mod.detect(calls=calls, settings={'outputStyle': 'Concise'}))
        calls = [dict(c, t=(0, 1_000_000, 0, 0, 0)) for c in calls if not c['side'] and 'opus' in c['model']]
        # two main Opus turns of 1M output at $20: 40, a tenth is 4
        self.assertAlmostEqual(mod.detect(calls=calls, settings={})['saving'], 4.0, places=2)

    def test_unused_plugins_skips_used_and_hooked(self):
        mod = self.load('unused-plugins')
        for name, kind in (('quiet', 'skills'), ('busy', 'skills'), ('hooked', 'hooks')):
            os.makedirs(os.path.join(self.home, 'cache', name, kind, 'thing'))
        json.dump({'plugins': {f'{n}@m': [{'installPath': os.path.join(self.home, 'cache', n)}] for n in ('quiet', 'busy', 'hooked')}},
                  open(os.path.join(self.home, 'plugins.json'), 'w'))
        os.makedirs(os.path.join(self.home, 'plugins'))
        os.replace(os.path.join(self.home, 'plugins.json'), os.path.join(self.home, 'plugins', 'installed_plugins.json'))
        sessions = {'s': {'names': {'busy:thing'}, 'mcp_used': set()}}
        settings = {'enabledPlugins': {'quiet@m': True, 'busy@m': True, 'hooked@m': True}}
        t = mod.detect(sessions=sessions, settings=settings, home=self.home, days=30)
        self.assertEqual(t['actions'][0]['value'], {'enabledPlugins': {'quiet@m': False}})

    def test_effort_tips(self):
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        calls = [dict(c, t=(0, 1_000_000, 0, 0, 0)) for c in calls if not c['side'] and 'opus' in c['model']]
        high = self.load('effort-too-high')
        self.assertIsNone(high.detect(calls=calls, settings={'modelSettings': {'claude-opus-5-5': {'effortLevel': 'medium'}}}))
        t = high.detect(calls=calls, settings={'modelSettings': {'claude-opus-5-5': {'effortLevel': 'xhigh'}}})
        # 2 main Opus turns of 1M output at $20: 40; medium writes 1/2.6 of it
        self.assertAlmostEqual(t['saving'], 40 * (1 - 1 / 2.6), places=2)
        ignored = self.load('effort-model-settings')
        self.assertIsNone(ignored.detect(calls=calls, settings={}))
        t = ignored.detect(calls=calls, settings={'effortLevel': 'high'})
        self.assertEqual(t['actions'][0]['value'], {'modelSettings': {'claude-opus-5-5': {'effortLevel': 'high'}}})
        self.assertIsNone(ignored.detect(calls=calls, settings={'effortLevel': 'high',
                                                                 'modelSettings': {'claude-opus-5-5': {'effortLevel': 'x'}}}))

    def test_output_style_case(self):
        mod = self.load('output-style-case')
        self.assertIsNone(mod.detect(settings={'outputStyle': 'Concise'}))
        self.assertIsNone(mod.detect(settings={'outputStyle': 'Explanatory'}))
        self.assertEqual(mod.detect(settings={'outputStyle': 'concise'})['actions'][0]['value'], {'outputStyle': 'Concise'})

    def test_always_on_rules_priced_on_this_project(self):
        mod = self.load('always-on-rules')
        rules = os.path.join(self.home, '.claude', 'rules')
        os.makedirs(rules)
        open(os.path.join(rules, 'big.md'), 'w').write('x' * 40_000)  # 10k tokens, no paths
        open(os.path.join(rules, 'scoped.md'), 'w').write('---\npaths:\n  - "*.cs"\n---\n' + 'x' * 40_000)
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        calls = [dict(c, cwd=norm(self.home)) for c in calls]
        t = mod.detect(calls=calls, cwd=self.home)
        # 10k tokens on 3 main turns: 2 Opus at 0.2, 1 Haiku at 0.01 per 1M
        self.assertAlmostEqual(t['measured'], 10_000 * (0.2 + 0.2 + 0.01) / 1e6, places=5)
        self.assertEqual(t['title'], '1 rule in this repo loads on every turn')
        self.assertIsNone(mod.detect(calls=calls, cwd=os.path.join(self.home, 'projects')))

    def test_rtk_counts_bash_output(self):
        mod = self.load('rtk')
        big = {'s': {'bash_chars': 1_000_000, 'bash_calls': 10}}
        self.assertIn('250,000 tokens', mod.detect(sessions=big, settings={})['problem'])
        self.assertIsNone(mod.detect(sessions=big, settings={'hooks': {'PreToolUse': [{'command': 'rtk hook'}]}}))
        self.assertIsNone(mod.detect(sessions={'s': {'bash_chars': 1000, 'bash_calls': 1}}, settings={}))

    def test_slash_only_skills_skips_used_and_marked(self):
        mod = self.load('slash-only-skills')
        for n, extra in (('a', ''), ('b', ''), ('used', ''), ('marked', 'disable-model-invocation: true\n')):
            os.makedirs(os.path.join(self.home, 'skills', n))
            open(os.path.join(self.home, 'skills', n, 'SKILL.md'), 'w').write(f'---\nname: {n}\ndescription: d\n{extra}---\n')
        t = mod.detect(sessions={'s': {'skills_used': {'used'}}}, home=self.home, days=30)
        self.assertEqual(t['choose']['items'], ['a', 'b'])

    def test_unused_mcp_counts_only_this_project(self):
        mod = self.load('unused-mcp')
        proj = os.path.join(self.home, 'proj')
        os.makedirs(os.path.join(proj, '.claude'))
        json.dump({'mcpServers': {'aspire': {}, 'pw': {}, 'off': {}}}, open(os.path.join(proj, '.mcp.json'), 'w'))
        json.dump({'enabledMcpjsonServers': ['aspire', 'pw']}, open(os.path.join(proj, '.claude', 'settings.json'), 'w'))
        # 'off' is approved in ~/.claude.json, which sits next to home
        claude_json = os.path.join(os.path.dirname(os.path.normpath(self.home)), '.claude.json')
        self.addCleanup(lambda: os.path.exists(claude_json) and os.remove(claude_json))
        json.dump({'projects': {proj.replace('\\', '/'): {'enabledMcpjsonServers': ['off']}}}, open(claude_json, 'w'))
        sessions = {'here': {'cwd': norm(proj), 'mcp_used': {'pw'}},
                    'elsewhere': {'cwd': norm(self.home), 'mcp_used': {'aspire'}}}
        t = mod.detect(sessions=sessions, cwd=proj, home=self.home, days=30)
        self.assertEqual(t['id'], 'unused-mcp:aspire,off')
        self.assertIn('are switched on', t['problem'])

    def test_unused_user_mcp_skips_denied(self):
        mod = self.load('unused-user-mcp')
        claude_json = os.path.join(os.path.dirname(os.path.normpath(self.home)), '.claude.json')
        self.addCleanup(lambda: os.path.exists(claude_json) and os.remove(claude_json))
        json.dump({'mcpServers': {'a': {}, 'b': {}, 'c': {}}}, open(claude_json, 'w'))
        t = mod.detect(sessions={'s': {'mcp_used': {'c'}}}, settings={'deniedMcpServers': [{'serverName': 'b'}]},
                       home=self.home, days=30)
        self.assertEqual(t['id'], 'unused-user-mcp:a')
        self.assertIn('a is set up', t['problem'])
        self.assertIsNone(mod.detect(sessions={}, settings={'deniedMcpServers': [{'serverName': n} for n in 'abc']},
                                     home=self.home, days=30))

    def test_playwright_agent_prices_what_later_turns_carry(self):
        mod = self.load('playwright-agent')
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        sessions = {'s1': {'pw_main': ['2026-10-19T10:00:00Z'] * 10}}
        t = mod.detect(calls=calls, sessions=sessions, home=self.home, days=30)
        # 10 results of 2k tokens, each carried into one later Opus turn at 0.2 per 1M: 0.004, under the floor
        self.assertIsNone(t)
        sessions = {'s1': {'pw_main': ['2026-10-19T10:00:00Z'] * 10_000}}
        t = mod.detect(calls=calls, sessions=sessions, home=self.home, days=30)
        self.assertAlmostEqual(t['saving'], 10_000 * 2_000 * 0.2 / 1e6, places=2)
        os.makedirs(os.path.join(self.home, 'agents'))
        open(os.path.join(self.home, 'agents', 'b.md'), 'w').write('---\ntools: mcp__playwright__*\n---\n')
        self.assertIsNone(mod.detect(calls=calls, sessions=sessions, home=self.home, days=30))

    def test_claude_md_import_replaces_only_picked_line(self):
        mod = self.load('claude-md-import')
        mod.MIN_USD = 0  # the fixture has only three main turns
        open(os.path.join(self.home, 'BIG.md'), 'w').write('x' * 400_000)  # about 100k tokens
        open(os.path.join(self.home, 'CLAUDE.md'), 'w').write('# me\n@BIG.md\n')
        calls, _ = analyze.read_calls(self.home, '2026-10-01')
        t = mod.detect(calls=calls, home=self.home, days=30)
        # 100k tokens on each of the 3 main turns: 2 on Opus at 0.2, 1 on Haiku at 0.01 per 1M
        self.assertAlmostEqual(t['measured'], 100_000 * (0.2 + 0.2 + 0.01) / 1e6, places=4)
        import actions
        r = actions.apply('i', t['actions'], ['BIG.md'], backups=os.path.join(self.home, 'b'))
        self.assertTrue(r['ok'], r)
        self.assertEqual(open(os.path.join(self.home, 'CLAUDE.md')).read(), '# me\nRead ~/.claude/BIG.md when the task needs it.\n')


if __name__ == '__main__':
    unittest.main()
