#!/bin/bash
# =============================================================================
# TPL 数据库恢复脚本
#
# 使用方法:
#   ./restore_tpl_data.sh -c <容器名> [选项] <备份文件>
#
# 选项:
#   -c, --container  指定 PostgreSQL 容器名称 (必需)
#   --all            恢复全部数据 (默认, 自动从文件名检测)
#   --tpl-only       只恢复 TPL 数据 (public schema)
#   --user-only      只恢复用户数据 (user_data schema)
#
# 示例:
#   ./restore_tpl_data.sh -c blade_postgresql_prod backup.sql
#   ./restore_tpl_data.sh -c blade_postgresql_new --tpl-only backup_tpl_xxx.sql
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
RESTORE_MODE="auto"
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

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

show_usage() {
    echo "Usage: $0 -c <container_name> [options] <backup_file>"
    echo ""
    echo "Options:"
    echo "  -c, --container  PostgreSQL container name (required)"
    echo "  --all            Restore all data (default)"
    echo "  --tpl-only       Only restore TPL data (public schema)"
    echo "  --user-only      Only restore user data (user_data schema)"
    echo ""
    echo "Examples:"
    echo "  $0 -c blade_postgresql_prod backup.sql"
    echo "  $0 -c blade_postgresql_new --tpl-only backup_tpl_xxx.sql"
}

check_docker_container() {
    if ! docker ps --filter "name=^${1}$" --format "{{.Names}}" | grep -q "^${1}$"; then
        return 1
    fi
    return 0
}

detect_backup_type() {
    local filename=$(basename "$1")
    if [[ "$filename" == *"_tpl_"* ]]; then
        echo "tpl-only"
    elif [[ "$filename" == *"_user_"* ]]; then
        echo "user-only"
    else
        echo "all"
    fi
}

get_schema_info() {
    local container="$1"
    local schema="$2"
    docker exec -i "$container" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$schema';" 2>/dev/null | tr -d ' '
}

confirm_restore() {
    local container="$1"
    local mode="$2"

    echo ""
    print_warning "⚠️  警告: 此操作将修改数据库!"
    echo ""

    case $mode in
        "tpl-only")
            local count=$(get_schema_info "$container" "public")
            print_info "将恢复: public schema (TPL 数据)"
            print_info "当前 public schema 有 ${count:-0} 个表"
            print_info "user_data schema 不受影响"
            ;;
        "user-only")
            local count=$(get_schema_info "$container" "user_data")
            print_info "将恢复: user_data schema (用户数据)"
            print_info "当前 user_data schema 有 ${count:-0} 个表"
            print_info "public schema (TPL 数据) 不受影响"
            ;;
        "all")
            local tpl=$(get_schema_info "$container" "public")
            local user=$(get_schema_info "$container" "user_data")
            print_info "将恢复: 全部数据"
            print_info "当前 public schema 有 ${tpl:-0} 个表"
            print_info "当前 user_data schema 有 ${user:-0} 个表"
            ;;
    esac

    echo ""
    read -p "❗ 第一次确认 - 继续恢复? (输入 'yes'): " c1
    [ "$c1" != "yes" ] && echo "已取消" && return 1

    echo ""
    read -p "❗❗ 第二次确认 - 数据将被覆盖, 继续? (输入 'yes'): " c2
    [ "$c2" != "yes" ] && echo "已取消" && return 1

    echo ""
    read -p "❗❗❗ 第三次确认 - 最后机会, 确定恢复? (输入 'yes'): " c3
    [ "$c3" != "yes" ] && echo "已取消" && return 1

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
            RESTORE_MODE="all"
            shift
            ;;
        --tpl-only)
            RESTORE_MODE="tpl-only"
            shift
            ;;
        --user-only)
            RESTORE_MODE="user-only"
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

# =============================================================================
# 主程序
# =============================================================================

print_header "TPL 数据库恢复工具"

# 检查必需参数
if [ -z "$CONTAINER_NAME" ]; then
    print_error "Error: 需要指定容器名称"
    echo ""
    show_usage
    exit 1
fi

if [ -z "$BACKUP_FILE" ]; then
    print_error "Error: 需要指定备份文件"
    echo ""
    show_usage
    exit 1
fi

# 检查备份文件
if [ ! -f "$BACKUP_FILE" ]; then
    print_error "备份文件不存在: $BACKUP_FILE"
    exit 1
fi

# 自动检测恢复模式
if [ "$RESTORE_MODE" == "auto" ]; then
    RESTORE_MODE=$(detect_backup_type "$BACKUP_FILE")
    print_info "从文件名检测到模式: $RESTORE_MODE"
fi

# 检查容器
if ! check_docker_container "$CONTAINER_NAME"; then
    print_error "容器 '$CONTAINER_NAME' 未运行"
    echo ""
    echo "运行中的 PostgreSQL 容器:"
    docker ps --filter "name=postgresql" --format "  - {{.Names}}" || echo "  (无)"
    exit 1
fi

print_success "容器正在运行"

# 显示配置
echo ""
print_info "容器: $CONTAINER_NAME"
print_info "模式: $RESTORE_MODE"
print_info "文件: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# 确认恢复
if ! confirm_restore "$CONTAINER_NAME" "$RESTORE_MODE"; then
    print_header "已取消"
    exit 1
fi

# 执行恢复
echo ""
print_info "开始恢复..."

if docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE" > /dev/null 2>&1; then
    echo ""
    print_success "恢复成功!"
    print_header "完成!"
    exit 0
else
    echo ""
    print_error "恢复失败!"
    print_header "失败!"
    exit 1
fi
