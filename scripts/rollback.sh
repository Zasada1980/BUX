#!/bin/bash
# rollback.sh — Rollback to previous deployment version
# Usage: ./rollback.sh [--to-version VERSION] [--force]

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT="/opt/bux"
COMPOSE_FILE="docker-compose.cloud.yml"
FORCE=false
TARGET_VERSION=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --to-version)
            TARGET_VERSION="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ============================================================================
# MAIN ROLLBACK LOGIC
# ============================================================================

main() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 BUX Rollback Script"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$PROJECT_ROOT" || {
        log_error "Failed to change directory to $PROJECT_ROOT"
        exit 1
    }
    
    # Find latest backup
    if [ -z "$TARGET_VERSION" ]; then
        log_info "Looking for latest backup..."
        
        LATEST_BACKUP_DIR=$(ls -td backups/*/ 2>/dev/null | head -1)
        
        if [ -z "$LATEST_BACKUP_DIR" ]; then
            log_error "No backups found in $PROJECT_ROOT/backups/"
            exit 1
        fi
        
        log_info "Found backup: $LATEST_BACKUP_DIR"
        
        # Extract version from backup deployment report
        if [ -f "${LATEST_BACKUP_DIR}cloud_deployment_"*.json ]; then
            TARGET_VERSION=$(cat "${LATEST_BACKUP_DIR}cloud_deployment_"*.json | jq -r .deployment.version 2>/dev/null || echo "unknown")
            log_info "Target version: $TARGET_VERSION"
        fi
    fi
    
    # Confirmation prompt
    if [ "$FORCE" != true ]; then
        echo ""
        echo "⚠️  WARNING: This will rollback to previous version!"
        echo "   Current deployment will be replaced."
        echo ""
        read -p "Continue? (yes/no): " CONFIRM
        
        if [ "$CONFIRM" != "yes" ]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi
    
    # Stop current containers
    log_info "Stopping current containers..."
    docker-compose -f "$COMPOSE_FILE" down
    
    # Restore database if backup exists
    if [ -n "$LATEST_BACKUP_DIR" ] && [ -f "${LATEST_BACKUP_DIR}shifts.db.backup" ]; then
        log_info "Restoring database from backup..."
        cp "${LATEST_BACKUP_DIR}shifts.db.backup" db/shifts.db
        log_success "Database restored"
    else
        log_error "No database backup found, skipping database restore"
    fi
    
    # Pull previous version images
    if [ -n "$TARGET_VERSION" ] && [ "$TARGET_VERSION" != "unknown" ]; then
        log_info "Pulling images for version: $TARGET_VERSION"
        
        # Update docker-compose to use target version
        # (Assuming images are tagged with version)
        docker pull zasada1980/bux-api:$TARGET_VERSION || log_error "Failed to pull API image"
        docker pull zasada1980/bux-bot:$TARGET_VERSION || log_error "Failed to pull bot image"
        docker pull zasada1980/bux-agent:$TARGET_VERSION || log_error "Failed to pull agent image"
    fi
    
    # Restart containers
    log_info "Starting containers..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_info "Waiting 30 seconds for services to start..."
    sleep 30
    
    # Health check
    log_info "Performing health check..."
    HEALTH_RESPONSE=$(curl -s http://localhost:8088/health 2>/dev/null || echo '{"ok": false}')
    HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r .ok 2>/dev/null || echo "false")
    
    if [ "$HEALTH_STATUS" = "true" ]; then
        log_success "Rollback completed successfully!"
        log_success "Health check: PASSED"
        
        # Generate rollback report
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        cat > "rollback_report_$TIMESTAMP.json" << EOF
{
  "rollback": {
    "timestamp": "$(date -Iseconds)",
    "target_version": "$TARGET_VERSION",
    "status": "SUCCESS"
  },
  "services": {
    "api": {"status": "$(docker inspect bux_api --format='{{.State.Status}}')"},
    "bot": {"status": "$(docker inspect bux_bot --format='{{.State.Status}}')"},
    "agent": {"status": "$(docker inspect bux_agent --format='{{.State.Status}}')"},
    "ollama": {"status": "$(docker inspect bux_ollama --format='{{.State.Status}}')}"}
  }
}
EOF
        
        log_info "Rollback report: rollback_report_$TIMESTAMP.json"
    else
        log_error "Rollback health check FAILED"
        log_error "Manual intervention required!"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================================================
# EXECUTE
# ============================================================================

main
