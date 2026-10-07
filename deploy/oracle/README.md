# Deploy on one Oracle Always Free VM with Docker Compose (ADR-0014)

PostgreSQL, API, Worker and the web UI behind Caddy, four containers on one Ubuntu VM. Caddy
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
- "Out of host capacity": set `availability_domain_index` to 1 or 2, or retry later.
- The output `public_ip` is the address. Point a domain's A record at it, or use `<ip>.sslip.io`.
- Cloud-init installs Docker and opens ports 80 and 443 on the VM; give it a minute after apply.
- State stays local and git-ignored; keep a copy, or `terraform destroy` stops working.
- By hand in the console instead: same ports (22 from your IP only, 80 and 443 public), then
  `curl -fsSL https://get.docker.com | sudo sh` and the iptables line from `cloud-init.yaml`.

## 2. Code and settings
```
git clone <repo url> hirekit && cd hirekit/deploy/oracle
cp .env.example .env && chmod 600 .env && nano .env
```

## 3. Start
```
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed      # first sign-in users; see backend/.env.example for SEED_PASSWORD_*
```
The first build takes several minutes on the VM.

## 4. Check
- `curl https://<SITE_ADDRESS>/healthz` returns `{"status":"ok",...}`.
- `docker compose logs -f worker` shows `worker_started`.
- Sign in, upload a resume, watch it leave "queued".

## Update
`git pull && docker compose up -d --build && docker compose run --rm api alembic upgrade head`

## Back up the database
`docker compose exec db pg_dump -U hirekit hirekit | gzip > hirekit-$(date +%F).sql.gz`, then copy it off the VM.
