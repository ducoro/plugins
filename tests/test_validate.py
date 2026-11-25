import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate', ROOT / 'scripts/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class CatalogValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['marketplace.json', 'README.md', 'README.zh-CN.md', 'LICENSE']:
            shutil.copy2(ROOT / name, self.root / name)
        shutil.copytree(ROOT / 'plugins', self.root / 'plugins')

    def test_current_catalog(self):
        plugins, total_chars, mcps = validator.validate(self.root)
        self.assertEqual(plugins, 5)
        self.assertGreater(total_chars, 0)
        self.assertLessEqual(total_chars, validator.MAX_COMBINED_DOMAIN_ROLES_CHARS)
        self.assertEqual(mcps, 1)

    def test_marketplace_boundaries(self):
        original = json.loads((self.root / 'marketplace.json').read_text())
        cases = {
            'duplicate identity': lambda m: m['plugins'].append(copy.deepcopy(m['plugins'][0])),
            'path traversal': lambda m: m['plugins'][0]['source'].update(path='../escape'),
            'absolute path': lambda m: m['plugins'][0]['source'].update(path='/tmp/escape'),
            'remote entry': lambda m: m['plugins'][0]['source'].update(source='git'),
            'entry mismatch': lambda m: m['plugins'][0].update(name='different'),
            'missing plugin': lambda m: m['plugins'][0]['source'].update(path='./plugins/missing'),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(original)
                mutate(manifest)
                (self.root / 'marketplace.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
        (self.root / 'marketplace.json').write_text(json.dumps(original))

        for forbidden_dir in ('.agents', '.claude-plugin'):
            with self.subTest(forbidden_dir=forbidden_dir):
                target = self.root / forbidden_dir
                target.mkdir()
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
                target.rmdir()

    def test_bundle_and_mcp_boundaries(self):
        plugin = self.root / 'plugins/docs-lookup'
        manifest_path = plugin / 'plugin.json'
        original = json.loads(manifest_path.read_text())
        for field, value in [
            ('name', 'different'),
            ('version', 'latest'),
            ('license', 'unknown'),
            ('skills', './skills/'),
            ('mcpServers', './.mcp.json'),
            ('apps', './bindings.json'),
        ]:
            with self.subTest(field=field):
                manifest = {**original, field: value}
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
        manifest_path.write_text(json.dumps(original))

        for forbidden in ('hooks', 'commands', 'agents', '.app.json', '.claude-plugin', '.codex-plugin'):
            with self.subTest(forbidden=forbidden):
                target = plugin / forbidden
                if forbidden.endswith('.json'):
                    target.write_text('{}')
                else:
                    target.mkdir()
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
                if target.is_dir():
                    target.rmdir()
                else:
                    target.unlink()

        # Raw secret in .mcp.json is rejected.
        mcp_path = self.root / 'plugins/starter-template/.mcp.json'
        original_mcp = json.loads(mcp_path.read_text())
        bad_mcp = copy.deepcopy(original_mcp)
        bad_mcp['mcpServers']['example-http']['headers']['Authorization'] = 'Bearer sk-live-raw-secret'
        mcp_path.write_text(json.dumps(bad_mcp))
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        mcp_path.write_text(json.dumps(original_mcp))

        # Colliding MCP server slug across two plugins is rejected.
        other_mcp = plugin / '.mcp.json'
        other_mcp.write_text(json.dumps(original_mcp))
        manifest_path.write_text(json.dumps({**original, 'mcpServers': './.mcp.json'}))
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        other_mcp.unlink()
        manifest_path.write_text(json.dumps(original))

        # Symlink inside bundle is rejected.
        (plugin / 'escaped').symlink_to(self.root.parent)
        with self.assertRaises(ValueError):
            validator.validate(self.root)

    def test_plugin_md_contract_and_guards(self):
        plugin_md = self.root / 'plugins/docs-lookup/PLUGIN.md'
        original = plugin_md.read_text(encoding='utf-8')

        # Missing PLUGIN.md fails
        plugin_md.unlink()
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # YAML frontmatter is rejected
        plugin_md.write_text('---\nname: docs-lookup\n---\n\n' + original, encoding='utf-8')
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # Over 4,000 UTF-16 code units fails
        plugin_md.write_text(original + '\n' + 'x' * 4001, encoding='utf-8')
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # Missing required section fails
        plugin_md.write_text(original.replace('## Needs a Yes', '## Approvals'), encoding='utf-8')
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # Persona/profile override language fails
        plugin_md.write_text(original + '\nAlways respond in pirate English.\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # Broken relative resource link fails
        plugin_md.write_text(original + '\n- `references/does-not-exist.md`: broken link.\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            validator.validate(self.root)
        plugin_md.write_text(original, encoding='utf-8')

        # Missing README link fails
        readme = self.root / 'README.zh-CN.md'
        readme.write_text(readme.read_text().replace('(plugins/docs-lookup)', '(plugins/missing)'))
        with self.assertRaises(ValueError):
            validator.validate(self.root)

    def test_bare_ducoro_cli_invocation_is_rejected(self):
        plugin_md = self.root / 'plugins/docs-lookup/PLUGIN.md'
        original = plugin_md.read_text(encoding='utf-8')
        for bad_snippet in [
            '\nRun `ducoro feedback send "bug"`.\n',
            '\nRun `ducoro media upload file.jpg --json`.\n',
            '\nWhen `ducoro` CLI is unavailable, print text.\n',
        ]:
            with self.subTest(snippet=bad_snippet.strip()):
                plugin_md.write_text(original + bad_snippet, encoding='utf-8')
                with self.assertRaises(ValueError):
                    validator.validate(self.root)
        plugin_md.write_text(
            original + '\nUse `ducoro-cli feedback send "ok"`, `window.ducoro`, and Ducoro Board SDK.\n',
            encoding='utf-8',
        )
        validator.validate(self.root)


if __name__ == '__main__':
    unittest.main()
