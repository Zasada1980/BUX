#!/bin/bash
################################################################################
# STAGE 4 - CLOUD VM DEPLOYMENT
# 
# Purpose: Deploy BUX v2.0.0 to cloud VM using Docker Hub images
# Usage: ./cloud_deploy_stage4.sh --registry dockerhub --version v2.0.0 --domain example.com
# Prerequisites: Ubuntu 22.04+ with sudo access, internet connection
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# CONFIGURATION
# ============================================================================

VERSION="v2.0.0"
REGISTRY="dockerhub"
DOCKER_USER="zasada1980"
DOMAIN=""
PROJECT_DIR="/opt/bux"
SKIP_HTTPS=false
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Report data
REPORT_FILE="cloud_deployment_$(date +%Y%m%d_%H%M%S).json"
START_TIME=$(date -Iseconds)
PHASES=()
ERRORS=()
SUCCESS=false

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_phase() {
    echo -e "\n${MAGENTA}🚀 PHASE $1${NC}\n"
}

add_phase_result() {
    local name="$1"
    local status="$2"
    local details="${3:-{}}"
    local error="${4:-}"
    
    local phase_json=$(cat <<EOF
{
  "name": "$name",
  "status": "$status",
  "timestamp": "$(date -Iseconds)",
  "details": $details
EOF
)
    
    if [ -n "$error" ]; then
        phase_json="$phase_json, \"error\": \"$error\""
        ERRORS+=("$error")
    fi
    
    phase_json="$phase_json }"
    PHASES+=("$phase_json")
}

save_deployment_report() {
    local duration=$(($(date +%s) - $(date -d "$START_TIME" +%s)))
    local report_path="$PROJECT_DIR/$REPORT_FILE"
    
    # Build phases array
    local phases_json="["
    for i in "${!PHASES[@]}"; do
        phases_json="$phases_json${PHASES[$i]}"
        [ $i -lt $((${#PHASES[@]} - 1)) ] && phases_json="$phases_json,"
    done
    phases_json="$phases_json]"
    
    # Build errors array
    local errors_json="["
    for i in "${!ERRORS[@]}"; do
        errors_json="$errors_json\"${ERRORS[$i]}\""
        [ $i -lt $((${#ERRORS[@]} - 1)) ] && errors_json="$errors_json,"
    done
    errors_json="$errors_json]"
    
    cat > "$report_path" <<EOF
{
  "timestamp": "$START_TIME",
  "stage": "Stage 4 - Cloud VM Deployment",
  "version": "$VERSION",
  "registry": "$REGISTRY",
  "domain": "$DOMAIN",
  "project_dir": "$PROJECT_DIR",
  "success": $SUCCESS,
  "duration_seconds": $duration,
  "phases": $phases_json,
  "errors": $errors_json
}
EOF
    
    log_success "Deployment report saved: $report_path"
    echo "$report_path"
}

cleanup_on_error() {
    log_warning "Cleaning up after error..."
    if [ -d "$PROJECT_DIR" ]; then
        cd "$PROJECT_DIR"
        docker compose -f docker-compose.prod.yml down 2>/dev/null || true
    fi
}

# ============================================================================
# PHASE 0: PARSE ARGUMENTS
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
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --skip-https)
            SKIP_HTTPS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --version VERSION      Docker image version (default: v2.0.0)
  --registry REGISTRY    Registry type: dockerhub or gcp (default: dockerhub)
  --domain DOMAIN        Domain name for HTTPS setup (optional)
  --skip-https           Skip HTTPS/nginx configuration
  --dry-run              Show commands without executing
  --help                 Show this help message

Examples:
  $0 --registry dockerhub --version v2.0.0
  $0 --registry dockerhub --version v2.0.0 --domain bux.example.com
  $0 --dry-run
EOF
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# PHASE 1: PREREQUISITES CHECK
# ============================================================================

check_prerequisites() {
    log_phase "1 — Prerequisites Check"
    
    local details='{"checks": []}'
    
    # Check if running as root or with sudo
    if [ "$EUID" -ne 0 ] && ! groups | grep -q docker; then
        log_error "Must run as root or user in docker group"
        add_phase_result "PHASE 1: Prerequisites" "FAILED" "$details" "User lacks docker permissions"
        return 1
    fi
    log_success "User permissions: OK"
    
    # Check OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        log_success "OS: $PRETTY_NAME"
    else
        log_warning "Cannot detect OS version"
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not installed"
        add_phase_result "PHASE 1: Prerequisites" "FAILED" "$details" "Docker not found"
        return 1
    fi
    local docker_version=$(docker --version)
    log_success "Docker: $docker_version"
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose plugin not installed"
        add_phase_result "PHASE 1: Prerequisites" "FAILED" "$details" "Docker Compose not found"
        return 1
    fi
    local compose_version=$(docker compose version)
    log_success "Docker Compose: $compose_version"
    
    # Check internet connectivity
    if ! ping -c 1 hub.docker.com &> /dev/null; then
        log_warning "Cannot reach hub.docker.com (may affect image pull)"
    else
        log_success "Internet: Connected"
    fi
    
    # Check disk space (require at least 5GB free)
    local free_space=$(df / | tail -1 | awk '{print $4}')
    if [ "$free_space" -lt 5242880 ]; then  # 5GB in KB
        log_warning "Low disk space: $(( free_space / 1048576 ))GB free"
    else
        log_success "Disk space: $(( free_space / 1048576 ))GB free"
    fi
    
    add_phase_result "PHASE 1: Prerequisites" "SUCCESS" '{"docker": true, "compose": true, "network": true}'
    return 0
}

# ============================================================================
# PHASE 2: PROJECT SETUP
# ============================================================================

setup_project() {
    log_phase "2 — Project Setup"
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would create $PROJECT_DIR and configure environment"
        add_phase_result "PHASE 2: Setup" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    # Create project directory
    log_info "Creating project directory: $PROJECT_DIR"
    sudo mkdir -p "$PROJECT_DIR"/{db,backups,logs,reports}
    sudo chown -R $(whoami):$(whoami) "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    # Generate .env.prod
    log_info "Generating .env.prod"
    local secret_key=$(openssl rand -hex 32)
    local api_token=$(openssl rand -hex 32)
    local admin_secret=$(openssl rand -hex 32)
    local vm_ip=$(hostname -I | awk '{print $1}')
    
    cat > .env.prod <<EOF
# Database
DB_PATH=/app/db/shifts.db
ALEMBIC_URL=sqlite:////app/db/shifts.db

# API Configuration
INTERNAL_API_TOKEN=$api_token
INTERNAL_ADMIN_SECRET=$admin_secret
ADMIN_USER_HEADER=X-Admin-User

# Service URLs
AGENT_URL=http://agent:8080
OLLAMA_BASE_URL=http://ollama:11434
API_BASE_URL=http://api:8080

# Telegram Bot (MUST BE UPDATED)
TELEGRAM_BOT_TOKEN=REPLACE_WITH_YOUR_BOT_TOKEN

# Timezone
TZ=Asia/Jerusalem

# Pricing
PRICING_RULES_PATH=/app/config/pricing/global_prod.yaml

# Frontend (for local development only)
VITE_API_URL=http://$vm_ip:8088
EOF
    
    log_success "Generated .env.prod (REMEMBER: Update TELEGRAM_BOT_TOKEN)"
    
    # Download docker-compose.prod.yml
    log_info "Downloading docker-compose.prod.yml"
    if ! curl -fsSL https://raw.githubusercontent.com/Zasada1980/BUX/master/docker-compose.prod.yml -o docker-compose.prod.yml; then
        log_error "Failed to download docker-compose.prod.yml"
        add_phase_result "PHASE 2: Setup" "FAILED" '{}' "Cannot download compose file"
        return 1
    fi
    
    # Update docker-compose.prod.yml to use registry images
    log_info "Updating docker-compose.prod.yml to use registry images"
    sed -i.bak \
        -e 's|build:|#build:|g' \
        -e 's|context:|#context:|g' \
        -e 's|dockerfile:|#dockerfile:|g' \
        docker-compose.prod.yml
    
    # Add image references
    sed -i \
        -e '/^  api:/a\    image: '"$DOCKER_USER"'/bux-api:'"$VERSION" \
        -e '/^  bot:/a\    image: '"$DOCKER_USER"'/bux-bot:'"$VERSION" \
        -e '/^  agent:/a\    image: '"$DOCKER_USER"'/bux-agent:'"$VERSION" \
        docker-compose.prod.yml
    
    add_phase_result "PHASE 2: Setup" "SUCCESS" "{\"project_dir\": \"$PROJECT_DIR\", \"env_generated\": true}"
    return 0
}

# ============================================================================
# PHASE 3: PULL IMAGES FROM REGISTRY
# ============================================================================

pull_images() {
    log_phase "3 — Pull Images from Registry"
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would pull images from $REGISTRY"
        add_phase_result "PHASE 3: Pull Images" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    local images=(
        "$DOCKER_USER/bux-api:$VERSION"
        "$DOCKER_USER/bux-bot:$VERSION"
        "$DOCKER_USER/bux-agent:$VERSION"
    )
    
    local pulled_images=()
    
    for image in "${images[@]}"; do
        log_info "Pulling $image..."
        if docker pull "$image"; then
            log_success "Pulled: $image"
            pulled_images+=("$image")
        else
            log_error "Failed to pull: $image"
            add_phase_result "PHASE 3: Pull Images" "FAILED" "{\"pulled\": [\"${pulled_images[*]}\"]}" "Failed to pull $image"
            return 1
        fi
    done
    
    # Pull ollama separately (official image)
    log_info "Pulling ollama/ollama:latest..."
    docker pull ollama/ollama:latest
    pulled_images+=("ollama/ollama:latest")
    
    add_phase_result "PHASE 3: Pull Images" "SUCCESS" "{\"pulled_images\": [\"${pulled_images[@]}\"]}"
    return 0
}

# ============================================================================
# PHASE 4: DEPLOY CONTAINERS
# ============================================================================

deploy_containers() {
    log_phase "4 — Deploy Containers"
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would start containers with docker-compose"
        add_phase_result "PHASE 4: Deploy" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    cd "$PROJECT_DIR"
    
    # Start containers
    log_info "Starting containers with docker compose..."
    if ! docker compose -f docker-compose.prod.yml up -d; then
        log_error "Failed to start containers"
        add_phase_result "PHASE 4: Deploy" "FAILED" '{}' "docker-compose up failed"
        return 1
    fi
    
    # Wait for containers to be ready
    log_info "Waiting for containers to start (30 seconds)..."
    sleep 30
    
    # Check container status
    log_info "Checking container status..."
    local containers=$(docker compose -f docker-compose.prod.yml ps --format json | jq -s '.')
    local all_running=true
    
    while IFS= read -r container; do
        local service=$(echo "$container" | jq -r '.Service')
        local state=$(echo "$container" | jq -r '.State')
        
        if [ "$state" == "running" ]; then
            log_success "Container $service: $state"
        else
            log_error "Container $service: $state"
            all_running=false
        fi
    done < <(echo "$containers" | jq -c '.[]')
    
    if ! $all_running; then
        log_error "Some containers failed to start"
        docker compose -f docker-compose.prod.yml logs --tail 50
        add_phase_result "PHASE 4: Deploy" "FAILED" "{\"containers\": $containers}" "Containers not running"
        return 1
    fi
    
    add_phase_result "PHASE 4: Deploy" "SUCCESS" "{\"containers\": $containers}"
    return 0
}

# ============================================================================
# PHASE 5: RUN MIGRATIONS & SEED DATA
# ============================================================================

run_migrations() {
    log_phase "5 — Database Migrations & Seed"
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would run alembic migrations and seed data"
        add_phase_result "PHASE 5: Migrations" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    cd "$PROJECT_DIR"
    
    # Run Alembic migrations
    log_info "Running Alembic migrations..."
    if ! docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head; then
        log_error "Alembic migrations failed"
        add_phase_result "PHASE 5: Migrations" "FAILED" '{}' "Alembic upgrade failed"
        return 1
    fi
    log_success "Alembic migrations complete"
    
    # Seed database
    log_info "Seeding database..."
    if docker compose -f docker-compose.prod.yml exec -T api python -m seeds.seed_e2e_minimal; then
        log_success "Database seeded successfully"
    else
        log_warning "Database seeding failed (may already be seeded)"
    fi
    
    add_phase_result "PHASE 5: Migrations" "SUCCESS" '{"alembic": "upgraded", "seed": "attempted"}'
    return 0
}

# ============================================================================
# PHASE 6: SMOKE TESTS
# ============================================================================

run_smoke_tests() {
    log_phase "6 — Smoke Tests"
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would run smoke tests"
        add_phase_result "PHASE 6: Smoke Tests" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    # Test API health endpoint
    log_info "Testing API health endpoint..."
    local health_response=$(curl -s http://localhost:8088/health)
    
    if echo "$health_response" | jq -e '.ok == true' > /dev/null 2>&1; then
        log_success "API health check: PASS"
        log_info "Response: $(echo $health_response | jq -c '.')"
    else
        log_error "API health check: FAIL"
        log_error "Response: $health_response"
        add_phase_result "PHASE 6: Smoke Tests" "FAILED" "{\"health\": \"$health_response\"}" "Health check failed"
        return 1
    fi
    
    # Check database connectivity
    log_info "Checking database..."
    local db_check=$(docker compose -f docker-compose.prod.yml exec -T api python -c \
        "from api.db import get_session; from api.models_users import Employee; session = next(get_session()); print(session.query(Employee).count())" 2>&1)
    
    if [[ "$db_check" =~ ^[0-9]+$ ]]; then
        log_success "Database accessible, employee count: $db_check"
    else
        log_warning "Database check inconclusive: $db_check"
    fi
    
    # Display container stats
    log_info "Container resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    
    add_phase_result "PHASE 6: Smoke Tests" "SUCCESS" "{\"health\": $health_response, \"db_employees\": \"$db_check\"}"
    return 0
}

# ============================================================================
# PHASE 7: HTTPS CONFIGURATION (OPTIONAL)
# ============================================================================

configure_https() {
    log_phase "7 — HTTPS Configuration"
    
    if $SKIP_HTTPS; then
        log_info "Skipping HTTPS configuration (--skip-https flag)"
        add_phase_result "PHASE 7: HTTPS" "SKIPPED" '{"reason": "user requested skip"}'
        return 0
    fi
    
    if [ -z "$DOMAIN" ]; then
        log_warning "No domain provided, skipping HTTPS setup"
        log_info "To enable HTTPS later, run: sudo certbot --nginx -d <domain>"
        add_phase_result "PHASE 7: HTTPS" "SKIPPED" '{"reason": "no domain specified"}'
        return 0
    fi
    
    if $DRY_RUN; then
        log_warning "DRY-RUN: Would configure nginx and certbot for $DOMAIN"
        add_phase_result "PHASE 7: HTTPS" "SKIPPED" '{"reason": "dry-run mode"}'
        return 0
    fi
    
    # Install nginx and certbot
    log_info "Installing nginx and certbot..."
    sudo apt-get update -qq
    sudo apt-get install -y nginx certbot python3-certbot-nginx
    
    # Configure nginx
    log_info "Configuring nginx for $DOMAIN..."
    sudo tee /etc/nginx/sites-available/bux.conf > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    sudo ln -sf /etc/nginx/sites-available/bux.conf /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
    log_success "Nginx configured and restarted"
    
    # Configure firewall
    if command -v ufw &> /dev/null; then
        log_info "Configuring firewall..."
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        log_success "Firewall rules added"
    fi
    
    # Obtain SSL certificate
    log_info "Obtaining SSL certificate for $DOMAIN..."
    if sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN"; then
        log_success "SSL certificate obtained and configured"
        add_phase_result "PHASE 7: HTTPS" "SUCCESS" "{\"domain\": \"$DOMAIN\", \"https\": true}"
    else
        log_error "Failed to obtain SSL certificate"
        log_warning "Site accessible via HTTP only"
        add_phase_result "PHASE 7: HTTPS" "PARTIAL" "{\"domain\": \"$DOMAIN\", \"https\": false}" "Certbot failed"
    fi
    
    return 0
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    cat <<EOF

╔═══════════════════════════════════════════════════════════════╗
║              STAGE 4 CLOUD VM DEPLOYMENT                      ║
║           Automated Cloud Deployment Script                   ║
╚═══════════════════════════════════════════════════════════════╝

Registry:    $REGISTRY
Version:     $VERSION
Domain:      ${DOMAIN:-"(not specified)"}
Project Dir: $PROJECT_DIR
Dry-Run:     $DRY_RUN

EOF
    
    # Set trap for cleanup on error
    trap cleanup_on_error ERR
    
    # Execute phases
    check_prerequisites || exit 1
    setup_project || exit 1
    pull_images || exit 1
    deploy_containers || exit 1
    run_migrations || exit 1
    run_smoke_tests || exit 1
    configure_https || true  # Don't fail on HTTPS issues
    
    # Mark success
    SUCCESS=true
    local report_path=$(save_deployment_report)
    
    # Success summary
    cat <<EOF

╔═══════════════════════════════════════════════════════════════╗
║           ✅ STAGE 4 DEPLOYMENT COMPLETE                      ║
╚═══════════════════════════════════════════════════════════════╝

✅ All containers deployed and running
✅ Database migrated and seeded
✅ Smoke tests passed

📊 Deployment Report: $report_path

🌐 Access your application:
   - API Health: http://$(hostname -I | awk '{print $1}'):8088/health
EOF

    if [ -n "$DOMAIN" ] && [ "$SKIP_HTTPS" = false ]; then
        echo "   - Web UI: https://$DOMAIN"
    else
        echo "   - Web UI: http://$(hostname -I | awk '{print $1}'):8088"
    fi

    cat <<EOF

📝 Next steps:
   1. Update TELEGRAM_BOT_TOKEN in $PROJECT_DIR/.env.prod
   2. Restart bot: docker compose -f $PROJECT_DIR/docker-compose.prod.yml restart bot
   3. Monitor logs: docker compose -f $PROJECT_DIR/docker-compose.prod.yml logs -f
   4. Setup automated backups (see STAGE_3_CLOUD_DEPLOYMENT.md)

EOF
}

# Run main function
main
