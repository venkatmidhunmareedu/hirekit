# Deploy on one Oracle Always Free VM with Docker Compose (ADR-0014)

PostgreSQL, API, Worker and the web UI behind Caddy, four containers on one Ubuntu VM. Caddy
serves the built web files and proxies `/v1/*` to the API. Nothing here is automated.

## 1. The VM
- Create an Always Free instance (Ampere A1, 2 OCPU and 12 GB is plenty; Ubuntu 24.04). If a
  region has no capacity, try another availability domain or retry later.
- Allow inbound TCP 80 and 443 in the subnet's security list, and 22 from your IP only. On the
  Ubuntu image also open the host firewall:
  `sudo iptables -I INPUT 5 -p tcp -m multiport --dports 80,443 -j ACCEPT && sudo netfilter-persistent save`.
- Point a domain's A record at the public IP, or use `<public-ip>.sslip.io` as the name.

## 2. Docker and code
```
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER   # log in again
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
