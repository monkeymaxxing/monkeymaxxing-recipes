---
id: umami-analytics
title: Add Umami web analytics
category: services
applies_to: [stack, solo]
summary: Runs Umami, cookieless web analytics, in a locked-down container behind your Cloudflare Tunnel, with its data in your existing Postgres and its backups, and with MMWatchdog checks.
author: monkeymaxxing
vetted_on: 2026-11-23
vetted_against:
  stack: v0.3.1
  solo: v0.1.0
vetted_method: live-checkpoint
---

# Add Umami web analytics

> [!IMPORTANT]
> Reviewed once when added. Recipes are not re-tested on every Stack or Solo release and are outside core support.

This recipe runs [Umami](https://umami.is/), an open-source web analytics
program, at its own host name, such as `analytics.example.com`. Your site
loads Umami's small script, which counts page views and visitors without
cookies. Umami keeps its data in a new database, `umami`, on the Postgres
server you already run, so the core backups cover it.

## When to use this (and when you don't need it)

Use this recipe when you want to know which pages people read, where they
come from, and how many there are, and you want that data on your own
servers instead of a third party's. Umami sets no cookie and stores no IP
address, which often removes the need for a cookie banner. Check that with
your own legal adviser for your country.

You may not need it:

- **Cloudflare Web Analytics** is free, needs no server, and is one switch
  in Cloudflare's dashboard for a host name that is already proxied. It
  shows page views, referrers, and countries. Choose it when that is all you
  want to know: it costs nothing to run or to update.
- **Your app's own logs and metrics** already count requests per route.
- **Umami Cloud**, the hosted service of Umami's makers, has a free tier.
  Choose it when you want Umami's reports without running Umami yourself.

Choose this recipe when you want Umami's reports (events, funnels, goals,
several sites in one place) and want the data in your own database.

## What it adds and what it costs

| Part | What it is |
| --- | --- |
| A container | `custom-umami.container`, a Podman Quadlet file, which systemd runs as `custom-umami.service` on `127.0.0.1:3000` |
| Software | Umami's official image, `ghcr.io/umami-software/umami:3.5.0`, pinned by its SHA-256 digest, and the `podman` package, which the core installs anyway |
| A database | The role `umami` and the database `umami` on your existing Postgres, with one login rule in `/etc/postgresql/pg_hba_custom_umami.conf` |
| Two vault secrets | The database password and Umami's `APP_SECRET`, both random. Step 2 names them for each product. |
| Two roles | `roles/custom_umami_database/main.yml` and `roles/custom_umami/` (`main.yml` and `files/umami.env`) |
| Fleet stages | On Solo, one stage, `custom_umami`. On the Stack, two: `custom_umami_database` on the database servers and `custom_umami` where the tunnel connector runs. Both inside the `# --- Custom extensions ---` lines. |
| One setting | `custom.umami` in `mmx_project_settings.yml` |
| An MMWatchdog check file | `mmwatchdog_checks/custom_umami.yml`, with the check group `custom_umami` |
| Edits to core files | One route in the core's `cloudflared_config.yml`, one restore-drill query in the app's settings, and, on the Stack only, the app's `secrets_from_vault` and three `app_secrets` lines (step 2). |
| Cloudflare | One proxied DNS record, and, as this recipe recommends, a Cloudflare Access application in front of the dashboard |

**Cost:** $0 a month in new servers. Umami uses about 200 to 400 MB of
memory on each server that runs it; measure it with
`systemctl status custom-umami.service`. Each page view is one small row in
Postgres, so a site with a million page views a month adds a few hundred
megabytes a year to the database and its backups. Cloudflare Access is free
for up to 50 people.

**Ongoing work:**

- **Updates are yours.** The image is pinned, so Umami's security fixes do
  not arrive by themselves. Watch Umami's releases on GitHub. To update, put
  the new tag and its digest in `custom.umami.image` and run the
  `custom_umami` stage. Umami changes its own tables at start (Prisma
  migrations), so read the release notes first, and update in a quiet hour.
- **The tunnel restarts once** when you add the route, as for any change to
  `cloudflared_config.yml`. With one tunnel connector, such as on Solo,
  requests drop for a few seconds.
- **Data grows forever unless you trim it.** Umami keeps every event. Delete
  old data in Umami's settings for a website when you no longer need it.

## Data, security, and backups

**Stateful, and covered by the core backups.** Umami keeps everything in the
database `umami` on your existing Postgres. The container itself keeps
nothing. So the core's continuous pgBackRest backups, with their locked
retention, and the weekly restore check cover Umami's data with no new
backup job. pgBackRest backs up the whole Postgres cluster, every database
in it, so a restore brings `umami` back with your app's data, to the same
moment.

**Proving the restore.** Step 7 adds one query to your app's
`restore_drill_check_queries`:

```sql
select exists (select 1 from pg_database where datname = 'umami')
```

The weekly restore check then fails if a restored backup lacks the `umami`
database. The query runs in the app's own database, and reads the cluster's
list of databases, which every database can see. pgBackRest restores the
cluster byte for byte, so the tables inside `umami` come back with it.

**No open port.** Umami listens on `127.0.0.1:3000` only. Umami's default
startup script (`scripts/start-docker.sh`) forces `HOSTNAME=0.0.0.0`, so the
Quadlet overrides `Exec=` to run the same database check and tracker update
and then start `node server.js` with `HOSTNAME=127.0.0.1`. The tunnel
connector that the core already runs carries `analytics.example.com` in from
Cloudflare. The recipe adds no firewall rule and no WireGuard connection:

- On Solo, Umami reaches Postgres at `solo01`'s own WireGuard address, as the
  app does.
- On the Stack, Umami runs on the app servers and reaches the database
  servers over the WireGuard connection and firewall rule that the apps
  already use for port 5432.

**One login rule in Postgres.** `/etc/postgresql/pg_hba_custom_umami.conf`
lets the role `umami` log in to the database `umami` only, with its
password, only from where Umami runs: `solo01`'s own address, or the app
servers' address range. The core's `pg_hba.conf` includes it with one
`include_if_exists` line, the same way it includes the apps' own rules.

**A locked-down container.** It has the same limits as the app's own
containers: a read-only file system with memory-backed `/tmp` and
`.next/cache`, `UserNS=auto` (root inside is not root on the server; the
image already runs as its own account, `nextjs`), no Linux capability,
`NoNewPrivileges=true`, and the core's AppArmor profile for app containers.
`DISABLE_TELEMETRY=1` and `DISABLE_UPDATES=1` stop Umami from reporting to
its makers and from checking for new versions.

> [!CAUTION]
> **Umami starts with the account `admin` and the password `umami`.**
> Anyone who reaches the dashboard can sign in with them. Step 9 puts the
> dashboard behind Cloudflare Access before the address is public, and step
> 11 changes the password at the first sign-in. Do not skip either.

**Secrets.** Two random values, both in the vault, never in Git:

- The database password of the role `umami`.
- `APP_SECRET`, with which Umami signs its sign-in tokens.

They reach one file, `/etc/custom_umami/umami.env` (mode `0600`, owner
`root`), which Podman passes to the container. On the Stack they also reach
the app's own secrets file, `/etc/shop/shop.env`, because the Stack gives a
vault key to servers only through an app's `secrets_from_vault` (step 2).

**MMWatchdog checks added**, in the check group `custom_umami` (underscores
only, so the triage agent can run it):

1. `umami_container_runs`: `custom-umami.service` is active.
2. `umami_answers_on_loopback`: `http://127.0.0.1:3000/api/heartbeat`
   answers 200.
3. `umami_public_address_answers`: `https://analytics.example.com/api/heartbeat`
   answers 200 through Cloudflare. It fails when the route, the DNS record,
   or the Access bypass for the heartbeat is missing.
4. `umami_reaches_its_database`: a new line in Umami's log that says it
   cannot reach Postgres, or cannot write to it. On the Stack this is the
   sign of a database failover (see the note in step 6).

All four send a `warn` alert: the site works without analytics. Change
`alert_severity` to `sos` to be woken.

## Apply steps

> [!WARNING]
> **This recipe adds vault keys** and, on the Stack, changes the app's
> `secrets_from_vault` and three `app_secrets` lines outside the extension
> block. It also changes the core's `cloudflared_config.yml` and adds a
> public address. The coding agent tells the person all of this, and waits
> for yes, before it starts. It touches no `sudoers`, no `ssh/`, no firewall
> rule, and no file that the Stack's desk review watches.

**The coding agent adapts these values:** the host name
(`analytics.example.com`, in a domain that is already at Cloudflare), the
app's name (`shop`), and `listen_port` when something on the server already
uses 3000 (`ss -tlnp | grep ':3000'` shows nothing when it is free).

**Where it runs on the Stack.** The Umami container runs where the tunnel
connector runs: on every app server, one server at a time. Each app
server's `cloudflared` sends `analytics.example.com` to its own
`127.0.0.1:3000`, so each app server needs its own Umami. All of them share
the one `umami` database. Umami changes its tables at start; the stage starts
one server at a time, and Prisma's migrations take a Postgres lock, so two
starts never change the tables at once.

**This recipe covers a Stack whose tunnel runs on the app servers only.**
Load-balancer servers have no firewall rule to the database servers, so
Umami cannot run there. Before the team adds load-balancer servers, the
coding agent either removes this recipe or extends it with a
`connections_between_server_pools` line from `load_balancer_servers` to
`database_servers` on port 5432 and a second login rule for their range.
That is a firewall change, so it asks the person first. Without it, the
load-balancer servers' `cloudflared` would send some analytics requests to
a port where nothing listens.

### 1. The settings, in `mmx_project_settings.yml`

Replace `custom: {}` with the block below. When `custom:` already has other
keys, add only the `umami:` key under it.

```yaml
# mmx_project_settings.yml, between the Custom extensions lines
  custom:
    umami:
      # Umami's official image, pinned by tag and by digest. Podman pulls by
      # the digest, so the image cannot change under the same tag. To update,
      # replace both with the new release's tag and digest.
      image: ghcr.io/umami-software/umami:3.5.0@sha256:27775432b252a187bd1e39c2e4e5e686ca71742f5fa08943ee2d18a1850ffc59
      host_name: analytics.example.com
      # Umami's port on 127.0.0.1. Reason for 3000: Umami's own default.
      listen_port: 3000
```

### 2. The secrets

**On Solo,** the coding agent makes both values itself, at random, inside
MMX. Neither is printed:

```sh
set-up-solo-services secrets generate --repo-dir . --key umami_database_password --length 48
set-up-solo-services secrets generate --repo-dir . --key umami_APP_SECRET --length 64
```

**Check:** `set-up-solo-services secrets list --repo-dir .` lists both keys.

**On the Stack,** the person's `ssh desk01-secrets` makes only the keys that
an app lists under `secrets_from_vault`, so Umami's two values are listed
under the app, as `UMAMI_DATABASE_PASSWORD` and `UMAMI_APP_SECRET`. The
vault keys are then `shop_UMAMI_DATABASE_PASSWORD` and `shop_UMAMI_APP_SECRET`.
The cost: the app's own containers also get both values in their
environment, and the app ignores them.

```yaml
# mmx_project_settings.yml, in apps.shop.secrets_from_vault
        UMAMI_DATABASE_PASSWORD:
          where_the_value_comes_from: generated_by_the_setup
        UMAMI_APP_SECRET:
          where_the_value_comes_from: generated_by_the_setup
```

The Stack refuses to run while an app's `secrets_from_vault` name is
missing from `app_secrets:`. Add two lines to each of the three
`app_secrets:` lists in `playbooks/every_server.yml`, in the stages
`jobs_server`, `app_server`, and `app_server_on_staging01`, beside the app's
other secrets:

```yaml
# playbooks/every_server.yml, in the app_secrets of jobs_server and app_server
            shop_UMAMI_DATABASE_PASSWORD: "{{ .secrets.shop_UMAMI_DATABASE_PASSWORD }}"
            shop_UMAMI_APP_SECRET: "{{ .secrets.shop_UMAMI_APP_SECRET }}"
```

```yaml
# playbooks/every_server.yml, in the app_secrets of app_server_on_staging01
            shop_UMAMI_DATABASE_PASSWORD: "{{ .secrets.staging_shop_UMAMI_DATABASE_PASSWORD }}"
            shop_UMAMI_APP_SECRET: "{{ .secrets.staging_shop_UMAMI_APP_SECRET }}"
```

These lines are outside the `# --- Custom extensions ---` lines. Record
them under `## Custom extensions` in your systems repository's `AGENTS.md`.
Commit and push. Then the person runs `ssh desk01-secrets`, which makes the
keys at random and pushes the vault. **Check:**
`ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
lists both keys, and not as `not defined`.

### 3. The database role, `roles/custom_umami_database/main.yml`

```yaml
# roles/custom_umami_database/main.yml
# The database of Umami on the existing Postgres, from the recipe
# custom_recipes/umami-analytics.md: one login rule, the role umami, and the
# database umami. The core's pgBackRest backups and restore check cover the
# whole cluster, so they cover this database too.
#
# The login rule lives in /etc/postgresql/pg_hba_custom_umami.conf, which
# pg_hba.conf includes, the same way the core includes the apps' rules. On
# the Stack, every database server gets the file, so a replica that becomes
# the primary already lets Umami in. The role and the database are created
# on the server that takes writes only; the replicas get them through
# replication.
inputs:
  postgresql_major_version:                 # vars.postgresql_major_version
    type: integer
    required: true
  pg_hba_file:                              # the cluster's pg_hba.conf
    type: string
    required: true
  login_address:                            # where Umami connects from, as one pg_hba.conf address
    type: string
    required: true
  this_server_takes_writes:                 # true on Solo; on the Stack, true on the primary only
    type: boolean
    required: true
  database_password:                        # the vault key of the umami role's password
    type: string
    required: true
    secret: true

node_tasks:
  - id: include_the_umami_login_in_pg_hba_conf
    line:
      path: "{{ .inputs.pg_hba_file }}"
      line: include_if_exists /etc/postgresql/pg_hba_custom_umami.conf
      insert_at_end_of_file: true
  - task_block:
      id: custom_umami_login
      changes:
        - id: write_the_umami_login_rule
          file:
            path: /etc/postgresql/pg_hba_custom_umami.conf
            content: |
              # Managed by MMX from roles/custom_umami_database/main.yml in the systems repository.
              # Umami's role logs in to its own database only, with its password,
              # only from where Umami runs.
              host    umami   umami   {{ .inputs.login_address }}   scram-sha-256
            owner: root
            group: postgres
            permissions_mode: "0640"
      activate:
        # Postgres reads pg_hba.conf again without dropping a connection.
        - id: reload_postgres
          shell:
            script: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/psql" --no-psqlrc --quiet --port 5432 --command "select pg_reload_conf()"'
            run_as_user_account: postgres
            env:
              POSTGRESQL_MAJOR_VERSION: "{{ .inputs.postgresql_major_version }}"
            only_when_tracked_inputs_changed: true

  - id: login_role_of_umami
    when: "{{ .inputs.this_server_takes_writes }}"
    postgresql_role:
      name: umami
      password: "{{ .inputs.database_password }}"
      can_log_in: true
      superuser: false
      can_create_databases: false
      can_create_roles: false
      can_start_replication: false
      member_of_roles: []
      member_of_roles_not_listed: remove
  # The same collation as the apps' databases: C.UTF-8 never changes with
  # the operating system's C library.
  - id: database_of_umami
    when: "{{ .inputs.this_server_takes_writes }}"
    postgresql_database:
      name: umami
      owner: umami
      encoding: UTF8
      locale: C.UTF-8
      template_database: template0
```

### 4. The container role, `roles/custom_umami/`

First create the environment file template, `roles/custom_umami/files/umami.env`.
It picks the WireGuard address of the database server that takes writes
(directly from `database_host` on Solo, or from `database_servers` on the
Stack) and refuses to render if no server takes writes:

```text
{{- /*
  /etc/custom_umami/umami.env, mode 0600, root. Podman passes it to the
  container. Both secrets are letters and digits, so the URL needs no
  escaping.
*/ -}}
{{- $host := .inputs.database_host -}}
{{- if not $host -}}
{{- range $name, $server := .inputs.database_servers -}}
{{- if eq (toString $server.takes_writes) "true" }}{{ $host = toString $server.private_ip }}{{ end -}}
{{- end -}}
{{- end -}}
{{- if not (regexMatch `^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$` $host) -}}
{{ fail "No database server reported that it takes writes, so Umami has no database to connect to. Check the database servers with show_the_database_servers_and_their_health, then run again." }}
{{- end -}}
# Managed by MMX from roles/custom_umami/files/umami.env in the systems repository.
DATABASE_URL=postgresql://umami:{{ .inputs.database_password }}@{{ $host }}:5432/umami?connect_timeout=3
APP_SECRET={{ .inputs.app_secret }}
```

Then create `roles/custom_umami/main.yml`:

```yaml
# roles/custom_umami/main.yml
# Umami web analytics in a Podman container, from the recipe
# custom_recipes/umami-analytics.md. Umami listens on 127.0.0.1 only. The
# tunnel connector that the core runs (cloudflared) sends the host name to
# it, by the route in the core's cloudflared_config.yml. Umami keeps its data
# in the database umami; the container keeps nothing.
#
# The role installs Podman itself. Reason: the custom extension stages run
# before the core's app stages, which install Podman, so a new server would
# not have it yet. The core installs the same package later, which changes
# nothing.
inputs:
  image:                                    # custom.umami.image: a tag and a sha256 digest
    type: string
    required: true
  listen_port:                              # custom.umami.listen_port, on 127.0.0.1 only
    type: integer
    required: true
  database_host:                            # Solo: solo01's WireGuard address; Stack: leave empty
    type: string
    default: ""
  database_servers:                         # Stack: .outputs.custom_umami_database; Solo: leave empty
    type: mapping
    default: {}
  apparmor_profile:                         # solo-app-containers on Solo, monkeymaxxing-app-containers on the Stack
    type: string
    required: true
  database_password:
    type: string
    required: true
    secret: true
  app_secret:                               # Umami's APP_SECRET, which signs its sign-in tokens
    type: string
    required: true
    secret: true

node_tasks:
  - id: the_image_is_pinned_by_its_digest
    assert:
      that:
        matches: ["{{ .inputs.image }}", '^ghcr\.io/umami-software/umami:[0-9A-Za-z._-]+@sha256:[0-9a-f]{64}$']
      message: >-
        custom.umami.image in mmx_project_settings.yml is "{{ .inputs.image }}". Write
        the image with its tag and its digest, such as
        ghcr.io/umami-software/umami:3.5.0@sha256:<64 hexadecimal characters>.
        Nothing changed.

  - id: install_podman
    apt_package:
      packages:
        - {name: podman, version: newest_when_first_installed}
  - id: pull_the_umami_image
    podman_image:
      image: "{{ .inputs.image }}"
      pull_image: when_missing

  - task_block:
      id: custom_umami
      changes:
        - id: create_the_settings_directory
          directory:
            path: /etc/custom_umami
            owner: root
            group: root
            permissions_mode: "0755"
        # Only root reads it. Podman passes it to the container.
        - id: write_the_umami_environment_file
          file:
            path: /etc/custom_umami/umami.env
            template: files/umami.env
            owner: root
            group: root
            permissions_mode: "0600"
        - id: install_the_quadlet_file
          podman_quadlet:
            name: custom-umami.container
            content: |
              # Managed by MMX from roles/custom_umami/main.yml in the systems repository.
              [Unit]
              Description=Umami web analytics (loopback only)

              [Container]
              ContainerName=custom-umami
              Image={{ .inputs.image }}
              # The server's own network, as the apps' containers have.
              # Umami's default scripts/start-docker.sh forces HOSTNAME=0.0.0.0,
              # so Exec runs the same startup steps with HOSTNAME=127.0.0.1.
              Network=host
              Exec=sh -ec 'export PATH="$PWD/node_modules/.bin:$PATH"; node scripts/check-db.js; node scripts/update-tracker.js; export HOSTNAME=127.0.0.1; exec node server.js'
              Environment=PORT={{ .inputs.listen_port }}
              Environment=DISABLE_TELEMETRY=1
              Environment=DISABLE_UPDATES=1
              EnvironmentFile=/etc/custom_umami/umami.env
              LogDriver=journald
              # The same limits as the apps' containers. Next.js writes its
              # cache to /app/.next/cache, an empty memory-backed folder here.
              ReadOnly=true
              ReadOnlyTmpfs=true
              Tmpfs=/app/.next/cache:mode=1777
              UserNS=auto
              DropCapability=all
              NoNewPrivileges=true
              PodmanArgs=--security-opt=apparmor={{ .inputs.apparmor_profile }}
              StopTimeout=30

              [Service]
              Restart=always
              # Umami changes its tables at start, which can take a while
              # after an update.
              TimeoutStartSec=300

              [Install]
              WantedBy=multi-user.target
      activate:
        - id: run_umami
          systemd_service:
            name: custom-umami.service
            state: running
            refresh: restart
      verify:
        - id: wait_until_umami_answers
          wait_for:
            url_responds: "http://127.0.0.1:{{ .inputs.listen_port }}/api/heartbeat"
            expected_http_status_codes: [200]
            wait_at_most: 180s
```

### 5. The fleet stage on Solo, in `playbooks/solo_server.yml`

Put this stage between the `# --- Custom extensions (start) ---` and
`# --- Custom extensions (end) ---` lines, above the last "Keep these three
boundary comment lines" line. The block runs after `postgres_and_backups`, so
Postgres is ready.

```yaml
  - id: custom_umami
    nodes: solo_server
    on_node_failure: stop_run
    node_tasks:
      - role: custom_umami_database
        inputs:
          postgresql_major_version: "{{ .vars.postgresql_major_version }}"
          pg_hba_file: "/etc/postgresql/{{ .vars.postgresql_major_version }}/main/pg_hba.conf"
          login_address: "{{ .vars.private_ip }}/32"
          this_server_takes_writes: true
          database_password: "{{ .secrets.umami_database_password }}"
      - role: custom_umami
        inputs:
          image: "{{ .vars.custom.umami.image }}"
          listen_port: "{{ .vars.custom.umami.listen_port }}"
          database_host: "{{ .vars.private_ip }}"
          apparmor_profile: solo-app-containers
          database_password: "{{ .secrets.umami_database_password }}"
          app_secret: "{{ .secrets.umami_APP_SECRET }}"
```

### 6. The fleet stages on the Stack, in `playbooks/every_server.yml`

Put both stages, in this order, between the `# --- Custom extensions (start) ---`
and `# --- Custom extensions (end) ---` lines. The block runs after the
database servers' stages, so Postgres is ready.

The first stage asks each database server whether it takes writes, and
creates the database on the one that does. The second stage gives Umami that
server's address, on each app server, while the tunnel connector runs
there.

```yaml
  - id: custom_umami_database
    nodes: database_servers
    max_nodes_at_once: 1
    on_node_failure: stop_fleet_stage
    node_tasks:
      - id: find_whether_this_server_takes_writes
        shell:
          script: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/psql" --no-psqlrc --quiet --port 5432 --tuples-only --no-align --command "select json_build_object(''takes_writes'', not pg_is_in_recovery())"'
          run_as_user_account: postgres
          run_script_in_dryrun: true
          changed_when: false
          env:
            POSTGRESQL_MAJOR_VERSION: "{{ .vars.postgresql_major_version }}"
      - role: custom_umami_database
        inputs:
          postgresql_major_version: "{{ .vars.postgresql_major_version }}"
          pg_hba_file: "/var/lib/postgresql/{{ .vars.postgresql_major_version }}/pg_auto_failover_node/pg_hba.conf"
          login_address: "{{ .vars.private_ip_ranges.app_servers }}"
          this_server_takes_writes: "{{ .node_tasks.find_whether_this_server_takes_writes.stdout_json.takes_writes }}"
          database_password: "{{ .secrets.shop_UMAMI_DATABASE_PASSWORD }}"
    outputs:
      takes_writes: "{{ .node_tasks.find_whether_this_server_takes_writes.stdout_json.takes_writes }}"
      private_ip: "{{ .vars.private_ip }}"

  - id: custom_umami
    nodes: app_servers
    when:
      not: "{{ .vars.tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers }}"
    max_nodes_at_once: 1
    on_node_failure: stop_fleet_stage
    node_tasks:
      - role: custom_umami
        inputs:
          image: "{{ .vars.custom.umami.image }}"
          listen_port: "{{ .vars.custom.umami.listen_port }}"
          database_servers: "{{ .outputs.custom_umami_database }}"
          apparmor_profile: monkeymaxxing-app-containers
          database_password: "{{ .secrets.shop_UMAMI_DATABASE_PASSWORD }}"
          app_secret: "{{ .secrets.shop_UMAMI_APP_SECRET }}"
```

> [!NOTE]
> **After a database failover on the Stack.** Your app finds the new primary
> by itself, because its `DATABASE_URL` lists every database server. Umami's
> database library (Prisma) takes one server only, so Umami keeps using the
> server that took writes at the last run. After a failover, Umami cannot
> record visits, and the check `umami_reaches_its_database` warns. Run the
> two stages again, and Umami follows the new primary:
> `./server_management_scripts/run_mmx_on_util01 run every_server --only-fleet-stages custom_umami_database,custom_umami`.
> With one database server, which is the Stack's default, this never happens.

### 7. The restore proof, in the app's settings

Add one query to the app's existing `restore_drill_check_queries` in
`mmx_project_settings.yml`:

```yaml
# mmx_project_settings.yml, in apps.shop.restore_drill_check_queries
        - name: the_umami_analytics_database_came_back
          sql: select exists (select 1 from pg_database where datname = 'umami')
```

### 8. The checks, `mmwatchdog_checks/custom_umami.yml`

Create the file. Then append `custom_umami.yml` to the end of the
`mmwatchdog_check_files` list that already exists. Never replace the list.

- Stack: in `inventories/servers.yml`, in the group `app_servers`. A default
  list then reads `mmwatchdog_check_files: [every_server.yml, app_servers.yml, custom_umami.yml]`.
- Solo: in `mmx_project_settings.yml`. A default list then reads
  `mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_umami.yml]`.

```yaml
# Managed by MMX from mmwatchdog_checks/custom_umami.yml in the systems repository.
# Umami web analytics, from the recipe custom_recipes/umami-analytics.md.
# Reason for warn: the site works without analytics. To be woken for a
# check, set that check's alert_severity to sos.
check_groups:
  custom_umami:
    check_every: 1m
    time_limit_per_run: 10s
    # Reason for 5 minutes: Umami changes its tables at start after an update.
    alert_after_failing_for: 5m
    recovered_after_healthy_for: 1m
    checks:
      umami_container_runs:
        systemd_unit_state:
          systemd_unit: custom-umami.service
          fail_when: the_unit_is_not_active
        alert_severity: warn
      umami_answers_on_loopback:
        http:
          url: "http://127.0.0.1:{{ .inputs.custom.umami.listen_port }}/api/heartbeat"
          expected_http_status_codes: [200]
        alert_severity: warn
      # Asks through Cloudflare and the tunnel. It also fails when the route
      # in cloudflared_config.yml, the DNS record, or the Cloudflare Access
      # bypass for /api/heartbeat is missing.
      umami_public_address_answers:
        http:
          url: "https://{{ .inputs.custom.umami.host_name }}/api/heartbeat"
          expected_http_status_codes: [200]
        alert_severity: warn
      # An event check: it warns at the first new log line that says Umami
      # cannot reach Postgres or cannot write to it, such as after a
      # failover on the Stack. It ends 30 minutes after the last such line.
      umami_reaches_its_database:
        log_lines:
          journal_of_systemd_unit: custom-umami.service
          fail_when_a_new_line_matches_regex: "read-only transaction|Can't reach database server|password authentication failed"
        alert_severity: warn
        recovered_after_healthy_for: 30m
```

### 9. The route, the dashboard's protection, and the DNS record

**The route in the tunnel.** Open the core's tunnel routes and add one route
above the catch-all line `- service: http_status:404`:

- Stack: `roles/tunnel_connector_and_caddy/files/cloudflared_config.yml`
- Solo: `roles/apps_and_tunnel/files/cloudflared_config.yml`

```yaml
  # custom_recipes/umami-analytics.md: Umami, on this server's loopback.
  - hostname: analytics.example.com
    service: http://127.0.0.1:3000
```

The host name and the port must match `host_name` and `listen_port` in step 1.
Record the edit under `## Custom extensions` in your systems repository's
`AGENTS.md`: the file now differs from the core's.

**Cloudflare Access in front of the dashboard (recommended).** The person
does this in Cloudflare's dashboard, under Zero Trust, Access,
Applications, **before** the DNS record exists:

1. A self-hosted application for `analytics.example.com`, all paths, with
   an Allow policy for the team's email addresses. Only the team then
   reaches the sign-in page and the reports.
2. A second self-hosted application for the same host name, with the paths
   `script.js`, `api/send`, and `api/heartbeat`, and a Bypass policy for
   Everyone. Visitors' browsers load the script and send their page views
   there, and MMWatchdog's public check reads the heartbeat. Access applies
   the more specific path first.

Without Access, the sign-in page is public. Then do step 11 within minutes
of adding the DNS record, before anyone else finds the address.

**The DNS record at Cloudflare.** Add a proxied CNAME record for the host
name, to the same tunnel that your app uses: `analytics` →
`TUNNEL_ID.cfargotunnel.com`, with "Proxied" on, the same way the setup
made the DNS record of your app's host name. Tell the person first: this
adds a public address.

### 10. Record it and run

Save this recipe as `custom_recipes/umami-analytics.md` with `source_url`,
`source_commit`, and `applied_on` at the top. Add an entry to
`custom_extensions:` in your checklist file (`monkeymaxxing_stack_checklist.yml`
or `monkeymaxxing_solo_checklist.yml`):

```yaml
custom_extensions:
  - id: umami-analytics
    title: Add Umami web analytics
    recipe: services/umami-analytics.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/services/umami-analytics.md
    source_commit: "<SHA>"
    applied_on: "2026-11-23"
    state: done
    verification: "The six steps of the Verification check section passed."
```

Replace `<SHA>` with the full commit you read and the date with the UTC date
of the applying commit.

Then follow your `AGENTS.md`: run `mmx validate`, commit, publish, run
`mmx dryrun`, and run in a quiet hour (the tunnel restarts). On the Stack, run
`./server_management_scripts/run_mmx_on_util01 run every_server`. On Solo,
run `mmx run solo_server`.

### 11. Change the password, and add the site

The person signs in at `https://analytics.example.com/login` as `admin`
with the password `umami`, and at once changes the password in Settings,
Profile, to a long one from their password manager. Then they add a website
in Settings, Websites, and copy its tracking code into the app's page
layout, such as:

```html
<script defer src="https://analytics.example.com/script.js" data-website-id="WEBSITE_ID"></script>
```

When the app sends a `Content-Security-Policy` header, add
`https://analytics.example.com` to its `script-src` and `connect-src`.

## Verification check

Run steps 1, 2, and 4 on a server that runs Umami (an app server on the
Stack, or `solo01` on Solo). On the Stack, use
`./server_management_scripts/run_mmx_on_util01 run-command --nodes app_servers -- COMMAND`.
On Solo, use `mmx run-command --nodes solo_server -- COMMAND`.

1. **Only the loopback address listens:**

   ```sh
   ss -tlnp | grep ':3000'
   ```

   Expected: exactly one line, with `127.0.0.1:3000`. A line with
   `0.0.0.0:3000`, `*:3000`, or `[::]:3000` means the recipe is wrong: stop
   and fix it.

2. **Umami answers on the loopback address:**

   ```sh
   curl -fsS http://127.0.0.1:3000/api/heartbeat
   ```

   Expected: exit code 0 and a short JSON answer, such as `{"ok":true}`.

3. **The public address works, and the dashboard is protected.** From any
   computer:

   ```sh
   curl -fsS https://analytics.example.com/api/heartbeat
   curl -sS -o /dev/null -w '%{http_code}\n' https://analytics.example.com/script.js
   curl -sS -o /dev/null -w '%{http_code}\n' https://analytics.example.com/login
   ```

   Expected: the same JSON answer; `200` for the script; and, with Access,
   a redirect (`302`) to Cloudflare Access for `/login`. A `404` from
   Cloudflare means the route is missing or does not match. A DNS error
   means the DNS record is not done.

4. **MMWatchdog is happy:**

   ```sh
   sudo mmwatchdog check-now custom_umami --count-as-scheduled-run --json
   ```

   Expected: exit code 0, with the four checks `umami_container_runs`,
   `umami_answers_on_loopback`, `umami_public_address_answers`, and
   `umami_reaches_its_database` healthy.

5. **The data is in Postgres.** Open a page of your site in a browser, then,
   on `solo01` or on the Stack's primary database server:

   ```sh
   runuser -u postgres -- psql --no-psqlrc --dbname umami --tuples-only --command "select count(*) from website_event"
   ```

   Expected: a number above 0.

6. **The password is changed.** Signing in as `admin` with `umami` fails.

The next weekly restore check proves the backup: its result lists
`the_umami_analytics_database_came_back` as passed.

## Clean removal

Remove everything, in this order, so no alert fires while it goes.

1. **Keep the old numbers, if the team wants them.** Dropping the database
   deletes every page view Umami recorded. The core backups keep it only
   until their retention ends. To keep it for longer, dump it first, on
   `solo01` or the Stack's primary database server, and move the file to
   wherever the team keeps records:

   ```sh
   runuser -u postgres -- pg_dump --format=custom --dbname umami --file /var/lib/postgresql/umami-final.dump
   ```

2. **Remove the public side.** Delete the tracking code from the app and
   deploy. Delete the proxied CNAME record and both Cloudflare Access
   applications. Remove the route (the `hostname:` line, the `service:` line,
   and their comment) from `cloudflared_config.yml`.
3. **Swap the stages for removal stages.** In the `# --- Custom extensions ---`
   block, replace the Umami stages with these, in this order: the container
   goes first, so no session holds the database open when it is dropped.

   ```yaml
     - id: remove_the_custom_umami_container
       nodes: app_servers                               # Solo: solo_server
       on_node_failure: stop_fleet_stage                # Solo: stop_run
       node_tasks:
         - id: remove_the_umami_container
           podman_quadlet:
             name: custom-umami.container
             state: file_and_service_removed_named_volumes_kept
         - id: remove_the_umami_settings
           directory:
             path: /etc/custom_umami
             state: absent
             also_delete_everything_inside: true
         - id: remove_the_umami_image
           shell:
             script: podman image rm --ignore "$IMAGE"
             env:
               IMAGE: ghcr.io/umami-software/umami:3.5.0@sha256:27775432b252a187bd1e39c2e4e5e686ca71742f5fa08943ee2d18a1850ffc59

     - id: remove_the_custom_umami_database
       nodes: database_servers                          # Solo: solo_server
       max_nodes_at_once: 1
       on_node_failure: stop_fleet_stage                # Solo: stop_run
       node_tasks:
         - id: find_whether_this_server_takes_writes
           shell:
             script: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/psql" --no-psqlrc --quiet --port 5432 --tuples-only --no-align --command "select json_build_object(''takes_writes'', not pg_is_in_recovery())"'
             run_as_user_account: postgres
             run_script_in_dryrun: true
             changed_when: false
             env:
               POSTGRESQL_MAJOR_VERSION: "{{ .vars.postgresql_major_version }}"
         - id: drop_the_umami_database
           when: "{{ .node_tasks.find_whether_this_server_takes_writes.stdout_json.takes_writes }}"
           postgresql_database:
             name: umami
             state: deleted_with_all_its_data
         - id: drop_the_umami_role
           when: "{{ .node_tasks.find_whether_this_server_takes_writes.stdout_json.takes_writes }}"
           postgresql_role:
             name: umami
             state: absent
         - id: remove_the_include_line
           line:
             path: "/var/lib/postgresql/{{ .vars.postgresql_major_version }}/pg_auto_failover_node/pg_hba.conf"   # Solo: /etc/postgresql/{{ .vars.postgresql_major_version }}/main/pg_hba.conf
             line: include_if_exists /etc/postgresql/pg_hba_custom_umami.conf
             state: absent
         - id: remove_the_umami_login_rule
           file:
             path: /etc/postgresql/pg_hba_custom_umami.conf
             state: absent
         - id: reload_postgres
           shell:
             script: '"/usr/lib/postgresql/$POSTGRESQL_MAJOR_VERSION/bin/psql" --no-psqlrc --quiet --port 5432 --command "select pg_reload_conf()"'
             run_as_user_account: postgres
             env:
               POSTGRESQL_MAJOR_VERSION: "{{ .vars.postgresql_major_version }}"
   ```

   Write the image you had in `custom.umami.image`. The stages leave the
   `podman` package in place: the core installs it for the apps.
4. **Remove the checks, the restore query, and the settings.** Remove
   `custom_umami.yml` from each `mmwatchdog_check_files` list, keeping the
   other entries, and delete `mmwatchdog_checks/custom_umami.yml`. Remove
   `the_umami_analytics_database_came_back` from the app's
   `restore_drill_check_queries`. Delete the `umami:` key under `custom:`;
   when it was the only key, write `custom: {}` again. On the Stack, remove
   `UMAMI_DATABASE_PASSWORD` and `UMAMI_APP_SECRET` from the app's
   `secrets_from_vault` and the six `app_secrets` lines from step 2.
5. **Run it.** Commit, publish, and run `every_server` (Solo:
   `solo_server`). Check that `systemctl status custom-umami.service` says
   the unit could not be found, that `ss -tlnp | grep ':3000'` prints
   nothing, and that
   `runuser -u postgres -- psql --no-psqlrc --tuples-only --command "select count(*) from pg_database where datname = 'umami'"`
   prints `0`.
6. **Delete the rest in a second commit.** Remove both removal stages, the
   folders `roles/custom_umami/` and `roles/custom_umami_database/`,
   `custom_recipes/umami-analytics.md`, the `umami-analytics` entry of
   `custom_extensions:`, and the notes under `## Custom extensions` in
   `AGENTS.md`. The vault keys stay in the vault, unused, which does no harm.
   Run `mmx validate`, commit, and publish. The system is then the same as
   before.
