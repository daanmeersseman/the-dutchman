"""Checks for actions.py on a temporary folder. Run: python test_actions.py"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actions


class ActionsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.backups = os.path.join(self.dir, 'backups')
        self.settings = os.path.join(self.dir, 'settings.json')
        with open(self.settings, 'w', encoding='utf-8') as f:
            json.dump({'env': {'A': '1'}, 'model': 'opus'}, f)

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_merge_then_undo_restores_bytes(self):
        before = self.read(self.settings)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'env': {'B': '2'}}}], backups=self.backups)
        self.assertTrue(r['ok'], r)
        self.assertEqual(json.loads(self.read(self.settings)), {'env': {'A': '1', 'B': '2'}, 'model': 'opus'})
        self.assertTrue(actions.undo('t', backups=self.backups)['ok'])
        self.assertEqual(self.read(self.settings), before)

    def test_dry_writes_nothing_and_shows_diff(self):
        before = self.read(self.settings)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}}], backups=self.backups, dry=True)
        self.assertTrue(r['ok'])
        self.assertIn('+  "x": 1', r['message'])
        self.assertEqual(self.read(self.settings), before)
        self.assertFalse(os.path.exists(self.backups))

    def test_plan_lists_only_changed_lines(self):
        actions.write_json(self.settings, json.loads(self.read(self.settings)))  # as Claude Code writes it
        before = self.read(self.settings)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'model': 'sonnet'}}],
                          backups=self.backups, show=True)
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['message'].splitlines()[1:], ['  model: "opus" → "sonnet"'])
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'env': {'B': '2'}}}],
                          backups=self.backups, show=True)
        self.assertEqual(r['message'].splitlines()[1:], ['  env.B: (not set) → "2"'])
        md = os.path.join(self.dir, 'SKILL.md')
        open(md, 'w').write('---\nname: x\n---\nbody\n')
        r = actions.apply('f', [{'op': 'frontmatter-set', 'file': md, 'key': 'k', 'value': 'v'}],
                          backups=self.backups, show=True)
        self.assertEqual(r['message'].splitlines()[1:], ['  +k: v'])
        new = os.path.join(self.dir, 'new', 'SKILL.md')
        src = os.path.join(self.dir, 'src.md')
        open(src, 'w').write('a\nb\n')
        r = actions.apply('c', [{'op': 'copy-file', 'src': src, 'dest': new}], backups=self.backups, show=True)
        self.assertTrue(r['message'].endswith('(new file, 2 lines)'), r)
        self.assertEqual(self.read(self.settings), before)
        self.assertFalse(os.path.exists(self.backups))
        self.assertFalse(os.path.exists(new))

    def test_null_removes_key_and_objects_in_list(self):
        actions.apply('n', [{'op': 'json-merge', 'file': self.settings, 'value': {'env': {'A': None}}},
                            {'op': 'json-list', 'file': self.settings, 'key': 'denied', 'add': [{'serverName': 'x'}]},
                            {'op': 'json-list', 'file': self.settings, 'key': 'denied', 'add': [{'serverName': 'x'}]}],
                      backups=self.backups)
        self.assertEqual(json.loads(self.read(self.settings)), {'env': {}, 'model': 'opus', 'denied': [{'serverName': 'x'}]})

    def test_line_replace_keeps_line_ending_and_fails_when_absent(self):
        md = os.path.join(self.dir, 'CLAUDE.md')
        with open(md, 'w', newline='') as f:
            f.write('a\r\n@RTK.md\r\nb\r\n')
        act = [{'op': 'line-replace', 'file': md, 'find': '@RTK.md', 'replace': 'Read it.'}]
        self.assertTrue(actions.apply('l', act, backups=self.backups)['ok'])
        with open(md, newline='') as f:
            self.assertEqual(f.read(), 'a\r\nRead it.\r\nb\r\n')
        self.assertFalse(actions.apply('l2', act, backups=self.backups)['ok'])

    def test_copy_into_new_folder_undo_removes_it(self):
        src = os.path.join(self.dir, 'src.md')
        open(src, 'w').write('hi')
        dest = os.path.join(self.dir, 'skills', 'handover', 'SKILL.md')
        self.assertTrue(actions.apply('c', [{'op': 'copy-file', 'src': src, 'dest': dest}], backups=self.backups)['ok'])
        self.assertEqual(self.read(dest), 'hi')
        actions.undo('c', backups=self.backups)
        self.assertFalse(os.path.exists(os.path.dirname(dest)))

    def test_json_list_moves_server(self):
        local = os.path.join(self.dir, 'local.json')
        json.dump({'enabledMcpjsonServers': ['aspire', 'x'], 'disabledMcpjsonServers': ['pw']}, open(local, 'w'))
        actions.apply('m', [{'op': 'json-list', 'file': local, 'key': 'enabledMcpjsonServers', 'remove': ['aspire']},
                            {'op': 'json-list', 'file': local, 'key': 'disabledMcpjsonServers', 'add': ['aspire']}],
                      backups=self.backups)
        self.assertEqual(json.loads(self.read(local)), {'enabledMcpjsonServers': ['x'], 'disabledMcpjsonServers': ['pw', 'aspire']})

    def test_frontmatter_per_item(self):
        for n in ('a', 'b'):
            os.makedirs(os.path.join(self.dir, n))
            open(os.path.join(self.dir, n, 'SKILL.md'), 'w').write('---\nname: x\ndescription: y\n---\nbody\n')
        act = [{'op': 'frontmatter-set', 'file': os.path.join(self.dir, '{item}', 'SKILL.md'),
                'key': 'disable-model-invocation', 'value': 'true'}]
        self.assertTrue(actions.apply('s', act, ['a'], backups=self.backups)['ok'])
        self.assertIn('disable-model-invocation: true\n---\nbody', self.read(os.path.join(self.dir, 'a', 'SKILL.md')))
        self.assertNotIn('disable', self.read(os.path.join(self.dir, 'b', 'SKILL.md')))

    def test_bad_item_is_refused(self):
        for bad in ('../evil', '..', '.', 'a/b'):
            r = actions.apply('s', [{'op': 'copy-file', 'src': 'x', 'dest': '{item}'}], [bad], backups=self.backups)
            self.assertFalse(r['ok'], bad)

    def test_failure_leaves_nothing_changed(self):
        before = self.read(self.settings)
        r = actions.apply('f', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}},
                                {'op': 'copy-file', 'src': os.path.join(self.dir, 'missing'), 'dest': self.settings}],
                          backups=self.backups)
        self.assertFalse(r['ok'])
        self.assertEqual(self.read(self.settings), before)

    def test_undo_refuses_after_later_edit_of_a_text_file(self):
        md = os.path.join(self.dir, 'CLAUDE.md')
        open(md, 'w').write('@RTK.md\n')
        actions.apply('l', [{'op': 'line-replace', 'file': md, 'find': '@RTK.md', 'replace': 'x'}], backups=self.backups)
        open(md, 'a').write('more\n')
        self.assertFalse(actions.undo('l', backups=self.backups)['ok'])
        self.assertEqual(self.read(md), 'x\nmore\n')

    def test_undo_after_a_second_tip_keeps_the_second(self):
        a = [{'op': 'json-merge', 'file': self.settings, 'value': {'promptCacheTtl': '1h', 'env': {'X': '1'}}}]
        b = [{'op': 'json-merge', 'file': self.settings, 'value': {'model': 'opusplan', 'env': {'Y': '2'}}},
             {'op': 'json-list', 'file': self.settings, 'key': 'denied', 'add': ['p']}]
        self.assertTrue(actions.apply('a', a, backups=self.backups)['ok'])
        self.assertTrue(actions.apply('b', b, backups=self.backups)['ok'])
        self.assertTrue(actions.undo('a', backups=self.backups)['ok'])
        self.assertEqual(json.loads(self.read(self.settings)),
                         {'env': {'A': '1', 'Y': '2'}, 'model': 'opusplan', 'denied': ['p']})
        # Claude Code adds a key and an item of its own; b still undoes, its list item goes, the other stays
        data = json.loads(self.read(self.settings))
        data['theme'] = 'dark'
        data['denied'].append('q')
        actions.write_json(self.settings, data)
        self.assertTrue(actions.undo('b', backups=self.backups)['ok'])
        self.assertEqual(json.loads(self.read(self.settings)),
                         {'env': {'A': '1'}, 'model': 'opus', 'theme': 'dark', 'denied': ['q']})

    def test_undo_refuses_when_its_own_key_changed(self):
        actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'model': 'sonnet'}}], backups=self.backups)
        actions.write_json(self.settings, {'env': {'A': '1'}, 'model': 'haiku'})
        r = actions.undo('t', backups=self.backups)
        self.assertFalse(r['ok'])
        self.assertIn('model', r['message'])
        self.assertEqual(json.loads(self.read(self.settings))['model'], 'haiku')

    def test_undo_removes_objects_it_created(self):
        actions.apply('t', [{'op': 'json-merge', 'file': self.settings,
                             'value': {'modelSettings': {'claude-opus-5-5': {'effortLevel': 'medium'}}}}], backups=self.backups)
        data = json.loads(self.read(self.settings))
        data['other'] = 1
        actions.write_json(self.settings, data)
        self.assertTrue(actions.undo('t', backups=self.backups)['ok'])
        self.assertEqual(json.loads(self.read(self.settings)), {'env': {'A': '1'}, 'model': 'opus', 'other': 1})

    def test_bom_and_nested_null(self):
        with open(self.settings, 'w', encoding='utf-8-sig') as f:
            json.dump({'model': 'opus'}, f)
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'env': {'A': None, 'B': '1'}}}],
                          backups=self.backups)
        self.assertTrue(r['ok'], r)
        self.assertEqual(json.loads(self.read(self.settings)), {'model': 'opus', 'env': {'B': '1'}})

    def test_copy_into_existing_folder_keeps_it(self):
        src = os.path.join(self.dir, 'src.md')
        open(src, 'w').write('hi')
        folder = os.path.join(self.dir, 'agents')
        os.makedirs(folder)
        actions.apply('c', [{'op': 'copy-file', 'src': src, 'dest': os.path.join(folder, 'a.md')}], backups=self.backups)
        actions.undo('c', backups=self.backups)
        self.assertTrue(os.path.isdir(folder))

    def test_json_list_refuses_a_non_list(self):
        actions.write_json(self.settings, {'denied': 'x'})
        r = actions.apply('t', [{'op': 'json-list', 'file': self.settings, 'key': 'denied', 'add': ['y']}], backups=self.backups)
        self.assertFalse(r['ok'])

    def test_invalid_json_is_not_overwritten(self):
        open(self.settings, 'w').write('{broken')
        r = actions.apply('t', [{'op': 'json-merge', 'file': self.settings, 'value': {'x': 1}}], backups=self.backups)
        self.assertFalse(r['ok'])
        self.assertEqual(self.read(self.settings), '{broken')


if __name__ == '__main__':
    unittest.main()
