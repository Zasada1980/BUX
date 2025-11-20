# Stage 5 CI/CD Setup Guide

## 📋 Prerequisites

1. **GitHub Account** with repository access
2. **Docker Hub Account** (zasada1980)
3. **SSH Access** to Hetzner server (46.224.36.109)
4. **GitHub CLI** installed locally (optional, for VS Code tasks)

---

## 🔐 Step 1: Configure GitHub Secrets

Navigate to your GitHub repository:
```
Settings → Secrets and variables → Actions → New repository secret
```

Add the following secrets:

### DOCKERHUB_USERNAME
```
zasada1980
```

### DOCKERHUB_TOKEN
1. Login to Docker Hub: https://hub.docker.com/
2. Go to Account Settings → Security → New Access Token
3. Name: `github-actions-bux`
4. Permissions: Read, Write, Delete
5. Copy the generated token
6. Paste into GitHub secret value

### SSH_KEY_PRIVATE
1. On your local machine, copy SSH private key:
   ```powershell
   Get-Content $env:USERPROFILE\.ssh\id_ed25519 | Set-Clipboard
   ```
2. Paste into GitHub secret value
3. **⚠️ CRITICAL:** Make sure to copy the ENTIRE key including:
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   ...
   -----END OPENSSH PRIVATE KEY-----
   ```

### HETZNER_HOST
```
46.224.36.109
```

---

## 📦 Step 2: Deploy Scripts to Server

Copy deployment scripts to Hetzner server:

```powershell
# From D:\TelegramOllama_ENV_DEMO\code

# Upload deployment scripts
scp -i $env:USERPROFILE\.ssh\id_ed25519 `
    scripts/deploy_cloud.sh `
    scripts/check_health.sh `
    scripts/rollback.sh `
    root@46.224.36.109:/opt/bux/scripts/

# Make scripts executable
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 `
    "chmod +x /opt/bux/scripts/*.sh"
```

**Verify:**
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 `
    "ls -lh /opt/bux/scripts/"
```

Expected output:
```
-rwxr-xr-x 1 root root 5.2K Nov 19 14:00 check_health.sh
-rwxr-xr-x 1 root root 7.8K Nov 19 14:00 deploy_cloud.sh
-rwxr-xr-x 1 root root 4.1K Nov 19 14:00 rollback.sh
```

---

## 🚀 Step 3: Enable GitHub Actions Workflows

Workflows are automatically enabled when `.github/workflows/*.yml` files are present in the repository.

**Verify workflows:**
1. Go to repository → Actions tab
2. You should see:
   - ✅ **CI - Build and Push Docker Images**
   - ✅ **CD - Deploy to Hetzner Cloud**

---

## 🧪 Step 4: Test CI/CD Pipeline

### Option A: Trigger via GitHub UI

1. Go to **Actions** tab
2. Select **CI - Build and Push Docker Images**
3. Click **Run workflow** → Select `master` branch → **Run workflow**
4. Wait for build to complete (~5-10 minutes)
5. Once CI completes, **CD - Deploy to Hetzner Cloud** will trigger automatically

### Option B: Trigger via Git Commit

```powershell
cd D:\TelegramOllama_ENV_DEMO\code

# Make a small change (e.g., update README)
echo "# Test CI/CD" >> README.md

git add README.md
git commit -m "test: trigger CI/CD pipeline"
git push origin master
```

**Watch progress:**
```powershell
# If you have GitHub CLI installed
gh run watch
```

Or open browser: https://github.com/Zasada1980/BUX/actions

---

## 📊 Step 5: Monitor Deployment

### Via GitHub Actions UI
1. Go to Actions tab
2. Click on running workflow
3. Watch real-time logs for each step

### Via VS Code Tasks
Press `Ctrl+Shift+P` → **Tasks: Run Task** → Select:

- **Watch GitHub Actions Run** — Real-time workflow monitoring
- **Check Cloud Deployment Status** — Container status + health
- **View Cloud Deployment Report** — Latest deployment JSON

### Via SSH (Manual)
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 @'
cd /opt/bux
cat cloud_deployment_*.json | tail -1 | jq .
docker-compose -f docker-compose.cloud.yml ps
curl -s http://localhost:8088/health | jq .
'@
```

---

## ✅ Step 6: Verify Success Criteria

| # | Criterion | Verification Command | Expected Result |
|---|-----------|---------------------|-----------------|
| 1 | **CI builds images** | Check GitHub Actions logs | 3 images pushed (api, bot, agent) |
| 2 | **Docker Hub updated** | `docker pull zasada1980/bux-api:latest` | Latest image downloaded |
| 3 | **CD deploys to Hetzner** | `ssh root@46.224.36.109 "docker ps"` | All 4 containers running |
| 4 | **Health endpoint OK** | `curl http://46.224.36.109:8088/health` | `{"ok": true}` |
| 5 | **JSON report created** | `ssh root@46.224.36.109 "ls /opt/bux/cloud_deployment_*.json"` | Recent timestamp file |

**All green?** ✅ Stage 5 CI/CD setup complete!

---

## 🔧 Troubleshooting

### Build Fails: "Login to Docker Hub failed"
**Solution:** Check `DOCKERHUB_TOKEN` secret is valid:
1. Regenerate token in Docker Hub
2. Update GitHub secret with new value

### Deploy Fails: "Permission denied (publickey)"
**Solution:** Check `SSH_KEY_PRIVATE` secret:
```powershell
# Test SSH key locally
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 "echo OK"
```
If this works, copy the ENTIRE key (including headers/footers) to GitHub secret.

### Health Check Fails After Deploy
**Solution:** Check container logs:
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 `
    "docker logs bux_api --tail=50"
```

Trigger rollback if needed:
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@46.224.36.109 `
    "/opt/bux/scripts/rollback.sh --force"
```

### Workflow Doesn't Trigger on Push
**Solution:** 
1. Check branch name matches workflow (`master` vs `main`)
2. Verify `.github/workflows/` files are in repository root
3. Check Actions are enabled: Settings → Actions → General → Allow all actions

---

## 🎯 Next Steps

### Setup Automated Health Monitoring (Cron)

```bash
ssh root@46.224.36.109

# Add cron job for health checks every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/bux/scripts/check_health.sh --notify") | crontab -

# Add cron job for nightly health check with rollback
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/bux/scripts/check_health.sh --rollback-on-fail") | crontab -

# Verify cron jobs
crontab -l
```

### Setup Slack/Email Notifications (Optional)

Edit `scripts/check_health.sh` and add notification logic in the `NOTIFY` section:

```bash
if [ "$NOTIFY" = true ]; then
    # Slack webhook
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
        -H 'Content-Type: application/json' \
        -d '{"text": "⚠️ BUX Health Check Failed!"}'
    
    # Or email via mail command
    echo "Health check failed at $(date)" | mail -s "BUX Alert" admin@example.com
fi
```

### Configure HTTPS (Let's Encrypt)

See `F16_STAGE_4_DEPLOYMENT_PLAN.md` → PHASE 7 for nginx + certbot setup.

---

## 📚 Documentation References

- **F15** — Stage 3 Completion Report (local build/push)
- **F16** — Stage 4 Deployment Plan (cloud deployment blueprint)
- **F17** — Hetzner Deployment Guide (manual deployment steps)
- **F18** — Cloud Deployment Execution Report (first deployment log)
- **Stage 5** — This guide (CI/CD automation)

---

## 🆘 Support

**Questions?** Check existing deployment reports in `d:\TelegramOllama_docs\reports\`

**Issues?** Create GitHub Issue with:
- Workflow run ID
- Error logs
- Output of `docker-compose ps`
- Health check response
