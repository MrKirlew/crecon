# Production Deployment Guide

Complete step-by-step guide for deploying the AI Executive Assistant to a production VPS.

## Prerequisites Checklist

- [ ] VPS with 4GB RAM, 2 vCPUs minimum
- [ ] Ubuntu 22.04 LTS or similar Linux distribution
- [ ] Domain name with DNS configured
- [ ] SSH access to VPS
- [ ] Google Cloud Platform account (for OAuth)
- [ ] OpenAI API key (or Anthropic/Google)

## Step 1: VPS Setup

### Recommended Providers

| Provider | Tier | Cost/Month | Notes |
|----------|------|------------|-------|
| DigitalOcean | Basic Droplet (4GB) | $24 | Easy setup, good docs |
| Hetzner | CX31 | €8.46 (~$9) | Best value |
| Linode | Shared 4GB | $24 | Reliable |
| Vultr | Cloud Compute 4GB | $24 | Global locations |

### Initial Server Configuration

```bash
# SSH into your VPS
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y curl git ufw

# Configure firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Create non-root user
adduser deploy
usermod -aG sudo deploy
su - deploy
```

## Step 2: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

## Step 3: Clone and Configure Repository

```bash
# Clone repository
cd /home/deploy
git clone https://github.com/yourusername/ai-executive-assistant.git
cd ai-executive-assistant

# Create .env from template
cp .env.example .env

# Generate secrets
openssl rand -hex 32  # Use for N8N_WEBHOOK_SECRET
openssl rand -hex 32  # Use for POSTGRES_PASSWORD
openssl rand -hex 32  # Use for N8N_BASIC_AUTH_PASSWORD

# Edit .env with your editor
nano .env
```

### Required .env Configuration

```bash
# PostgreSQL
POSTGRES_PASSWORD=<generated-secret-1>
POSTGRES_NON_ROOT_PASSWORD=<generated-secret-1>

# N8N
N8N_HOST=your-domain.com
N8N_PROTOCOL=https
WEBHOOK_URL=https://your-domain.com/webhook
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<generated-secret-2>
N8N_WEBHOOK_SECRET=<generated-secret-3>

# LLM API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...  # Optional
GOOGLE_API_KEY=...  # Optional

# Model Configuration
DEFAULT_LLM_MODEL=gpt-4o-mini
PREMIUM_LLM_MODEL=gpt-4

# Token Budget
MAX_TOKENS_PER_REQUEST=8000
TOKEN_BUDGET_WARNING_THRESHOLD=6000
```

## Step 4: DNS Configuration

Configure your domain's DNS records:

```
Type: A
Name: @
Value: <your-vps-ip>
TTL: 300

Type: A
Name: www
Value: <your-vps-ip>
TTL: 300
```

Wait for DNS propagation (5-30 minutes). Verify:

```bash
dig your-domain.com +short
# Should return your VPS IP
```

## Step 5: SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install -y certbot

# Stop any services using port 80
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop nginx 2>/dev/null || true

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Copy certificates to project
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
sudo chown -R deploy:deploy nginx/ssl
chmod 644 nginx/ssl/*.pem

# Set up auto-renewal
sudo crontab -e
# Add this line:
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/*.pem /home/deploy/ai-executive-assistant/nginx/ssl/ && docker-compose -f /home/deploy/ai-executive-assistant/docker-compose.yml exec nginx nginx -s reload
```

## Step 6: Deploy Application

```bash
# Navigate to project directory
cd /home/deploy/ai-executive-assistant

# Run deployment script
./scripts/deploy.sh

# Or manually:
docker-compose pull
docker-compose build
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

Expected output:
```
NAME                      STATUS          PORTS
ai_assistant_fastapi      Up 2 minutes    8000/tcp
ai_assistant_n8n          Up 2 minutes    5678/tcp
ai_assistant_nginx        Up 2 minutes    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
ai_assistant_postgres     Up 2 minutes    5432/tcp
ai_assistant_qdrant       Up 2 minutes    6333-6334/tcp
```

## Step 7: Verify Deployment

```bash
# Test health endpoint
curl https://your-domain.com/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-01-15T12:00:00Z",
  "services": {
    "fastapi": true,
    "qdrant": true,
    "n8n": true
  },
  "version": "1.0.0"
}

# Test PWA
curl -I https://your-domain.com

# Should return:
HTTP/2 200
content-type: text/html
...
```

## Step 8: Configure Google OAuth

### 8.1 Google Cloud Console Setup

1. Go to https://console.cloud.google.com
2. Create new project: "AI Executive Assistant"
3. Enable APIs (search and enable each):
   - Google Calendar API
   - Gmail API
   - Google Sheets API
   - Google People API (Contacts)
   - Google Drive API

### 8.2 Create OAuth Credentials

1. Navigate to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Configure OAuth consent screen (if first time):
   - User Type: Internal (for Google Workspace) or External
   - App name: "AI Executive Assistant"
   - User support email: your email
   - Authorized domains: your-domain.com
   - Scopes: Add all required scopes (see below)

4. Create OAuth Client:
   - Application type: Web application
   - Name: "AI Assistant Production"
   - Authorized JavaScript origins:
     ```
     https://your-domain.com
     ```
   - Authorized redirect URIs:
     ```
     https://your-domain.com/rest/oauth2-credential/callback
     ```

5. Click "Create" and copy:
   - Client ID
   - Client Secret

### 8.3 Required OAuth Scopes

Add these scopes in the OAuth consent screen:

```
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/contacts
https://www.googleapis.com/auth/contacts.readonly
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.file
```

### 8.4 Configure N8N Credentials

**Option 1: Via N8N UI** (if exposed):

1. Access N8N: `https://your-domain.com/n8n` (if nginx config enables it)
2. Login with basic auth credentials from `.env`
3. Go to "Credentials" → "Add Credential"
4. Select "Google OAuth2 API"
5. Enter:
   - Client ID: [from Google Cloud Console]
   - Client Secret: [from Google Cloud Console]
6. Click "Connect my account"
7. Authorize all scopes

**Option 2: Via Environment Variables**:

Add to `.env`:
```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=https://your-domain.com/rest/oauth2-credential/callback
```

Restart N8N:
```bash
docker-compose restart n8n
```

## Step 9: Import N8N Workflows

```bash
# Copy workflow templates
cp n8n/workflows/templates/*.json n8n/workflows/

# Restart N8N to detect new workflows
docker-compose restart n8n
```

Manual import via N8N UI:
1. Access N8N UI
2. Click "Workflows" → "Import from File"
3. Select each workflow JSON
4. Configure credentials in each workflow
5. Activate workflows

## Step 10: Index Knowledge Base

### Create Initial Index

```bash
# Example: Index executive documents
curl -X POST https://your-domain.com/api/rag/index \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "company-overview",
    "text": "Our company was founded in 2020... [full text]",
    "metadata": {
      "source": "internal-docs",
      "type": "company-info",
      "date": "2025-01-15"
    }
  }'
```

### Batch Indexing

Create a script to index multiple documents:

```bash
#!/bin/bash

API_URL="https://your-domain.com/api/rag/index/batch"

curl -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "document_id": "doc1",
        "text": "Content of document 1...",
        "metadata": {"source": "gmail", "type": "email"}
      },
      {
        "document_id": "doc2",
        "text": "Content of document 2...",
        "metadata": {"source": "drive", "type": "report"}
      }
    ]
  }'
```

### Sync with Google Drive

Create N8N workflow to automatically index new documents:
1. Trigger: Google Drive - On file upload
2. Google Drive - Download file
3. HTTP Request - POST to `/api/rag/index`

## Step 11: Production Optimizations

### Enable Caching (Redis)

```bash
# Update .env
ENABLE_CACHE=true

# Start Redis
docker-compose --profile cache up -d redis

# Verify
docker-compose ps redis
```

### Enable Observability (Langfuse)

```bash
# Update .env
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Or self-hosted:
docker-compose --profile observability up -d langfuse

# Access: https://your-domain.com:3000
```

### Configure Automated Backups

```bash
# Create backup cron job
crontab -e

# Add daily backup at 2 AM
0 2 * * * /home/deploy/ai-executive-assistant/scripts/backup.sh >> /home/deploy/backups.log 2>&1

# Test backup
./scripts/backup.sh
```

### Resource Monitoring

```bash
# Monitor Docker stats
docker stats

# Check disk usage
df -h
docker system df

# Clean up unused resources
docker system prune -a --volumes
```

## Step 12: Testing

### Test Chat Interface

1. Open browser: `https://your-domain.com`
2. Should see PWA install prompt
3. Send test message: "Hello, what can you do?"
4. Verify response from AI
5. Check token usage displayed

### Test RAG

```bash
# Search indexed documents
curl -X POST https://your-domain.com/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "company overview",
    "top_k": 3
  }'
```

### Test N8N Integration

```bash
# Create calendar event
curl -X POST https://your-domain.com/api/workflows/calendar/event \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Meeting",
    "start_time": "2025-01-20T14:00:00Z",
    "end_time": "2025-01-20T15:00:00Z",
    "attendees": ["test@example.com"],
    "description": "Testing N8N integration"
  }'
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Restart specific service
docker-compose restart <service-name>

# Rebuild and restart
docker-compose up -d --build <service-name>
```

### 502 Bad Gateway

Usually means FastAPI isn't responding:

```bash
# Check FastAPI logs
docker-compose logs fastapi

# Restart FastAPI
docker-compose restart fastapi
```

### SSL Certificate Issues

```bash
# Verify certificate files exist
ls -la nginx/ssl/

# Check certificate validity
openssl x509 -in nginx/ssl/cert.pem -text -noout

# Reload nginx
docker-compose exec nginx nginx -s reload
```

### N8N Workflows Not Triggering

1. Verify webhook secret matches in `.env` and N8N
2. Check N8N logs: `docker-compose logs n8n`
3. Test webhook directly: See N8N workflows README

## Maintenance

### Update Application

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### Rotate Secrets

```bash
# Generate new secrets
openssl rand -hex 32

# Update .env
nano .env

# Update N8N webhook nodes
# Restart services
docker-compose restart
```

### Scale Resources

If experiencing performance issues:

```bash
# Increase Docker memory limit
# Edit /etc/docker/daemon.json:
{
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  }
}

# Restart Docker
sudo systemctl restart docker
docker-compose up -d
```

Or upgrade VPS tier to 8GB RAM.

## Security Checklist

- [ ] Strong passwords in `.env` (16+ characters)
- [ ] Firewall configured (UFW)
- [ ] SSL certificates installed and auto-renewing
- [ ] N8N webhook secret is strong and secret
- [ ] Google OAuth scopes are minimal required
- [ ] Regular backups configured
- [ ] Logs monitored for errors
- [ ] System updates applied monthly
- [ ] `.env` file not committed to git

## Monitoring URLs

- PWA: `https://your-domain.com`
- Health: `https://your-domain.com/health`
- API Docs: `https://your-domain.com/api/docs`
- N8N UI: `http://your-domain.com:5678` (if enabled)
- Langfuse: `http://your-domain.com:3000` (if enabled)

## Support

- GitHub Issues: [repository URL]
- Documentation: `/README.md`, `/n8n/workflows/README.md`
- FastAPI Docs: `https://your-domain.com/api/docs`

---

**Deployment Complete!** Your AI Executive Assistant is now running in production.
