"""
Feature Filter - 特征过滤工具模块

提供统一的字符串和符号过滤逻辑，供各模块复用。
"""

import hashlib
import json
import os
from typing import List, Set, Optional

from loguru import logger

from app.config import settings
from app.services.tpl_detection.utils.demangle import (
    demangle_symbol,
    extract_function_name,
)


# ========== 全局缓存 ==========
_COMMON_STRING_HASHES: Optional[Set[str]] = None
_COMMON_FUNCTION_HASHES: Optional[Set[str]] = None


# ========== 通用特征加载 ==========

def _compute_hash(s: str) -> str:
    """计算字符串的 SHA256 hash"""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _load_common_string_hashes() -> Set[str]:
    """
    加载通用字符串的 hash 集合

    从 common_strings.json 加载，格式为:
    [{"string_id": 1, "string_hash": "xxx", "string_value": "xxx", "library_count": 100}, ...]
    """
    global _COMMON_STRING_HASHES
    if _COMMON_STRING_HASHES is not None:
        return _COMMON_STRING_HASHES

    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
        "data", "common_strings.json"
    )
    file_path = getattr(settings, 'COMMON_STRINGS_PATH', default_path)

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                items = json.load(f)
            # 提取 hash（如果有）或从 string_value 计算
            _COMMON_STRING_HASHES = set()
            for item in items:
                if 'string_hash' in item:
                    _COMMON_STRING_HASHES.add(item['string_hash'])
                elif 'string_value' in item:
                    _COMMON_STRING_HASHES.add(_compute_hash(item['string_value']))
            logger.info(f"Loaded {len(_COMMON_STRING_HASHES)} common strings")
        except Exception as e:
            logger.warning(f"Failed to load common strings: {e}")
            _COMMON_STRING_HASHES = set()
    else:
        _COMMON_STRING_HASHES = set()

    return _COMMON_STRING_HASHES


def _load_common_function_hashes() -> Set[str]:
    """
    加载通用函数名的 hash 集合

    从 common_function_names.json 加载，格式为:
    [{"function_id": 1, "function_hash": "xxx", "function_name": "xxx", "library_count": 100}, ...]
    """
    global _COMMON_FUNCTION_HASHES
    if _COMMON_FUNCTION_HASHES is not None:
        return _COMMON_FUNCTION_HASHES

    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
        "data", "common_function_names.json"
    )
    file_path = getattr(settings, 'COMMON_FUNCTION_NAMES_PATH', default_path)

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                items = json.load(f)
            # 提取 hash（如果有）或从 function_name 计算
            _COMMON_FUNCTION_HASHES = set()
            for item in items:
                if 'function_hash' in item:
                    _COMMON_FUNCTION_HASHES.add(item['function_hash'])
                elif 'function_name' in item:
                    _COMMON_FUNCTION_HASHES.add(_compute_hash(item['function_name']))
            logger.info(f"Loaded {len(_COMMON_FUNCTION_HASHES)} common function names")
        except Exception as e:
            logger.warning(f"Failed to load common function names: {e}")
            _COMMON_FUNCTION_HASHES = set()
    else:
        _COMMON_FUNCTION_HASHES = set()

    return _COMMON_FUNCTION_HASHES


# ========== 字符串过滤 ==========

# ELF section 名称黑名单
# 这些是几乎所有 ELF 二进制都有的通用 section names，不能作为库识别的证据
_ELF_SECTION_BLACKLIST = {
    # 核心 section（几乎所有二进制都有）
    ".text", ".data", ".bss", ".rodata",
    ".init", ".fini", ".plt", ".got",
    # 动态链接相关
    ".dynsym", ".dynstr", ".dynamic",
    ".plt.got", ".got.plt", ".rela.plt", ".rela.dyn",
    # 版本和符号相关
    ".gnu.hash", ".gnu.version", ".gnu.version_r",
    # 异常处理
    ".eh_frame", ".eh_frame_hdr",
    # 初始化/终止数组
    ".init_array", ".fini_array",
    # 其他
    ".note.gnu.build-id", ".data.rel.ro",
    ".shstrtab", ".comment",
}


def _is_cpp_function_name(s: str) -> bool:
    """检查字符串是否像 C/C++ 函数名"""
    if not s:
        return False
    # C++ mangled 符号
    if s.startswith("_Z") or s.startswith("__Z") or s.startswith("?"):
        return True
    # 全大写字符串通常是宏/常量，不是函数名（如 NOT_ALPHA, INV_CHAR_CLASS）
    if s.isupper():
        return False
    # 普通函数名格式：字母开头，只包含字母数字下划线
    if s[0].isalpha() or s[0] == '_':
        if all(c.isalnum() or c == '_' for c in s):
            # 长度和格式特征
            if 3 <= len(s) <= 50 and '_' in s:
                return True
    return False


def filter_strings(
    strings: List[str],
    min_length: int = 5,
    max_length: int = 500,
) -> List[str]:
    """
    过滤字符串特征

    过滤规则：
    - 排除 ELF section 名称
    - 长度限制 [min_length, max_length)
    - 排除 C/C++ 函数名格式
    - 排除通用字符串 (hash 过滤)

    Args:
        strings: 原始字符串列表
        min_length: 最小长度（含）
        max_length: 最大长度（不含）

    Returns:
        过滤后的字符串列表
    """
    if not strings:
        return []

    common_hashes = _load_common_string_hashes()
    common_filtered_count = 0
    filtered = set()

    for s in strings:
        # 排除 ELF section 名称
        if s in _ELF_SECTION_BLACKLIST:
            continue

        # 长度限制：>= min_length 且 < max_length
        if not (min_length <= len(s) < max_length):
            continue

        # 排除 C/C++ 函数名格式
        if _is_cpp_function_name(s):
            continue

        # 排除通用字符串
        if common_hashes:
            string_hash = _compute_hash(s.strip())
            if string_hash in common_hashes:
                common_filtered_count += 1
                continue

        filtered.add(s.strip())

    if common_filtered_count > 0:
        logger.debug(f"String filter: excluded {common_filtered_count} common strings")

    return sorted(filtered)


# ========== 符号过滤 ==========

# 排除的系统符号前缀
_EXCLUDED_SYMBOL_PREFIXES = {
    'std::', 'std_',
    'operator', 'typeinfo',
    '__cxa_', '__gxx_',
}


def _remove_template_args(s: str) -> str:
    """去掉模板参数：vector<int>::push_back -> vector::push_back"""
    result = []
    depth = 0
    for char in s:
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif depth == 0:
            result.append(char)
    return "".join(result)


def _is_valid_function_name(name: str, min_length: int = 5, max_length: int = 50) -> bool:
    """检查函数名是否有效"""
    if not name:
        return False

    if not (min_length <= len(name) <= max_length):
        return False

    excluded = {'operator', 'typeinfo', 'vtable', 'std', '__cxa', '__gxx'}
    for ex in excluded:
        if name.startswith(ex):
            return False

    if name.startswith('~'):
        return False

    return True


def _is_valid_demangled_name(name: str, min_length: int = 5, max_length: int = 200) -> bool:
    """检查 demangled 函数名是否有效"""
    if not name:
        return False

    if len(name) < min_length or len(name) > max_length:
        return False

    excluded_prefixes = {'std::', 'operator', 'typeinfo', 'vtable', '__cxa', '__gxx', '__gnu_cxx'}
    for ex in excluded_prefixes:
        if name.startswith(ex):
            return False

    if '::~' in name or name.startswith('~'):
        return False

    return True


def filter_symbols(
    symbols: List[str],
    min_length: int = 5,
    max_length: int = 50,
) -> List[str]:
    """
    过滤符号特征

    过滤规则：
    - C++ 符号 demangle
    - 排除 _/__ 开头的系统符号
    - 长度限制
    - 排除系统符号前缀
    - 排除通用函数名 (hash 过滤)

    Args:
        symbols: 原始符号列表
        min_length: 最小长度
        max_length: 最大长度

    Returns:
        过滤后的符号列表
    """
    if not symbols:
        return []

    filtered = set()

    for symbol in symbols:
        symbol = symbol.strip()
        if not symbol:
            continue

        # 检查是否是 C++ mangled 符号
        is_mangled = (
            symbol.startswith("_Z") or
            symbol.startswith("__Z") or
            symbol.startswith("?")
        )

        if is_mangled:
            # 尝试 demangle
            demangled = demangle_symbol(symbol)
            if demangled and demangled != symbol:
                # 去掉参数部分
                paren_pos = demangled.find("(")
                if paren_pos != -1:
                    demangled = demangled[:paren_pos]
                # 去掉模板参数
                demangled = _remove_template_args(demangled)
                if demangled and _is_valid_demangled_name(demangled):
                    filtered.add(demangled)
                    # 同时添加最后的函数名部分
                    func_name = extract_function_name(symbol)
                    if func_name and _is_valid_function_name(func_name, min_length, max_length):
                        filtered.add(func_name)
        else:
            # 非 mangled 符号
            if symbol.startswith('_') or symbol.startswith('__'):
                continue

            if not (min_length <= len(symbol) <= max_length):
                continue

            skip = False
            for prefix in _EXCLUDED_SYMBOL_PREFIXES:
                if symbol.startswith(prefix):
                    skip = True
                    break
            if skip:
                continue

            filtered.add(symbol)

    # 过滤通用函数名
    common_hashes = _load_common_function_hashes()
    if common_hashes:
        common_filtered_count = 0
        final_filtered = set()
        for func_name in filtered:
            name_to_check = func_name
            if '::' in func_name:
                name_to_check = func_name.split('::')[-1]

            func_hash = _compute_hash(name_to_check)
            if func_hash in common_hashes:
                common_filtered_count += 1
            else:
                final_filtered.add(func_name)

        if common_filtered_count > 0:
            logger.debug(f"Symbol filter: excluded {common_filtered_count} common function names")

        return sorted(final_filtered)

    return sorted(filtered)
