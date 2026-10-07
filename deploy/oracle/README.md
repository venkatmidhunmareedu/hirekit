# Deploy on one Oracle Always Free VM (ADR-0014)

API, Worker, PostgreSQL and the built web UI on one Ubuntu VM. Caddy serves the web files and
proxies `/v1/*` to the API on 127.0.0.1:8080. Nothing here is automated; run the steps once.

## 1. The VM
- Create an Always Free instance (Ampere A1, 2 OCPU and 12 GB is plenty; Ubuntu 24.04). If a region
  has no capacity, try another availability domain or retry later.
- Networking: in the subnet's security list and the instance, allow inbound TCP 80 and 443 (and 22
  from your IP only). On Ubuntu images also open the host firewall:
  `sudo iptables -I INPUT 5 -p tcp -m multiport --dports 80,443 -j ACCEPT && sudo netfilter-persistent save`.
- Point a domain's A record at the public IP, or use `<ip>.sslip.io`.
- Keep it from being reclaimed as idle: a small always-on process counts, but check the Oracle notices.

## 2. Packages and user
```
sudo apt update && sudo apt install -y postgresql caddy git nodejs npm
sudo npm i -g pnpm
sudo useradd -m -s /bin/bash hirekit
sudo -iu hirekit sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo mkdir -p /opt/hirekit /etc/hirekit && sudo chown hirekit /opt/hirekit
```

## 3. Database
```
sudo -u postgres psql -c "CREATE USER hirekit PASSWORD '<strong password>'"
sudo -u postgres psql -c "CREATE DATABASE hirekit OWNER hirekit"
```
PostgreSQL listens on localhost only by default; leave it so.

## 4. Code, env, migrate
```
sudo -iu hirekit git clone <repo url> /opt/hirekit     # or git pull on an update
cd /opt/hirekit/backend && sudo -iu hirekit uv sync --no-dev
sudo install -m 600 -o hirekit /dev/null /etc/hirekit/backend.env
sudoedit /etc/hirekit/backend.env
```
`/etc/hirekit/backend.env` (never commit it):
```
ENV=production
LOG_FORMAT=json
DATABASE_URL=postgresql+asyncpg://hirekit:<password>@localhost:5432/hirekit
MODEL_MODE=live
OPENROUTER_API_KEY=<key with a credit limit>
KEY_CREDIT_LIMIT_CONFIRMED=yes
```
Then, as the `hirekit` user in `/opt/hirekit/backend`:
`DATABASE_URL=... uv run alembic upgrade head`. Create the first users with the seed tooling
(`app.seed`, see `backend/.env.example` for the SEED_PASSWORD_* variables).

## 5. Web build
On the VM: `cd /opt/hirekit/web && pnpm install --frozen-lockfile && pnpm build`
(or build on your machine and copy `web/dist` to `/opt/hirekit/web/dist`).

## 6. Services
```
sudo cp /opt/hirekit/deploy/oracle/hirekit-*.service /etc/systemd/system/
sudo cp /opt/hirekit/deploy/oracle/Caddyfile /etc/caddy/Caddyfile   # edit the host first
sudo systemctl daemon-reload
sudo systemctl enable --now hirekit-api hirekit-worker
sudo systemctl reload caddy
```

## 7. Check
- `curl https://<host>/healthz` returns `{"status":"ok",...}`.
- `journalctl -u hirekit-worker -f` shows `worker_started`.
- Sign in, upload a resume, watch it leave "queued".

## Update
`git pull`, `uv sync --no-dev`, `alembic upgrade head`, `pnpm build`, then
`sudo systemctl restart hirekit-api hirekit-worker`.
