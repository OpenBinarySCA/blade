#!/bin/bash
# =============================================================================
# Deploy Debug Infrastructure
# Starts PostgreSQL, Redis, MinIO containers with ports exposed
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/../compose"

echo "============================================================"
echo "Deploying Debug Infrastructure"
echo "============================================================"

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

cd "$COMPOSE_DIR"

echo ""
echo -e "${YELLOW}Starting infrastructure containers...${NC}"
docker compose -f docker-compose-infra-debug.yml up -d

echo ""
echo -e "${GREEN}✓ Debug infrastructure deployed!${NC}"
echo ""
echo "Containers:"
docker compose -f docker-compose-infra-debug.yml ps
echo ""
echo "Exposed Ports:"
echo "  PostgreSQL: localhost:5466"
echo "  Redis:      localhost:6366"
echo "  MinIO API:  localhost:9000"
echo "  MinIO Web:  localhost:9001"
echo ""
echo "Next steps:"
echo "  1. Restore data (if needed): ./scripts/restore_tpl_data.sh --debug <backup_file>"
echo "  2. Start application: ./scripts/start_debug.sh"
