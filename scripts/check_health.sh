#!/bin/bash
# check_health.sh — Health monitoring script for BUX services
# Usage: ./check_health.sh [--notify] [--rollback-on-fail]

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

API_HOST="localhost"
API_PORT="8088"
HEALTH_ENDPOINT="http://${API_HOST}:${API_PORT}/health"
LOG_FILE="/opt/bux/logs/health_check.log"
NOTIFY=false
ROLLBACK_ON_FAIL=false

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --notify)
            NOTIFY=true
            shift
            ;;
        --rollback-on-fail)
            ROLLBACK_ON_FAIL=true
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

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_container() {
    local container_name=$1
    local status=$(docker inspect "$container_name" --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
    
    if [ "$status" = "running" ]; then
        log "✅ $container_name: running"
        return 0
    else
        log "❌ $container_name: $status"
        return 1
    fi
}

# ============================================================================
# MAIN HEALTH CHECK
# ============================================================================

main() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "🏥 Health Check Started"
    
    FAILED=false
    
    # Check API health endpoint
    log "Checking API health endpoint: $HEALTH_ENDPOINT"
    
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$HEALTH_ENDPOINT" 2>/dev/null || echo "000")
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
    RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTH_STATUS=$(echo "$RESPONSE_BODY" | jq -r .ok 2>/dev/null || echo "false")
        
        if [ "$HEALTH_STATUS" = "true" ]; then
            log "✅ API health check PASSED (200 OK, {\"ok\": true})"
        else
            log "⚠️ API returned 200 but health status is not true"
            log "Response: $RESPONSE_BODY"
            FAILED=true
        fi
    else
        log "❌ API health check FAILED (HTTP $HTTP_CODE)"
        log "Response: $RESPONSE_BODY"
        FAILED=true
    fi
    
    # Check container status
    log "Checking container status..."
    
    for container in bux_api bux_bot bux_agent bux_ollama; do
        if ! check_container "$container"; then
            FAILED=true
        fi
    done
    
    # Check disk space
    log "Checking disk space..."
    DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$DISK_USAGE" -gt 90 ]; then
        log "⚠️ Disk usage is high: ${DISK_USAGE}%"
        FAILED=true
    else
        log "✅ Disk usage OK: ${DISK_USAGE}%"
    fi
    
    # Check database accessibility
    log "Checking database..."
    
    if [ -f /opt/bux/db/shifts.db ]; then
        DB_SIZE=$(stat -c%s /opt/bux/db/shifts.db)
        log "✅ Database found (${DB_SIZE} bytes)"
    else
        log "❌ Database file not found"
        FAILED=true
    fi
    
    # Final status
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$FAILED" = true ]; then
        log "❌ Health check FAILED"
        
        if [ "$ROLLBACK_ON_FAIL" = true ]; then
            log "🔄 Triggering rollback..."
            /opt/bux/scripts/rollback.sh
        fi
        
        if [ "$NOTIFY" = true ]; then
            # Send notification (placeholder for email/Slack/etc.)
            log "📧 Sending failure notification..."
        fi
        
        exit 1
    else
        log "✅ All health checks PASSED"
        exit 0
    fi
}

# ============================================================================
# EXECUTE
# ============================================================================

mkdir -p "$(dirname "$LOG_FILE")"
main
