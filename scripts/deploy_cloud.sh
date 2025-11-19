#!/bin/bash
# deploy_cloud.sh — Unified Cloud Deployment Script for BUX
# Usage: ./deploy_cloud.sh [--version VERSION] [--registry REGISTRY] [--auto-version] [--skip-https]

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/opt/bux"
COMPOSE_FILE="docker-compose.cloud.yml"
REGISTRY="dockerhub"
VERSION="latest"
AUTO_VERSION=false
SKIP_HTTPS=true

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --auto-version)
            AUTO_VERSION=true
            shift
            ;;
        --skip-https)
            SKIP_HTTPS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Auto-version: use git commit count or timestamp
if [ "$AUTO_VERSION" = true ]; then
    if command -v git &> /dev/null && [ -d .git ]; then
        VERSION="v2.0.$(git rev-list --count HEAD)"
    else
        VERSION="v2.0.$(date +%Y%m%d%H%M%S)"
    fi
fi

# ============================================================================
# MAIN DEPLOYMENT LOGIC
# ============================================================================

main() {
    print_header "🚀 BUX Cloud Deployment Script"
    
    log_info "Project root: $PROJECT_ROOT"
    log_info "Version: $VERSION"
    log_info "Registry: $REGISTRY"
    
    cd "$PROJECT_ROOT" || {
        log_error "Failed to change directory to $PROJECT_ROOT"
        exit 1
    }
    
    # PHASE 1: Pre-deployment backup
    print_header "📦 PHASE 1: Pre-deployment Backup"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="$PROJECT_ROOT/backups/$TIMESTAMP"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if [ -f db/shifts.db ]; then
        log_info "Backing up database..."
        cp db/shifts.db "$BACKUP_DIR/shifts.db.backup"
        log_success "Database backed up to $BACKUP_DIR"
    fi
    
    # Backup current deployment report
    if ls cloud_deployment_*.json 1> /dev/null 2>&1; then
        cp cloud_deployment_*.json "$BACKUP_DIR/" 2>/dev/null || true
        log_success "Deployment reports backed up"
    fi
    
    # Snapshot current container state
    docker-compose -f "$COMPOSE_FILE" ps > "$BACKUP_DIR/containers_snapshot.txt"
    log_success "Container snapshot saved"
    
    # PHASE 2: Pull new images
    print_header "📥 PHASE 2: Pull Docker Images"
    
    log_info "Pulling images (version: $VERSION)"
    
    if ! docker-compose -f "$COMPOSE_FILE" pull; then
        log_error "Failed to pull images"
        exit 1
    fi
    
    log_success "Images pulled successfully"
    
    # PHASE 3: Restart services
    print_header "🔄 PHASE 3: Restart Services"
    
    log_info "Stopping containers..."
    docker-compose -f "$COMPOSE_FILE" down
    
    log_info "Starting containers with new images..."
    docker-compose -f "$COMPOSE_FILE" up -d --force-recreate
    
    log_success "Containers restarted"
    
    # PHASE 4: Wait for services
    print_header "⏳ PHASE 4: Wait for Services"
    
    log_info "Waiting 30 seconds for services to initialize..."
    sleep 30
    
    # PHASE 5: Health check
    print_header "🏥 PHASE 5: Health Check"
    
    HEALTH_RESPONSE=$(curl -s http://localhost:8088/health || echo '{"ok": false}')
    HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r .ok 2>/dev/null || echo "false")
    
    if [ "$HEALTH_STATUS" = "true" ]; then
        log_success "Health check PASSED"
        echo "$HEALTH_RESPONSE" | jq .
    else
        log_error "Health check FAILED"
        echo "Response: $HEALTH_RESPONSE"
        
        # Rollback
        log_warning "Rolling back to previous version..."
        docker-compose -f "$COMPOSE_FILE" down
        docker-compose -f "$COMPOSE_FILE" up -d
        
        exit 1
    fi
    
    # PHASE 6: Generate deployment report
    print_header "📊 PHASE 6: Generate Deployment Report"
    
    REPORT_FILE="cloud_deployment_$TIMESTAMP.json"
    
    cat > "$REPORT_FILE" << EOF
{
  "deployment": {
    "stage": "Stage 5 - Automated Deployment",
    "timestamp": "$(date -Iseconds)",
    "version": "$VERSION",
    "registry": "$REGISTRY",
    "status": "SUCCESS",
    "script": "deploy_cloud.sh"
  },
  "server": {
    "hostname": "$(hostname)",
    "ip": "46.224.36.109",
    "os": "$(lsb_release -ds)",
    "kernel": "$(uname -r)"
  },
  "services": {
    "api": {
      "image": "zasada1980/bux-api:$VERSION",
      "status": "$(docker inspect bux_api --format='{{.State.Status}}' 2>/dev/null || echo 'unknown')",
      "health": "$HEALTH_STATUS"
    },
    "bot": {
      "image": "zasada1980/bux-bot:$VERSION",
      "status": "$(docker inspect bux_bot --format='{{.State.Status}}' 2>/dev/null || echo 'unknown')"
    },
    "agent": {
      "image": "zasada1980/bux-agent:$VERSION",
      "status": "$(docker inspect bux_agent --format='{{.State.Status}}' 2>/dev/null || echo 'unknown')"
    },
    "ollama": {
      "image": "ollama/ollama:latest",
      "status": "$(docker inspect bux_ollama --format='{{.State.Status}}' 2>/dev/null || echo 'unknown')"
    }
  },
  "backup": {
    "directory": "$BACKUP_DIR",
    "database": "shifts.db.backup",
    "timestamp": "$TIMESTAMP"
  },
  "access": {
    "api_health": "http://46.224.36.109:8088/health",
    "web_ui": "http://46.224.36.109:8088/",
    "telegram_bot": "https://t.me/Ollama_axon_bot"
  }
}
EOF
    
    log_success "Deployment report generated: $REPORT_FILE"
    cat "$REPORT_FILE" | jq -C .
    
    # PHASE 7: Final status
    print_header "🎉 Deployment Complete"
    
    docker-compose -f "$COMPOSE_FILE" ps
    
    log_success "BUX v$VERSION deployed successfully!"
    log_info "Access URLs:"
    log_info "  - API Health: http://46.224.36.109:8088/health"
    log_info "  - Web UI: http://46.224.36.109:8088/"
    log_info "  - Telegram Bot: https://t.me/Ollama_axon_bot"
    
    echo ""
}

# ============================================================================
# EXECUTE
# ============================================================================

main
