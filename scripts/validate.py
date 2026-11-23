"""Validate the official Skill + MCP plugin marketplace without third-party dependencies."""
import json
from pathlib import Path
import re
import sys

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
VERSION = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')
ENV_PLACEHOLDER = re.compile(r'\$\{[A-Z][A-Z0-9_]*\}')
SENSITIVE_KEY = re.compile(r'(token|secret|password|passwd|api[_-]?key|authorization)', re.I)
FORBIDDEN_BUNDLE_ENTRIES = ['hooks', 'commands', 'agents', '.app.json']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: {error}') from error
    require(isinstance(value, dict), f'{path}: expected a JSON object')
    return value


def extract_marketplace_plugins(catalog, label, expect_string_source=False):
    require(catalog.get('name') == 'ducoro', f'{label}: marketplace identity must be ducoro')
    entries = catalog.get('plugins')
    require(isinstance(entries, list) and entries, f'{label}: catalog must contain plugins')
    names = []
    seen = set()
    for entry in entries:
        require(isinstance(entry, dict), f'{label}: plugin entry must be an object')
        name = entry.get('name')
        require(isinstance(name, str) and NAME.fullmatch(name), f'{label}: invalid plugin name: {name}')
        require(name not in seen, f'{label}: duplicate plugin: {name}')
        seen.add(name)
        source = entry.get('source')
        expected_path = f'./plugins/{name}'
        if expect_string_source:
            require(source == expected_path, f'{label}/{name}: source must be "{expected_path}"')
        else:
            require(isinstance(source, dict), f'{label}/{name}: source must be an object')
            require(source.get('source') == 'local', f'{label}/{name}: source must be local')
            require(source.get('path') == expected_path, f'{label}/{name}: source must point to its bundle')
        names.append(name)
    return names


def validate_mcp_file(mcp_path, plugin_name):
    data = read_object(mcp_path)
    servers = data.get('mcpServers')
    require(isinstance(servers, dict) and servers, f'{plugin_name}: .mcp.json must define a non-empty mcpServers object')
    for server_id, spec in servers.items():
        require(isinstance(server_id, str) and NAME.fullmatch(server_id),
                f'{plugin_name}: invalid MCP server id: {server_id}')
        require(isinstance(spec, dict), f'{plugin_name}/{server_id}: MCP server spec must be an object')
        has_command = isinstance(spec.get('command'), str) and spec['command'].strip()
        has_url = isinstance(spec.get('url'), str) and spec['url'].strip()
        require(has_command or has_url, f'{plugin_name}/{server_id}: MCP server must declare command or url')
        for container_key in ('env', 'headers'):
            mapping = spec.get(container_key)
            if mapping is None:
                continue
            require(isinstance(mapping, dict), f'{plugin_name}/{server_id}: {container_key} must be an object')
            for k, v in mapping.items():
                require(isinstance(v, str), f'{plugin_name}/{server_id}: {container_key}.{k} must be a string')
                if SENSITIVE_KEY.search(k):
                    require(ENV_PLACEHOLDER.search(v),
                            f'{plugin_name}/{server_id}: {container_key}.{k} must use an ${{ENV_VAR}} placeholder, never a raw secret')


def validate(root):
    root = root.resolve()
    for path in root.rglob('*'):
        if '.git' in path.relative_to(root).parts:
            continue
        require(not path.is_symlink(), f'{path}: symlinks are not distributable')

    root_catalog = read_object(root / 'marketplace.json')
    agents_catalog = read_object(root / '.agents/plugins/marketplace.json')
    claude_catalog = read_object(root / '.claude-plugin/marketplace.json')

    root_names = extract_marketplace_plugins(root_catalog, 'marketplace.json', expect_string_source=False)
    agents_names = extract_marketplace_plugins(agents_catalog, '.agents/plugins/marketplace.json', expect_string_source=False)
    claude_names = extract_marketplace_plugins(claude_catalog, '.claude-plugin/marketplace.json', expect_string_source=True)
    require(root_names == agents_names == claude_names,
            'marketplace.json, .agents/plugins/marketplace.json, and .claude-plugin/marketplace.json must list identical plugins in the same order')

    require((root / 'LICENSE').is_file(), 'LICENSE is required')
    readmes = [(root / name).read_text(encoding='utf-8') for name in ['README.md', 'README.zh-CN.md']]
    require('(README.zh-CN.md)' in readmes[0], 'English README must link to Chinese')
    require('(README.md)' in readmes[1], 'Chinese README must link to English')

    plugin_names = set(root_names)
    total_skills = 0
    total_mcps = 0

    for name in root_names:
        bundle = root / 'plugins' / name
        require(bundle.is_dir(), f'{name}: plugin directory is missing')
        license_path = bundle / 'LICENSE'
        require(license_path.is_file(), f'{name}: bundle LICENSE is required')
        require(license_path.read_bytes() == (root / 'LICENSE').read_bytes(),
                f'{name}: bundle must carry the full repository license')

        for forbidden in FORBIDDEN_BUNDLE_ENTRIES:
            require(not (bundle / forbidden).exists(),
                    f'{name}: host-specific entry "{forbidden}" is not allowed in portable plugins')

        open_manifest = read_object(bundle / 'plugin.json')
        codex_manifest = read_object(bundle / '.codex-plugin/plugin.json')
        claude_manifest = read_object(bundle / '.claude-plugin/plugin.json')

        for label, manifest in [
            ('plugin.json', open_manifest),
            ('.codex-plugin/plugin.json', codex_manifest),
            ('.claude-plugin/plugin.json', claude_manifest),
        ]:
            require(manifest.get('name') == name, f'{name} ({label}): manifest identity mismatch')
            require(isinstance(manifest.get('version'), str) and VERSION.fullmatch(manifest['version']),
                    f'{name} ({label}): version must be major.minor.patch')
            require(isinstance(manifest.get('description'), str) and manifest['description'].strip(),
                    f'{name} ({label}): description is required')
            require(manifest.get('license') == 'Apache-2.0', f'{name} ({label}): license must be Apache-2.0')
            require('apps' not in manifest, f'{name} ({label}): host-specific apps field is not allowed')

        for field in ('version', 'description'):
            require(open_manifest[field] == codex_manifest[field] == claude_manifest[field],
                    f'{name}: {field} must match across plugin.json, .codex-plugin/plugin.json, and .claude-plugin/plugin.json')

        for label, manifest in [('plugin.json', open_manifest), ('.codex-plugin/plugin.json', codex_manifest)]:
            require(manifest.get('skills') == './skills/', f'{name} ({label}): skills must be ./skills/')

        mcp_file = bundle / '.mcp.json'
        has_mcp_file = mcp_file.is_file()
        for label, manifest in [('plugin.json', open_manifest), ('.codex-plugin/plugin.json', codex_manifest)]:
            if has_mcp_file:
                require(manifest.get('mcpServers') == './.mcp.json',
                        f'{name} ({label}): mcpServers must be "./.mcp.json" when .mcp.json is present')
            else:
                require('mcpServers' not in manifest,
                        f'{name} ({label}): mcpServers declared without .mcp.json')
        if has_mcp_file:
            validate_mcp_file(mcp_file, name)
            total_mcps += len(read_object(mcp_file)['mcpServers'])

        skills = bundle / 'skills'
        require(skills.is_dir(), f'{name}: missing skills directory')
        directories = sorted(skills.iterdir())
        require(directories, f'{name}: at least one skill is required')
        plugin_skill_names = set()
        for skill in directories:
            require(skill.is_dir() and NAME.fullmatch(skill.name), f'{skill}: invalid skill directory')
            require(skill.name not in plugin_skill_names, f'{name}: duplicate skill: {skill.name}')
            plugin_skill_names.add(skill.name)
            total_skills += 1
            try:
                body = (skill / 'SKILL.md').read_text(encoding='utf-8')
            except OSError as error:
                raise ValueError(f'{skill}: missing SKILL.md') from error
            parts = body.split('---', 2)
            require(len(parts) == 3 and not parts[0].strip(), f'{skill}: missing YAML frontmatter')
            require(re.search(rf'^name:\s*{re.escape(skill.name)}\s*$', parts[1], re.M),
                    f'{skill}: frontmatter name must match directory')
            description = re.search(r'^description:[ \t]*(\S[^\r\n]*)$', parts[1], re.M)
            require(description, f'{skill}: description is required')
            require(len(description[1].encode('utf-16-le')) // 2 <= 300,
                    f'{skill}: description must fit the 300 UTF-16-unit injection limit')
            require(parts[2].strip(), f'{skill}: instructions are required')

        for readme in readmes:
            require(f'(plugins/{name})' in readme, f'{name}: missing README catalog link')

    on_disk = {p.name for p in (root / 'plugins').iterdir() if p.is_dir()}
    require(on_disk == plugin_names, 'every plugin directory must be registered exactly once')
    return len(plugin_names), total_skills, total_mcps


if __name__ == '__main__':
    try:
        plugins, skills, mcps = validate(Path(__file__).resolve().parents[1])
    except (ValueError, OSError) as error:
        print(f'Validation failed: {error}', file=sys.stderr)
        sys.exit(1)
    print(f'Validated {plugins} plugins, {skills} skills, and {mcps} MCP server declaration(s).')
