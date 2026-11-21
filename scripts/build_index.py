#!/usr/bin/env python3
"""Write the catalog from each recipe's frontmatter.

  python3 scripts/build_index.py           # rewrite index.yml and the README.md catalog
  python3 scripts/build_index.py --check   # fail when either is out of date; change nothing

`index.yml` is the machine-readable catalog for coding agents and scripts. The
README.md catalog is the table between `<!-- CATALOG:START -->` and
`<!-- CATALOG:END -->`. Both come from the recipes' frontmatter, so they never
disagree with the recipes. Never edit either by hand.

Standard library only: no `pip install` is needed.
"""
import sys

from recipes_common import (
    CATEGORIES, CATEGORY_HEADINGS, REPOSITORY_ROOT, FrontmatterError, read_recipe, recipe_paths, yaml_scalar,
)

INDEX_PATH = REPOSITORY_ROOT / 'index.yml'
README_PATH = REPOSITORY_ROOT / 'README.md'
CATALOG_START = '<!-- CATALOG:START -->'
CATALOG_END = '<!-- CATALOG:END -->'
INDEX_HEADER = (
    '# The catalog of every recipe. Written by scripts/build_index.py from each recipe\'s frontmatter.\n'
    '# Never edit this file by hand: change the recipe, then run `python3 scripts/build_index.py`.\n'
)
PRODUCT_NAMES = {'stack': 'Stack', 'solo': 'Solo'}
# Plain words for each vetted_method in the README catalog; CONTRACT.md defines the methods.
VETTED_METHOD_WORDS = {
    'live-checkpoint': 'tried on a test system',
    'script-tests': 'scripts tested',
    'review-only': 'read and reviewed',
}


def load_recipes():
    """All recipes as dicts, sorted by category order, then id."""
    recipes = []
    for category, path in recipe_paths():
        try:
            fields, _ = read_recipe(path)
        except FrontmatterError as problem:
            raise SystemExit('%s: %s\nRun `python3 scripts/lint_recipes.py` for the full list of problems.'
                             % (path.relative_to(REPOSITORY_ROOT), problem))
        missing = [key for key in ('id', 'title', 'applies_to', 'summary', 'author') if key not in fields]
        if missing:
            raise SystemExit('%s: missing frontmatter field(s) %s\nRun `python3 scripts/lint_recipes.py`.'
                             % (path.relative_to(REPOSITORY_ROOT), ', '.join(missing)))
        fields['category'] = category
        fields['path'] = '%s/%s' % (category, path.name)
        recipes.append(fields)
    recipes.sort(key=lambda recipe: (CATEGORIES.index(recipe['category']), recipe['id']))
    return recipes


def index_text(recipes):
    if not recipes:
        return INDEX_HEADER + 'recipes: []\n'
    lines = [INDEX_HEADER.rstrip('\n'), 'recipes:']
    for recipe in recipes:
        lines.append('  - id: %s' % yaml_scalar(recipe['id']))
        lines.append('    title: %s' % yaml_scalar(recipe['title']))
        lines.append('    category: %s' % recipe['category'])
        lines.append('    path: %s' % recipe['path'])
        lines.append('    applies_to: [%s]' % ', '.join(recipe['applies_to']))
        lines.append('    summary: %s' % yaml_scalar(recipe['summary']))
        lines.append('    author: %s' % yaml_scalar(recipe['author']))
        if 'vetted_on' in recipe:
            lines.append('    vetted_on: %s' % yaml_scalar(recipe['vetted_on']))
        if 'vetted_against' in recipe:
            lines.append('    vetted_against:')
            for product, release in recipe['vetted_against'].items():
                lines.append('      %s: %s' % (product, yaml_scalar(release)))
        if 'vetted_method' in recipe:
            lines.append('    vetted_method: %s' % recipe['vetted_method'])
    return '\n'.join(lines) + '\n'


def table_cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def link_label(text):
    return table_cell(text).replace('[', '\\[').replace(']', '\\]')


def vetted_cell(recipe):
    if 'vetted_on' not in recipe:
        return 'Not checked yet'
    releases = ' and '.join('%s %s' % (PRODUCT_NAMES.get(product, product), release)
                            for product, release in recipe.get('vetted_against', {}).items())
    method = recipe.get('vetted_method', '')
    text = recipe['vetted_on']
    if releases:
        text += ', on ' + releases
    if method:
        text += ': ' + VETTED_METHOD_WORDS.get(method, method)
    return text


def catalog_text(recipes):
    sections = []
    for category in CATEGORIES:
        heading = '### %s' % CATEGORY_HEADINGS[category]
        in_category = [recipe for recipe in recipes if recipe['category'] == category]
        about = ''
        if (REPOSITORY_ROOT / category / 'README.md').is_file():
            about = 'About these guides: [%s/README.md](%s/README.md).\n\n' % (category, category)
        if not in_category:
            sections.append('%s\n\n%s_No recipes yet._\n' % (heading, about))
            continue
        rows = ['| Recipe | What it does | Works with | Checked |', '| --- | --- | --- | --- |']
        for recipe in in_category:
            applies = ', '.join(PRODUCT_NAMES.get(product, product) for product in recipe['applies_to'])
            rows.append('| [%s](%s) | %s | %s | %s |' % (
                link_label(recipe['title']), recipe['path'], table_cell(recipe['summary']),
                applies, table_cell(vetted_cell(recipe))))
        sections.append('%s\n\n%s%s\n' % (heading, about, '\n'.join(rows)))
    return '\n'.join(sections)


def readme_text(recipes):
    text = README_PATH.read_text(encoding='utf-8')
    start, end = text.find(CATALOG_START), text.find(CATALOG_END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit('README.md needs the lines %s and %s, in that order, around the catalog.'
                         % (CATALOG_START, CATALOG_END))
    before = text[:start + len(CATALOG_START)]
    after = text[end:]
    return '%s\n\n%s\n\n%s' % (before, catalog_text(recipes).rstrip('\n'), after)


def main(arguments):
    if arguments not in ([], ['--check']):
        print('Usage: build_index.py [--check]')
        return 2
    recipes = load_recipes()
    wanted = {INDEX_PATH: index_text(recipes), README_PATH: readme_text(recipes)}
    stale = [path for path, text in wanted.items()
             if not path.is_file() or path.read_text(encoding='utf-8') != text]
    if arguments == ['--check']:
        if stale:
            for path in stale:
                print('%s is out of date.' % path.relative_to(REPOSITORY_ROOT))
            print('Run `python3 scripts/build_index.py` and commit the result. '
                  'Never edit index.yml or the README.md catalog by hand.')
            return 1
        print('index.yml and the README.md catalog are up to date (%d recipes).' % len(recipes))
        return 0
    for path in stale:
        path.write_text(wanted[path], encoding='utf-8')
        print('Wrote %s' % path.relative_to(REPOSITORY_ROOT))
    if not stale:
        print('Already up to date (%d recipes).' % len(recipes))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
