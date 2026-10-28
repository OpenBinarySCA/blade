#!/bin/bash
# =============================================================================
# TPL 数据库备份脚本
# 从 docker-compose-postgresql.yml 启动的 PostgreSQL 数据库备份数据
#
# 使用方法:
#   ./backup_tpl_data.sh [保存路径]
#
#   如果不指定路径,默认保存到当前目录,文件名格式: tpl_data_backup_YYYYMMDD_HHMMSS.sql
#   如果指定路径,则保存到指定路径
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
CONTAINER_NAME="blade_postgresql_debug"
DB_USER="tpl_data"
DB_PASSWORD="tpl_data"
DB_NAME="tpl_data"

# 处理保存路径参数
if [ -z "$1" ]; then
    # 没有指定路径,使用当前目录并生成带时间戳的文件名
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$(pwd)/tpl_data_backup_${TIMESTAMP}.sql"
else
    # 指定了路径,直接使用
    BACKUP_FILE="$1"

    # 如果指定的是目录,则在该目录下生成带时间戳的文件名
    if [ -d "$BACKUP_FILE" ]; then
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        BACKUP_FILE="$BACKUP_FILE/tpl_data_backup_${TIMESTAMP}.sql"
    fi
fi

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

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

check_docker_container() {
    if ! docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        return 1
    fi
    return 0
}

# =============================================================================
# 主程序
# =============================================================================

print_header "TPL 数据库备份工具"

# 检查 Docker 容器是否运行
if ! check_docker_container; then
    print_error "PostgreSQL 容器 '$CONTAINER_NAME' 未运行"
    echo "请先启动容器: docker-compose -f compose/docker-compose-tpl_data_postgres.yml up -d"
    exit 1
fi

print_success "PostgreSQL 容器正在运行"

# 执行备份
echo ""
echo "开始备份数据库..."
echo "备份文件: $BACKUP_FILE"

if docker exec -t "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists -F p > "$BACKUP_FILE" 2>/dev/null; then
    # 获取文件大小
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    echo ""
    print_success "备份成功!"
    echo "  文件路径: $BACKUP_FILE"
    echo "  文件大小: $FILE_SIZE"

    print_header "备份完成!"
    exit 0
else
    print_error "备份失败!"
    # 删除不完整的备份文件
    [ -f "$BACKUP_FILE" ] && rm -f "$BACKUP_FILE"

    print_header "备份失败!"
    exit 1
fi
