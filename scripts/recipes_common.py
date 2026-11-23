"""Shared helpers for lint_recipes.py and build_index.py.

Standard library only, so the checks need no `pip install` in CI or on a
contributor's machine. The frontmatter parser reads only the small YAML shape
that CONTRACT.md allows: `key: value` lines, an inline list such as
`[stack, solo]`, and one mapping (`vetted_against`) whose children are indented
`product: version` lines.
"""
import json
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

# The order of this list is the order of the catalog and of index.yml.
CATEGORIES = ['services', 'watchdog-checks', 'providers', 'frameworks', 'migrations']

CATEGORY_HEADINGS = {
    'services': 'Services',
    'watchdog-checks': 'Watchdog checks',
    'providers': 'Providers',
    'frameworks': 'Frameworks',
    'migrations': 'Migrations',
}

PRODUCTS = ['stack', 'solo']
VETTED_FIELDS = ['vetted_on', 'vetted_against', 'vetted_method']
VETTED_METHODS = ['live-checkpoint', 'script-tests', 'review-only']

TRUST_BANNER = [
    '> [!IMPORTANT]',
    '> Reviewed once when added. Recipes are not re-tested on every Stack or '
    'Solo release and are outside core support.',
]


class FrontmatterError(Exception):
    """The frontmatter is missing or is not in the shape CONTRACT.md allows."""


def recipe_paths(root=REPOSITORY_ROOT):
    """Every recipe file, as (category, path): `<category>/*.md` except README.md."""
    found = []
    for category in CATEGORIES:
        folder = Path(root) / category
        if folder.is_dir():
            for path in sorted(folder.glob('*.md')):
                if path.name != 'README.md':
                    found.append((category, path))
    return found


def split_frontmatter(text):
    """Return (frontmatter_text, body_text). Raise FrontmatterError when absent."""
    lines = text.split('\n')
    if not lines or lines[0].rstrip() != '---':
        raise FrontmatterError('the file must start with a "---" line that opens the frontmatter')
    for number in range(1, len(lines)):
        if lines[number].rstrip() == '---':
            return '\n'.join(lines[1:number]), '\n'.join(lines[number + 1:])
    raise FrontmatterError('the frontmatter has no closing "---" line')


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        return re.sub(r'\\(["\\])', r'\1', inner)
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _parse_inline_list(value):
    inner = value.strip()[1:-1]
    return [_unquote(item) for item in inner.split(',') if item.strip()]


def parse_frontmatter(frontmatter_text):
    """Parse the frontmatter text into a dict. Raise FrontmatterError on any other shape."""
    result = {}
    current_mapping = None
    for number, line in enumerate(frontmatter_text.split('\n'), start=1):
        if not line.isprintable():
            raise FrontmatterError('frontmatter line %d holds a non-printable character' % number)
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indented = line[0] in ' \t'
        match = re.match(r'^\s*([A-Za-z0-9_-]+):(?:\s+(.*))?$', line)
        if not match:
            raise FrontmatterError('frontmatter line %d is not "key: value": %r' % (number, line))
        key, value = match.group(1), (match.group(2) or '').strip()
        if indented:
            if current_mapping is None:
                raise FrontmatterError('frontmatter line %d is indented under no key' % number)
            if key in result[current_mapping]:
                raise FrontmatterError('frontmatter repeats %s under %s' % (key, current_mapping))
            result[current_mapping][key] = _unquote(value)
            continue
        if key in result:
            raise FrontmatterError('frontmatter repeats the key %s' % key)
        current_mapping = None
        if value == '':
            result[key] = {}
            current_mapping = key
        elif value.startswith('['):
            if not value.endswith(']'):
                raise FrontmatterError('frontmatter line %d opens a list and does not close it' % number)
            result[key] = _parse_inline_list(value)
        else:
            result[key] = _unquote(value)
    return result


def read_recipe(path):
    """Return (frontmatter dict, body text) for a recipe file."""
    frontmatter_text, body = split_frontmatter(Path(path).read_text(encoding='utf-8'))
    return parse_frontmatter(frontmatter_text), body


def yaml_scalar(value):
    """Write a string as a double-quoted YAML scalar so strings never turn into numbers or booleans."""
    return json.dumps(str(value), ensure_ascii=False)
