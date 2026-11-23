# Monkeymaxxing Recipes

**Ready-made additions for the
[Monkeymaxxing Stack](https://github.com/monkeymaxxing/monkeymaxxing-stack)
and [Monkeymaxxing Solo](https://github.com/monkeymaxxing/monkeymaxxing-solo).
Ask your coding agent for a recipe, and the agent adds the recipe to your
system after you say yes.**

The Stack and Solo start small on purpose. Every system gets the same parts:
Debian 13, Postgres 17, Cloudflare Tunnel, WireGuard, MMX, and MMWatchdog, so
you make no setup choices on day one. But systems grow. For example, one team
needs a Redis cache, another needs a search engine, and another wants a server
provider that the Stack does not support yet.

Each recipe is one Markdown file that your coding agent follows. There are two
kinds of recipe:

- **Add-ons** add something to your running system, such as a Redis cache or
  a static docs site next to your app. Your coding agent asks you before the
  agent adds an add-on, and then keeps a copy of the add-on in your systems
  repository.
- **Guides** help your coding agent with one job: running the Stack at another
  server provider, preparing an app in your framework, or moving an app from a
  platform such as Heroku. The agent reads the guide while the agent does that
  job.

| Folder | Kind | What the recipes in the folder do | Works with |
| --- | --- | --- | --- |
| `services/` | Add-on | Add a service, such as a Redis cache or a static site next to your app | Stack, Solo |
| `watchdog-checks/` | Add-on | Add MMWatchdog checks for an extra service, your domain, or your app's own health | Stack, Solo |
| `providers/` | Guide | Run the Stack at a server provider other than Hetzner Cloud and OVHcloud | Stack |
| `frameworks/` | Guide | Get a Rails, Django, Laravel, Next.js, or other app ready to deploy | Stack, Solo |
| `migrations/` | Guide | Move an app from a platform such as Heroku, Railway, Render, or Vercel | Stack, Solo |

Recipes only add to the Stack and Solo. A recipe never replaces Postgres,
Cloudflare Tunnel, MMX, or MMWatchdog. [What stays out](#what-stays-out)
explains why.

## How to use a recipe

Ask your coding agent in plain words, from your systems repository. You do not
need to clone this repository.

```text
Check monkeymaxxing-recipes for a Redis recipe and add it to my Stack.
```

```text
Is there a recipe that serves our docs site next to the app? Add it to my Solo server.
```

```text
Has my Redis recipe changed since I added it?
```

For an add-on, your coding agent works in four steps:

1. **Finds the add-on.** The agent reads the add-on at one fixed version of
   this repository, so what you approve is exactly what gets applied.
2. **Checks the add-on and asks you.** The agent checks the add-on against the
   Stack's safety rules: no open web or SSH ports, no secrets in Git, locked
   backups for stored data, and fixed software versions. Then the agent tells
   you what the add-on adds, what the add-on costs, how its data is backed up,
   and when a maintainer last checked the add-on. The agent waits for your yes.
3. **Adds the add-on to your system.** The agent copies the add-on into your
   systems repository, writes the changes, shows you a preview with
   `mmx dryrun`, applies the changes, and runs the add-on's own check.
4. **Leaves the copy with you.** Your copy belongs to you, so a later change in
   this repository never reaches your servers by itself. You can edit your
   copy, and every add-on ends with steps to remove the add-on again.

For a guide, your coding agent reads the guide during the job and does not
stop to ask, because a guide adds nothing to your system by itself. A
`providers/` guide is copied into `provider_guides/` in your systems
repository. Framework and migration guides leave no files in your systems
repository.

The "Using a recipe" section of your systems repository's `AGENTS.md` gives
your coding agent the detailed rules for these steps.

## How far to trust a recipe

> [!IMPORTANT]
> **A maintainer reviews each recipe once, but usually does not run the
> recipe. The Stack and Solo are tested with every release.**

The Stack and Solo are tested on real servers with every release. A recipe in
this repository is reviewed once, when a maintainer accepts the recipe: the
maintainer reads the recipe for security problems and checks the recipe against
the [Recipe Contract](CONTRACT.md). The person who wrote the recipe tested the
recipe on their own system. A maintainer tries a recipe on a test system only
sometimes, for example for a widely used add-on, and the catalog says when.
Nobody tests a recipe again after the review, and support for the Stack and
Solo does not cover recipes. A recipe reviewed on an older version may need
small changes on a newer version, and your coding agent makes those changes
with you.

A recipe from anywhere else, such as another website or a pull request that is
not merged yet, is untrusted. Your coding agent tells you so, and walks you
through every trade-off before the agent changes anything.

## The catalog

The Checked column says when a maintainer reviewed each recipe, on which
version, and how:

- **Read and reviewed:** a maintainer read and reviewed the recipe but did not
  run the recipe. Most recipes are checked this way.
- **Scripts tested:** a maintainer also ran the recipe's own script tests.
  Provider guides are checked this way.
- **Tried on a test system:** a maintainer also added the recipe to a test
  system, checked that the recipe works, and removed the recipe again.

<!-- CATALOG:START -->

### Services

| Recipe | What it does | Works with | Checked |
| --- | --- | --- | --- |
| [Add a Redis cache](services/redis-cache-pool.md) | Adds private Redis cache servers that your app reaches over WireGuard, with MMWatchdog checks. Redis keeps no data that needs a backup. | Stack | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run scheduled app tasks with systemd timers](services/scheduled-tasks.md) | Runs your app's own commands on a schedule, such as a nightly cleanup, in a one-off container of the live release, on one server, with MMWatchdog checks for failed or missed runs. | Stack, Solo | 2026-11-23, on Stack v0.3.1 and Solo v0.1.0: tried on a test system |
| [Add a Redis cache sidecar on Solo](services/solo-redis-sidecar.md) | Runs Redis as a cache in a locked-down container on solo01, on 127.0.0.1 only, with MMWatchdog checks. Redis keeps no data that needs a backup. | Solo | 2026-11-23, on Solo v0.1.0: tried on a test system |
| [Serve a static site alongside your app](services/static-site.md) | Serves a static site, such as a docs or marketing site, from your existing servers and Cloudflare Tunnel, with MMWatchdog checks. | Stack, Solo | 2026-11-21, on Stack v0.3.0 and Solo v0.1.0: read and reviewed |
| [Add Umami web analytics](services/umami-analytics.md) | Runs Umami, cookieless web analytics, in a locked-down container behind your Cloudflare Tunnel, with its data in your existing Postgres and its backups, and with MMWatchdog checks. | Stack, Solo | 2026-11-23, on Stack v0.3.1 and Solo v0.1.0: tried on a test system |

### Watchdog checks

| Recipe | What it does | Works with | Checked |
| --- | --- | --- | --- |
| [Watch Postgres background job queues](watchdog-checks/background-job-queue.md) | Adds MMWatchdog checks that warn when jobs pile up in a Postgres-backed job queue, such as Solid Queue, GoodJob, Oban, or pg-boss, or wait too long to start. | Stack, Solo | 2026-11-23, on Stack v0.3.1 and Solo v0.1.0: tried on a test system |
| [Watch TLS certificates and DNS records](watchdog-checks/domain-and-tls-expiry.md) | Adds MMWatchdog checks that warn before a TLS certificate expires and warn when a public DNS answer changes. | Stack, Solo | 2026-11-21, on Stack v0.3.0 and Solo v0.1.0: read and reviewed |
| [Watch Postgres for table bloat and slow queries](watchdog-checks/postgres-bloat-and-slow-queries.md) | Adds MMWatchdog checks that warn when the apps' tables collect too many dead rows and when an app query is slow on average. | Stack, Solo | 2026-11-23, on Stack v0.3.1 and Solo v0.1.0: tried on a test system |

### Providers

About these guides: [providers/README.md](providers/README.md).

| Recipe | What it does | Works with | Checked |
| --- | --- | --- | --- |
| [AWS EC2](providers/aws-ec2.md) | Runs the Stack on AWS EC2 instances. | Stack | 2026-11-21, on Stack v0.3.0: scripts tested |
| [DigitalOcean](providers/digitalocean.md) | Runs the Stack on DigitalOcean Droplets. | Stack | 2026-11-21, on Stack v0.3.0: scripts tested |
| [Google Compute Engine](providers/google-compute-engine.md) | Runs the Stack on Google Compute Engine instances. | Stack | 2026-11-21, on Stack v0.3.0: scripts tested |
| [Scaleway Instances](providers/scaleway.md) | Runs the Stack on Scaleway Instances. | Stack | 2026-11-21, on Stack v0.3.0: scripts tested |
| [Vultr Cloud Compute](providers/vultr.md) | Runs the Stack on Vultr Cloud Compute instances. | Stack | 2026-11-21, on Stack v0.3.0: scripts tested |

### Frameworks

About these guides: [frameworks/README.md](frameworks/README.md).

| Recipe | What it does | Works with | Checked |
| --- | --- | --- | --- |
| [Run Django with PostgreSQL](frameworks/django-pg.md) | Gets a Django app ready to deploy, with Gunicorn as the web server and WhiteNoise serving static files. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Express with PostgreSQL](frameworks/express-pg.md) | Gets an Express app ready to deploy, with the Stack's database helper and Node's cluster module. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run FastAPI with PostgreSQL](frameworks/fastapi-pg.md) | Gets a FastAPI app ready to deploy, with psycopg connection pools and Gunicorn running Uvicorn workers. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Go with net/http and pgx](frameworks/go-net-http-pgx.md) | Gets a Go app ready to deploy. pgx reads the database address list as it is and finds the writable database server itself. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Laravel with Livewire and Eloquent](frameworks/laravel-livewire-eloquent.md) | Gets a Laravel app with Livewire and Eloquent ready to deploy, served by FrankenPHP. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Next.js with PostgreSQL](frameworks/nextjs-prisma-pg.md) | Gets a Next.js app ready to deploy as a standalone Node server. The last release's frontend files stay available, so open pages keep working during a deploy. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Nuxt with PostgreSQL](frameworks/nuxt-pg.md) | Gets a Nuxt app ready to deploy on the Nitro Node server. The last release's frontend files stay available, so open pages keep working during a deploy. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Rails with PostgreSQL](frameworks/rails-pg.md) | Gets a Rails app ready to deploy, with Puma as the web server and Propshaft for assets. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run Rust with Axum and tokio-postgres](frameworks/rust-axum-tokio-postgres.md) | Gets a Rust app ready to deploy. The app finds the writable database server itself. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run SvelteKit with PostgreSQL](frameworks/sveltekit-pg.md) | Gets a SvelteKit app ready to deploy with adapter-node. The last release's frontend files stay available, so open pages keep working during a deploy. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Run TanStack Start with PostgreSQL](frameworks/tanstack-start-pg.md) | Gets a TanStack Start app ready to deploy as a long-running Nitro Node server. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |

### Migrations

About these guides: [migrations/README.md](migrations/README.md).

| Recipe | What it does | Works with | Checked |
| --- | --- | --- | --- |
| [Check whether a Base44 app can move](migrations/base44-feasibility.md) | Explains what a Base44 export leaves behind, so you can judge the work before you start. Based on the Base44 documentation only. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from a container platform you run yourself](migrations/from-any-container-platform.md) | Moves an app from a container platform you run yourself. The old database stays in use until the new app works. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Bolt to your own system](migrations/from-bolt.md) | Moves an app built in Bolt and replaces the services Bolt supplied. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Coolify to your own system](migrations/from-coolify.md) | Moves an app from Coolify, with its settings, database, and stored files. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Docker Compose to your own system](migrations/from-docker-compose.md) | Moves a Docker Compose app, with its user accounts, private uploads, and background jobs. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Dokku to your own system](migrations/from-dokku.md) | Moves a Dokku app with its workers, uploads, and scheduled jobs. The database moves last. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Amazon ECS to your own system](migrations/from-ecs.md) | Moves an app from Amazon ECS and replaces the AWS services the app uses. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Firebase to your own system](migrations/from-firebase.md) | Moves a Firebase app and replaces Firebase login, storage, functions, and database. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Fly.io to your own system](migrations/from-fly.md) | Moves an app from Fly.io, exporting its database, stored files, secrets, and Machine settings one by one. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Heroku to your own system](migrations/from-heroku.md) | Moves a Heroku app, with its database and stored files, and checks that the copy works before you switch. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Kamal to your own system](migrations/from-kamal.md) | Moves a Rails app deployed with Kamal that already uses PostgreSQL and S3-compatible file storage. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Kubernetes to your own system](migrations/from-kubernetes.md) | Moves an app out of Kubernetes. The database moves last. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Lovable to your own system](migrations/from-lovable.md) | Moves a Lovable app. The generated pages stay, and the backend is replaced. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Netlify to your own system](migrations/from-netlify.md) | Moves a Netlify app, including Netlify Identity users. Netlify cannot export their passwords, so those users set new ones. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Railway to your own system](migrations/from-railway.md) | Moves a Railway app, with its database and private stored files. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Render to your own system](migrations/from-render.md) | Moves a Render app, with its database and stored files, after a practice run. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Replit to your own system](migrations/from-replit.md) | Moves a Replit app, with its database and stored files, after a practice run. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Supabase to your own system](migrations/from-supabase.md) | Moves a Supabase app and replaces its login, storage, and other hosted services, not only its database. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |
| [Move from Vercel to your own system](migrations/from-vercel.md) | Moves a Vercel app, including the users, private files, jobs, and settings that a code export leaves behind. | Stack, Solo | 2026-11-21, on Stack v0.3.0: read and reviewed |

<!-- CATALOG:END -->

`index.yml` holds the same catalog for coding agents and scripts.
`scripts/build_index.py` writes both catalogs from the recipe files, so the
catalogs always match the recipes.

## What stays out

Recipes add to the Stack and Solo, but a recipe never swaps out one of their
parts. For example, replacing Postgres with MySQL, or Cloudflare Tunnel with a
public web server, breaks the security, backup, and recovery promises that the
Stack and Solo are tested to keep. This repository does not accept recipes like
that.

You can still make such a change on your own system, because the Stack and Solo
are open source and plain files. Your coding agent explains what you give up
first. The changed part is then your own design, and the tests and support for
the Stack and Solo no longer cover that part.

## Contributing

Built something useful on your own Stack or Solo? Your coding agent can turn
your work into a recipe. [CONTRIBUTING.md](CONTRIBUTING.md) has a prompt you can
paste, and the [backlog](BACKLOG.md) lists the recipes people want most.

| Document | What the document gives you |
| --- | --- |
| [CONTRACT.md](CONTRACT.md) | The rules every recipe follows: the fields at the top of the file, the required sections, and the Stack rules a recipe must keep |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to send a recipe, and how a maintainer checks the recipe |
| [BACKLOG.md](BACKLOG.md) | Recipes we would love to have, most wanted first |
| [AGENTS.md](AGENTS.md) | Instructions for a coding agent working in this repository |

## License

Monkeymaxxing Recipes is licensed under the [Apache License 2.0](LICENSE).
