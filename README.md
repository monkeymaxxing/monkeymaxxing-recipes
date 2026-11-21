# Monkeymaxxing Recipes

**The shared cookbook for the
[Monkeymaxxing Stack](https://github.com/monkeymaxxing/monkeymaxxing-stack)
and [Monkeymaxxing Solo](https://github.com/monkeymaxxing/monkeymaxxing-solo).
Your coding agent reads a recipe, checks it, and adds it to your system.**

The Stack and Solo stay small on purpose: Debian 13, Postgres 17,
Cloudflare Tunnel, WireGuard, MMX, and MMWatchdog, with no setup menus.
That is what keeps day one free of decisions. But real systems grow. One
team needs a Redis cache, another needs a search engine, another wants a
server provider that the core does not cover.

Monkeymaxxing Recipes is where those additions live. Each recipe is one
plain Markdown file that your coding agent can follow:

| Folder | What the recipes in it do | Used by |
| --- | --- | --- |
| `services/` | Add a service on top of your system: a new server pool on the Stack (such as Redis or Meilisearch), or a small extra on Solo | Stack, Solo |
| `watchdog-checks/` | Add MMWatchdog check packs: monitoring for an extra service, a domain, or your app's own health | Stack, Solo |
| `providers/` | Run the Stack at a server provider beyond the core's Hetzner Cloud and OVHcloud | Stack |
| `frameworks/` | Get an app in a given framework (Rails, Django, Laravel, Next.js, and others) ready to deploy | Stack, Solo |
| `migrations/` | Move an app from a platform such as Heroku, Railway, Render, or Vercel | Stack, Solo |

Recipes only **add** to the core. A recipe never replaces Postgres,
Cloudflare Tunnel, MMX, or MMWatchdog. See [What stays out](#what-stays-out).

> [!IMPORTANT]
> **Recipes are not tested the way the core is.** There are three levels of trust:
>
> 1. **The core: Monkeymaxxing Stack and Monkeymaxxing Solo.** Tested
>    continuously on real servers, maintained, and upgraded with each release.
> 2. **Recipes in this repository.** A maintainer checks each recipe **once**,
>    when it is accepted: it follows the [Recipe Contract](CONTRACT.md), it
>    passes a security review, and, where possible, it is proven once on a real
>    test system. The recipe then records the date (`vetted_on`) and the Stack
>    or Solo version (`vetted_against`) of that check. After that, a recipe is
>    **not tested again on a schedule, and the core's support does not cover
>    it.** A recipe checked against an older version may need small changes on
>    a newer one. Your coding agent reads the recipe with you and adapts it.
> 3. **Anything else:** a recipe from another website or repository, a pull
>    request that is not merged yet, or a change that swaps out a core part.
>    Your coding agent treats it as an untrusted proposal. It tells you so
>    plainly and walks you through every trade-off before it changes anything.

## How to use a recipe

You do not need to clone this repository or learn its layout. Ask your
coding agent in plain words, from your systems repository:

```text
Check monkeymaxxing-recipes for a Redis recipe and add it to my Stack.
```

```text
Is there a recipe that watches my domain's TLS certificate? Add it to my Solo server.
```

```text
Has my Redis recipe changed since I added it?
```

Here is what the agent does, following the "Using a recipe" rules in your
systems repository's `AGENTS.md`:

1. **Finds the recipe at a fixed commit.** The agent looks up the current
   commit of this repository once, then reads `index.yml` and the recipe at
   that exact commit. It never follows the moving `main` branch, so what you
   approve is exactly what gets applied. If you cloned this repository, the
   agent reads your clone instead.
2. **Checks it and asks you first.** For `services/` and `watchdog-checks/`
   recipes, the agent checks the recipe against the core's safety rules (no
   open web or SSH ports, no secrets in Git, locked backups for stored data,
   pinned software). Then it tells you in plain words what the recipe adds,
   what it costs, how its data is backed up, and when it was last checked.
   It waits for your yes. Guides in `frameworks/`, `migrations/`, and
   `providers/` are reference documents, so the agent reads them during
   setup without stopping to ask.
3. **Copies it into your repository.** The agent copies a `services/` or
   `watchdog-checks/` recipe into `custom_recipes/<id>.md` in your systems
   repository, with the source address, the commit it came from
   (`source_commit`), and the date it was applied. It then writes the real
   files: a role, an MMWatchdog check file named `custom_<name>.yml`, and
   entries in the `# --- Custom extensions ---` slots and the `custom:`
   settings. It records the recipe under `custom_extensions:` in your
   checklist, previews the change with `mmx dryrun`, applies it, and runs the
   recipe's verification check.
4. **Leaves it with you.** Your copy is never linked back to this repository,
   so a change here never reaches your servers by itself. You can edit your
   copy freely. Each recipe ends with clean removal steps, so you can take it
   out again later.

A `providers/` guide is copied into `provider_guides/` in your systems
repository. A `frameworks/` guide is used while you prepare your app
repository, and a `migrations/` guide during the one-time move. Neither
leaves files behind in your systems repository.

## The catalog

<!-- CATALOG:START -->

### Services

| Recipe | What it does | Applies to | Vetted |
| --- | --- | --- | --- |
| [Add a Redis cache pool](services/redis-cache-pool.md) | Adds a private, stateless Redis cache pool over WireGuard with Debian packages and MMWatchdog checks. | Stack | 2026-11-21, Stack v0.3.0, review-only |
| [Serve a static site alongside your app](services/static-site.md) | Serves one static site, such as a docs or marketing site, from your existing servers through your existing Cloudflare Tunnel, with MMWatchdog checks. | Stack, Solo | 2026-11-21, Stack v0.3.0, Solo v0.1.0, review-only |

### Watchdog checks

| Recipe | What it does | Applies to | Vetted |
| --- | --- | --- | --- |
| [Watch TLS certificates and DNS records](watchdog-checks/domain-and-tls-expiry.md) | Adds a drop-in MMWatchdog check pack that warns before TLS certificates expire and verifies public DNS answers. | Stack, Solo | 2026-11-21, Stack v0.3.0, Solo v0.1.0, review-only |

### Providers

About these guides: [providers/README.md](providers/README.md).

| Recipe | What it does | Applies to | Vetted |
| --- | --- | --- | --- |
| [AWS EC2](providers/aws-ec2.md) | Run the Stack on AWS EC2 instances, with the five provider scripts and their fake-API tests. | Stack | 2026-11-21, Stack v0.3.0, script-tests |
| [DigitalOcean](providers/digitalocean.md) | Run the Stack on DigitalOcean Droplets, with the five provider scripts and their fake-API tests. | Stack | 2026-11-21, Stack v0.3.0, script-tests |
| [Google Compute Engine](providers/google-compute-engine.md) | Run the Stack on Google Compute Engine instances, with the five provider scripts and their fake-API tests. | Stack | 2026-11-21, Stack v0.3.0, script-tests |
| [Scaleway Instances](providers/scaleway.md) | Run the Stack on Scaleway Instances, with the five provider scripts and their fake-API tests. | Stack | 2026-11-21, Stack v0.3.0, script-tests |
| [Vultr Cloud Compute](providers/vultr.md) | Run the Stack on Vultr Cloud Compute instances, with the five provider scripts and their fake-API tests. | Stack | 2026-11-21, Stack v0.3.0, script-tests |

### Frameworks

About these guides: [frameworks/README.md](frameworks/README.md).

| Recipe | What it does | Applies to | Vetted |
| --- | --- | --- | --- |
| [Run Django with PostgreSQL on the Stack](frameworks/django-pg.md) | Get a Django app with PostgreSQL ready to run on the Stack, with psycopg, Gunicorn and WhiteNoise assets. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Express with PostgreSQL on the Stack](frameworks/express-pg.md) | Get an Express app with PostgreSQL ready to run on the Stack, with the Stack database helper and the Node cluster. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run FastAPI with PostgreSQL on the Stack](frameworks/fastapi-pg.md) | Get a FastAPI app with PostgreSQL ready to run on the Stack, with psycopg pools and Gunicorn/Uvicorn workers. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Go with net/http and pgx on the Stack](frameworks/go-net-http-pgx.md) | Get a Go app using net/http and pgx ready to run on the Stack, with native multi-host database connections. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Laravel, Livewire and Eloquent on the Stack](frameworks/laravel-livewire-eloquent.md) | Get a Laravel, Livewire and Eloquent app ready to run on the Stack, served by FrankenPHP. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run a Next.js app on the Stack](frameworks/nextjs-prisma-pg.md) | Get a Next.js app with PostgreSQL ready to run on the Stack, using standalone Node output and retained frontend assets. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Nuxt with PostgreSQL on the Stack](frameworks/nuxt-pg.md) | Get a Nuxt app with PostgreSQL ready to run on the Stack, using the Nitro Node server and retained frontend assets. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Rails with PostgreSQL on the Stack](frameworks/rails-pg.md) | Get a Rails app with PostgreSQL ready to run on the Stack, with Active Record, Puma and Propshaft assets. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run Rust with Axum and tokio-postgres on the Stack](frameworks/rust-axum-tokio-postgres.md) | Get a Rust app using Axum and tokio-postgres ready to run on the Stack, with native writable-server selection. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run SvelteKit with PostgreSQL on the Stack](frameworks/sveltekit-pg.md) | Get a SvelteKit app with PostgreSQL ready to run on the Stack, using adapter-node and retained frontend assets. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Run a TanStack Start app on the Stack](frameworks/tanstack-start-pg.md) | Get a TanStack Start app with PostgreSQL ready to run on the Stack, using a persistent Nitro Node server. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |

### Migrations

About these guides: [migrations/README.md](migrations/README.md).

| Recipe | What it does | Applies to | Vetted |
| --- | --- | --- | --- |
| [Base44 migration feasibility](migrations/base44-feasibility.md) | Checks whether a Base44 app can move to the Stack as a backend replacement project, against Base44 documentation. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from a platform you run yourself](migrations/from-any-container-platform.md) | Move an app from a container platform you run yourself, keeping the old database until the new app works. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Bolt app to your own system](migrations/from-bolt.md) | Move an app built in Bolt to the Stack, replacing the services Bolt supplied. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Coolify to your own system](migrations/from-coolify.md) | Move a Coolify-hosted portal to the Stack, exporting resource settings, database rows and mounted files. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Docker Compose app to your own system](migrations/from-docker-compose.md) | Move a team-owned Docker Compose app to the Stack, keeping accounts, private uploads and background work. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Dokku to your own system](migrations/from-dokku.md) | Move a Dokku app, its workers, uploads and schedule to the Stack, with the database moved last. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Amazon ECS to your own system](migrations/from-ecs.md) | Move an app from Amazon ECS to the Stack, replacing the AWS services the app uses. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Firebase app to your own system](migrations/from-firebase.md) | Move a Firebase app to the Stack, replacing Firebase authentication, storage, functions and database. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Fly.io to your own system](migrations/from-fly.md) | Move an app from Fly.io to the Stack, with separate exports of data, objects, secrets and Machine settings. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Heroku to your own system](migrations/from-heroku.md) | Move a Heroku customer portal to the Stack and prove the exported copy works on independent PostgreSQL and S3-compatible storage. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Kamal app to your own system](migrations/from-kamal.md) | Move a Kamal-deployed Rails 8 app that already uses PostgreSQL and private S3-compatible storage to the Stack. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Kubernetes to your own system](migrations/from-kubernetes.md) | Move an application out of Kubernetes to the Stack, with PostgreSQL moved last. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Lovable portal to your own system](migrations/from-lovable.md) | Move a Lovable portal to the Stack, keeping the generated TanStack pages and replacing the backend. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Netlify app to your own system](migrations/from-netlify.md) | Move a Netlify app to the Stack, including the Netlify Identity users who cannot export password hashes. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Railway to your own system](migrations/from-railway.md) | Move a Railway portal to the Stack after exporting PostgreSQL and private bucket objects. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move from Render to your own system](migrations/from-render.md) | Rehearse moving a Render customer portal to PostgreSQL 17 and S3-compatible storage on the Stack. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Replit app to your own system](migrations/from-replit.md) | Rehearse moving a Replit customer portal to PostgreSQL and S3-compatible storage on the Stack. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Move a Supabase app to your own system](migrations/from-supabase.md) | Move a Supabase app to the Stack, replacing its managed services as well as its Postgres tables. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |
| [Rehearse a Vercel app migration](migrations/from-vercel.md) | Rehearse a Vercel app migration, moving users, private files, jobs and service settings that a code export leaves behind. | Stack, Solo | 2026-11-21, Stack v0.3.0, review-only |

<!-- CATALOG:END -->

`index.yml` holds the same catalog for coding agents and scripts. Both are
generated from each recipe's frontmatter, so they never disagree with the
recipes.

## What stays out

Recipes add to the core; they never swap a core part. Replacing Postgres
with MySQL, or Cloudflare Tunnel with a public web server, changes the
security, backup, and recovery promises that the core is tested to keep.
This repository does not hold recipes like that.

The Stack and Solo are open source and plain files, so you can still make
such a change yourself with your coding agent. It is then your own design:
the agent explains what you give up, and the core's tests and support no
longer cover that part.

## Contributing

Built something useful on your own Stack or Solo? Your coding agent can
turn it into a recipe in a few minutes.
[CONTRIBUTING.md](CONTRIBUTING.md) has a prompt you can paste. The
[backlog](BACKLOG.md) lists the recipes people want most.

| Document | What it gives you |
| --- | --- |
| [CONTRACT.md](CONTRACT.md) | The rules every recipe follows: frontmatter, required sections, and the core rules it must keep |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to send a recipe, and how it is checked |
| [BACKLOG.md](BACKLOG.md) | Recipes we would love to have, in priority order |
| [AGENTS.md](AGENTS.md) | Instructions for a coding agent working in this repository |

## License

Monkeymaxxing Recipes is licensed under the [Apache License 2.0](LICENSE).
