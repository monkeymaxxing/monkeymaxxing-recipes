#!/usr/bin/env python3
"""Check every recipe against CONTRACT.md.

  python3 scripts/lint_recipes.py
  python3 scripts/lint_recipes.py --check-pr-vetting <base-ref>

The first form checks, for each `<category>/*.md` recipe (README.md files are
not recipes): the frontmatter fields, the trust banner right after the title,
and, for `services/` and `watchdog-checks/`, the six required headings in
order. It also checks that relative Markdown links in the repository's
Markdown files point at files that exist.

The second form is for pull requests. It fails when the pull request adds or
changes `vetted_on`, `vetted_against`, or `vetted_method` in any recipe,
because only a maintainer may write those fields. The reason: they tell a
reader how far to trust a recipe.

Standard library only: no `pip install` is needed.
"""
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

from recipes_common import (
    CATEGORIES, PRODUCTS, REPOSITORY_ROOT, TRUST_BANNER, VETTED_FIELDS, VETTED_METHODS,
    FrontmatterError, parse_frontmatter, read_recipe, recipe_paths, split_frontmatter,
)

REQUIRED_FIELDS = ['id', 'title', 'category', 'applies_to', 'summary', 'author']
ALLOWED_FIELDS = REQUIRED_FIELDS + VETTED_FIELDS
ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]*$')
SECTIONS_WITH_REQUIRED_HEADINGS = ['services', 'watchdog-checks']
REQUIRED_HEADINGS = [
    '## When to use this (and when you don\'t need it)',
    '## What it adds and what it costs',
    '## Data, security, and backups',
    '## Apply steps',
    '## Verification check',
    '## Clean removal',
]
RECIPE_PATH_PATTERN = re.compile(r'^(%s)/[^/]+\.md$' % '|'.join(CATEGORIES))


def relative(path):
    return str(Path(path).relative_to(REPOSITORY_ROOT))


def lines_outside_code_fences(body):
    """Yield (line_number, line) for lines that are not inside a ``` or ~~~ fence."""
    fence = None
    for number, line in enumerate(body.split('\n'), start=1):
        stripped = line.lstrip()
        marker = stripped[:3]
        if fence is None and marker in ('```', '~~~'):
            fence = marker
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        yield number, line


def check_frontmatter(category, path, fields, errors):
    name = relative(path)
    for key in fields:
        if key not in ALLOWED_FIELDS:
            errors.append('%s: unknown frontmatter field "%s"' % (name, key))
    for key in REQUIRED_FIELDS:
        if key not in fields:
            errors.append('%s: missing frontmatter field "%s"' % (name, key))
    for key in ('title', 'summary', 'author'):
        if key in fields and (not isinstance(fields[key], str) or not fields[key].strip()):
            errors.append('%s: "%s" must be a non-empty string' % (name, key))
    recipe_id = fields.get('id')
    if 'id' in fields:
        if not isinstance(recipe_id, str) or not recipe_id.strip():
            errors.append('%s: "id" must be a non-empty string' % name)
        else:
            if not ID_PATTERN.match(recipe_id):
                errors.append('%s: id "%s" must use lowercase letters, digits, and hyphens (^[a-z0-9][a-z0-9-]*$)'
                              % (name, recipe_id))
            if recipe_id != path.stem:
                errors.append('%s: id "%s" must match the file name "%s"' % (name, recipe_id, path.stem))
    if 'category' in fields and fields['category'] != category:
        errors.append('%s: category "%s" must match the folder "%s"' % (name, fields['category'], category))
    applies_to = fields.get('applies_to')
    if 'applies_to' in fields:
        valid = (isinstance(applies_to, list) and applies_to
                 and all(item in PRODUCTS for item in applies_to)
                 and len(set(applies_to)) == len(applies_to))
        if not valid:
            errors.append('%s: applies_to must be [stack], [solo], or [stack, solo]' % name)
            applies_to = None

    present = [key for key in VETTED_FIELDS if key in fields]
    if present and len(present) != len(VETTED_FIELDS):
        errors.append('%s: a recipe has all of vetted_on, vetted_against, and vetted_method, or none of them '
                      '(only has %s)' % (name, ', '.join(present)))
    if 'vetted_on' in fields:
        try:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(fields['vetted_on'])):
                raise ValueError
            datetime.date.fromisoformat(fields['vetted_on'])
        except (ValueError, TypeError):
            errors.append('%s: vetted_on must be a real date written YYYY-MM-DD' % name)
    if 'vetted_method' in fields and fields['vetted_method'] not in VETTED_METHODS:
        errors.append('%s: vetted_method must be one of %s' % (name, ', '.join(VETTED_METHODS)))
    if 'vetted_against' in fields:
        against = fields['vetted_against']
        if not isinstance(against, dict) or not against:
            errors.append('%s: vetted_against must list at least one "product: release" line' % name)
        elif applies_to is not None and not set(against).issubset(set(applies_to)):
            errors.append('%s: vetted_against has %s, which includes a product not in applies_to (%s)'
                          % (name, sorted(against), sorted(applies_to)))
        else:
            for product, release in against.items():
                if not release:
                    errors.append('%s: vetted_against.%s needs a release such as v0.3.0' % (name, product))


def check_banner(path, body, errors):
    """The first non-blank line is `# Title`, and the two banner lines follow after blank lines only."""
    name = relative(path)
    lines = body.split('\n')
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith('# '):
        errors.append('%s: the title line "# ..." must come right after the frontmatter' % name)
        return
    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if lines[index:index + 2] != TRUST_BANNER:
        errors.append('%s: the trust banner must follow the title word for word (see CONTRACT.md, "The trust banner")'
                      % name)


def check_required_headings(category, path, body, errors):
    if category not in SECTIONS_WITH_REQUIRED_HEADINGS:
        return
    name = relative(path)
    headings = [line.rstrip() for _, line in lines_outside_code_fences(body) if line.startswith('## ')]
    position = 0
    for required in REQUIRED_HEADINGS:
        if required in headings[position:]:
            position = headings.index(required, position) + 1
        elif required in headings:
            errors.append('%s: the heading "%s" is out of order; the required headings come in the order '
                          'CONTRACT.md lists them' % (name, required))
        else:
            errors.append('%s: missing the heading "%s"' % (name, required))


LINK_PATTERN = re.compile(r'\]\(\s*(<[^>]*>|[^)\s]+)[^)]*\)')
REFERENCE_PATTERN = re.compile(r'^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)')


def check_links(path, errors):
    text = Path(path).read_text(encoding='utf-8')
    if text.startswith('---'):
        try:
            _, text = split_frontmatter(text)
        except FrontmatterError:
            pass
    for number, line in lines_outside_code_fences(text):
        without_code = re.sub(r'`[^`]*`', '', line)
        targets = [match.group(1) for match in LINK_PATTERN.finditer(without_code)]
        reference = REFERENCE_PATTERN.match(without_code)
        if reference:
            targets.append(reference.group(1))
        for target in targets:
            target = target.strip('<>')
            if re.match(r'^([a-z][a-z0-9+.-]*:|#|//)', target, re.I):
                continue
            file_part = target.split('#', 1)[0].split('?', 1)[0]
            if not file_part:
                continue
            resolved = (Path(path).parent / file_part).resolve()
            if not resolved.exists():
                errors.append('%s:%d: the link "%s" points at nothing' % (relative(path), number, target))


def markdown_files():
    skipped = {'.git', 'node_modules', '__pycache__'}
    for folder, subfolders, files in os.walk(REPOSITORY_ROOT):
        subfolders[:] = [name for name in subfolders if name not in skipped]
        for file in sorted(files):
            if file.endswith('.md'):
                yield Path(folder) / file


def lint():
    errors = []
    seen_ids = {}
    for category, path in recipe_paths():
        try:
            fields, body = read_recipe(path)
        except FrontmatterError as problem:
            errors.append('%s: %s' % (relative(path), problem))
            continue
        check_frontmatter(category, path, fields, errors)
        check_banner(path, body, errors)
        check_required_headings(category, path, body, errors)
        recipe_id = fields.get('id')
        if isinstance(recipe_id, str):
            if recipe_id in seen_ids:
                errors.append('%s: id "%s" is already used by %s' % (relative(path), recipe_id, seen_ids[recipe_id]))
            else:
                seen_ids[recipe_id] = relative(path)
    for path in markdown_files():
        check_links(path, errors)
    return errors, len(seen_ids)


def git(*arguments):
    result = subprocess.run(['git', '-C', str(REPOSITORY_ROOT)] + list(arguments),
                            capture_output=True, text=True)
    return result


def parsed_vetted_fields(text):
    """Return the parsed vetted_* fields from frontmatter, or None if text is absent."""
    if text is None:
        return {key: None for key in VETTED_FIELDS}
    frontmatter_text, _ = split_frontmatter(text)
    fields = parse_frontmatter(frontmatter_text)
    return {key: fields.get(key) for key in VETTED_FIELDS}


def check_pr_vetting(base_ref, head_ref='HEAD'):
    merge_base = git('merge-base', base_ref, head_ref)
    if merge_base.returncode != 0:
        print('Cannot find where %s left %s: %s' % (head_ref, base_ref, merge_base.stderr.strip()))
        print('In GitHub Actions, check out with "fetch-depth: 0" so both commits exist.')
        return 2
    base = merge_base.stdout.strip()
    changed = git('diff', '--name-status', '--no-renames', base, head_ref)
    if changed.returncode != 0:
        print('git diff failed: %s' % changed.stderr.strip())
        return 2
    problems = []
    for entry in changed.stdout.splitlines():
        status, _, path = entry.partition('\t')
        if not RECIPE_PATH_PATTERN.match(path) or path.endswith('/README.md'):
            continue
        if status.startswith('D'):
            continue
        after_result = git('show', '%s:%s' % (head_ref, path))
        if after_result.returncode != 0:
            problems.append('%s: cannot read proposed recipe from %s' % (path, head_ref))
            continue
        before_result = git('show', '%s:%s' % (base, path))
        before_text = before_result.stdout if before_result.returncode == 0 else None
        try:
            after_vetted = parsed_vetted_fields(after_result.stdout)
        except FrontmatterError as problem:
            problems.append('%s: frontmatter is unreadable (%s), so vetted_* fields cannot be verified' % (path, problem))
            continue
        try:
            before_vetted = parsed_vetted_fields(before_text)
        except FrontmatterError:
            before_vetted = None
        if before_vetted != after_vetted:
            verb = 'adds' if before_text is None else 'changes'
            problems.append('%s: this pull request %s vetted_on, vetted_against, or vetted_method. '
                            'Remove those lines; a maintainer adds them after the check.' % (path, verb))
    for problem in problems:
        print(problem)
    if problems:
        print('\nOnly a maintainer writes the vetted_* fields (CONTRACT.md, "Frontmatter").')
        return 1
    print('No recipe in this pull request adds or changes vetted_on, vetted_against, or vetted_method.')
    return 0


def main(arguments):
    if arguments and arguments[0] == '--check-pr-vetting':
        if len(arguments) not in (2, 3):
            print('Usage: lint_recipes.py --check-pr-vetting <base-ref> [<head-ref>]')
            return 2
        head_ref = arguments[2] if len(arguments) == 3 else 'HEAD'
        return check_pr_vetting(arguments[1], head_ref)
    if arguments:
        print('Usage: lint_recipes.py [--check-pr-vetting <base-ref> [<head-ref>]]')
        return 2
    errors, recipe_count = lint()
    for error in errors:
        print(error)
    if errors:
        print('\n%d problem(s) in %d recipe(s). The rules are in CONTRACT.md.' % (len(errors), recipe_count))
        return 1
    print('%d recipes pass the Recipe Contract checks.' % recipe_count)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
