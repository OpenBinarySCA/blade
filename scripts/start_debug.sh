#!/bin/bash
# =============================================================================
# Start Debug Application (Local)
# Starts FastAPI, Celery Worker, and Web frontend locally (no containers)
# Requires: Debug infrastructure running (PostgreSQL, Redis, MinIO)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo "============================================================"
echo "Starting Debug Application (Local)"
echo "============================================================"

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Trap to kill all background processes on exit
trap 'echo -e "\n${RED}Stopping all services...${NC}"; kill $(jobs -p) 2>/dev/null; exit' INT TERM EXIT

echo ""
echo -e "${GREEN}Starting all services...${NC}"
echo ""

# Start API server
echo -e "${BLUE}[1/4] Starting API Server...${NC}"
cd "$PROJECT_ROOT"
python3 start_server.py 2>&1 | sed "s/^/[API] /" &
API_PID=$!

# Give the API server a moment to start
sleep 2

# Start Celery worker
echo -e "${BLUE}[2/4] Starting Celery Worker...${NC}"
cd "$PROJECT_ROOT"
celery -A app.celery_tasks.celery_app worker \
  -Q tpl_detection_tasks,batch_refresh_tasks \
  --loglevel=info \
  --concurrency=4 2>&1 | sed "s/^/[CELERY] /" &
CELERY_PID=$!

# Give Celery a moment to start
sleep 2

# Start frontend
echo -e "${BLUE}[3/4] Starting Frontend...${NC}"
cd "$PROJECT_ROOT/web"
npm run dev 2>&1 | sed "s/^/[WEB] /" &
WEB_PID=$!

# Give frontend a moment to start
sleep 1

# Start admin frontend
echo -e "${BLUE}[4/4] Starting Admin Frontend...${NC}"
cd "$PROJECT_ROOT/admin-web"
npm run dev 2>&1 | sed "s/^/[ADMIN] /" &
ADMIN_PID=$!

echo ""
echo -e "${GREEN}All services started!${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""
echo "Process IDs:"
echo "  API Server:     $API_PID"
echo "  Celery Worker:  $CELERY_PID"
echo "  Frontend:       $WEB_PID"
echo "  Admin Frontend: $ADMIN_PID"
echo ""
echo "URLs:"
echo "  API:   http://localhost:2000"
echo "  Web:   http://localhost:2001"
echo "  Admin: http://localhost:2002"
echo ""

# Wait for all background processes
wait
