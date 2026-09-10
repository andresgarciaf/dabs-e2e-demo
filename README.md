# dabs-e2e-demo

A minimal Databricks Asset Bundle that demonstrates the full **dev -> PR -> prod**
promotion flow, driven from the Databricks workspace and finished by GitHub Actions.

One workspace, two identities, separated by workspace folder and UC schema:

| | Dev | Prod |
|---|---|---|
| Identity | You (`sts-demo`) | Service principal `andresg-demo-sp` (`sts-demo-sp`) |
| Deployed by | You, from the Databricks workspace | GitHub Actions, as the SP |
| Bundle mode | `development` | `production` |
| Workspace path | `/Workspace/Users/<you>/.bundle/dabs-e2e-demo` | `/Workspace/DevOps/dabs-e2e-demo` |
| UC output | `sts.e2e_demo_dev` | `sts.e2e_demo_prod` |

## What it builds

- **`nyctaxi_pipeline`** - a serverless SDP pipeline reading `samples.nyctaxi.trips`,
  landing `trips_bronze` and a `daily_fares` aggregate.
- **`nyctaxi_job`** - a job whose single task refreshes that pipeline.

## Prerequisites

- Databricks CLI >= 0.292 (`databricks --version`).
- Two profiles in `~/.databrickscfg`: `sts-demo` (you) and `sts-demo-sp` (the SP).
- Dev profile token is valid: `databricks auth login --profile sts-demo`.

## The demo, end to end

### 1. Dev loop (in the Databricks workspace)

Clone this repo as a **Git folder** in the workspace, then from the workspace terminal:

```bash
databricks bundle deploy -t dev -p sts-demo
databricks bundle run nyctaxi_job -t dev -p sts-demo
```

Check the output in **`sts.e2e_demo_dev`**. Iterate on `src/nyctaxi_pipeline.py`
and redeploy until it looks right. In `development` mode resources are prefixed
`[dev <you>] ...` and the pipeline runs in development mode, so nothing collides
with prod.

### 2. Commit and open a PR

From the workspace Git folder, commit your change and push a branch, then open a
pull request against `main`. The **validate** workflow runs
`databricks bundle validate -t prod` on the PR.

### 3. Review, approve, merge

A reviewer approves and merges to `main`.

### 4. Prod deploy (GitHub Actions, as the SP)

On merge, the **deploy-prod** workflow authenticates as the service principal and runs:

```bash
databricks bundle deploy -t prod   # -> /Workspace/DevOps/dabs-e2e-demo
databricks bundle run nyctaxi_job -t prod
```

Data lands in **`sts.e2e_demo_prod`**. No human ever touches prod directly.

## One-time setup: the prod folder

The service principal cannot create top-level workspace folders, so create
`/Workspace/DevOps` once as yourself and grant the SP `CAN_MANAGE`:

```bash
# 1. Create the folder as your user.
databricks workspace mkdirs /Workspace/DevOps -p sts-demo

# 2. Get its numeric object id.
DIR_ID=$(databricks workspace get-status /Workspace/DevOps -p sts-demo -o json | jq -r .object_id)

# 3. Grant the SP CAN_MANAGE so GitHub Actions can deploy into it.
databricks workspace set-permissions directories "$DIR_ID" -p sts-demo --json '{
  "access_control_list": [
    {"service_principal_name": "1ca8ef92-3abb-48c7-b708-0ee2f9c9ef28", "permission_level": "CAN_MANAGE"}
  ]
}'
```

## One-time setup: GitHub Actions secrets

The prod deploy authenticates via OAuth machine-to-machine. In the GitHub repo,
add these **Actions secrets**:

| Secret | Value |
|---|---|
| `DATABRICKS_HOST` | `https://adb-7405615905758195.15.azuredatabricks.net` |
| `DATABRICKS_CLIENT_ID` | `1ca8ef92-3abb-48c7-b708-0ee2f9c9ef28` (the SP's application ID) |
| `DATABRICKS_CLIENT_SECRET` | An OAuth secret minted for the SP (see below) |

Mint an OAuth secret for the service principal:

```bash
# Account admin: list the SP, then create a secret for it.
databricks account service-principal-secrets create <SP_ID> -p <account-profile>
```

Or in the workspace UI: **Settings -> Identity and access -> Service principals ->
andresg-demo-sp -> Secrets -> Generate secret**. Copy the secret once and store it
as the `DATABRICKS_CLIENT_SECRET` GitHub secret.

> Never commit the client secret. It lives only in GitHub Actions secrets.

## Notes

- The GitHub workflows pin `databricks/setup-cli@main`; pin to a released tag for
  reproducible CI.
- Local prod deploys should also run as the SP (`-p sts-demo-sp`) so the deploying
  identity matches `run_as`.
