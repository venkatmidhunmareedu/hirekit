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
The VM needs only the compose file and a `.env`; no clone, no source code. On your machine:
```
cp deploy/oracle/.env.example deploy/oracle/.env && chmod 600 deploy/oracle/.env && nano deploy/oracle/.env
make vm-copy          # copies both files to ~/hirekit on the VM (VM_IP defaults to the Terraform output)
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
make vm-up            # or on the VM: docker compose pull && docker compose up -d
# the migrate service applies the migrations first
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
