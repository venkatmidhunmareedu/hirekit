# Deploy on one Oracle Always Free VM with Docker Compose (ADR-0014)

API, Worker and the web UI behind Caddy, three containers on one Ubuntu VM; PostgreSQL is Supabase. Caddy
serves the built web files and proxies `/v1/*` to the API. Nothing here is automated.

## 1. The VM
Created outside this repo (the Terraform lives with the rest of the infra). It needs Ubuntu with Docker,
ports 80 and 443 public and 22 from your IP. By hand: `curl -fsSL https://get.docker.com | sudo sh`.
Point a domain's A record at the VM, or use `<ip>.sslip.io`.

## 2. Settings on the VM
The VM needs only the compose file and a `.env`; no clone, no source code. On your machine:
```
cp deploy/oracle/.env.example deploy/oracle/.env && chmod 600 deploy/oracle/.env && nano deploy/oracle/.env
make vm-copy          # copies both files to ~/hirekit on the VM (pass VM_IP=<address>)
```

## 3. Build and push the images (on your machine)
```
docker login -u midhunmareedu        # password: a Docker Hub access token with write access
make images                          # or: make images-build, then make images-push
```
It prints the tag. The repositories are `hirekit-backend` and `hirekit-web` on Docker Hub.

**They are public**, so anyone can pull them. The images hold the backend code, the prompts, the
synthetic seed resumes and recordings, never `.env` files or keys (`.dockerignore`). The free Docker
Hub plan allows one private repository, so two private ones need a paid plan. Do not bake a secret
into an image; secrets reach the containers only through `.env` on the VM.

## 4. Start (on the VM)
```
# in .env set REGISTRY_NAMESPACE=midhunmareedu (leave IMAGE_TAG empty: it means latest)
make vm-up VM_IP=<address>   # or on the VM: docker compose pull && docker compose up -d
# the migrate service applies the migrations, then the budget service creates the USD 8 budget row
```
The migrations create no accounts. The sign-in users come from the seed command, which also loads
the sample roles and resumes. Because `ENV=production`, it needs `--allow-production` and both
passwords (at least 16 characters), which you type without echo so they stay out of shell history:
```
read -rsp "recruiter password: " SEED_PASSWORD_RECRUITER; echo
read -rsp "interviewer password: " SEED_PASSWORD_INTERVIEWER; echo
export SEED_PASSWORD_RECRUITER SEED_PASSWORD_INTERVIEWER
docker compose run --rm -e SEED_PASSWORD_RECRUITER -e SEED_PASSWORD_INTERVIEWER api python -m app.seed --allow-production
```
Sign in as `recruiter@hirekit.local` or `interviewer@hirekit.local`. Running it again keeps existing
users; add `--reset-passwords` to change their passwords.

Nothing is built on the VM, so the 1 GB Micro shape is enough.

## 5. Check
- `curl https://<SITE_ADDRESS>/healthz` returns `{"status":"ok",...}`.
- `docker compose logs -f worker` shows `worker_started`.
- Sign in, upload a resume, watch it leave "queued".

## Update
On your machine run `build-push.sh`; on the VM
`docker compose pull && docker compose up -d`; migrations run by themselves.

## Database (Supabase)
- Use the **session pooler** connection string (Project Settings, Database, Connection string,
  Session pooler). The direct connection is IPv6 only and this VM has IPv4. Put it in `.env` as
  `DATABASE_URL`, with the `postgresql+asyncpg://` prefix and `?ssl=require` on the end.
- URL-encode special characters in the password (`@` becomes `%40`).
- Backups and restores are Supabase's; check the plan you are on.
