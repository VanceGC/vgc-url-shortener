# VGC.to URL Shortener

Flask + MySQL + Docker URL shortener with click tracking, QR codes, and a clean dark UI.

## Features
- Click tracking per link
- QR code generation & download
- Label/notes per link
- Search/filter links
- Custom aliases
- Per-link Open Graph previews, using destination metadata by default or custom metadata when selected
- Secure password hashing
- MySQL backend
- Docker containerized

---

## Deployment on Hetzner

### 1. Copy files to server
```bash
scp -r vgc-url-shortener/ root@5.78.93.10:/opt/vgc-url-shortener
```

### 2. SSH into server
```bash
ssh root@5.78.93.10
cd /opt/vgc-url-shortener
```

### 3. Generate your credentials
```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate password hash (replace 'yourpassword')
python3 -c "import hashlib; print(hashlib.sha256('yourpassword'.encode()).hexdigest())"
```

### 4. Create .env file
```bash
cp .env.example .env
nano .env
# Fill in all values
```

### 5. Build and start
```bash
docker compose up -d --build
```

App runs on port 5001. 

---

## Migrate existing URLs from A2 Hosting

### Step 1: Export from A2
```bash
# On A2 server
cd ~/public_html/Sites/vgc_to
sqlite3 url_shortener.db .dump > url_shortener_backup.sql
```

### Step 2: Copy to your Mac
```bash
scp timjvanc@mi3-ts100.a2hosting.com:~/public_html/Sites/vgc_to/url_shortener_backup.sql ~/Desktop/
```

### Step 3: Copy to Hetzner
```bash
scp ~/Desktop/url_shortener_backup.sql root@5.78.93.10:/opt/vgc-url-shortener/
```

### Step 4: Run migration (after docker compose is running)
```bash
cd /opt/vgc-url-shortener
pip3 install pymysql
DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=vgcto DB_PASS=yourdbpass DB_NAME=vgcto python3 migrate.py url_shortener_backup.sql
```

---

## Set up reverse proxy in CyberPanel

Create website `vgc.to` in CyberPanel, then add to vHost conf:

```
context / {
  type                proxy
  handler             localhost:5001
  addDefaultCharset   off
}
```

Then issue SSL via CyberPanel for vgc.to.

---

## Updating
```bash
cd /opt/vgc-url-shortener
docker compose down
docker compose up -d --build
```

## Branches

- `main` mirrors the application currently running at vgc.to.
- `staging` contains the next set of changes for testing before production deployment.

Set `PUBLIC_BASE_URL` and `APP_PORT` in `.env` when running a separate environment. For example, staging uses `https://staging.vgc.to` and port `5002`.
