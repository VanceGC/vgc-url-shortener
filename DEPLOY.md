# VGC.to URL Shortener — Deployment Guide

## Prerequisites
- Fresh Ubuntu 24.04 server (CX23 on Hetzner recommended)
- Domain vgc.to pointed to server IP
- SSH access as root

---

## Step 1 — Install Docker

```bash
curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

---

## Step 2 — Copy App Files to Server

From your Mac:
```bash
scp vgc-url-shortener.tar.gz root@YOUR_SERVER_IP:/opt/
```

On the server:
```bash
cd /opt
tar -xzf vgc-url-shortener.tar.gz
cd vgc-url-shortener
```

---

## Step 3 — Generate Credentials

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate DB passwords (run twice, use different values)
openssl rand -hex 16

# Generate admin password hash (replace 'yourpassword' with your chosen password)
python3 -c "import hashlib; print(hashlib.sha256('yourpassword'.encode()).hexdigest())"
```

---

## Step 4 — Create .env File

```bash
cp .env.example .env
nano .env
```

Fill in all values:
```
SECRET_KEY=<output from openssl rand -hex 32>
MYSQL_ROOT_PASSWORD=<first openssl rand -hex 16>
DB_NAME=vgcto
DB_USER=vgcto
DB_PASS=<second openssl rand -hex 16>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<output from python3 hash command>
```

---

## Step 5 — Build and Launch

```bash
docker compose up -d --build
```

Verify it's running:
```bash
docker ps | grep vgc
curl http://localhost:5001
```

You should see a redirect to `/login`.

---

## Step 6 — Set Up Caddy as Reverse Proxy

Install Caddy:
```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy -y
```

Create Caddyfile:
```bash
nano /etc/caddy/Caddyfile
```

Paste this (replace with your actual domain):
```
vgc.to {
    reverse_proxy localhost:5001
}
```

Start Caddy:
```bash
systemctl enable caddy
systemctl start caddy
systemctl status caddy
```

Caddy will automatically obtain and renew SSL certificates via Let's Encrypt.

---

## Step 7 — Migrate Existing URLs

### Export from A2 Hosting
On your A2 server:
```bash
cd ~/public_html/Sites/vgc_to
sqlite3 url_shortener.db .dump > url_shortener_backup.sql
```

Copy to your Mac:
```bash
scp timjvanc@mi3-ts100.a2hosting.com:~/public_html/Sites/vgc_to/url_shortener_backup.sql ~/Desktop/
```

Copy to new server:
```bash
scp ~/Desktop/url_shortener_backup.sql root@YOUR_SERVER_IP:/opt/vgc-url-shortener/
```

### Run Migration
On the server:
```bash
cd /opt/vgc-url-shortener

# Copy files into container
docker cp url_shortener_backup.sql vgc-url-shortener-app-1:/app/
docker cp migrate.py vgc-url-shortener-app-1:/app/

# Run migration
docker exec vgc-url-shortener-app-1 python3 migrate.py url_shortener_backup.sql
```

You should see output like:
```
Found 47 URLs to migrate
Migration complete!
  Imported: 47
  Skipped:  0
```

---

## Step 8 — Update DNS

In Cloudflare, update the vgc.to A record to point to your new server IP.
Set proxy status to **Proxied** (orange cloud).
Set SSL/TLS mode to **Full** in Cloudflare SSL settings.

---

## Step 9 — Verify

Visit https://vgc.to — you should see the VGC login page.
Log in with your admin credentials.
Verify your existing short links appear in the dashboard.
Test a few existing links to make sure redirects work.

---

## Updating the App

```bash
cd /opt/vgc-url-shortener
docker compose down
docker compose up -d --build
```

---

## Useful Commands

```bash
# View logs
docker logs vgc-url-shortener-app-1

# Restart app only
docker restart vgc-url-shortener-app-1

# Check all containers
docker ps

# Check Caddy logs
journalctl -u caddy -f
```

---

## N8N Integration

To create short links from N8N, use an HTTP Request node:

- **Method:** POST
- **URL:** https://vgc.to/api/shorten
- **Auth:** Cookie (log in first and capture session cookie)
- **Body (JSON):**
```json
{
  "url": "https://your-long-url.com",
  "custom_alias": "optional-alias",
  "label": "Campaign Name"
}
```

**Response:**
```json
{
  "short_url": "https://vgc.to/abc123",
  "short": "abc123"
}
```
