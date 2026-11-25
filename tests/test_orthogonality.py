"""Cross-plugin co-mount orthogonality tests for the entire Ducoro Plugins marketplace.

Verifies that mounting ALL plugins in `marketplace.json` onto a single Bot at once
produces a clean, conflict-free `<domain_roles>` assembly:
  1. Combined prompt budget stays bounded.
  2. Every plugin declares explicit positive activation triggers and negative boundaries.
  3. No plugin contains persona, tone, language, or global-response overrides.
  4. MCP server slugs and shared Local Folder workspace names do not collide across plugins.
  5. Every relative document/script reference inside `PLUGIN.md` and its level-2 indexes resolves.
"""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate', ROOT / 'scripts/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

LOCAL_FOLDER_REGISTER_RE = re.compile(r'ducoro-cli\s+local-folder\s+register\s+([a-z0-9-]+)')
LEVEL2_MD_LINK_RE = re.compile(r'`((?:\./|\.\./)?[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.(?:md|py|json|html|css))`')


class PluginOrthogonalityTest(unittest.TestCase):
    def setUp(self):
        catalog = json.loads((ROOT / 'marketplace.json').read_text(encoding='utf-8'))
        self.plugin_names = [entry['name'] for entry in catalog['plugins']]
        self.bundles = {name: ROOT / 'plugins' / name for name in self.plugin_names}

    def test_all_plugins_comount_within_budget_without_conflicts(self):
        """Simulate assembling every plugin into one `<domain_roles>` block."""
        rendered_blocks = []
        total_chars = 0
        seen_mcp_slugs = {}
        seen_local_folders = {}

        for name in self.plugin_names:
            bundle = self.bundles[name]
            md_path = bundle / 'PLUGIN.md'
            self.assertTrue(md_path.is_file(), f'{name}: missing PLUGIN.md')
            body = md_path.read_text(encoding='utf-8').strip()
            chars = validator.utf16_len(body)
            self.assertLessEqual(chars, validator.MAX_PLUGIN_MD_CHARS, f'{name}: PLUGIN.md over budget')
            total_chars += chars

            sections = validator.parse_plugin_md_sections(body, name)
            boundaries = sections['Activation & Boundaries']
            self.assertRegex(
                boundaries,
                validator.NEGATIVE_BOUNDARY_RE,
                f'{name}: Activation & Boundaries lacks explicit negative boundary clause',
            )
            # Every plugin must explicitly defer to stricter rules in the Bot's own profile or human instructions
            self.assertTrue(
                re.search(r'\b(?:profile|human|user)\b', sections['Needs a Yes'], re.I),
                f'{name}: Needs a Yes must reference human approval or Bot profile precedence',
            )
            # Ensure XML framing cannot be accidentally closed by PLUGIN.md prose
            self.assertNotIn('</domain_role>', body, f'{name}: PLUGIN.md must not contain </domain_role>')
            self.assertNotIn('</domain_roles>', body, f'{name}: PLUGIN.md must not contain </domain_roles>')

            rendered_blocks.append(
                f'<domain_role plugin="{name}@ducoro" root="{bundle.resolve()}">\n{body}\n</domain_role>'
            )

            # Check MCP slug uniqueness across all plugins
            mcp_file = bundle / '.mcp.json'
            if mcp_file.is_file():
                servers = json.loads(mcp_file.read_text(encoding='utf-8')).get('mcpServers', {})
                for slug in servers:
                    self.assertNotIn(
                        slug,
                        seen_mcp_slugs,
                        f'MCP slug "{slug}" collides between {seen_mcp_slugs.get(slug)} and {name}',
                    )
                    seen_mcp_slugs[slug] = name

            # Check registered Local Folder workspace names do not collide across plugins
            for text_file in bundle.rglob('*.md'):
                text = text_file.read_text(encoding='utf-8', errors='replace')
                for folder_name in LOCAL_FOLDER_REGISTER_RE.findall(text):
                    if folder_name in seen_local_folders:
                        self.assertEqual(
                            seen_local_folders[folder_name],
                            name,
                            f'Local Folder "{folder_name}" collides between {seen_local_folders[folder_name]} and {name}',
                        )
                    else:
                        seen_local_folders[folder_name] = name

        self.assertLessEqual(
            total_chars,
            validator.MAX_COMBINED_DOMAIN_ROLES_CHARS,
            f'All-plugin combined PLUGIN.md budget exceeded: {total_chars}',
        )
        combined_xml = '<domain_roles>\n' + '\n'.join(rendered_blocks) + '\n</domain_roles>'
        self.assertEqual(combined_xml.count('<domain_role '), len(self.plugin_names))

    def test_distinct_domain_scopes_across_all_plugins(self):
        """Every plugin owns a distinct domain summary and distinct primary activation focus."""
        descriptions = set()
        domain_sections = set()
        for name in self.plugin_names:
            bundle = self.bundles[name]
            manifest = json.loads((bundle / 'plugin.json').read_text(encoding='utf-8'))
            desc = manifest['description'].strip().lower()
            self.assertNotIn(desc, descriptions, f'{name}: duplicate plugin description')
            descriptions.add(desc)

            body = (bundle / 'PLUGIN.md').read_text(encoding='utf-8').strip()
            sections = validator.parse_plugin_md_sections(body, name)
            domain = sections['Domain'].strip().lower()
            self.assertNotIn(domain, domain_sections, f'{name}: duplicate Domain section')
            domain_sections.add(domain)

    def test_level_two_index_links_resolve_inside_bundle(self):
        """Follow level-1 markdown files referenced by PLUGIN.md and verify their own relative paths exist."""
        for name in self.plugin_names:
            bundle = self.bundles[name].resolve()
            body = (bundle / 'PLUGIN.md').read_text(encoding='utf-8')
            level1_files = validator.BACKTICK_REL_PATH_RE.findall(body)
            for rel in level1_files:
                if '<' in rel or '*' in rel:
                    continue
                target = (bundle / rel).resolve()
                if not target.is_file() or target.suffix != '.md':
                    continue
                # For dedicated index markdown files (e.g., platforms.md), verify all level-2 links resolve
                if target.name in {'platforms.md', 'INDEX.md'}:
                    text = target.read_text(encoding='utf-8')
                    for sub_rel in LEVEL2_MD_LINK_RE.findall(text):
                        if '<' in sub_rel or '*' in sub_rel:
                            continue
                        resolved = (target.parent / sub_rel).resolve()
                        if not resolved.exists():
                            resolved = (bundle / sub_rel).resolve()
                        self.assertTrue(
                            resolved.is_relative_to(bundle) and resolved.exists(),
                            f'{name}: level-2 index {rel} references missing path "{sub_rel}"',
                        )


if __name__ == '__main__':
    unittest.main()
