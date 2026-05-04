# Evently AWS Infrastructure (CDK)

This folder supports a layered deployment:

1. **Foundation stack**: VPC, S3, SNS, and an **ECR repository** for the backend image
2. **API stack (optional)**: Internet-facing ALB + Auto Scaling EC2 running the backend container, a managed Valkey queue, and notification workers — enabled when you pass `-c apiImageUri=...`

The API stack imports VPC exports from the foundation stack.

## Prerequisites

- Node.js 18+
- AWS CLI configured (`aws configure`)
- Docker installed locally
- Backend image pushed to Amazon ECR
- Required backend secrets saved in AWS SSM Parameter Store

## Stack overview

| Stack | Created resources |
|---|---|
| Foundation (`evently-stack.ts`) | VPC, S3 bucket, SNS topic, ECR repository (`<project>-<env>-backend`) |
| API (`api-stack.ts`) | ALB, target group, launch template, Auto Scaling Group, scaling policy, ElastiCache Valkey replication group |

## Background workers and Redis/Valkey

The backend uses `arq` plus Redis-compatible storage for event reminder jobs. In local development, `just dev` starts Redis and a separate `notif-worker` process. In AWS, the API stack mirrors that shape:

- API EC2 instances run the backend web container.
- Each API EC2 instance also runs a `notif-worker` container from the same backend image.
- All API and worker containers share one private ElastiCache Valkey replication group through `REDIS_URL`.

The default cache node is `cache.t4g.micro`, the smallest selected managed node option for this project. It is shared across multiple EC2 instances, but it is not highly available because the stack creates one primary node and no replicas to keep cost down. Add replicas later if this becomes production infrastructure.

## Frontend (manual)

Hosting (for example **Amplify Console**) is not created by this CDK app. After the API stack deploys, use the **ApiAlbDnsName** output and set **`FRONTEND_URL`** in SSM (see below) to your real site origin (for example `https://main.<id>.amplifyapp.com`) so CORS and OAuth redirects match.

### HTTPS Amplify + HTTP ALB (mixed content)

Browsers block a **secure** Amplify page from calling **`http://`…** on the ALB directly. The app uses same-origin **`/api/...`** and Next.js **rewrites** those to your ALB.

In **Amplify → App → Environment variables** (for the branch that builds), set:

| Variable | Example | Purpose |
|----------|---------|--------|
| `BACKEND_PROXY_TARGET` | `http://<ApiAlbDnsName>` | Build-time rewrite target (no trailing slash). Required for `/api` → backend. |
| `API_INTERNAL_URL` | `http://<ApiAlbDnsName>` | Server-side `fetch` in RSC hits the ALB directly (same URL is fine). |

Do **not** set `NEXT_PUBLIC_API_URL` for Amplify unless you intentionally bypass `/api` (that env wins if set).

Then **redeploy** the Amplify app so `next.config.ts` picks up `BACKEND_PROXY_TARGET` at build time.

On **localhost**, the app still defaults to **`http://localhost:8000`** when `NEXT_PUBLIC_API_URL` is unset. For local use of `/api` rewrites, set `BACKEND_PROXY_TARGET=http://127.0.0.1:8000` as well.

If you connect a Git repo to Amplify, use the root **`amplify.yml`** for the monorepo build (`frontend/`).

## Required SSM parameters

By default, the API EC2 user-data reads these parameters:

- `/<projectName>/<environment>/DATABASE_URL`
- `/<projectName>/<environment>/SESSION_SECRET_KEY`
- `/<projectName>/<environment>/FRONTEND_URL`
- `/<projectName>/<environment>/OAUTH_CLIENT_ID`
- `/<projectName>/<environment>/OAUTH_CLIENT_SECRET`
- `/<projectName>/<environment>/ADMIN_EMAILS`

The API stack also tries to read these optional parameters:

- `/<projectName>/<environment>/RESEND_API_KEY`
- `/<projectName>/<environment>/EMAIL_FROM`

If `RESEND_API_KEY` is missing, EC2 boot continues and the backend logs that email notifications are disabled. When email notifications are enabled, set `EMAIL_FROM` to a Resend-verified sender, for example `Evently <notifications@your-domain.example>`.

Example for default project and environment:

- `/evently/dev/DATABASE_URL`
- `/evently/dev/SESSION_SECRET_KEY`
- `/evently/dev/FRONTEND_URL`
- `/evently/dev/OAUTH_CLIENT_ID`
- `/evently/dev/OAUTH_CLIENT_SECRET`
- `/evently/dev/ADMIN_EMAILS`
- `/evently/dev/RESEND_API_KEY` (optional)
- `/evently/dev/EMAIL_FROM` (optional)

## Deploy blueprint (POC)

### 1) Install dependencies and bootstrap

```bash
cd infrastructure
npm install
npx cdk bootstrap
```

### 2) Deploy foundation stack only

```bash
npx cdk deploy <foundation-stack-name>
```

If you did not set custom context, use:

```bash
npx cdk deploy evently-dev-stack
```

### 3) Build and push backend image to ECR

After the foundation stack deploys, use the **BackendEcrRepositoryUri** output (or repository name `<project>-<env>-backend`, e.g. `evently-dev-backend`). From the repository root:

```bash
aws ecr get-login-password --region "$AWS_REGION" \
| docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
docker build -t evently-backend ./backend
docker tag evently-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/evently-dev-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/evently-dev-backend:latest
```

### 4) Deploy API stack after foundation

```bash
npx cdk deploy <api-stack-name> \
  -c apiImageUri=<account>.dkr.ecr.<region>.amazonaws.com/evently-dev-backend:latest
```

Default names:

```bash
npx cdk deploy evently-dev-stack-api \
  -c apiImageUri=<account>.dkr.ecr.<region>.amazonaws.com/evently-dev-backend:latest
```

### 5) Configure `DATABASE_URL` for Mongo Atlas (or external MongoDB)

Store a reachable Mongo URI (not localhost) in SSM before rolling API instances:

```bash
aws ssm put-parameter \
  --name "/evently/dev/DATABASE_URL" \
  --type "SecureString" \
  --value "mongodb+srv://<user>:<password>@<cluster-host>/evently?retryWrites=true&w=majority" \
  --overwrite
```

After your frontend URL is known, set **`FRONTEND_URL`** in SSM to that origin (for example your Amplify branch URL). Add your deployed backend callback in Google Cloud OAuth:

- **Authorized redirect URI**: `https://<your-api-domain>/auth/callback` (or `http://...` if you use the ALB DNS over HTTP for a demo)
- **Authorized JavaScript origin**: your deployed frontend origin

### 6) Optional context tuning

- `-c apiInstanceType=t3.micro`
- `-c apiMinCapacity=2`
- `-c apiDesiredCapacity=2`
- `-c apiMaxCapacity=4`
- `-c apiHealthCheckPath=/health` (override if you use a custom liveness path)
- `-c apiStackName=<custom-api-stack-name>`
- `-c enableNotificationWorker=true` (set to `false` to skip the worker and Valkey queue)
- `-c valkeyNodeType=cache.t4g.micro`

## Deployment sequencing

- Deploy foundation first so VPC, `VpcCidr`, subnet, and ECR exports exist.
- Deploy the API stack with `apiImageUri` pointing at your image in the foundation ECR repo.

## Outputs

Foundation stack:

- `VpcId`, `VpcCidr`
- `S3AssetsBucket`
- `SnsTopicArn`
- `BackendEcrRepositoryUri`

API stack:

- `ApiAlbDnsName`
- `ApiAsgName`
- `ValkeyEndpoint`
- `ValkeyPort`

## Notes

- API health checks default to **`/health`** (no database dependency). Override with `-c apiHealthCheckPath=...` if needed.
- **Redis/Valkey (`REDIS_URL`)**: the API stack creates a private ElastiCache Valkey replication group by default when notification workers are enabled and writes `REDIS_URL` into the container environment. HTTP serving can still run without it if you deploy with `-c enableNotificationWorker=false`, but event email reminders stay disabled.
- The default Valkey replication group is a single `cache.t4g.micro` primary node for cost control. It supports multiple EC2 instances sharing one queue, but it is not HA.
- If `apiImageUri` is not provided, the API stack is not synthesized.
- **Mixed content (HTTPS Amplify + HTTP ALB):** set **`BACKEND_PROXY_TARGET`** (see [Frontend (manual)](#frontend-manual)), or terminate TLS on the ALB with a certificate.
- API EC2 instances are granted `ssm:GetParameter` / `kms:Decrypt` (for SecureString) on `/<project>/<environment>/*` so existing user-data can load secrets.
