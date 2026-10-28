#!/bin/bash
# =============================================================================
# TPL 数据库备份脚本
#
# 使用方法:
#   ./backup_tpl_data.sh -c <容器名> [选项] [保存路径]
#
# 选项:
#   -c, --container  指定 PostgreSQL 容器名称 (必需)
#   --all            备份全部数据 (默认)
#   --tpl-only       只备份 TPL 数据 (public schema)
#   --user-only      只备份用户数据 (user_data schema)
#
# 示例:
#   ./backup_tpl_data.sh -c blade_postgresql_debug
#   ./backup_tpl_data.sh -c blade_postgresql_new --tpl-only
#   ./backup_tpl_data.sh -c blade_postgresql_prod --tpl-only ~/backup.sql
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 数据库配置
DB_USER="tpl_data"
DB_NAME="tpl_data"

# 默认值
CONTAINER_NAME=""
BACKUP_MODE="all"
BACKUP_FILE=""

# =============================================================================
# 函数定义
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

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

show_usage() {
    echo "Usage: $0 -c <container_name> [options] [save_path]"
    echo ""
    echo "Options:"
    echo "  -c, --container  PostgreSQL container name (required)"
    echo "  --all            Backup all data (default)"
    echo "  --tpl-only       Backup only TPL data (public schema)"
    echo "  --user-only      Backup only user data (user_data schema)"
    echo ""
    echo "Examples:"
    echo "  $0 -c blade_postgresql_debug"
    echo "  $0 -c blade_postgresql_new --tpl-only"
    echo "  $0 -c blade_postgresql_prod --tpl-only ~/backup.sql"
}

check_docker_container() {
    if ! docker ps --filter "name=^${1}$" --format "{{.Names}}" | grep -q "^${1}$"; then
        return 1
    fi
    return 0
}

# =============================================================================
# 参数解析
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --all)
            BACKUP_MODE="all"
            shift
            ;;
        --tpl-only)
            BACKUP_MODE="tpl-only"
            shift
            ;;
        --user-only)
            BACKUP_MODE="user-only"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# 检查必需参数
if [ -z "$CONTAINER_NAME" ]; then
    print_error "Error: Container name is required"
    echo ""
    show_usage
    exit 1
fi

# 生成备份文件名
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
if [ -z "$BACKUP_FILE" ]; then
    case $BACKUP_MODE in
        "all")      BACKUP_FILE="$(pwd)/tpl_data_backup_all_${TIMESTAMP}.sql" ;;
        "tpl-only") BACKUP_FILE="$(pwd)/tpl_data_backup_tpl_${TIMESTAMP}.sql" ;;
        "user-only") BACKUP_FILE="$(pwd)/tpl_data_backup_user_${TIMESTAMP}.sql" ;;
    esac
elif [ -d "$BACKUP_FILE" ]; then
    case $BACKUP_MODE in
        "all")      BACKUP_FILE="$BACKUP_FILE/tpl_data_backup_all_${TIMESTAMP}.sql" ;;
        "tpl-only") BACKUP_FILE="$BACKUP_FILE/tpl_data_backup_tpl_${TIMESTAMP}.sql" ;;
        "user-only") BACKUP_FILE="$BACKUP_FILE/tpl_data_backup_user_${TIMESTAMP}.sql" ;;
    esac
fi

# =============================================================================
# 主程序
# =============================================================================

print_header "TPL 数据库备份工具"

echo ""
print_info "容器: $CONTAINER_NAME"
print_info "模式: $BACKUP_MODE"
print_info "文件: $BACKUP_FILE"
echo ""

# 检查容器
if ! check_docker_container "$CONTAINER_NAME"; then
    print_error "容器 '$CONTAINER_NAME' 未运行"
    echo ""
    echo "运行中的 PostgreSQL 容器:"
    docker ps --filter "name=postgresql" --format "  - {{.Names}}" || echo "  (无)"
    exit 1
fi

print_success "容器正在运行"

# 构建 pg_dump 参数
DUMP_ARGS="-U $DB_USER -d $DB_NAME --clean --if-exists -F p"

case $BACKUP_MODE in
    "tpl-only")
        DUMP_ARGS="$DUMP_ARGS --schema=public"
        print_info "只备份 public schema (TPL 数据)"
        ;;
    "user-only")
        DUMP_ARGS="$DUMP_ARGS --schema=user_data"
        print_info "只备份 user_data schema (用户数据)"
        ;;
    "all")
        print_info "备份全部数据"
        ;;
esac

# 执行备份
echo ""
echo "开始备份..."
echo "命令: docker exec $CONTAINER_NAME pg_dump $DUMP_ARGS"
echo ""

docker exec "$CONTAINER_NAME" pg_dump $DUMP_ARGS > "$BACKUP_FILE"
RESULT=$?

if [ $RESULT -eq 0 ] && [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo ""
    print_success "备份成功!"
    echo "  文件: $BACKUP_FILE"
    echo "  大小: $FILE_SIZE"
    print_header "完成!"
    exit 0
else
    echo ""
    print_error "备份失败! (exit code: $RESULT)"
    [ -f "$BACKUP_FILE" ] && rm -f "$BACKUP_FILE"
    exit 1
fi
