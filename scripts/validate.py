"""Validate the official Ducoro Domain Role plugin marketplace without third-party dependencies."""
import json
from pathlib import Path
import re
import sys

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
VERSION = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')
ENV_PLACEHOLDER = re.compile(r'\$\{[A-Z][A-Z0-9_]*\}')
SENSITIVE_KEY = re.compile(r'(token|secret|password|passwd|api[_-]?key|authorization)', re.I)

MAX_PLUGIN_MD_CHARS = 4_000
MAX_COMBINED_DOMAIN_ROLES_CHARS = 20_000

REQUIRED_SECTIONS = (
    'Domain',
    'Activation & Boundaries',
    'Operating Loop',
    'Needs a Yes',
    'Resources & Tools',
)

FORBIDDEN_ROOT_ENTRIES = ['.agents', '.claude-plugin']
FORBIDDEN_BUNDLE_ENTRIES = ['hooks', 'commands', 'agents', '.app.json', '.claude-plugin', '.codex-plugin']
BARE_DUCORO_CLI = re.compile(
    r'(?<![A-Za-z0-9_.-])ducoro\s+(?:board|render|feedback|media|local-folder|space|spaces|agent|agents|daemon|job|task|plan|plugin|skill|mcp|cli)\b|`ducoro`\s+CLI'
)
DISALLOWED_PLUGIN_MD_OVERRIDES = (
    re.compile(r'\b(?:your persona is|your voice is|adopt a .+ tone)\b', re.I),
    re.compile(r'\b(?:always respond in|always reply in|always answer in)\b', re.I),
    re.compile(r'\b(?:override|ignore)\s+(?:the\s+)?(?:agent\s+)?profile\b', re.I),
    re.compile(r'\bignore\s+(?:all\s+)?other\s+plugins\b', re.I),
    re.compile(r'\balways\s+format\s+every\s+response\b', re.I),
)
NEGATIVE_BOUNDARY_RE = re.compile(
    r'\b(?:stay inactive|do not activate|never activate|out of scope|do not handle|do not use (?:this|for)|inactive for|leave .+ to|not for)\b',
    re.I,
)
H2_RE = re.compile(r'^##[ \t]+(.+?)[ \t]*$', re.M)
BACKTICK_REL_PATH_RE = re.compile(
    r'`((?:\./)?(?:references|playbooks|platforms|scripts|assets|skills|docs)/[^`\s()]+)`'
)
MARKDOWN_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)\s]+)\)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utf16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def read_object(path: Path):
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


def validate_mcp_file(mcp_path: Path, plugin_name: str, seen_mcp_slugs: dict):
    data = read_object(mcp_path)
    servers = data.get('mcpServers')
    require(isinstance(servers, dict) and servers, f'{plugin_name}: .mcp.json must define a non-empty mcpServers object')
    for server_id, spec in servers.items():
        require(isinstance(server_id, str) and NAME.fullmatch(server_id),
                f'{plugin_name}: invalid MCP server id: {server_id}')
        require(server_id not in seen_mcp_slugs,
                f'{plugin_name}: MCP server id "{server_id}" collides with plugin "{seen_mcp_slugs.get(server_id)}"')
        seen_mcp_slugs[server_id] = plugin_name
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
    return len(servers)


def parse_plugin_md_sections(body: str, plugin_name: str) -> dict:
    matches = list(H2_RE.finditer(body))
    headings = [m.group(1).strip() for m in matches]
    require(
        tuple(headings) == REQUIRED_SECTIONS,
        f'{plugin_name}: PLUGIN.md must contain exactly these ## sections in order: {list(REQUIRED_SECTIONS)} (got {headings})',
    )
    sections = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        heading = match.group(1).strip()
        require(content, f'{plugin_name}: PLUGIN.md section "## {heading}" must not be empty')
        sections[heading] = content
    return sections


def validate_plugin_md_paths(bundle: Path, plugin_name: str, body: str):
    bundle_resolved = bundle.resolve()
    candidates = set(BACKTICK_REL_PATH_RE.findall(body))
    for link_target in MARKDOWN_LINK_RE.findall(body):
        if link_target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        clean = link_target.split('#', 1)[0]
        if clean:
            candidates.add(clean)

    for rel in sorted(candidates):
        cleaned = rel.rstrip('.,;:')
        require(not cleaned.startswith('/') and '..' not in Path(cleaned).parts,
                f'{plugin_name}: PLUGIN.md path "{cleaned}" must stay inside the plugin root')
        if '<' in cleaned or '*' in cleaned:
            prefix = cleaned.split('<', 1)[0].split('*', 1)[0].rstrip('/')
            if prefix:
                target = (bundle_resolved / prefix).resolve()
                require(target.is_relative_to(bundle_resolved) and target.exists(),
                        f'{plugin_name}: PLUGIN.md template path "{cleaned}" base "{prefix}" does not exist')
            continue
        target = (bundle_resolved / cleaned).resolve()
        require(target.is_relative_to(bundle_resolved) and target.exists(),
                f'{plugin_name}: PLUGIN.md referenced path "{cleaned}" does not exist')


def validate_plugin_md(bundle: Path, plugin_name: str) -> tuple[int, dict]:
    md_path = bundle / 'PLUGIN.md'
    require(md_path.is_file() and not md_path.is_symlink(), f'{plugin_name}: PLUGIN.md is required')
    raw = md_path.read_text(encoding='utf-8')
    body = raw.strip()
    require(body, f'{plugin_name}: PLUGIN.md must not be empty')
    require(
        not body.startswith('---\n') and not body.startswith('---\r\n'),
        f'{plugin_name}: PLUGIN.md must not include YAML frontmatter (metadata lives in plugin.json)',
    )
    chars = utf16_len(body)
    require(
        chars <= MAX_PLUGIN_MD_CHARS,
        f'{plugin_name}: PLUGIN.md is {chars} UTF-16 code units, exceeding the {MAX_PLUGIN_MD_CHARS}-char budget',
    )
    sections = parse_plugin_md_sections(body, plugin_name)
    require(
        NEGATIVE_BOUNDARY_RE.search(sections['Activation & Boundaries']),
        f'{plugin_name}: PLUGIN.md "## Activation & Boundaries" must explicitly state when to stay inactive / out of scope',
    )
    for pattern in DISALLOWED_PLUGIN_MD_OVERRIDES:
        require(
            not pattern.search(body),
            f'{plugin_name}: PLUGIN.md must not override global persona, language, or Agent profile rules ({pattern.pattern})',
        )
    validate_plugin_md_paths(bundle, plugin_name, body)
    return chars, sections


def validate_cli_references(bundle: Path, root: Path):
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


def validate(root: Path):
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
    total_chars = 0
    total_mcps = 0
    seen_mcp_slugs = {}

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
        require('skills' not in manifest, f'{name} (plugin.json): legacy skills field is not allowed; use PLUGIN.md')

        mcp_file = bundle / '.mcp.json'
        has_mcp_file = mcp_file.is_file()
        if has_mcp_file:
            require(manifest.get('mcpServers') == './.mcp.json',
                    f'{name} (plugin.json): mcpServers must be "./.mcp.json" when .mcp.json is present')
            total_mcps += validate_mcp_file(mcp_file, name, seen_mcp_slugs)
        else:
            require('mcpServers' not in manifest,
                    f'{name} (plugin.json): mcpServers declared without .mcp.json')

        chars, _sections = validate_plugin_md(bundle, name)
        total_chars += chars

        for readme in readmes:
            require(f'(plugins/{name})' in readme, f'{name}: missing README catalog link')

        validate_cli_references(bundle, root)

    require(
        total_chars <= MAX_COMBINED_DOMAIN_ROLES_CHARS,
        f'Combined PLUGIN.md size across all plugins is {total_chars} chars, exceeding the {MAX_COMBINED_DOMAIN_ROLES_CHARS}-char co-mount budget',
    )

    on_disk = {p.name for p in (root / 'plugins').iterdir() if p.is_dir()}
    require(on_disk == plugin_names, 'every plugin directory must be registered exactly once')
    return len(plugin_names), total_chars, total_mcps


if __name__ == '__main__':
    try:
        plugins, total_chars, mcps = validate(Path(__file__).resolve().parents[1])
    except (ValueError, OSError) as error:
        print(f'Validation failed: {error}', file=sys.stderr)
        sys.exit(1)
    print(f'Validated {plugins} plugins ({total_chars} combined PLUGIN.md chars) and {mcps} MCP server declaration(s).')
