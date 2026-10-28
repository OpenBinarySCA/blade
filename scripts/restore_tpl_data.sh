#!/bin/bash
# =============================================================================
# TPL Database Restore Script
# Restores backup file to PostgreSQL container
#
# Usage:
#   ./restore_tpl_data.sh --prod <backup_file>   # For production container
#   ./restore_tpl_data.sh --debug <backup_file>  # For debug container
#   ./restore_tpl_data.sh <backup_file>          # Auto-detect running container
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Database config
DB_USER="tpl_data"
DB_PASSWORD="tpl_data"
DB_NAME="tpl_data"

# =============================================================================
# Functions
# =============================================================================

print_header() {
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

show_usage() {
    echo "Usage:"
    echo "  $0 --prod <backup_file>   # Restore to production container"
    echo "  $0 --debug <backup_file>  # Restore to debug container"
    echo "  $0 <backup_file>          # Auto-detect running container"
    echo ""
    echo "Examples:"
    echo "  $0 --prod tpl_data_backup_20251102_153000.sql"
    echo "  $0 --debug /path/to/backup.sql"
    echo "  $0 backup.sql"
}

check_docker_container() {
    local container_name="$1"
    if ! docker ps --filter "name=$container_name" --format "{{.Names}}" | grep -q "^${container_name}$"; then
        return 1
    fi
    return 0
}

detect_container() {
    if check_docker_container "blade_postgresql_prod"; then
        echo "blade_postgresql_prod"
    elif check_docker_container "blade_postgresql_debug"; then
        echo "blade_postgresql_debug"
    else
        echo ""
    fi
}

validate_backup_file() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi

    if [[ "$backup_file" != *.sql ]]; then
        print_warning "Warning: File is not .sql format"
    fi

    return 0
}

check_database_exists() {
    local container_name="$1"
    local table_count=$(docker exec -i "$container_name" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

    if [ -n "$table_count" ] && [ "$table_count" -gt 0 ]; then
        return 0
    else
        return 1
    fi
}

restore_database() {
    local container_name="$1"
    local backup_file="$2"

    echo ""
    echo "Restoring database..."
    echo "Container: $container_name"
    echo "Backup file: $backup_file"

    local filesize=$(du -h "$backup_file" | cut -f1)
    echo "File size: $filesize"
    echo ""

    # Check if database already has data
    if check_database_exists "$container_name"; then
        local table_count=$(docker exec -i "$container_name" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        print_warning "Database contains $table_count tables"
        echo ""
        print_warning "⚠️  WARNING: This will clear existing data and restore from backup!"
        echo ""

        # First confirmation
        read -p "❗ First confirmation - Clear existing database? (type 'yes' to continue): " confirm1
        if [ "$confirm1" != "yes" ]; then
            echo "Operation cancelled"
            return 1
        fi

        echo ""
        # Second confirmation
        read -p "❗❗ Second confirmation - Data will be permanently deleted, continue? (type 'yes'): " confirm2
        if [ "$confirm2" != "yes" ]; then
            echo "Operation cancelled"
            return 1
        fi

        echo ""
        # Third confirmation
        read -p "❗❗❗ Third confirmation - Last chance, really clear and restore? (type 'yes'): " confirm3
        if [ "$confirm3" != "yes" ]; then
            echo "Operation cancelled"
            return 1
        fi

        echo ""
        print_info "Passed all confirmations, starting restore..."
    else
        print_info "Database is empty, ready to import data"
        print_warning "Warning: This will restore data from backup!"
        read -p "Continue? (type 'yes'): " confirm

        if [ "$confirm" != "yes" ]; then
            echo "Operation cancelled"
            return 1
        fi
    fi

    echo ""
    echo "Restoring database..."

    if docker exec -i "$container_name" psql -U "$DB_USER" -d "$DB_NAME" < "$backup_file" > /dev/null 2>&1; then
        echo ""
        print_success "Database restored successfully!"
        return 0
    else
        echo ""
        print_error "Database restore failed!"
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================

print_header "TPL Database Restore Tool"

# Parse arguments
MODE=""
BACKUP_FILE=""

if [ $# -eq 0 ]; then
    print_error "Error: Missing arguments"
    echo ""
    show_usage
    exit 1
fi

if [ "$1" == "--prod" ]; then
    MODE="prod"
    CONTAINER_NAME="blade_postgresql_prod"
    BACKUP_FILE="$2"
elif [ "$1" == "--debug" ]; then
    MODE="debug"
    CONTAINER_NAME="blade_postgresql_debug"
    BACKUP_FILE="$2"
else
    # Auto-detect mode
    MODE="auto"
    BACKUP_FILE="$1"
    CONTAINER_NAME=$(detect_container)
fi

# Check backup file argument
if [ -z "$BACKUP_FILE" ]; then
    print_error "Error: Missing backup file path"
    echo ""
    show_usage
    exit 1
fi

# Auto-detect container if needed
if [ "$MODE" == "auto" ]; then
    if [ -z "$CONTAINER_NAME" ]; then
        print_error "No running PostgreSQL container found"
        echo "Please start infrastructure first:"
        echo "  Production: ./scripts/deploy_prod_infra.sh"
        echo "  Debug:      ./scripts/deploy_debug_infra.sh"
        exit 1
    fi
    print_info "Auto-detected container: $CONTAINER_NAME"
fi

# Check if container is running
if ! check_docker_container "$CONTAINER_NAME"; then
    print_error "Container '$CONTAINER_NAME' is not running"
    if [ "$MODE" == "prod" ]; then
        echo "Please run: ./scripts/deploy_prod_infra.sh"
    elif [ "$MODE" == "debug" ]; then
        echo "Please run: ./scripts/deploy_debug_infra.sh"
    fi
    exit 1
fi

print_success "Container '$CONTAINER_NAME' is running"

# Validate backup file
validate_backup_file "$BACKUP_FILE"

# Execute restore
if restore_database "$CONTAINER_NAME" "$BACKUP_FILE"; then
    echo ""
    print_header "Restore Complete!"
    exit 0
else
    echo ""
    print_header "Restore Failed!"
    exit 1
fi
