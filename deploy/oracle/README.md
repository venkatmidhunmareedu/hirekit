# Deploy on one Oracle Always Free VM with Docker Compose (ADR-0014)

API, Worker and the web UI behind Caddy, three containers on one Ubuntu VM; PostgreSQL is Supabase. Caddy
serves the built web files and proxies `/v1/*` to the API. Nothing here is automated.

## 1. The VM with Terraform
Needs `terraform` and an OCI API key (`oci setup config` writes `~/.oci/config`; upload the public
key under Profile, API keys).
```
cd deploy/oracle/terraform
cp terraform.tfvars.example terraform.tfvars && nano terraform.tfvars
terraform init && terraform plan
terraform apply
```
`apply` creates the network and a free Ampere A1 VM (2 OCPU, 12 GB, Ubuntu 24.04).
- "Out of host capacity" on the default Ampere shape: add `shape = "VM.Standard.E2.1.Micro"` to
  `terraform.tfvars` for the free 1 GB AMD VM, which has no capacity problem. Images are built on
  your machine, so the VM only pulls and runs them.
  Or retry later (Hyderabad has one availability domain, so `availability_domain_index` does not help).
- The output `public_ip` is the address. Point a domain's A record at it, or use `<ip>.sslip.io`.
- Cloud-init installs Docker and opens ports 80 and 443 on the VM; give it a minute after apply.
- State stays local and git-ignored; keep a copy, or `terraform destroy` stops working.
- By hand in the console instead: same ports (22 from your IP only, 80 and 443 public), then
  `curl -fsSL https://get.docker.com | sudo sh` and the iptables line from `cloud-init.yaml`.

## 2. Settings on the VM
The VM needs only the compose file and a `.env`; no clone, no source code. Run the `scp` from
`deploy/oracle` on your machine.
```
scp docker-compose.yml .env.example ubuntu@<public_ip>:
# then on the VM:
cp .env.example .env && chmod 600 .env && nano .env
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
docker compose pull && docker compose up -d
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed      # first sign-in users; see backend/.env.example for SEED_PASSWORD_*
```
Nothing is built on the VM, so the 1 GB Micro shape is enough.

## 5. Check
- `curl https://<SITE_ADDRESS>/healthz` returns `{"status":"ok",...}`.
- `docker compose logs -f worker` shows `worker_started`.
- Sign in, upload a resume, watch it leave "queued".

## Update
On your machine run `build-push.sh`; on the VM
`docker compose pull && docker compose up -d && docker compose run --rm api alembic upgrade head`.

## Database (Supabase)
- Use the **session pooler** connection string (Project Settings, Database, Connection string,
  Session pooler). The direct connection is IPv6 only and this VM has IPv4. Put it in `.env` as
  `DATABASE_URL`, with the `postgresql+asyncpg://` prefix and `?ssl=require` on the end.
- URL-encode special characters in the password (`@` becomes `%40`).
- Backups and restores are Supabase's; check the plan you are on.
