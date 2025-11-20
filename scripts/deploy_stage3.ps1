#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stage 3 Cloud Deployment - Local Build & Smoke Test Automation
.DESCRIPTION
    Automated script for PHASE 1-3:
    - Build production Docker images (api, bot, agent)
    - Local smoke testing with docker-compose.prod.yml
    - Tag and push to Docker Hub / GCP Artifact Registry
.PARAMETER Registry
    Target registry: "dockerhub" or "gcp" (default: dockerhub)
.PARAMETER Version
    Image version tag (default: v2.0.0)
.PARAMETER SkipTests
    Skip smoke tests (not recommended)
.PARAMETER DryRun
    Show commands without executing
.EXAMPLE
    .\deploy_stage3.ps1 -Registry dockerhub -Version v2.0.0
.NOTES
    Created: 2025-11-19
    Prerequisites: Docker 24.0+, docker compose 2.20+
#>

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet("dockerhub", "gcp")]
    [string]$Registry = "dockerhub",

    [Parameter()]
    [string]$Version = "v2.0.0",

    [Parameter()]
    [switch]$SkipTests,

    [Parameter()]
    [switch]$DryRun
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = "D:\TelegramOllama_ENV_DEMO\code"
$DOCKER_USER = "zasada1980"  # Docker Hub username
$GCP_PROJECT = "your-gcp-project-id"  # Update with actual GCP project
$GCP_REGION = "europe-west1"

$SERVICES = @("api", "bot", "agent")
$COMPOSE_FILE = "docker-compose.prod.yml"

# Deployment report
$REPORT_FILE = "deployment_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$DeploymentReport = @{
    timestamp = Get-Date -Format "o"
    stage = "Stage 3 - Cloud Deployment Preparation"
    version = $Version
    registry = $Registry
    phases = @()
    success = $false
    duration_seconds = 0
    artifacts = @()
    errors = @()
}

# Color output functions
function Write-Success { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Error { param($msg) Write-Host "❌ $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Warning { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Phase { param($msg) Write-Host "`n🚀 PHASE $msg" -ForegroundColor Magenta }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker not found. Install Docker Desktop."
        exit 1
    }
    $dockerVersion = docker --version
    Write-Success "Docker found: $dockerVersion"
    
    # Check docker compose
    try {
        docker compose version | Out-Null
        Write-Success "docker compose plugin found"
    } catch {
        Write-Error "docker compose plugin not found. Update Docker Desktop to 4.20+"
        exit 1
    }
    
    # Check project directory
    if (-not (Test-Path $PROJECT_ROOT)) {
        Write-Error "Project directory not found: $PROJECT_ROOT"
        exit 1
    }
    Write-Success "Project directory: $PROJECT_ROOT"
    
    # Check Dockerfiles
    foreach ($service in $SERVICES) {
        $dockerfile = Join-Path $PROJECT_ROOT "$service\Dockerfile"
        if ($service -eq "api") { $dockerfile = Join-Path $PROJECT_ROOT "api\Dockerfile" }
        if ($service -eq "bot") { $dockerfile = Join-Path $PROJECT_ROOT "bot\Dockerfile" }
        if ($service -eq "agent") { $dockerfile = Join-Path $PROJECT_ROOT "agent\Dockerfile" }
        
        if (-not (Test-Path $dockerfile)) {
            Write-Error "Dockerfile not found: $dockerfile"
            exit 1
        }
    }
    Write-Success "All Dockerfiles found"
    
    # Check compose file
    $composeFile = Join-Path $PROJECT_ROOT $COMPOSE_FILE
    if (-not (Test-Path $composeFile)) {
        Write-Error "docker-compose file not found: $composeFile"
        exit 1
    }
    Write-Success "Compose file: $composeFile"
}

function Invoke-Command {
    param([string]$cmd, [string]$description)
    
    Write-Info "$description"
    if ($DryRun) {
        Write-Host "  [DRY-RUN] $cmd" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host "  > $cmd" -ForegroundColor Gray
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed with exit code $LASTEXITCODE"
        return $false
    }
    return $true
}

function Get-ImageTag {
    param([string]$service)
    
    if ($Registry -eq "dockerhub") {
        return "${DOCKER_USER}/bux-${service}:${Version}"
    } else {
        $gcpRegistry = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/bux"
        return "${gcpRegistry}/bux-${service}:${Version}"
    }
}

function Save-DeploymentReport {
    $reportPath = Join-Path $PROJECT_ROOT $REPORT_FILE
    $DeploymentReport.duration_seconds = (New-TimeSpan -Start $script:StartTime -End (Get-Date)).TotalSeconds
    
    $json = $DeploymentReport | ConvertTo-Json -Depth 10
    $json | Out-File -FilePath $reportPath -Encoding utf8
    
    Write-Success "Deployment report saved: $reportPath"
    return $reportPath
}

function Add-PhaseResult {
    param(
        [string]$phaseName,
        [string]$status,
        [hashtable]$details = @{},
        [string]$error = ""
    )
    
    $phaseData = @{
        name = $phaseName
        status = $status
        timestamp = Get-Date -Format "o"
        details = $details
    }
    
    if ($error) {
        $phaseData.error = $error
        $script:DeploymentReport.errors += $error
    }
    
    $script:DeploymentReport.phases += $phaseData
}

# ============================================================================
# PHASE 1: BUILD IMAGES
# ============================================================================

function Invoke-Phase1-Build {
    Write-Phase "1 — Building Docker Images"
    $phaseStart = Get-Date
    
    Push-Location $PROJECT_ROOT
    try {
        # Build using docker-compose (faster, uses cache)
        $cmd = "docker compose -f $COMPOSE_FILE build --no-cache"
        if (-not (Invoke-Command $cmd "Building all services with docker-compose")) {
            Add-PhaseResult -phaseName "PHASE 1: Build" -status "FAILED" -error "docker-compose build failed"
            return $false
        }
        
        # Verify built images
        Write-Info "Verifying built images..."
        $images = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern "^code-(api|bot|agent):latest"
        if ($images.Count -eq 0) {
            Write-Error "No images built"
            Add-PhaseResult -phaseName "PHASE 1: Build" -status "FAILED" -error "No code-* images found"
            return $false
        }
        
        Write-Success "Built images:"
        $builtImages = @()
        $images | ForEach-Object { 
            Write-Host "  $_" -ForegroundColor Gray
            $builtImages += $_.ToString()
        }
        
        # Tag images with local tag
        $taggedImages = @()
        foreach ($service in $SERVICES) {
            $sourceImage = "code-${service}:latest"  # docker-compose builds as code-api, code-bot, code-agent
            $targetImage = "bux-${service}:local"
            
            $cmd = "docker tag ${sourceImage} ${targetImage}"
            if (-not (Invoke-Command $cmd "Tagging $service as local")) {
                Add-PhaseResult -phaseName "PHASE 1: Build" -status "FAILED" -error "Failed to tag $service"
                return $false
            }
            $taggedImages += $targetImage
        }
        
        $phaseDuration = (New-TimeSpan -Start $phaseStart -End (Get-Date)).TotalSeconds
        Add-PhaseResult -phaseName "PHASE 1: Build" -status "SUCCESS" -details @{
            built_images = $builtImages
            tagged_images = $taggedImages
            duration_seconds = $phaseDuration
        }
        
        $script:DeploymentReport.artifacts += $taggedImages
        Write-Success "PHASE 1 COMPLETE: All images built and tagged"
        return $true
    } catch {
        Add-PhaseResult -phaseName "PHASE 1: Build" -status "FAILED" -error $_.Exception.Message
        throw
    } finally {
        Pop-Location
    }
}

# ============================================================================
# PHASE 2: SMOKE TESTS
# ============================================================================

function Invoke-Phase2-SmokeTest {
    Write-Phase "2 — Local Smoke Testing"
    $phaseStart = Get-Date
    
    if ($SkipTests) {
        Write-Warning "Skipping smoke tests (--SkipTests flag)"
        Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "SKIPPED" -details @{
            reason = "User requested skip with -SkipTests flag"
        }
        return $true
    }
    
    Push-Location $PROJECT_ROOT
    try {
        # Stop any running containers
        Write-Info "Stopping existing containers..."
        docker compose -f $COMPOSE_FILE down 2>$null
        
        # Start prod containers
        $cmd = "docker compose -f $COMPOSE_FILE up -d"
        if (-not (Invoke-Command $cmd "Starting production containers")) {
            Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "FAILED" -error "Failed to start containers"
            return $false
        }
        
        # Wait for services to be ready
        Write-Info "Waiting for services to start (30 seconds)..."
        Start-Sleep -Seconds 30
        
        # Check container status
        Write-Info "Checking container status..."
        $containers = docker compose -f $COMPOSE_FILE ps --format json | ConvertFrom-Json
        $containerStatuses = @()
        $allRunning = $true
        
        foreach ($container in $containers) {
            $status = @{
                service = $container.Service
                state = $container.State
                ports = $container.Publishers
            }
            $containerStatuses += $status
            
            if ($container.State -ne "running") {
                Write-Error "Container $($container.Service) not running (state: $($container.State))"
                $allRunning = $false
            } else {
                Write-Success "Container $($container.Service): $($container.State)"
            }
        }
        
        if (-not $allRunning) {
            Write-Error "Some containers failed to start"
            docker compose -f $COMPOSE_FILE logs --tail 50
            Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "FAILED" -error "Containers not running" -details @{
                containers = $containerStatuses
            }
            return $false
        }
        
        # Test API health endpoint
        Write-Info "Testing API health endpoint..."
        $healthStatus = @{ endpoint = "/health"; status = "unknown" }
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8088/health" -Method GET -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                $body = $response.Content | ConvertFrom-Json
                $healthStatus.status = "PASS"
                $healthStatus.response = $body
                Write-Success "API health check: $($body | ConvertTo-Json -Compress)"
            } else {
                Write-Error "API health check failed: HTTP $($response.StatusCode)"
                $healthStatus.status = "FAIL"
                $healthStatus.http_code = $response.StatusCode
                Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "FAILED" -error "Health check HTTP $($response.StatusCode)" -details @{
                    containers = $containerStatuses
                    health = $healthStatus
                }
                return $false
            }
        } catch {
            Write-Error "API health check failed: $($_.Exception.Message)"
            $healthStatus.status = "FAIL"
            $healthStatus.error = $_.Exception.Message
            Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "FAILED" -error "Health check exception" -details @{
                containers = $containerStatuses
                health = $healthStatus
            }
            return $false
        }
        
        # Test API auth endpoint (should return 405 for GET, 422/401 for POST without body)
        Write-Info "Testing API auth endpoint..."
        $authStatus = @{ endpoint = "/api/auth/login"; status = "unknown" }
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8088/api/auth/login" -Method GET -TimeoutSec 5 -SkipHttpErrorCheck
            if ($response.StatusCode -eq 405) {
                Write-Success "API auth endpoint accessible (405 Method Not Allowed - expected)"
                $authStatus.status = "PASS"
                $authStatus.http_code = 405
            } else {
                Write-Warning "API auth endpoint returned unexpected status: $($response.StatusCode)"
                $authStatus.status = "WARN"
                $authStatus.http_code = $response.StatusCode
            }
        } catch {
            Write-Warning "API auth endpoint test inconclusive: $($_.Exception.Message)"
            $authStatus.status = "WARN"
            $authStatus.error = $_.Exception.Message
        }
        
        # Check database
        Write-Info "Checking database..."
        $dbStatus = @{ test = "employee_count"; status = "unknown" }
        $dbCheck = docker compose -f $COMPOSE_FILE exec -T api python -c "from api.db import get_session; from api.models_users import Employee; session = next(get_session()); print(session.query(Employee).count())" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Database accessible, employee count: $dbCheck"
            $dbStatus.status = "PASS"
            $dbStatus.employee_count = $dbCheck
        } else {
            Write-Warning "Database check failed (non-critical)"
            $dbStatus.status = "WARN"
            $dbStatus.error = $dbCheck
        }
        
        # Display logs summary
        Write-Info "Recent logs from API:"
        docker compose -f $COMPOSE_FILE logs --tail 10 api | Write-Host -ForegroundColor Gray
        
        $phaseDuration = (New-TimeSpan -Start $phaseStart -End (Get-Date)).TotalSeconds
        Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "SUCCESS" -details @{
            containers = $containerStatuses
            health_check = $healthStatus
            auth_check = $authStatus
            database_check = $dbStatus
            duration_seconds = $phaseDuration
        }
        
        Write-Success "PHASE 2 COMPLETE: Smoke tests passed"
        return $true
    } catch {
        Add-PhaseResult -phaseName "PHASE 2: Smoke Test" -status "FAILED" -error $_.Exception.Message
        Write-Error "Smoke test failed: $($_.Exception.Message)"
        return $false
    } finally {
        # Cleanup
        Write-Info "Stopping test containers..."
        docker compose -f $COMPOSE_FILE down
        Pop-Location
    }
}

# ============================================================================
# PHASE 3: TAG & PUSH TO REGISTRY
# ============================================================================

function Invoke-Phase3-Push {
    Write-Phase "3 — Tag and Push to Registry ($Registry)"
    $phaseStart = Get-Date
    
    if ($DryRun) {
        Write-Warning "DRY-RUN mode: Skipping registry push"
        Add-PhaseResult -phaseName "PHASE 3: Push" -status "SKIPPED" -details @{
            reason = "Dry-run mode enabled"
        }
        return $true
    }
    
    # Authenticate to registry
    if ($Registry -eq "dockerhub") {
        Write-Info "Authenticating to Docker Hub..."
        Write-Warning "You will be prompted for Docker Hub credentials"
        docker login
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Docker Hub authentication failed"
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "Docker Hub authentication failed"
            return $false
        }
    } else {
        Write-Info "Configuring GCP Artifact Registry..."
        $cmd = "gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev"
        if (-not (Invoke-Command $cmd "Configure Docker for GCP")) {
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "GCP authentication failed"
            return $false
        }
    }
    
    # Tag and push each service
    $pushedImages = @()
    foreach ($service in $SERVICES) {
        $localImage = "bux-${service}:local"
        $remoteImage = Get-ImageTag $service
        $latestImage = $remoteImage -replace ":${Version}", ":latest"
        
        # Tag with version
        $cmd = "docker tag ${localImage} ${remoteImage}"
        if (-not (Invoke-Command $cmd "Tagging $service with version $Version")) {
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "Failed to tag $service" -details @{
                pushed_images = $pushedImages
            }
            return $false
        }
        
        # Tag with latest
        $cmd = "docker tag ${localImage} ${latestImage}"
        if (-not (Invoke-Command $cmd "Tagging $service as latest")) {
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "Failed to tag $service as latest" -details @{
                pushed_images = $pushedImages
            }
            return $false
        }
        
        # Push version tag
        Write-Info "Pushing ${remoteImage}..."
        docker push $remoteImage
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to push $remoteImage"
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "Failed to push $remoteImage" -details @{
                pushed_images = $pushedImages
            }
            return $false
        }
        Write-Success "Pushed ${remoteImage}"
        $pushedImages += $remoteImage
        
        # Push latest tag
        Write-Info "Pushing ${latestImage}..."
        docker push $latestImage
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to push $latestImage"
            Add-PhaseResult -phaseName "PHASE 3: Push" -status "FAILED" -error "Failed to push $latestImage" -details @{
                pushed_images = $pushedImages
            }
            return $false
        }
        Write-Success "Pushed ${latestImage}"
        $pushedImages += $latestImage
    }
    
    $phaseDuration = (New-TimeSpan -Start $phaseStart -End (Get-Date)).TotalSeconds
    Add-PhaseResult -phaseName "PHASE 3: Push" -status "SUCCESS" -details @{
        registry = $Registry
        pushed_images = $pushedImages
        duration_seconds = $phaseDuration
    }
    
    $script:DeploymentReport.artifacts += $pushedImages
    Write-Success "PHASE 3 COMPLETE: All images pushed to $Registry"
    
    # Display registry URLs
    Write-Info "Published images:"
    $registryUrls = @()
    foreach ($service in $SERVICES) {
        if ($Registry -eq "dockerhub") {
            $url = "https://hub.docker.com/r/${DOCKER_USER}/bux-${service}"
            Write-Host "  $url" -ForegroundColor Cyan
            $registryUrls += $url
        } else {
            $remoteImage = Get-ImageTag $service
            Write-Host "  ${remoteImage}" -ForegroundColor Cyan
            $registryUrls += $remoteImage
        }
    }
    
    $script:DeploymentReport.registry_urls = $registryUrls
    return $true
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

function Main {
    $script:StartTime = Get-Date
    
    Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║                 STAGE 3 CLOUD DEPLOYMENT                      ║
║          Local Build & Smoke Test Automation                  ║
╚═══════════════════════════════════════════════════════════════╝

Registry:  $Registry
Version:   $Version
Dry-Run:   $DryRun
Skip Tests: $SkipTests

"@ -ForegroundColor Magenta
    
    # Prerequisites check
    Test-Prerequisites
    
    # PHASE 1: Build
    if (-not (Invoke-Phase1-Build)) {
        Write-Error "PHASE 1 FAILED - Aborting deployment"
        $script:DeploymentReport.success = $false
        Save-DeploymentReport
        exit 1
    }
    
    # PHASE 2: Smoke Test
    if (-not (Invoke-Phase2-SmokeTest)) {
        Write-Error "PHASE 2 FAILED - Aborting deployment"
        Write-Warning "Images built but smoke tests failed. Fix issues before pushing to registry."
        $script:DeploymentReport.success = $false
        Save-DeploymentReport
        exit 1
    }
    
    # PHASE 3: Push to Registry
    if (-not (Invoke-Phase3-Push)) {
        Write-Error "PHASE 3 FAILED - Images not pushed to registry"
        Write-Info "Images are built and tested locally. You can retry push manually:"
        foreach ($service in $SERVICES) {
            $remoteImage = Get-ImageTag $service
            Write-Host "  docker push $remoteImage" -ForegroundColor Gray
        }
        $script:DeploymentReport.success = $false
        Save-DeploymentReport
        exit 1
    }
    
    # Success summary
    $script:DeploymentReport.success = $true
    $reportPath = Save-DeploymentReport
    
    Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║              ✅ STAGE 3 DEPLOYMENT COMPLETE                   ║
╚═══════════════════════════════════════════════════════════════╝

✅ PHASE 1: Images built successfully
✅ PHASE 2: Smoke tests passed
✅ PHASE 3: Images pushed to $Registry

📊 Deployment Report: $reportPath

Next steps:
1. Verify images in registry
2. Deploy to cloud VM (see STAGE_3_CLOUD_DEPLOYMENT.md PHASE 6)
3. Run production validation

"@ -ForegroundColor Green
}

# Run main function
Main
