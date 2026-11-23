# Recipe backlog

These are the recipes we would most like to have, in priority order within
each category. Each one is a good size for one contributor, or for a coding
agent with a spare afternoon.

To take one, open an issue named "Working on: <id>" so nobody else starts
the same recipe. Then follow [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Recipe Contract](CONTRACT.md). When a recipe is merged, it leaves this list.

## `services/`

1. **`meilisearch-search-pool`** (Stack): a private Meilisearch pool over
   WireGuard, reached by the app servers only. Show how to rebuild the index
   from Postgres, so the pool can stay stateless with no backup of its own.
2. **`plausible-analytics`** (Stack): Plausible needs ClickHouse beside
   Postgres. Cover the ClickHouse data's backup to locked storage, and a
   restore check.
3. **`clickhouse-analytics-pool`** (Stack): a ClickHouse pool for event
   data, with locked offsite backups and a restore proof.
4. **`media-worker-pool`** (Stack): a pool for heavy jobs such as video or
   image processing, sized apart from the app servers. A section on GPU
   servers is welcome.

## `watchdog-checks/`

1. **`http-endpoint-latency`** (Stack, Solo): response time, HTTP status,
   and TLS for a list of extra addresses, such as an API or an admin page,
   from settings under `custom:`.
2. **`outside-service-reachability`** (Stack, Solo): checks that the outside
   services the app depends on, such as a payment or email provider, answer
   from the server.

## `providers/`

Each new provider whose API takes a token in a header also needs a one-line
change in the Stack: its API address added to `providerGuideAPIAddresses`
in `set_up_outside_services/personal_token.go` in
[monkeymaxxing-stack](https://github.com/monkeymaxxing/monkeymaxxing-stack).
That list keeps a coding agent from sending the provider token to any other
host. Link that change from the recipe's pull request.

1. **`netcup`** (Stack): low-cost servers in Germany and Austria. Check
   first how its API manages servers and keys.
2. **`upcloud`** (Stack): servers in Europe, the US, and Asia, with a
   token-based API.
3. **`akamai-linode`** (Stack): Linode servers. An earlier attempt stopped
   when the account was rejected at sign-up review, so start with an account
   that is already approved.

## `frameworks/` and `migrations/`

1. **Re-checks on newer versions:** apply an existing guide on the newest
   Stack or Solo release and the framework's newest version, then send the
   changes it needed.
2. **New framework guides:** Phoenix (Elixir), Spring Boot (Java), and
   ASP.NET Core, each with an example app that meets the app contract.
3. **New migration guides:** from Google Cloud Run, AWS Elastic Beanstalk,
   and Azure App Service.
