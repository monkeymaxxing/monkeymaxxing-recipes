---
id: domain-and-tls-expiry
title: Watch TLS certificates and DNS records
category: watchdog-checks
applies_to: [stack, solo]
summary: Adds MMWatchdog checks that warn before a TLS certificate expires and warn when a public DNS answer changes.
author: monkeymaxxing
vetted_on: 2026-11-21
vetted_against:
  stack: v0.3.0
  solo: v0.1.0
vetted_method: review-only
---

# Watch TLS certificates and DNS records

> [!IMPORTANT]
> Vetted once on submission (`vetted_on`) against `vetted_against`. Not routinely re-tested and outside core Stack/Solo support.

This recipe adds one MMWatchdog check file. For each public name you list, it
connects over TLS and warns you before the certificate expires. It can also
ask a public DNS server for the name's records and warn you when the answer is
not what you expect.

## When to use this (and when you don't need it)

You may not need this recipe. Cloudflare's Universal SSL certificate renews
by itself, and the core's `http` checks of your public host names already
verify the certificate. If a certificate expires, those `http` checks fail.
But they fail after the expiry, when your users already see the error. This
recipe warns you earlier.

Use it when you want:

- **An early `warn` before a certificate expires.** The default is 14 days
  before expiry. You change it with `warn_before_expiry` under `custom:`.
  This helps for a certificate that nothing renews for you: a custom domain
  with its own certificate, a third-party API endpoint you depend on, or a
  mail server's TLS port such as IMAP on 993.
- **A warning when a DNS answer changes unexpectedly.** The `dns` check asks
  the public DNS server `1.1.1.1:53` for a record of your name. With
  `expected_record_values`, the answer must hold exactly those values. A
  record that someone changed, or that a mistake removed, then fails the
  check.

Two limits to know:

- For a name behind the Cloudflare proxy, the TLS check sees Cloudflare's
  certificate, which Cloudflare renews. The warning is then rarely useful.
  The DNS answer for such a name is also Cloudflare's addresses, which can
  change, so leave out `expected_record_values` for it. The check then only
  requires that the name answers.
- The `tls` check works for TLS that starts at the first byte: ports 443,
  465, 993, and 995. A mail port that switches to TLS with STARTTLS, such as
  587, needs MMWatchdog's `smtp` check instead. This recipe does not cover it.

## What it adds and what it costs

It costs $0. It adds no server, no package, no container, and no role.

It adds:

- One file, `mmwatchdog_checks/custom_domain_tls.yml`, with one check group,
  `custom_domain_tls`. Each endpoint you list gets one `tls` check, and one
  `dns` check when you give it a `check_dns_record_type`.
- One entry, `custom_domain_tls.yml`, in `mmwatchdog_check_files`: in the
  `util_server` group of `inventories/servers.yml` on the Stack (the checks
  run on `util01`), and in `mmx_project_settings.yml` on Solo (the checks run
  on `solo01`).
- Settings under `custom.domain_tls:` in `mmx_project_settings.yml`.

The ongoing work is small. Edit the endpoint list when you add or remove a
public name, and run `every_server` (Stack) or `solo_server` (Solo) to apply
the change. A `warn` for a certificate means: renew it.

## Data, security, and backups

The recipe is stateless. It stores no data of its own, so it needs no backup
and no restore proof. MMWatchdog keeps its normal check readings, as it does
for every check.

- **Network:** each run makes outgoing connections only: one TLS handshake
  per endpoint, which sends nothing else, and one DNS question per `dns`
  check to `dns_server`. The recipe opens no port, so it adds no firewall rule
  and no WireGuard connection.
- **Secrets:** none. The checks need no token, key, or password.
- **Verification is never skipped.** The `tls` check trusts the system's
  certificate authorities. A server with a private certificate authority is
  outside this recipe.
- **Check group name:** `custom_domain_tls`. It uses underscores only and
  matches `^[a-z0-9_]+$`, so on the Stack the triage agent can run
  `sudo mmwatchdog check-now custom_domain_tls --count-as-scheduled-run`.
- **Alerts:** every check has `alert_severity: warn`. A warn tells a person
  during the day and wakes nobody. A certificate that expires in 14 days is
  no reason to wake someone.

## Apply steps

The recipe touches no vault key, `sudoers`, `ssh/`, or file that the Stack's
desk review watches. The coding agent does not need to stop for any of them.

Use `example.com` names below. The coding agent adapts these values to the
team's system:

- `endpoints`: the team's public host names, ports, and DNS record types.
- `warn_before_expiry`: the warning time, if the team wants another.
- `expected_record_values`: only for names whose answer should never change.

**1. Add the settings** under `custom:` in `mmx_project_settings.yml`. On both
the Stack and Solo, `custom:` is inside the `# --- Custom extensions ---`
lines. Add `domain_tls:` under `custom:`, alongside any existing custom
settings. When `custom:` is still `custom: {}`, replace that line with the
block below. When it already has other keys, add only the `domain_tls:` key
and keep the rest:

```yaml
  custom:
    domain_tls:
      # How long before a certificate expires the check starts to fail.
      # Reason for 14d: certbot and most hosts renew with about 30 days left,
      # so a certificate with 14 days left means renewal has failed for two
      # weeks, and a person still has time to fix it.
      warn_before_expiry: 14d
      # The DNS server that the dns checks ask, as host:port. It is the
      # only server asked; the node's own resolver is never used.
      dns_server: "1.1.1.1:53"
      endpoints:
        - name: shop_https
          host: shop.example.com
          port: 443
          check_dns_record_type: A
        # Optional second example: a mail server's TLS port, with a DNS
        # answer that must stay exactly as written.
        # - name: mail_imaps
        #   host: mail.example.com
        #   port: 993
        #   check_dns_record_type: A
        #   expected_record_values: ["203.0.113.25"]
```

Each endpoint has these fields:

| Field | Meaning |
| --- | --- |
| `name` | Lowercase letters, digits, and underscores only. It starts the check names, such as `shop_https_certificate_does_not_expire_soon`. Unique in the list. Keep it short: an alert title holds at most 120 characters, and MMWatchdog shortens a longer one. |
| `host` | The host name to check. The certificate must be valid for it. |
| `port` | The port that speaks TLS from its first byte, such as `443`. |
| `check_dns_record_type` | Optional. `A`, `AAAA`, `CNAME`, `MX`, `NS`, `TXT`, or `SRV`. Without it, the endpoint gets no `dns` check. The DNS question is for `host`. `PTR` is not on the list: a `PTR` question needs an IP address, not a host name. `CNAME` fails for a host name behind the Cloudflare proxy, because Cloudflare answers a proxied name with `A` and `AAAA` records and hides the `CNAME`. Use `A` or `AAAA` there. |
| `expected_record_values` | Optional, with `check_dns_record_type`. The answer must hold exactly these values, in any order. Without it, any answer with at least one record passes. |

**2. Create `mmwatchdog_checks/custom_domain_tls.yml`.** MMX renders this
template on the server into `/etc/mmwatchdog/check_groups/custom_domain_tls.yml`.

```yaml
{{- /*
  MMWatchdog's check group for the certificates and DNS records of the
  public names in custom.domain_tls (mmx_project_settings.yml). This file is
  an MMX template. It reads the role input custom.
*/ -}}
{{- $settings := .inputs.custom.domain_tls }}
{{- if not $settings.endpoints }}{{ fail "custom.domain_tls.endpoints in mmx_project_settings.yml is empty. List at least one endpoint, or remove custom_domain_tls.yml from mmwatchdog_check_files." }}{{ end }}
# Managed by MMX from mmwatchdog_checks/custom_domain_tls.yml in the systems repository.
# This check file comes from the recipe domain-and-tls-expiry (custom_recipes/domain-and-tls-expiry.md).
# To be woken for a check, set that check's alert_severity to sos.
check_groups:
  # check_every 1h: a certificate or a record changes in days, not minutes.
  # time_limit_per_run 15s: a TLS handshake or a DNS answer that takes longer
  # than 15 seconds counts as a failure.
  # alert_after_failing_for 3h: three failed runs in a row, so one network
  # blip sends nothing. A certificate that is 14 days from expiry can wait.
  # recovered_after_healthy_for 0s: the first healthy run after a renewal or
  # a repaired record closes the alert.
  # Reason for warn: nothing is down yet. The certificate check warns before
  # the expiry, and an expired certificate is also caught by the http checks.
  custom_domain_tls:
    check_every: 1h
    time_limit_per_run: 15s
    alert_after_failing_for: 3h
    recovered_after_healthy_for: 0s
    checks:
{{- range $endpoint := $settings.endpoints }}
      {{ $endpoint.name }}_certificate_does_not_expire_soon:
        tls:
          address: {{ printf "%s:%v" $endpoint.host $endpoint.port | toJson }}
          fail_when_certificate_expires_within: {{ $settings.warn_before_expiry }}
        alert_severity: warn
{{- /* index gives "" for an optional field that the endpoint leaves out; $endpoint.field would fail. */}}
{{- $dns_record_type := index $endpoint "check_dns_record_type" }}
{{- $expected_record_values := index $endpoint "expected_record_values" }}
{{- if $dns_record_type }}
      {{ $endpoint.name }}_dns_answers_as_expected:
        dns:
          dns_server: {{ $settings.dns_server | toJson }}
          record_name: {{ $endpoint.host | toJson }}
          record_type: {{ $dns_record_type }}
{{- if $expected_record_values }}
          expected_record_values: {{ $expected_record_values | toJson }}
{{- end }}
        alert_severity: warn
{{- end }}
{{- end }}
```

**3. Register the check file.**

On the **Stack**, in `inventories/servers.yml`, add the file at the end of
the `util_server` group's list. The checks then run on `util01`:

```yaml
  util_server:
    nodes: [util01]
    vars:
      is_util_server: true
      mmwatchdog_check_files: [every_server.yml, util_server.yml, custom_domain_tls.yml]
```

On **Solo**, in `mmx_project_settings.yml`, add the file at the end of
`mmwatchdog_check_files`. The checks then run on `solo01`:

```yaml
  mmwatchdog_check_files: [every_server.yml, postgres_and_backups.yml, apps_and_tunnel.yml, custom_domain_tls.yml]
```

**4. Record the recipe.** Save this recipe as
`custom_recipes/domain-and-tls-expiry.md`, with `source_url`,
`source_commit`, and `applied_on` at the top. Then add this entry to
`custom_extensions:` in `monkeymaxxing_stack_checklist.yml` (Stack) or
`monkeymaxxing_solo_checklist.yml` (Solo), with the result of the
verification check below:

```yaml
custom_extensions:
  - id: domain-and-tls-expiry
    title: Watch TLS certificates and DNS records
    recipe: watchdog-checks/domain-and-tls-expiry.md
    source_url: https://github.com/monkeymaxxing/monkeymaxxing-recipes/blob/<SHA>/watchdog-checks/domain-and-tls-expiry.md
    source_commit: "<SHA>"
    applied_on: "2026-11-21"
    state: done
    verification: "mmwatchdog status --json showed custom_domain_tls healthy on util01"
```

Both checklist files use these same fields. Replace `<SHA>` with the full
commit you read, use the UTC date of the applying commit, and write `solo01`
instead of `util01` on Solo.

**5. Validate and apply.** Run `mmx validate every_server` on the Stack, or
`mmx validate solo_server` on Solo. Then follow the system's normal change
steps in `AGENTS.md`: commit, publish, preview with `dryrun`, and run
`every_server` (Stack) or `solo_server` (Solo). MMX renders the file into a
candidate directory, has `mmwatchdog validate` check it, and only then
installs it into `/etc/mmwatchdog/check_groups/`. The run also removes any
check file that `mmwatchdog_check_files` does not list.

## Verification check

Run these on `util01` (Stack) or `solo01` (Solo).

```sh
sudo mmwatchdog status --json
```

In the output, every check of the group `custom_domain_tls` must be healthy.
For the example endpoint, those are `shop_https_certificate_does_not_expire_soon`
and `shop_https_dns_answers_as_expected`. The first run happens right after
MMWatchdog loads the file. Wait a minute if a check shows no result yet.

```sh
sudo mmwatchdog check-now custom_domain_tls --count-as-scheduled-run --json
```

The command must exit with status 0 (`echo $?` prints `0`). With `--json`, the
output shows the `measurements` of each check. For the `tls` check, it must
report a message like `TLS certificate is valid`, with a
`certificate_expires_in_seconds` measurement larger than 14 days
(1,209,600 seconds). For the `dns` check, it must report the answer, such as
`the A record of shop.example.com at the DNS server 1.1.1.1:53 is ...`.

To see the warning work, you may set `warn_before_expiry` to a time longer than
the certificate's life, such as `3650d`. Apply it, run `check-now`, and the
`tls` check fails with `TLS certificate expires at ...`. Then set it back.

## Clean removal

Take these steps in one commit, so the system is the same as before:

1. Remove `custom_domain_tls.yml` from `mmwatchdog_check_files`, and keep the
   other entries: in the `util_server` group of `inventories/servers.yml`
   (Stack), or in `mmx_project_settings.yml` (Solo).
2. Delete `mmwatchdog_checks/custom_domain_tls.yml` and
   `custom_recipes/domain-and-tls-expiry.md`.
3. Remove only the `domain_tls:` key from `custom:` in
   `mmx_project_settings.yml`. Leave every other custom setting in place.
   Leave `custom: {}` only when no other custom settings remain.
4. Remove the `domain-and-tls-expiry` entry from `custom_extensions:` in the
   checklist file.
5. Run `mmx validate`, then apply the commit with `every_server` (Stack) or
   `solo_server` (Solo).

The run deletes `custom_domain_tls.yml` from both the candidate directory and
the live `/etc/mmwatchdog/check_groups/`, because the file is no longer in
`mmwatchdog_check_files`. MMWatchdog then stops the checks. The recipe kept
no data, opened no port, and added no secret, so nothing else needs undoing.
