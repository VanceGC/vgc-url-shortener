#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY=/opt/vgc-url-shortener
DATABASE_CONTAINER=vgc-url-shortener-db-1
BACKUP_DIRECTORY=/opt/backups/vgc-url-shortener/automatic
HEALTH_URL=http://127.0.0.1:5001/login

exec 9>/var/lock/vgc-url-shortener-deploy.lock
flock -w 600 9

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
  logger -t vgc-url-shortener-deploy -- "$*"
}

wait_for_health() {
  for _ in $(seq 1 30); do
    if [ "$(curl -sS -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)" = 200 ]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

cd "$REPOSITORY"
previous_commit=$(git rev-parse HEAD)
git fetch --prune origin main
target_commit=$(git rev-parse origin/main)

if [ "$previous_commit" = "$target_commit" ]; then
  log "Production is already at $target_commit"
  exit 0
fi

if ! git merge-base --is-ancestor "$previous_commit" "$target_commit"; then
  log "Refusing non-fast-forward deployment from $previous_commit to $target_commit"
  exit 1
fi

install -d -m 700 "$BACKUP_DIRECTORY"
backup_file="$BACKUP_DIRECTORY/production-$(date -u +%Y%m%dT%H%M%SZ)-${previous_commit:0:12}.sql.gz"
docker exec "$DATABASE_CONTAINER" sh -lc \
  'exec mysqldump --no-tablespaces --single-transaction --quick --routines --triggers --default-character-set=utf8mb4 -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  | gzip -9 > "$backup_file"
gzip -t "$backup_file"
chmod 600 "$backup_file"
log "Database backup completed before deploying $target_commit"

git reset --hard "$target_commit"
if ! docker compose config >/dev/null || ! docker compose build app; then
  git reset --hard "$previous_commit"
  log "Build failed for $target_commit, production was not replaced"
  exit 1
fi

docker compose up -d --no-deps app
if wait_for_health; then
  log "Production deployment completed at $target_commit"
  exit 0
fi

log "Health check failed for $target_commit, rolling back to $previous_commit"
git reset --hard "$previous_commit"
docker compose build app
docker compose up -d --no-deps app

if wait_for_health; then
  log "Rollback completed at $previous_commit"
else
  log "Critical: rollback health check failed at $previous_commit"
fi
exit 1
