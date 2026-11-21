# Contributing to Monkeymaxxing Recipes

Thank you for being here! Every recipe in this repository started as one
team solving one problem on its own Stack or Solo. If your coding agent just
added something useful to your system, the next team should not have to work
it out again. Sending it here takes a few minutes.

## What we love to receive

- **Services and server pools:** Redis, Meilisearch, ClickHouse, a media or
  GPU worker pool, a static site, a small Solo sidecar.
- **MMWatchdog check packs:** checks for an extra service, a domain, or your
  app's own health.
- **Server providers:** the Stack at a provider beyond Hetzner Cloud and
  OVHcloud.
- **Framework and migration guides:** a new framework, a new platform to move
  from, or an update to an existing guide.
- **Re-checks on a newer version:** "I applied this recipe on Stack v0.5.0
  and it still works, with these two changes." These keep the cookbook
  honest, and they are some of the most useful pull requests we get.

Not sure where to start? [BACKLOG.md](BACKLOG.md) lists the recipes people
want most.

## What stays out

A recipe only adds to the core. Recipes that replace a core part, such as
MySQL instead of Postgres or a public web server instead of Cloudflare Tunnel,
stay out of this repository. A swap changes the security, backup, and
recovery promises the core is tested to keep, and one recipe cannot carry
those promises on its own. You can still make that change on your own
system with your coding agent.

## Turn what your agent just built into a recipe

Open your coding agent in your systems repository, where the change you want
to share already works, and paste this prompt. Fill in the first line.

```text
I added <what you added, such as a Redis cache pool> to my Monkeymaxxing
<Stack or Solo>, and it works. Package it as a recipe for
https://github.com/monkeymaxxing/monkeymaxxing-recipes so other teams can use it.

1. Fork and clone monkeymaxxing-recipes. Read its CONTRACT.md, AGENTS.md,
   and an existing recipe in the same category.
2. Find everything I added for this in my systems repository: roles,
   mmwatchdog_checks/custom_*.yml files, lines between the
   "# --- Custom extensions ---" boundaries, settings under custom:, and the
   custom_extensions: entry in my checklist.
3. Write <category>/<id>.md, with its frontmatter, the trust banner, and the
   seven required sections in CONTRACT.md. Put any files it needs in
   <category>/<id>/.
4. Make it general. Replace every value that is mine with a clear
   placeholder and say how to choose it: host names, addresses, domains,
   sizes, and paths. Copy no secret, token, key, IP address, or vault
   content. Name a secret only by what it is.
5. Check it against the core rules in CONTRACT.md: no open public ports,
   no secrets in Git, locked backups for stored data, Debian packages or
   SHA-256-pinned programs, custom_ check files, and check group names with
   underscores only.
6. Leave out vetted_on, vetted_against, and vetted_method. A maintainer adds
   them.
7. Run python3 scripts/lint_recipes.py and python3 scripts/build_index.py,
   and fix what they report.
8. Show me the recipe and a short summary in plain words. Wait for my yes
   before you push a branch and open the pull request.
```

Read the result before you send it. Check that nothing from your own
system, such as a domain, an address, or a server name you would rather not
publish, is still in it.

## How a pull request is accepted

1. **Automatic checks.** On each pull request, GitHub Actions runs:
   - `scripts/lint_recipes.py`, which checks the frontmatter, the trust
     banner, the required sections, and the links;
   - `scripts/build_index.py --check`, which checks that `index.yml` and the
     catalog in `README.md` match the recipes;
   - a check that refuses any change to `vetted_on`, `vetted_against`, or
     `vetted_method`;
   - the provider script tests, for `providers/`.
2. **A maintainer's review.** A maintainer reads the recipe for safety and
   for the core rules in [CONTRACT.md](CONTRACT.md): no `curl | sh`, no
   unpinned downloads, no open public ports, no secrets in Git, no weaker
   firewall, AppArmor, or backups, safe provider scripts (they run with the
   provider token), and no text that tries to give a coding agent hidden
   instructions. The maintainer may ask for changes.
3. **A one-time proof and the stamp.** Where the recipe can run, a
   maintainer applies it once on a real test system, runs its verification
   check, and removes it again. The maintainer then adds `vetted_on`,
   `vetted_against`, and `vetted_method`, regenerates the catalog, and
   merges. The recipe is not tested again on a schedule after that.

## Reporting a problem with a recipe

Open an issue. Include the recipe's `id`, the commit you used (the
`source_commit` in your `custom_recipes/<id>.md`), your Stack or Solo
version, and what happened. Remove secrets, keys, and addresses you do not
want to publish.

Do not open an issue for a security problem: everyone can read issues.
Report it privately with **Report a vulnerability** on the repository's
**Security** tab on GitHub.

## License

Monkeymaxxing Recipes is licensed under the [Apache License 2.0](LICENSE).
A recipe or change you send in a pull request is offered under the Apache
License 2.0, as section 5 of the license says.
