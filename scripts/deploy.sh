#!/bin/bash

# AI Executive Assistant - Deployment Script
# Automates the deployment process with safety checks

set -e  # Exit on error

echo "========================================"
echo "AI Executive Assistant - Deployment"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Error: Do not run this script as root${NC}"
    exit 1
fi

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check Docker Compose installation
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo -e "${RED}CRITICAL: Edit .env file with your configuration before proceeding!${NC}"
    exit 1
fi

# Verify critical environment variables
echo "Checking environment configuration..."

check_env_var() {
    local var_name=$1
    local var_value=$(grep "^${var_name}=" .env | cut -d'=' -f2)

    if [ -z "$var_value" ] || [[ "$var_value" == *"CHANGE_ME"* ]]; then
        echo -e "${RED}Error: ${var_name} not configured in .env${NC}"
        return 1
    fi
    return 0
}

REQUIRED_VARS=(
    "POSTGRES_PASSWORD"
    "N8N_WEBHOOK_SECRET"
    "N8N_BASIC_AUTH_PASSWORD"
    "OPENAI_API_KEY"
)

ERRORS=0
for var in "${REQUIRED_VARS[@]}"; do
    if ! check_env_var "$var"; then
        ERRORS=$((ERRORS + 1))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Configuration errors found. Please fix .env file.${NC}"
    exit 1
fi

echo -e "${GREEN}Environment configuration OK${NC}"

# Check SSL certificates
echo "Checking SSL certificates..."
if [ ! -f nginx/ssl/cert.pem ] || [ ! -f nginx/ssl/key.pem ]; then
    echo -e "${YELLOW}Warning: SSL certificates not found${NC}"
    read -p "Generate self-signed certificate for development? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p nginx/ssl
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/CN=localhost"
        chmod 644 nginx/ssl/*.pem
        echo -e "${GREEN}Self-signed certificate generated${NC}"
    else
        echo -e "${RED}SSL certificates required. Exiting.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}SSL certificates found${NC}"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p nginx/ssl
mkdir -p n8n/workflows
mkdir -p backend
mkdir -p frontend/dist/assets

# Pull latest images
echo "Pulling Docker images..."
docker-compose pull

# Build custom images
echo "Building custom images..."
docker-compose build

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to start..."
sleep 10

# Check service health
echo "Checking service health..."
HEALTH_CHECK_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $HEALTH_CHECK_RETRIES ]; do
    if docker-compose ps | grep -q "Up"; then
        echo -e "${GREEN}Services are running${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for services... ($RETRY_COUNT/$HEALTH_CHECK_RETRIES)"
    sleep 5
done

if [ $RETRY_COUNT -eq $HEALTH_CHECK_RETRIES ]; then
    echo -e "${RED}Services failed to start. Check logs with: docker-compose logs${NC}"
    exit 1
fi

# Display service status
echo ""
echo "========================================"
echo "Deployment Status"
echo "========================================"
docker-compose ps

echo ""
echo "========================================"
echo "Service URLs"
echo "========================================"
echo "PWA Frontend: https://localhost (or your domain)"
echo "API Docs: https://localhost/api/docs"
echo "Health Check: https://localhost/health"
echo ""
echo "N8N UI: http://localhost:5678 (if enabled)"
echo "Langfuse: http://localhost:3000 (if using --profile observability)"
echo ""

echo "========================================"
echo "Next Steps"
echo "========================================"
echo "1. Configure Google OAuth credentials in N8N"
echo "2. Import workflow templates from /n8n/workflows/"
echo "3. Index your knowledge base via /api/rag/index"
echo "4. Test the system via the PWA interface"
echo ""
echo "View logs: docker-compose logs -f"
echo "Stop services: docker-compose down"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
