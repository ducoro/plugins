"""Validate the official Ducoro Skill + MCP plugin marketplace without third-party dependencies."""
import json
from pathlib import Path
import re
import sys

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
VERSION = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')
ENV_PLACEHOLDER = re.compile(r'\$\{[A-Z][A-Z0-9_]*\}')
SENSITIVE_KEY = re.compile(r'(token|secret|password|passwd|api[_-]?key|authorization)', re.I)
FORBIDDEN_ROOT_ENTRIES = ['.agents', '.claude-plugin']
FORBIDDEN_BUNDLE_ENTRIES = ['hooks', 'commands', 'agents', '.app.json', '.claude-plugin', '.codex-plugin']
BARE_DUCORO_CLI = re.compile(
    r'(?<![A-Za-z0-9_.-])ducoro\s+(?:board|feedback|media|local-folder|space|spaces|agent|agents|daemon|job|task|plan|plugin|skill|mcp|cli)\b|`ducoro`\s+CLI'
)


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


def extract_marketplace_plugins(catalog, label):
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


def parse_yaml_single_line_scalar(raw_value, skill, field):
    value = raw_value.strip()
    require(value, f'{skill}: {field} is required')
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except ValueError as error:
            raise ValueError(f'{skill}: invalid double-quoted YAML {field}: {error}') from error
        require(isinstance(parsed, str) and parsed.strip(), f'{skill}: {field} must be a non-empty string')
        return parsed
    if value.startswith("'"):
        require(len(value) >= 2 and value.endswith("'"), f'{skill}: unterminated single-quoted YAML {field}')
        inner = value[1:-1]
        require("'" not in inner.replace("''", ''), f'{skill}: invalid single-quoted YAML {field}')
        parsed = inner.replace("''", "'")
        require(parsed.strip(), f'{skill}: {field} must be a non-empty string')
        return parsed
    # Unquoted YAML plain scalars break standard YAML parsers on ": ", trailing ":",
    # inline " #" comments, or leading YAML syntax indicator characters.
    require(': ' not in value and not value.endswith(':'),
            f'{skill}: {field} contains ": " or trailing ":" and must be quoted in YAML frontmatter')
    require(' #' not in value,
            f'{skill}: {field} contains " #" comment sequence and must be quoted in YAML frontmatter')
    require(value[0] not in '&*!|>%@`[{?#,',
            f'{skill}: {field} starts with YAML syntax character "{value[0]}" and must be quoted')
    return value


def validate_cli_references(bundle, root):
    for file_path in sorted(bundle.rglob('*')):
        if not file_path.is_file():
            continue
        raw = file_path.read_bytes()
        if b'\x00' in raw:
            continue
        rel = file_path.relative_to(root).as_posix()
        for lineno, line in enumerate(raw.decode('utf-8', errors='replace').splitlines(), start=1):
            require(
                not BARE_DUCORO_CLI.search(line),
                f'{rel}:{lineno}: use "ducoro-cli" instead of bare "ducoro" CLI invocation',
            )


def validate(root):
    root = root.resolve()
    for path in root.rglob('*'):
        if '.git' in path.relative_to(root).parts:
            continue
        require(not path.is_symlink(), f'{path}: symlinks are not distributable')

    for forbidden in FORBIDDEN_ROOT_ENTRIES:
        require(not (root / forbidden).exists(),
                f'{forbidden}: external host marketplace directory is not allowed in the Ducoro marketplace')

    root_catalog = read_object(root / 'marketplace.json')
    root_names = extract_marketplace_plugins(root_catalog, 'marketplace.json')

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
                    f'{name}: unsupported entry "{forbidden}" is not allowed in Ducoro plugins')

        manifest = read_object(bundle / 'plugin.json')
        require(manifest.get('name') == name, f'{name} (plugin.json): manifest identity mismatch')
        require(isinstance(manifest.get('version'), str) and VERSION.fullmatch(manifest['version']),
                f'{name} (plugin.json): version must be major.minor.patch')
        require(isinstance(manifest.get('description'), str) and manifest['description'].strip(),
                f'{name} (plugin.json): description is required')
        require(manifest.get('license') == 'Apache-2.0', f'{name} (plugin.json): license must be Apache-2.0')
        require('apps' not in manifest, f'{name} (plugin.json): unsupported apps field is not allowed')
        require(manifest.get('skills') == './skills/', f'{name} (plugin.json): skills must be ./skills/')

        mcp_file = bundle / '.mcp.json'
        has_mcp_file = mcp_file.is_file()
        if has_mcp_file:
            require(manifest.get('mcpServers') == './.mcp.json',
                    f'{name} (plugin.json): mcpServers must be "./.mcp.json" when .mcp.json is present')
            validate_mcp_file(mcp_file, name)
            total_mcps += len(read_object(mcp_file)['mcpServers'])
        else:
            require('mcpServers' not in manifest,
                    f'{name} (plugin.json): mcpServers declared without .mcp.json')

        skills = bundle / 'skills'
        require(skills.is_dir(), f'{name}: missing skills directory')
        directories = sorted(skills.iterdir())
        require(directories, f'{name}: at least one skill is required')
        plugin_skill_names = set()
        for skill in directories:
            require(skill.is_dir() and NAME.fullmatch(skill.name), f'{skill}: invalid skill directory')
            require(skill.name not in plugin_skill_names, f'{name}: duplicate skill: {skill.name}')
            require(not (skill / 'agents').exists(),
                    f'{skill}: external host metadata directory "agents" is not allowed')
            plugin_skill_names.add(skill.name)
            total_skills += 1
            try:
                body = (skill / 'SKILL.md').read_text(encoding='utf-8')
            except OSError as error:
                raise ValueError(f'{skill}: missing SKILL.md') from error
            parts = body.split('---', 2)
            require(len(parts) == 3 and not parts[0].strip(), f'{skill}: missing YAML frontmatter')
            name_match = re.search(r'^name:[ \t]*([^\r\n]*)$', parts[1], re.M)
            require(name_match, f'{skill}: frontmatter name is required')
            parsed_name = parse_yaml_single_line_scalar(name_match[1], skill, 'name')
            require(parsed_name == skill.name, f'{skill}: frontmatter name must match directory')
            description = re.search(r'^description:[ \t]*(\S[^\r\n]*)$', parts[1], re.M)
            require(description, f'{skill}: description is required')
            parsed_description = parse_yaml_single_line_scalar(description[1], skill, 'description')
            require(len(parsed_description.encode('utf-16-le')) // 2 <= 300,
                    f'{skill}: description must fit the 300 UTF-16-unit injection limit')
            require(parts[2].strip(), f'{skill}: instructions are required')

        for readme in readmes:
            require(f'(plugins/{name})' in readme, f'{name}: missing README catalog link')

        validate_cli_references(bundle, root)

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
