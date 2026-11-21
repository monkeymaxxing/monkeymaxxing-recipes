---
id: static-site
title: Serve a static site alongside your app
category: services
applies_to: [stack, solo]
summary: Serves a static site, such as a docs or marketing site, from your existing servers and Cloudflare Tunnel, with MMWatchdog checks.
author: monkeymaxxing
vetted_on: 2026-11-21
vetted_against:
  stack: v0.3.0
  solo: v0.1.0
vetted_method: review-only
---

# Serve a static site alongside your app

> [!IMPORTANT]
> Vetted once on submission (`vetted_on`) against `vetted_against`. Not routinely re-tested and outside core Stack/Solo support.

## When to use this (and when you don't need it)

Use this recipe when you want one plain static site, such as a docs site or
a marketing site, at its own host name (for example `docs.example.com`),
next to your app. The site's files live in your systems repository in Git.
The recipe needs no new server, no new package, and no new account.

You may not need it:

- **Your app can serve its own pages.** A marketing page or a docs page is
  often one more route or one more folder of assets in the app. That is the
  simplest choice. It deploys with the app.
- **Cloudflare Pages.** It builds the site from a Git repository, keeps old
  versions, and serves it from Cloudflare's own network. Choose it when the
  site is big, when it changes many times a day, or when a build tool must
  run on each change. It needs a Cloudflare Pages project and a build
  setup, and it is not part of your Stack or Solo servers.

Choose this recipe when the site is small, changes now and then, and you
want it on the servers you already run, behind the tunnel you already have.

## What it adds and what it costs

- **Servers:** none. The site runs on the servers that already run Caddy and
  the tunnel connector: the app servers on the Stack (and the load-balancer
  servers, once you have them), or `solo01` on Solo.
- **Packages:** the `caddy` package, from the same apt repository that the
  core uses. The role installs it itself, with the core's own signing key
  file, so a new or rebuilt server serves the site on its first run. The core
  names the same repository and package, so the two never disagree. MMX
  keeps the package from starting its own `caddy.service` while it installs.
  The site runs as a second, separate Caddy process that serves files.
- **Services:** one systemd service, `custom-static-site.service`. It serves
  the folder `/srv/custom_static_site` on `127.0.0.1:8090`, and nothing else.
- **Files:** a role `roles/custom_static_site/`, one check file
  `mmwatchdog_checks/custom_static_site.yml`, one fleet stage, and the
  setting `custom.static_site`.
- **One edit to a core file.** The tunnel's routes live in the core's
  `cloudflared_config.yml`, because the core's tunnel is managed from Git and
  not from Cloudflare's dashboard. The recipe adds one route to that file,
  above the catch-all line. This is the only core file the recipe changes.
  The Stack merges upgrades into your files with `--3way`, so the route
  survives unless an upgrade changes the exact same lines. A Solo upgrade, or
  a Stack upgrade that does change those lines, can leave a conflict or drop
  the route. The third check below warns you if the route goes away. Record
  the edit under `## Custom extensions` in your systems repository's
  `AGENTS.md`, so the next coding agent knows the file differs from the core.
- **A tunnel restart.** Any change to `cloudflared_config.yml` restarts
  `cloudflared` on the server. On a setup with one connector, such as Solo or
  a Stack with one app server, requests drop for a few seconds. With more
  servers, the others keep serving. Apply the route change in a quiet hour.
- **Cost:** $0 a month. The extra Caddy process is small; measure it with
  `systemctl status custom-static-site.service` on your server.
- **Ongoing work:** Caddy updates come with the core's security updates, but
  this service keeps running the old program until it restarts. A reboot, or
  `systemctl restart custom-static-site.service`, picks up the new program.
  A new version of your site is a commit and a run of one fleet stage. The
  run copies the files and leaves Caddy running; it restarts Caddy only when
  the Caddyfile or the unit changes.
- **Site size:** the files are copied from Git to each server on every run.
  A docs or marketing site of a few megabytes suits this. A site of many
  hundreds of megabytes, such as one with videos, belongs in Cloudflare Pages
  or in object storage.
- **Caching:** Cloudflare caches common file types, such as images, scripts,
  and style sheets, at its edge by default. It does not cache HTML pages
  unless you add a Cache Rule for the host name at Cloudflare.

## Data, security, and backups

- **Stateless.** The service keeps no data. The site's files are in your
  systems repository, and a rebuilt server gets them on its next run. There
  is nothing to back up beyond the repository, and no restore to prove.
- **No open port.** Caddy listens on `127.0.0.1:8090` only. The tunnel
  connector that the core already runs carries web requests in from
  Cloudflare, so no server gets a public web port. The recipe adds no
  firewall rule and no WireGuard connection.
- **Hardened service.** `custom-static-site.service` runs with
  `DynamicUser=yes`, so it has no account of its own and cannot write
  anywhere except its own state folder. It sets `NoNewPrivileges=yes`,
  `ProtectSystem=strict`, `ReadOnlyPaths=/srv/custom_static_site`, and drops
  every Linux capability except the one that Caddy's packaged binary
  carries (`CAP_NET_BIND_SERVICE`, which the service never uses, because the
  port is above 1024). The site files are owned by `root`, so the service
  cannot change them. Caddy's admin interface is switched off.
- **No secret.** The recipe adds no secret to the vault. Nothing in the site's
  folder should be secret: the whole folder is public.
- **MMWatchdog checks added**, in the check group `custom_static_site` (it
  uses underscores only, so the triage agent can run it):
  1. `static_site_file_server_runs`: systemd reports the service as active.
  2. `static_site_answers_on_loopback`: `http://127.0.0.1:8090/` answers 200.
  3. `static_site_public_address_answers`: the public address
     answers 200 through Cloudflare, and the page holds the text from your
     `index.html` (`response_body_contains`), so an empty 200 never passes.
     It also fails when the route or the DNS record is missing, such as after
     an upgrade overwrote the route.
  All three send a `warn` alert. Change `alert_severity` to `sos` to be woken.

## Apply steps

This recipe touches none of the vault's keys, `sudoers`, `ssh/`, or the files
that the systems desk review watches. It changes one core file, as the
section above says: the coding agent tells the person so before it starts.

The coding agent adapts these values to the team's system:

- `docs.example.com` is the host name. Use a host name in a domain that is
  already at Cloudflare, and not one that an app already uses.
- `8090` is the port on `127.0.0.1`. Use another port above 1024 when
  something else on the server already uses 8090 or the range of the app
  ports, which are close to 8001 and 8002.
- On the Stack, the stage follows the core's tunnel stage: it runs on the
  `app_servers` until `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`
  is `true`, and on the `load_balancer_servers` always. During a move to load
  balancers, both pools serve the site. Each pool that serves it also needs
  `custom_static_site.yml` in its `mmwatchdog_check_files` (step 5).

Make these changes in the systems repository.

**1. The settings.** In `mmx_project_settings.yml`, replace `custom: {}` with
the block below. When `custom:` already has other keys, add only the
`static_site:` key under it.

```yaml
  custom:
    static_site:
      host_name: docs.example.com
      listen_port: 8090
```

**2. The role.** Create `roles/custom_static_site/main.yml`:

```yaml
# Serves one static site from this server, for the recipe
# custom_recipes/static-site.md. A second Caddy process serves the folder
# /srv/custom_static_site on 127.0.0.1 only. The tunnel connector that the
# core runs (cloudflared) sends the site's host name to that port, by the
# route in the core's cloudflared_config.yml.
#
# The role installs Caddy itself, from the same apt repository and with the
# same signing key file as the core's role, so a new or rebuilt server serves
# the site on its first run. The core installs the same package later in the
# run, which changes nothing. MMX keeps the package from starting its own
# caddy.service while it installs.
inputs:
  listen_port:                              # custom.static_site.listen_port: above 1024, on 127.0.0.1 only
    type: integer
    required: true

node_tasks:
  - id: add_the_caddy_apt_repository
    apt_repository:
      name: caddy
      uris: [https://dl.cloudsmith.io/public/caddy/stable/deb/debian]
      suites: [any-version]
      components: [main]
      # The core's own key file, so there is only one copy. On Solo, write
      # ../../roles/apps_and_tunnel/files/caddy_apt_signing_key.asc instead.
      # MMX refuses a path with .. in a role input, so the path is written
      # here and not passed in.
      signing_key_source: ../../roles/tunnel_connector_and_caddy/files/caddy_apt_signing_key.asc
  - id: install_caddy
    apt_package:
      packages:
        - {name: caddy, version: newest_when_first_installed}

  # The site's files are copied from roles/custom_static_site/files/site/ in
  # the systems repository. A file that is no longer there is deleted from
  # the server. root owns them, so the service cannot change them. This task
  # stays outside the block below, so a new version of the site never
  # restarts Caddy: Caddy reads the files from the disk on each request.
  - id: copy_the_site_files
    directory:
      path: /srv/custom_static_site
      source: files/site
      also_delete_entries_not_in_source: true
      owner: root
      group: root
      permissions_mode: "0755"
      file_permissions_mode: "0644"

  - task_block:
      id: custom_static_site
      changes:
        - id: create_the_settings_directory
          directory:
            path: /etc/custom_static_site
            owner: root
            group: root
            permissions_mode: "0755"
        # The admin interface is off, so nothing listens on Caddy's usual
        # admin port, and nothing on 127.0.0.1 can change this server's
        # configuration. default_bind 127.0.0.1 binds only the loopback
        # address. The site address http://:PORT has no host name, so Caddy
        # answers any Host header on that port: docs.example.com, as
        # cloudflared passes it on, and 127.0.0.1, for the local checks. The
        # port is reachable only from this server, so no other name can reach
        # it.
        - id: write_the_caddyfile
          file:
            path: /etc/custom_static_site/Caddyfile
            content: |
              # Managed by MMX from roles/custom_static_site/main.yml in the systems repository.
              {
                  admin off
                  auto_https off
                  persist_config off
                  default_bind 127.0.0.1
              }
              http://:{{ .inputs.listen_port }} {
                  root * /srv/custom_static_site
                  encode zstd gzip
                  header X-Content-Type-Options nosniff
                  file_server
              }
            owner: root
            group: root
            permissions_mode: "0644"
            check_new_file:
              shell:
                script: caddy validate --adapter caddyfile --config "$NEW_FILE"
                dryrun: caddy validate --adapter caddyfile --config "$NEW_FILE"
                env:
                  NEW_FILE: "{{ .new_file.path }}"
        # CapabilityBoundingSet keeps CAP_NET_BIND_SERVICE only because
        # Caddy's packaged binary carries that file capability. An empty
        # set would make systemd refuse to start the program. The service
        # uses no capability: it listens above port 1024.
        - id: install_the_unit
          systemd_unit:
            name: custom-static-site.service
            content: |
              # Managed by MMX from roles/custom_static_site/main.yml in the systems repository.
              [Unit]
              Description=Static site file server (Caddy, loopback only)
              After=network-online.target
              Wants=network-online.target

              [Service]
              Type=notify
              DynamicUser=yes
              StateDirectory=custom-static-site
              Environment=XDG_DATA_HOME=/var/lib/custom-static-site XDG_CONFIG_HOME=/var/lib/custom-static-site
              ExecStart=/usr/bin/caddy run --config /etc/custom_static_site/Caddyfile --adapter caddyfile
              Restart=on-failure
              RestartSec=5s
              NoNewPrivileges=yes
              CapabilityBoundingSet=CAP_NET_BIND_SERVICE
              AmbientCapabilities=
              ProtectSystem=strict
              ReadOnlyPaths=/srv/custom_static_site
              ProtectHome=yes
              PrivateTmp=yes
              PrivateDevices=yes
              ProtectKernelTunables=yes
              ProtectKernelModules=yes
              ProtectControlGroups=yes
              RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
              RestrictNamespaces=yes
              LockPersonality=yes
              SystemCallArchitectures=native

              [Install]
              WantedBy=multi-user.target
      activate:
        - id: run_the_file_server
          systemd_service:
            name: custom-static-site
            state: running
            start_at_boot: true
            refresh: restart
      verify:
        - id: wait_until_the_file_server_accepts_connections
          wait_for:
            tcp_port_accepts_connections: "{{ .inputs.listen_port }}"
            wait_at_most: 10s
```

**3. The site.** Put the site's files in `roles/custom_static_site/files/site/`.
Use the site generator's output folder, such as `dist/` or `_site/`. Start with
this page, so the first run has something to serve. Create
`roles/custom_static_site/files/site/index.html`:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Docs</title></head>
<body><h1>Docs</h1><p>This page is served by the static-site recipe.</p></body>
</html>
```

**4. The fleet stage.** Put this stage between the `# --- Custom extensions ---`
lines of the playbook, above its last "Keep these three boundary comment
lines" line, with its own id.

On the Stack, in `playbooks/every_server.yml`. The `nodes:` and `when:` lines
are the same as the core's `tunnel_connector_and_caddy` stage, so the site
runs where the tunnel connector runs:

```yaml
  - id: custom_static_site
    nodes: [app_servers, load_balancer_servers]
    when:
      any:
        - "{{ .vars.is_load_balancer_server }}"
        - not: "{{ .vars.tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers }}"
    max_nodes_at_once: 1
    on_node_failure: stop_fleet_stage
    node_tasks:
      - role: custom_static_site
        inputs:
          listen_port: "{{ .vars.custom.static_site.listen_port }}"
```

On Solo, in `playbooks/solo_server.yml`:

```yaml
  - id: custom_static_site
    nodes: solo_server
    on_node_failure: stop_run
    node_tasks:
      - role: custom_static_site
        inputs:
          listen_port: "{{ .vars.custom.static_site.listen_port }}"
```

**Moving the Stack to load-balancer servers.** While
`tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers` is `false`,
the stage serves the site on the app servers. When you add load-balancer
servers, the stage also serves it there, so both pools answer during the
move. When you set the flag to `true`, the stage stops selecting the app
servers, and the service on them keeps running with nothing to feed it. Once
the load-balancer servers carry the requests, run the removal stage from
"Clean removal" once with `nodes: app_servers`, then delete that stage. Add
`custom_static_site.yml` to the `load_balancer_servers` check list and take it
out of the `app_servers` list in the same commit.

**5. The checks.** Create `mmwatchdog_checks/custom_static_site.yml`. MMX
renders it on each server. Then append `custom_static_site.yml` to the
end of the `mmwatchdog_check_files` list that already exists. Never replace
the list: other custom check packs may be in it.

- Stack: in `inventories/servers.yml`, in the group `app_servers` (and in
  `load_balancer_servers`, once it has servers), append it. A default list
  then reads `mmwatchdog_check_files: [every_server.yml, app_servers.yml, custom_static_site.yml]`.
- Solo: in `mmx_project_settings.yml`, append it. A default list then reads
  `mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_static_site.yml]`.

```yaml
# Managed by MMX from mmwatchdog_checks/custom_static_site.yml in the systems repository.
# To be woken for a check, set that check's alert_severity to sos.
# Reason for warn: a static site is not your app. The check says what failed.
check_groups:
  custom_static_site:
    check_every: 1m
    time_limit_per_run: 10s
    alert_after_failing_for: 5m
    recovered_after_healthy_for: 1m
    checks:
      static_site_file_server_runs:
        systemd_unit_state:
          systemd_unit: custom-static-site.service
          fail_when: the_unit_is_not_active
        alert_severity: warn
      static_site_answers_on_loopback:
        http:
          url: "http://127.0.0.1:{{ .inputs.custom.static_site.listen_port }}/"
          expected_http_status_codes: [200]
        alert_severity: warn
      # Asks through Cloudflare and the tunnel. It also fails when the route
      # in cloudflared_config.yml or the DNS record is missing.
      # response_body_contains is text from your index.html. Change it with
      # the page, or an empty 200 from the tunnel's catch-all could pass.
      static_site_public_address_answers:
        http:
          url: "https://{{ .inputs.custom.static_site.host_name }}/"
          expected_http_status_codes: [200]
          response_body_contains: This page is served by the static-site recipe.
        alert_severity: warn
```

**6. The route in the tunnel.** Open the core's tunnel routes and add one
route above the catch-all line `- service: http_status:404`:

- Stack: `roles/tunnel_connector_and_caddy/files/cloudflared_config.yml`
- Solo: `roles/apps_and_tunnel/files/cloudflared_config.yml`

```yaml
  # custom_recipes/static-site.md: the static site, served on this server's loopback.
  - hostname: docs.example.com
    service: http://127.0.0.1:8090
```

The host name and the port are written here as they are, so they must match
`host_name` and `listen_port` in step 1. A mismatch makes the third check
fail. The route goes through the same tunnel as your apps, so the people who
use it never see a server address. On the Stack, the same file also serves
`staging01`'s tunnel. There the route points at a port where nothing
listens, but no DNS record points at it, so it does no harm.

**7. The DNS record at Cloudflare.** Add a proxied CNAME record for the host
name, to the same tunnel that your app uses:
`docs` → `TUNNEL_ID.cfargotunnel.com`, with "Proxied" on. Make it the same way
the setup made the DNS record of your app's host name. Never use an
address of a server. Tell the person first: this adds a public address, which
works only after the next step has run.

**8. Record it.** Save this recipe as `custom_recipes/static-site.md` with
`source_url`, `source_commit`, and `applied_on` at the top. Add an entry to
`custom_extensions:` in your checklist file:

```yaml
custom_extensions:
  - id: static-site
    title: Serve a static site alongside your app
    recipe: services/static-site.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/services/static-site.md
    source_commit: "<SHA>"
    applied_on: "2026-11-21"
    state: done
    verification: "The four steps of the Verification check section passed."
```

Replace `<SHA>` with the full commit you read and the date with the UTC date of
the applying commit. Also add one line under `## Custom extensions` in your
systems repository's `AGENTS.md`: this recipe edits `cloudflared_config.yml`,
a core file.

Then follow your `AGENTS.md`: run `mmx validate`, commit, publish, run
`mmx dryrun`, and run. On the Stack, run `every_server`:
`./server_management_scripts/run_mmx_on_util01 run every_server`. On Solo, run
`mmx run solo_server`. To publish a new version of the site later, change the
files in `roles/custom_static_site/files/site/`, commit, publish, and run
`./server_management_scripts/run_mmx_on_util01 run every_server --only-fleet-stages custom_static_site`
(Solo: `mmx run solo_server --only-fleet-stages custom_static_site`). A change
to the site files alone does not restart Caddy.

## Verification check

Run these on a server that runs the site (an app server on the Stack, or
`solo01` on Solo). On the Stack, use
`./server_management_scripts/run_mmx_on_util01 run-command --nodes app_servers -- COMMAND`.
On Solo, use `mmx run-command --nodes solo_server -- COMMAND`.

1. **Only the loopback address listens:**

   ```sh
   ss -tlnp | grep ':8090'
   ```

   Expected: exactly one line, with `127.0.0.1:8090` and `caddy` in the
   process column. A line with `0.0.0.0:8090`, `*:8090`, or `[::]:8090` means
   the recipe is wrong: stop and fix it.

2. **The server answers on the loopback address:**

   ```sh
   curl -fsS http://127.0.0.1:8090/
   ```

   Expected: the text of your site's `index.html`, and exit code 0. Check that
   the text is there: an empty page with exit code 0 is a failure. To see that
   the site also answers for its public host name, run
   `curl -fsS -H 'Host: docs.example.com' http://127.0.0.1:8090/` and expect the
   same text.

3. **The public address answers through Cloudflare**, from any computer:

   ```sh
   curl -fsS https://docs.example.com/
   ```

   Expected: the same text, not an empty page. A `404` from Cloudflare means
   the route in step 6 is missing or does not match. A DNS error means step 7
   is not done.

4. **MMWatchdog is happy:**

   ```sh
   sudo mmwatchdog check-now custom_static_site
   sudo mmwatchdog status custom_static_site --json
   ```

   Expected: `check-now` exits with 0, and `status` lists the three checks
   `static_site_file_server_runs`, `static_site_answers_on_loopback`, and
   `static_site_public_address_answers`, with none of them failing.

## Clean removal

Remove everything, in this order, so no alert fires while it goes.

1. **Remove the public side first.** Delete the proxied CNAME record for
   the host name at Cloudflare. Remove the route (the `hostname:` line and
   the `service:` line, and their comment) from `cloudflared_config.yml`.
   That restarts `cloudflared`, as the route did when you added it.
2. **Swap the stage for a removal stage.** In the `# --- Custom extensions ---`
   block, replace the `custom_static_site` stage with this stage. On Solo,
   write `nodes: solo_server` and `on_node_failure: stop_run`. To remove the
   site only from the app servers after a move to load-balancer servers, write
   `nodes: app_servers`.

   ```yaml
     - id: remove_the_custom_static_site
       nodes: [app_servers, load_balancer_servers]
       on_node_failure: stop_fleet_stage
       node_tasks:
         - id: stop_the_file_server
           when: {path_exists: /etc/systemd/system/custom-static-site.service}
           systemd_service:
             name: custom-static-site
             state: stopped
             start_at_boot: false
         # StateDirectory belongs to the unit. This deletes its folders,
         # /var/lib/private/custom-static-site and /var/lib/custom-static-site,
         # and it needs the unit file, so it runs before the unit is removed.
         - id: remove_the_state_of_the_file_server
           when: {path_exists: /etc/systemd/system/custom-static-site.service}
           shell:
             script: systemctl clean --what=state custom-static-site.service
         - id: remove_the_unit
           systemd_unit:
             name: custom-static-site.service
             state: absent
         - id: remove_the_site_files
           directory:
             path: /srv/custom_static_site
             state: absent
             also_delete_everything_inside: true
         - id: remove_the_settings_directory
           directory:
             path: /etc/custom_static_site
             state: absent
             also_delete_everything_inside: true
   ```

   The stage leaves the `caddy` package and its apt repository in place: the
   core installs both on the same servers.
3. **Remove the checks.** Remove `custom_static_site.yml` from each
   `mmwatchdog_check_files` list that you appended it to in step 5, and keep
   the other entries. MMX then removes the check group from each server.
   Delete `mmwatchdog_checks/custom_static_site.yml`.
4. **Remove the settings.** Delete the `static_site:` key under `custom:`.
   When it was the only key, write `custom: {}` again.
5. **Run it.** Commit, publish, and run `every_server` (Solo:
   `solo_server`). Check that `systemctl status custom-static-site.service`
   says the unit could not be found, and that `ls /srv/custom_static_site
   /var/lib/custom-static-site /var/lib/private/custom-static-site` fails on
   each server.
6. **Delete the rest in a second commit.** Remove the
   `remove_the_custom_static_site` stage, the folder
   `roles/custom_static_site/`, `custom_recipes/static-site.md`, the
   `static-site` entry of `custom_extensions:`, and the note about the route
   under `## Custom extensions` in `AGENTS.md`. Run `mmx validate`, commit, and
   publish. The system is then the same as before.
