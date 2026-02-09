#!/usr/bin/env python3
"""
Generate static documentation site for MCP Security Hub.

Extracts data from README.md, docker-compose.yml, and individual MCP READMEs
to generate a searchable, filterable documentation website.
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Missing dependencies. Install with: pip install pyyaml jinja2")
    sys.exit(1)


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = PROJECT_ROOT / "docs"


def parse_readme_tables(readme_path: Path) -> dict:
    """Parse MCP server tables from main README.md."""
    content = readme_path.read_text()

    servers = []
    current_category = None

    # Find category headers and their tables
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match category headers like "### Reconnaissance (8 servers)"
        category_match = re.match(r'^### (.+?) \((\d+) servers?\)', line)
        if category_match:
            current_category = category_match.group(1)
            i += 1
            continue

        # Match table rows
        if current_category and line.startswith('| ['):
            # Parse: | [name](./path) | tools | description |
            match = re.match(r'\| \[([^\]]+)\]\(([^)]+)\) \| ([^|]*) \| ([^|]+) \|', line)
            if match:
                name = match.group(1)
                path = match.group(2).strip('./')
                tools = match.group(3).strip()
                description = match.group(4).strip()

                # Extract external link if present
                ext_link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', description)
                external_url = ext_link_match.group(2) if ext_link_match else None

                # Clean description (remove markdown links)
                clean_desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', description)

                servers.append({
                    'name': name,
                    'path': path,
                    'category': current_category,
                    'tools_count': tools if tools and tools != '-' else None,
                    'description': clean_desc,
                    'external_url': external_url,
                    'is_wrapper': 'Wrapper' in description or 'wrapper' in description,
                })

        i += 1

    return servers


def parse_docker_compose(compose_path: Path) -> dict:
    """Parse service details from docker-compose.yml."""
    content = compose_path.read_text()
    data = yaml.safe_load(content)

    services = {}
    for name, config in data.get('services', {}).items():
        services[name] = {
            'image': config.get('image', f'{name}:latest'),
            'build_context': config.get('build', {}).get('context') if isinstance(config.get('build'), dict) else config.get('build'),
            'ports': config.get('ports', []),
            'environment': list(config.get('environment', {}).keys()) if isinstance(config.get('environment'), dict) else config.get('environment', []),
            'cap_add': config.get('cap_add', []),
            'cap_drop': config.get('cap_drop', []),
            'volumes': config.get('volumes', []),
            'mem_limit': config.get('mem_limit'),
            'cpus': config.get('cpus'),
        }

    return services


def parse_mcp_readme(readme_path: Path) -> dict:
    """Parse individual MCP README for tool details."""
    if not readme_path.exists():
        return {}

    content = readme_path.read_text()

    # Extract tools from table
    tools = []
    in_tools_table = False
    for line in content.split('\n'):
        if '| Tool ' in line or '| Name ' in line:
            in_tools_table = True
            continue
        if in_tools_table:
            if line.startswith('|---'):
                continue
            if not line.startswith('|'):
                in_tools_table = False
                continue
            # Parse tool row
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2:
                tool_name = parts[0].strip('`')
                tool_desc = parts[1] if len(parts) > 1 else ''
                tools.append({'name': tool_name, 'description': tool_desc})

    # Extract environment variables
    env_vars = []
    in_env_table = False
    for line in content.split('\n'):
        if '| Variable ' in line or '| Environment ' in line:
            in_env_table = True
            continue
        if in_env_table:
            if line.startswith('|---'):
                continue
            if not line.startswith('|'):
                in_env_table = False
                continue
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2:
                env_vars.append({
                    'name': parts[0].strip('`'),
                    'description': parts[1] if len(parts) > 1 else '',
                    'required': 'required' in parts[2].lower() if len(parts) > 2 else False
                })

    return {
        'tools': tools,
        'environment_variables': env_vars,
    }


def generate_site():
    """Generate the static documentation site."""
    print("Generating documentation site...")

    # Parse data sources
    readme_path = PROJECT_ROOT / "README.md"
    compose_path = PROJECT_ROOT / "docker-compose.yml"

    servers = parse_readme_tables(readme_path)
    docker_services = parse_docker_compose(compose_path)

    # Enrich server data with docker-compose and individual README info
    for server in servers:
        service_name = server['name']

        # Add docker-compose info
        if service_name in docker_services:
            server['docker'] = docker_services[service_name]

        # Add individual README info
        readme_path = PROJECT_ROOT / server['path'] / "README.md"
        mcp_details = parse_mcp_readme(readme_path)
        server.update(mcp_details)

    # Group by category
    categories = {}
    for server in servers:
        cat = server['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(server)

    # Category metadata
    category_info = {
        'Reconnaissance': {'icon': 'bi-search', 'color': '#3498db'},
        'Web Security': {'icon': 'bi-globe', 'color': '#e74c3c'},
        'Binary Analysis': {'icon': 'bi-file-binary', 'color': '#9b59b6'},
        'Cloud Security': {'icon': 'bi-cloud', 'color': '#1abc9c'},
        'Secrets Detection': {'icon': 'bi-key', 'color': '#f39c12'},
        'Exploitation': {'icon': 'bi-bug', 'color': '#c0392b'},
        'OSINT': {'icon': 'bi-person-badge', 'color': '#2980b9'},
        'Threat Intelligence': {'icon': 'bi-shield-exclamation', 'color': '#8e44ad'},
        'Active Directory': {'icon': 'bi-diagram-3', 'color': '#27ae60'},
        'Password Cracking': {'icon': 'bi-unlock', 'color': '#d35400'},
        'Code Security': {'icon': 'bi-code-slash', 'color': '#16a085'},
        'Meta': {'icon': 'bi-gear', 'color': '#7f8c8d'},
    }

    # Setup Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template('index.html')

    # Render HTML
    html = template.render(
        servers=servers,
        categories=categories,
        category_info=category_info,
        total_servers=len(servers),
        total_tools=sum(int(re.sub(r'[^\d]', '', s.get('tools_count') or '0') or 0) for s in servers if s.get('tools_count')),
    )

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / 'css').mkdir(exist_ok=True)
    (OUTPUT_DIR / 'js').mkdir(exist_ok=True)

    # Write HTML
    (OUTPUT_DIR / 'index.html').write_text(html)
    print(f"  Generated: {OUTPUT_DIR / 'index.html'}")

    # Copy static assets
    css_src = TEMPLATES_DIR / 'style.css'
    js_src = TEMPLATES_DIR / 'app.js'

    if css_src.exists():
        (OUTPUT_DIR / 'css' / 'style.css').write_text(css_src.read_text())
        print(f"  Copied: {OUTPUT_DIR / 'css' / 'style.css'}")

    if js_src.exists():
        (OUTPUT_DIR / 'js' / 'app.js').write_text(js_src.read_text())
        print(f"  Copied: {OUTPUT_DIR / 'js' / 'app.js'}")

    # Generate JSON data for API access
    json_data = {
        'servers': servers,
        'categories': list(categories.keys()),
        'stats': {
            'total_servers': len(servers),
            'total_tools': sum(int(re.sub(r'[^\d]', '', s.get('tools_count') or '0') or 0) for s in servers if s.get('tools_count')),
        }
    }
    (OUTPUT_DIR / 'data.json').write_text(json.dumps(json_data, indent=2))
    print(f"  Generated: {OUTPUT_DIR / 'data.json'}")

    print(f"\nDone! Open {OUTPUT_DIR / 'index.html'} to view the site.")


if __name__ == '__main__':
    generate_site()
