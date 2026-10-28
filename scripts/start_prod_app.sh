#!/bin/bash
# =============================================================================
# Start Production Application
# Starts API, Celery, Web, Nginx containers
# Requires: Production infrastructure running (blade-network-prod)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/../compose"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo "============================================================"
echo "Starting Production Application"
echo "============================================================"

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file from compose/.env.production.example"
    exit 1
fi

# Check if network exists
if ! docker network inspect blade-network-prod > /dev/null 2>&1; then
    echo -e "${RED}Error: blade-network-prod not found${NC}"
    echo "Please run ./scripts/deploy_prod_infra.sh first"
    exit 1
fi

cd "$COMPOSE_DIR"

echo ""
echo -e "${YELLOW}Building and starting application containers...${NC}"
docker compose -f docker-compose-app-prod.yml up -d --build

echo ""
echo -e "${GREEN}✓ Production application started!${NC}"
echo ""
echo "Containers:"
docker compose -f docker-compose-app-prod.yml ps
echo ""
echo "Access:"
echo "  Web UI:   http://localhost"
echo "  API Docs: http://localhost/api/docs"
