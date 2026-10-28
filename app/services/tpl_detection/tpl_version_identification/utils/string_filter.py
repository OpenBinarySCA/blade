"""
Version String Filtering Utilities
版本字符串过滤工具
"""
import re
from typing import List


def filter_reference_strings(library_name: str, strings: List[str]):
    """
    优化的版本字符串过滤函数 - 清晰的分层过滤逻辑

    Args:
        library_name (str): 目标库名称
        strings (List[str]): 从二进制文件提取的字符串列表

    Returns:
        dict: 按优先级分组的可能包含版本信息的字符串
    """

    # ===========================================
    # 第一步：排除明显不是版本号的字符串
    # ===========================================
    def should_exclude(s: str) -> bool:
        """判断字符串是否应该被排除"""
        EXCLUDE_PATTERNS = [
            # 函数名和符号引用
            r'\w+_version\s*\(',
            r'@@GLIBC_\d+\.\d+',
            r'^[A-Z0-9_]+_(?:new|free|init|set_version|get_version|create|destroy)$',

            # IP地址
            r'(?<!\d)(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?!\d)'

            # 日期格式
            r'(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])',

            # 哈希值和内存地址
            r'^[0-9A-Fa-f]{32,}$',
            r'0x[0-9A-Fa-f]{6,}',

            # PostScript和字体相关 - 新增
            r'%!PS-Adobe.*',
            r'Resource-CIDFont',
            r'Resource-Font',

            # 明显的非版本号格式 - 新增
            r'\d+[*\[\]<>{}|\\]',  # 包含特殊字符的数字
            r'^0{3,}\d+\.0{2,}\d+',  # 多个前导零

            # 无意义的字符串
            r'^(?:version|verify|ver)$',
            r'^[._\-]+$',
            r'^[Vv]\d*$',
        ]

        # 快速排除已知系统库
        if any(marker in s.lower() for marker in ['glibc', 'kernel', 'libc']):
            return True

        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, s, re.IGNORECASE):
                return True
        return False

    def is_valid_version_number(version_str: str) -> bool:
        """检查提取的版本号是否有效"""
        # 排除明显无效的版本号
        if re.search(r'[*\[\]<>{}|\\%]', version_str):
            return False

        # 检查是否有过多的前导零
        parts = version_str.split('.')
        for part in parts:
            if len(part) > 1 and part.startswith('0') and part != '0':
                # 允许 "01" 这样的格式，但不允许 "001"
                if len(part) > 2:
                    return False

        return True

    # ===========================================
    # 第二步：生成库名变体
    # ===========================================
    def generate_library_variants(lib_name: str) -> set:
        """生成库名的各种变体"""
        if not lib_name:
            return set()

        variants = set()
        lib_lower = lib_name.lower()

        # 基础变体
        variants.update([
            lib_lower, lib_name.upper(), lib_name.capitalize()
        ])

        # lib前缀处理
        if not lib_lower.startswith("lib") and len(lib_name) > 2:
            variants.add("lib" + lib_lower)
        if lib_lower.startswith("lib") and len(lib_name) > 3:
            variants.add(lib_lower[3:])

        # 连字符和下划线变体
        if '-' in lib_name:
            variants.add(lib_name.replace('-', '_'))
        if '_' in lib_name:
            variants.add(lib_name.replace('_', '-'))

        return variants

    def extract_context(string: str, match_obj) -> str:
        """提取匹配的上下文"""
        if len(string) <= 200:
            return string.strip()

        start_pos = match_obj.start()
        end_pos = match_obj.end()

        # 按行提取
        line_start = string.rfind('\n', 0, start_pos)
        line_start = line_start + 1 if line_start != -1 else max(0, start_pos - 100)

        line_end = string.find('\n', end_pos)
        line_end = line_end if line_end != -1 else min(len(string), end_pos + 100)

        context = string[line_start:line_end].strip()

        # 如果太长，按词边界截取
        if len(context) > 200:
            words = context.split()
            match_text = match_obj.group()
            for i, word in enumerate(words):
                if match_text in word:
                    start_idx = max(0, i - 10)
                    end_idx = min(len(words), i + 10)
                    context = ' '.join(words[start_idx:end_idx])
                    break

        return context

    # ===========================================
    # 第三步：按优先级定义搜索模式
    # ===========================================

    # 优先级1: 标准版本号字符串 (明确的版本格式)
    STANDARD_VERSION_PATTERNS = [
        # 带关键词的版本声明
        r'(?:version|ver|v)[\s:=]+\d+\.\d+(?:\.\d+)*(?:[a-zA-Z0-9\-+]+)?',
        r'(?:build|release)[\s:=]+\d+\.\d+(?:\.\d+)*',
        # 标准的三段式版本号 (x.y.z)
        r'\b(?:[1-9]\d*|0)\.(?:[1-9]\d*|0)\.(?:[1-9]\d*|0)\b',
        # 语义化版本号（可能带预发布标签）
        r'\b(?:v)?\d+\.\d+\.\d+(?:\-(?:alpha|beta|rc|dev|snapshot)\.?\d*)?(?:\+[\w\d\-\.]+)?\b',
    ]

    # 优先级2: 库专有的字符串 (包含库名的版本信息)
    def get_library_specific_patterns(lib_name: str) -> list:
        if not lib_name:
            return []
        escaped_name = re.escape(lib_name.lower())
        return [
            escaped_name + r'[\s\-_]*(?:version|ver|v)[\s:=]*\d+(?:\.\d+)+',
            r'lib' + escaped_name + r'[\s\-_]*\d+(?:\.\d+)+',
            escaped_name + r'[\s\-_]*\d+(?:\.\d+)+',
            escaped_name + r'\.so\.\d+(?:\.\d+)*',
        ]

    # 优先级3: 通用版本字符串 (两段式版本号，需要更多验证)
    GENERIC_VERSION_PATTERNS = [
        # 两段版本号，但不允许多个前导零
        r'\b(?:[1-9]\d*|0)\.(?:[1-9]\d*|0[1-9]|\d{2,})\b',
        # 四段或更多段的版本号
        r'\b(?:[1-9]\d*|0)\.(?:[1-9]\d*|0)\.(?:[1-9]\d*|0)\.(?:[1-9]\d*|0)+\b',
    ]

    # 优先级4: 路径和日志中的版本信息
    PATH_LOG_VERSION_PATTERNS = [
        r'/usr/lib.*?\d+\.\d+(?:\.\d+)?',
        r'\.so\.\d+(?:\.\d+)*',
        r'\.dll\.\d+(?:\.\d+)*',
        r'(?:gcc|clang|built with).*?\d+\.\d+(?:\.\d+)?',
        r'\.pdb.*?\d+\.\d+(?:\.\d+)?',
    ]

    # 优先级5: 其他可能的版本信息
    OTHER_VERSION_PATTERNS = [
        r'(?:copyright|©)\s*(?:19|20)\d{2}',
        r'(?:build|built)[\s:]*\d{8,}',
        r'@\w+[-_.]\d+(?:[-_.]\d+)+',
    ]

    # ===========================================
    # 第四步：执行搜索和分类
    # ===========================================

    # 预处理：过滤明显不是版本的字符串
    filtered_strings = [s for s in strings if not should_exclude(s)]
    # print(filtered_strings)

    # 生成库名变体
    lib_variants = generate_library_variants(library_name)

    def contains_library_name(s: str) -> bool:
        """检查字符串是否包含库名"""
        return any(variant in s.lower() for variant in lib_variants)

    # 结果容器
    results = {
        "standard_versions": [],  # 标准版本声明
        "library_specific": [],  # 库专有版本信息
        "generic_versions": [],  # 通用版本号
        "path_log_versions": [],  # 路径和日志中的版本
        "other_versions": [],  # 其他可能的版本信息
    }

    seen_contexts = set()

    def process_patterns(patterns: list, result_key: str, validate_version: bool = False):
        """处理一组模式"""
        for string in filtered_strings:
            for pattern in patterns:
                try:
                    matches = list(re.finditer(pattern, string, re.IGNORECASE))
                    for match in matches:
                        context = extract_context(string, match)

                        # 避免重复
                        if context in seen_contexts:
                            continue

                        # 对通用版本号进行额外验证
                        if validate_version:
                            version_nums = re.findall(r'\d+(?:\.\d+)+', match.group())
                            if not any(is_valid_version_number(v) for v in version_nums):
                                continue

                        seen_contexts.add(context)
                        results[result_key].append(context)

                except re.error:
                    continue

    # 按优先级依次处理
    process_patterns(STANDARD_VERSION_PATTERNS, "standard_versions")
    process_patterns(get_library_specific_patterns(library_name), "library_specific")
    process_patterns(GENERIC_VERSION_PATTERNS, "generic_versions", validate_version=True)
    process_patterns(PATH_LOG_VERSION_PATTERNS, "path_log_versions")
    process_patterns(OTHER_VERSION_PATTERNS, "other_versions")

    # ===========================================
    # 第五步：构成最终结果
    # ===========================================

    # 去重并按长度排序（短的优先，通常更准确）
    for key in results:
        results[key] = list(dict.fromkeys(results[key]))  # 保持顺序去重
        results[key] = sorted(results[key], key=len)

    return results
