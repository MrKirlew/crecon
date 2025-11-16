# AI Executive Assistant - Containerized PWA Deployment

A fully sovereign, self-hosted AI Executive Assistant platform leveraging Retrieval-Augmented Generation (RAG) and tight Google ecosystem integration (Contacts, Calendar, Gmail, Drive, Sheets, Docs) using Docker-based microservices.

## 🎯 System Overview

### Architecture: 5-Layer Microservice Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    PWA Frontend (React/Vanilla JS)               │
│                      Progressive Web Application                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                 Nginx Reverse Proxy (Edge Layer)                 │
│         TLS Termination │ Static Assets │ API Routing            │
└──────────────┬───────────────────────────────┬──────────────────┘
               │                               │
       ┌───────▼────────┐              ┌──────▼─────────┐
       │  FastAPI Agent │              │  N8N Workflows │
       │  (Intelligence)│◄─────────────┤  (Execution)   │
       │  RAG │ Tokens  │  Webhook     │  Google APIs   │
       └───────┬────────┘  Auth        └────────────────┘
               │
       ┌───────▼────────┐
       │     Qdrant     │
       │   (Knowledge)  │
       │  Vector Store  │
       └────────────────┘
               │
       ┌───────▼────────┐
       │   PostgreSQL   │
       │  (Persistence) │
       └────────────────┘
```

### Core Components

| Service | Role | Port | Technology |
|---------|------|------|------------|
| **Nginx** | Edge/Proxy | 80, 443 | Alpine Linux |
| **FastAPI** | AI Gateway | 8000 | Python 3.11 |
| **N8N** | Automation | 5678 | Node.js |
| **Qdrant** | Vector DB | 6333, 6334 | Rust |
| **PostgreSQL** | Database | 5432 | PostgreSQL 15 |
| **Redis** (Optional) | Cache | 6379 | Redis 7 |
| **Langfuse** (Optional) | Observability | 3000 | Next.js |

## ✨ Intelligent Recording & Media Analysis

- **Silent Recording Pipeline** – New `/api/recordings/silent` endpoint silently captures meetings, transcribes audio (via Gemini), optionally summarizes conversations, then routes transcripts through Gmail or stores them in Drive as either plain text or native Google Docs.
- **Automated Distribution** – Choose per-recording delivery rules: email teams with formatted HTML notes, drop transcripts into Drive folders, and auto-share with collaborators.
- **Multimodal Insight Engine** – `/api/media/analyze` accepts images (screen-shares, whiteboards) or documents (PDF/DOCX/TXT) and runs both Ollama (local vision model configurable via `OLLAMA_VISION_MODEL`) and Gemini in parallel for summaries, data extraction, sentiment, and action items.
- **Document/Text Extraction** – Built-in PDF + DOCX parsing feeds clean text into LLMs before analysis, drastically improving signal quality for long documents.

## 🚀 Quick Start

### Prerequisites

- VPS with **minimum 4GB RAM, 2 vCPUs** (Recommended: DigitalOcean/Hetzner)
- Docker Engine 24.0+ and Docker Compose 2.0+
- Domain name with DNS configured
- SSL/TLS certificate (Let's Encrypt recommended)

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/yourusername/ai-executive-assistant.git
cd ai-executive-assistant

# Copy environment template
cp .env.example .env

# Generate webhook secret
openssl rand -hex 32
# Copy output to .env as N8N_WEBHOOK_SECRET
```

### 2. Configure Environment

Edit `.env` file with your credentials:

```bash
# PostgreSQL
POSTGRES_PASSWORD=<strong-password>
POSTGRES_NON_ROOT_PASSWORD=<strong-password>

# N8N
N8N_HOST=your-domain.com
N8N_WEBHOOK_SECRET=<output-from-openssl-rand-hex-32>
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<strong-password>

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...  # Optional
GOOGLE_API_KEY=...  # Optional

# Model Selection (cost optimization)
DEFAULT_LLM_MODEL=gpt-4o-mini
PREMIUM_LLM_MODEL=gpt-4
```

### 3. SSL Certificate Setup

#### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
sudo chmod 644 nginx/ssl/*.pem
```

#### Option B: Self-Signed (Development Only)

```bash
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/CN=your-domain.com"
```

### 4. Deploy Stack

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
curl https://your-domain.com/health
```

### 5. Configure Google OAuth (N8N)

1. **Google Cloud Console** (https://console.cloud.google.com):
   - Create new project
   - Enable APIs: Calendar, Gmail, Sheets, Contacts, Drive
   - Create OAuth 2.0 credentials (Web application)
   - Redirect URI: `https://your-domain.com/rest/oauth2-credential/callback`

2. **N8N Credentials**:
   - Access N8N UI: `https://your-domain.com/n8n` (if enabled in nginx config)
   - Add "Google OAuth2 API" credential
   - Paste Client ID and Secret
   - Authorize all required scopes

3. **Import Workflows**:
   - See `/n8n/workflows/README.md` for workflow blueprints
   - Import templates via N8N UI

### 6. Index Knowledge Base (RAG)

```bash
# Example: Index a document via API
curl -X POST https://your-domain.com/api/rag/index \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "executive-summary-q1",
    "text": "Q1 2025 Revenue: $2.5M...",
    "metadata": {
      "source": "google-drive",
      "type": "financial-report",
      "date": "2025-01-15"
    }
  }'
```

## 📊 Cost Analysis & TCO

### Infrastructure Costs (Monthly)

| Component | Tier | Monthly Cost |
|-----------|------|--------------|
| VPS (4GB/2vCPU) | Shared | $10-12 |
| Managed PostgreSQL | Optional | $10-25 |
| Domain + DNS | - | $1-2 |
| **Base Infrastructure** | | **$11-39** |

### Variable Costs: LLM API Usage

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Use Case |
|-------|----------------------|------------------------|----------|
| **GPT-4o Mini** | $0.60 | $2.40 | **Default** (Routine tasks) |
| **Gemini 2.5 Flash** | $0.15 | $0.60 | High-volume, low-complexity |
| **GPT-4** | $1.25 | $10.00 | Complex reasoning only |

### Projected Monthly OPEX

| Usage Tier | Token Volume | LLM Cost | Total OPEX |
|------------|--------------|----------|------------|
| Light (Test) | 10M tokens | $5 | **$16-44** |
| Moderate (Executive) | 50M tokens | $25 | **$36-64** |
| Heavy (Automation) | 240M tokens | $120 | **$131-159** |

**Key Insight**: Self-hosting becomes cost-effective at **>50,000 workflows/month** compared to managed services.

### Cost Optimization Strategies

1. **Model Routing**: Use GPT-4o-mini by default, GPT-4 only for complex tasks
2. **RAG Caching**: Cache frequent queries via Redis
3. **Token Budget Limits**: Pre-flight checks prevent runaway costs
4. **Batch Processing**: Group multiple operations in single API call

## 🏗️ Development Guide

### Project Structure

```
.
├── docker-compose.yml          # Orchestration
├── .env.example                # Environment template
├── backend/                    # FastAPI AI Agent
│   ├── Dockerfile
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings management
│   ├── token_counter.py        # Cost control
│   ├── rag_service.py          # Qdrant integration
│   ├── n8n_bridge.py           # Workflow execution
│   ├── models.py               # Pydantic schemas
│   └── requirements.txt
├── frontend/                   # PWA
│   └── dist/
│       ├── index.html
│       ├── manifest.webmanifest
│       ├── sw.js               # Service worker
│       └── assets/
│           └── app.js
├── nginx/                      # Reverse proxy
│   ├── nginx.conf
│   └── conf.d/
│       └── ai-assistant.conf
└── n8n/
    └── workflows/              # N8N blueprints
        └── README.md
```

### Local Development

```bash
# Backend development
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend development (if using build tools)
cd frontend
npm install
npm run dev
```

### Adding New LLM Models

Edit `backend/config.py`:

```python
cost_per_1m_input_tokens: dict[str, float] = {
    "gpt-4o-mini": 0.60,
    "your-new-model": 0.50,  # Add pricing
}
```

### Creating Custom Workflows

1. Design workflow in N8N UI
2. Configure webhook trigger with Header Auth
3. Document payload schema in `/n8n/workflows/README.md`
4. Add helper method in `backend/n8n_bridge.py`
5. Test via FastAPI endpoint

## 🔐 Security Best Practices

### Environment Variables

- **Never commit `.env`** to version control
- Use strong passwords (16+ characters, mixed case, symbols)
- Rotate secrets quarterly
- Use different passwords for each service

### Webhook Security

```bash
# Generate strong webhook secret
openssl rand -hex 32

# Must match exactly in:
# 1. N8N Webhook node → Header Value
# 2. .env → N8N_WEBHOOK_SECRET
```

### Network Isolation

- Internal services (Qdrant, PostgreSQL) only accessible via Docker network
- N8N webhooks require secret header (401 if invalid)
- Nginx applies security headers (CSP, HSTS, X-Frame-Options)

### SSL/TLS

- **Production**: Use Let's Encrypt certificates
- **Auto-renewal**: Set up certbot cron job
- **Strong ciphers**: TLS 1.2+ only (configured in nginx.conf)

### Google OAuth Scopes

Only request minimum required scopes:
```
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/contacts.readonly
https://www.googleapis.com/auth/drive.file
```

## 📈 Monitoring & Observability

### Health Checks

```bash
# System health
curl https://your-domain.com/health

# Check individual services
docker-compose ps
docker-compose logs fastapi
docker-compose logs n8n
```

### Langfuse Integration (Optional)

Enable in `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Then start Langfuse container
docker-compose --profile observability up -d
```

Access: `https://your-domain.com:3000` (or configure nginx proxy)

### Metrics to Monitor

1. **Token Usage**: Track daily/monthly spend via Langfuse
2. **Response Latency**: Monitor FastAPI + N8N execution time
3. **RAG Quality**: Score retrieval relevance (Qdrant similarity scores)
4. **Error Rates**: Watch for 401 (auth), 500 (server), timeout errors
5. **Resource Usage**: CPU/RAM via `docker stats`

## 🐛 Troubleshooting

### Common Issues

#### 1. 401 Unauthorized from N8N

**Cause**: Webhook secret mismatch

**Fix**:
```bash
# Verify secrets match
grep N8N_WEBHOOK_SECRET .env
# Check N8N Webhook node → Authentication → Header Value

# Restart services after changing .env
docker-compose restart fastapi n8n
```

#### 2. PWA Not Installing

**Cause**: Service worker caching or missing MIME type

**Fix**:
```bash
# Check nginx logs
docker-compose logs nginx | grep manifest

# Verify MIME type registration in nginx.conf
# Should include: application/manifest+json webmanifest;

# Clear browser cache and try again
```

#### 3. RAG Returns No Results

**Cause**: No documents indexed or threshold too high

**Fix**:
```bash
# Check collection stats
curl https://your-domain.com/api/rag/stats

# Lower similarity threshold (backend/config.py)
rag_score_threshold: float = 0.5  # Lower = more results
```

#### 4. High LLM Costs

**Cause**: Premium model used for all requests or RAG adding too much context

**Fix**:
```python
# Set lower token budget (backend/config.py)
max_tokens_per_request: int = 4000
max_rag_context_tokens: int = 2000

# Enforce model routing
DEFAULT_LLM_MODEL=gpt-4o-mini
```

#### 5. N8N Workflow Timeout

**Cause**: Long-running workflow or nginx timeout

**Fix**:
```nginx
# Increase timeout in nginx/conf.d/ai-assistant.conf
proxy_read_timeout 180s;

# Use async execution in FastAPI
async_execution=True
```

### Logs & Debugging

```bash
# View all logs
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi
docker-compose logs -f n8n

# Check last 100 lines
docker-compose logs --tail=100 nginx

# PostgreSQL query logs
docker-compose exec postgres psql -U n8n -c "SELECT * FROM execution_entity ORDER BY id DESC LIMIT 10;"
```

## 🔄 Updates & Maintenance

### Updating Services

```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build

# Clean up old images
docker image prune -f
```

### Database Backups

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U n8n n8n > backup_$(date +%Y%m%d).sql

# Backup Qdrant
docker-compose exec qdrant tar -czf - /qdrant/storage > qdrant_backup_$(date +%Y%m%d).tar.gz

# Restore
cat backup_20250115.sql | docker-compose exec -T postgres psql -U n8n n8n
```

### SSL Certificate Renewal

```bash
# Renew Let's Encrypt (run monthly)
sudo certbot renew

# Copy new certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem

# Reload nginx
docker-compose exec nginx nginx -s reload
```

## 🚀 Advanced Features

### Redis Caching (Optional)

Enable in `.env`:

```bash
ENABLE_CACHE=true

# Start Redis
docker-compose --profile cache up -d redis
```

Benefits:
- RAG query caching (reduces Qdrant load)
- LLM response caching (reduces API costs)
- Session storage

### Open Source LLM (Ollama)

Replace commercial APIs with self-hosted models:

```bash
# Add to docker-compose.yml
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
```

**Trade-off**: Higher VPS cost (GPU required) vs. zero variable LLM costs

### Multi-User Support

Add authentication layer:

1. Implement JWT auth in FastAPI
2. User-specific Qdrant collections
3. N8N user credential isolation
4. PostgreSQL user table

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [N8N Documentation](https://docs.n8n.io/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Google API Documentation](https://developers.google.com/)
- [PWA Guide](https://web.dev/progressive-web-apps/)

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md

---

**Built with**: FastAPI • N8N • Qdrant • Docker • Nginx • PostgreSQL

**Supported by**: OpenAI • Anthropic • Google Gemini
