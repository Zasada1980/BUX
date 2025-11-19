# GitHub Actions Deployment Setup

## Required GitHub Secrets

Navigate to: `Settings → Secrets and variables → Actions → New repository secret`

Add the following secrets:

### 1. DOCKERHUB_USERNAME
```
zasada1980
```

### 2. DOCKERHUB_TOKEN
Create Docker Hub access token:
1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Name: `github-actions-bux`
4. Permissions: `Read & Write`
5. Copy token and paste here

### 3. SSH_KEY_PRIVATE
Copy your private SSH key:

**Windows PowerShell:**
```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519 | Set-Clipboard
```

**Linux/macOS:**
```bash
cat ~/.ssh/id_ed25519 | pbcopy  # macOS
cat ~/.ssh/id_ed25519 | xclip   # Linux
```

Then paste the **entire content** (including `-----BEGIN` and `-----END` lines) into the secret.

---

## Server Setup

SSH into Hetzner server and prepare deployment directory:

```bash
ssh root@46.224.36.109

# Create scripts directory
mkdir -p /opt/bux/scripts

# Copy deployment scripts (will be done by GitHub Actions)
# Or manually:
cd /opt/bux/scripts
wget https://raw.githubusercontent.com/Zasada1980/BUX/master/scripts/deploy_cloud.sh
wget https://raw.githubusercontent.com/Zasada1980/BUX/master/scripts/check_health.sh
chmod +x *.sh
```

---

## Workflow Triggers

### Automatic Deployment
Push to `master` branch:
```bash
git add .
git commit -m "Deploy v2.0.X"
git push origin master
```

This will:
1. Trigger `ci_build.yml` (build & push images)
2. On success, trigger `cd_deploy.yml` (deploy to Hetzner)

### Manual Deployment via VS Code
Press `Ctrl+Shift+P` → `Tasks: Run Task` → `Trigger GitHub Actions Deploy`

Or via command line:
```bash
gh workflow run cd_deploy.yml --ref master
```

---

## Monitoring Deployment

### GitHub Actions UI
https://github.com/Zasada1980/BUX/actions

### VS Code Terminal
Use tasks from `.vscode/tasks.json`:
- `Check Cloud Deployment Status`
- `View Cloud Deployment Report`
- `Tail Cloud API Logs`

### Server Logs
```bash
ssh root@46.224.36.109
cd /opt/bux
tail -f deployment_auto_*.json
docker-compose logs -f api
```

---

## Rollback Procedure

### Automatic Rollback
If health check fails after deployment, CD workflow automatically rolls back to previous version.

### Manual Rollback
```bash
ssh root@46.224.36.109
cd /opt/bux
./deploy_cloud.sh --rollback
```

Or via VS Code Task: `Deploy Cloud (Manual)` → edit args to `--rollback`

---

## Health Monitoring

### Manual Check
```bash
ssh root@46.224.36.109
/opt/bux/scripts/check_health.sh
```

### Automated Cron (Daily 3 AM)
```bash
ssh root@46.224.36.109
crontab -e
```

Add:
```cron
0 3 * * * /opt/bux/scripts/check_health.sh || /opt/bux/scripts/deploy_cloud.sh --rollback
```

---

## Troubleshooting

### Build fails
- Check Docker Hub credentials in GitHub Secrets
- Verify Dockerfile paths (api/Dockerfile, bot/Dockerfile, agent/Dockerfile)

### Deploy fails
- Verify SSH key in GitHub Secrets (must be private key, not public)
- Check server accessibility: `ssh root@46.224.36.109`
- Check disk space: `df -h /`

### Health check fails
- Verify API is running: `docker logs bux_api`
- Check health endpoint: `curl http://46.224.36.109:8088/health`
- Review deployment logs: `cat /opt/bux/deployment_auto_*.json`

---

## Success Criteria

✅ Workflows are enabled in GitHub Actions  
✅ All 3 secrets configured  
✅ Push to `master` triggers automatic build  
✅ Build success triggers automatic deploy  
✅ Health check passes after deploy  
✅ Deployment report created on server  
✅ Rollback works on failure  

---

**Next Steps:** Push a test commit to `master` and watch the magic happen! 🚀
