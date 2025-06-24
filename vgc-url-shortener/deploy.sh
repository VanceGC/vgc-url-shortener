#!/bin/bash

# VGC URL Shortener - DigitalOcean Deployment Script
# This script automates the deployment process on a DigitalOcean droplet

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons"
fi

# Configuration
APP_DIR="/home/$(whoami)/vgc-url-shortener"
DOMAIN="vgc.to"
EMAIL="admin@vgc.to"  # Change this to your email

log "Starting VGC URL Shortener deployment..."

# Update system
log "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $(whoami)
    rm get-docker.sh
    log "Docker installed. Please log out and log back in for group changes to take effect."
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    log "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create application directory
log "Setting up application directory..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Create necessary directories
mkdir -p data logs logs/caddy

# Set up environment file
if [ ! -f .env ]; then
    log "Creating environment configuration..."
    cp .env.example .env
    
    # Generate a secure secret key
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/your-super-secret-key-change-this-in-production/$SECRET_KEY/" .env
    sed -i "s/admin@vgc.to/$EMAIL/" .env
    
    warn "Please review and customize the .env file before continuing"
    warn "Update the ADMIN_EMAIL and other settings as needed"
fi

# Set up firewall
log "Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Build and start services
log "Building and starting services..."
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be healthy
log "Waiting for services to start..."
sleep 30

# Check service health
log "Checking service health..."
if docker-compose ps | grep -q "Up (healthy)"; then
    log "Services are running and healthy!"
else
    warn "Some services may not be healthy. Checking logs..."
    docker-compose logs --tail=50
fi

# Set up log rotation
log "Setting up log rotation..."
sudo tee /etc/logrotate.d/vgc-url-shortener > /dev/null <<EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $(whoami) $(whoami)
    postrotate
        docker-compose -f $APP_DIR/docker-compose.yml restart flask-app
    endscript
}
EOF

# Set up backup script
log "Setting up backup script..."
cat > "$APP_DIR/backup.sh" << 'EOF'
#!/bin/bash
# VGC URL Shortener Backup Script

BACKUP_DIR="/home/$(whoami)/backups"
APP_DIR="/home/$(whoami)/vgc-url-shortener"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup database
cp "$APP_DIR/data/app.db" "$BACKUP_DIR/app_db_$DATE.db"

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$APP_DIR" .env docker-compose.yml Caddyfile

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x "$APP_DIR/backup.sh"

# Set up cron job for backups
log "Setting up automated backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh >> $APP_DIR/logs/backup.log 2>&1") | crontab -

# Set up monitoring script
log "Setting up monitoring script..."
cat > "$APP_DIR/monitor.sh" << 'EOF'
#!/bin/bash
# VGC URL Shortener Monitoring Script

APP_DIR="/home/$(whoami)/vgc-url-shortener"
cd "$APP_DIR"

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "$(date): Services are down, attempting restart..." >> logs/monitor.log
    docker-compose up -d
fi

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "$(date): Disk usage is at ${DISK_USAGE}%" >> logs/monitor.log
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEM_USAGE" -gt 80 ]; then
    echo "$(date): Memory usage is at ${MEM_USAGE}%" >> logs/monitor.log
fi
EOF

chmod +x "$APP_DIR/monitor.sh"

# Set up monitoring cron job
(crontab -l 2>/dev/null; echo "*/5 * * * * $APP_DIR/monitor.sh") | crontab -

# Display final information
log "Deployment completed successfully!"
echo
echo -e "${BLUE}=== VGC URL Shortener Deployment Summary ===${NC}"
echo -e "${GREEN}✓ Application deployed to: $APP_DIR${NC}"
echo -e "${GREEN}✓ Services running on: https://$DOMAIN${NC}"
echo -e "${GREEN}✓ Health check: https://$DOMAIN/api/health${NC}"
echo -e "${GREEN}✓ Automatic backups configured${NC}"
echo -e "${GREEN}✓ Monitoring configured${NC}"
echo -e "${GREEN}✓ Log rotation configured${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Point your domain $DOMAIN to this server's IP address"
echo "2. Wait for DNS propagation (up to 24 hours)"
echo "3. SSL certificates will be automatically obtained by Caddy"
echo "4. Review and customize the .env file if needed"
echo "5. Test the application at https://$DOMAIN"
echo
echo -e "${BLUE}Useful commands:${NC}"
echo "  View logs: docker-compose logs -f"
echo "  Restart services: docker-compose restart"
echo "  Update application: git pull && docker-compose build --no-cache && docker-compose up -d"
echo "  Backup database: $APP_DIR/backup.sh"
echo "  Monitor services: $APP_DIR/monitor.sh"
echo
echo -e "${GREEN}Deployment completed! Your URL shortener is ready to use.${NC}"

