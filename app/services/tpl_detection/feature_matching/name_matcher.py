"""
Name Matcher - 库名相似性匹配器

职责：从二进制信息中快速查找可能的库名（作为特征匹配的 hint）
- 检查来源：二进制文件名、字符串、函数名
- 输出：可能的库名集合
"""

import json
import os
import re
from typing import List, Optional, Set

from loguru import logger

from app.config import settings


# ========== 全局缓存 ==========
_LIBRARY_NAMES: Optional[dict] = None  # {name_lower: {"id": id, "name": original_name}}
_LIBRARY_NAME_SET: Optional[Set[str]] = None  # 库名集合，用于快速查找
_LIB_PREFIX_PATTERN: Optional[re.Pattern] = None  # lib前缀匹配正则
_TOKEN_PATTERN: Optional[re.Pattern] = None  # 分词正则


def _load_library_names() -> dict:
    """
    加载库名列表

    Returns:
        dict: {name_lower: {"id": id, "name": original_name}}
    """
    global _LIBRARY_NAMES, _LIBRARY_NAME_SET, _LIB_PREFIX_PATTERN, _TOKEN_PATTERN

    if _LIBRARY_NAMES is not None:
        return _LIBRARY_NAMES

    # 默认路径
    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
        "data", "libraries.json"
    )

    hash_file_path = getattr(settings, 'LIBRARY_NAMES_PATH', default_path)

    if os.path.exists(hash_file_path):
        try:
            with open(hash_file_path, 'r') as f:
                libraries = json.load(f)

            # 构建查找字典，过滤掉太短的名字（<=3字符容易误匹配）
            _LIBRARY_NAMES = {}
            for lib in libraries:
                name = lib["name"]
                if len(name) > 3:  # 只保留长度 > 3 的库名
                    _LIBRARY_NAMES[name.lower()] = {"id": lib["id"], "name": name}

            # 构建库名集合，用于 O(1) 查找
            _LIBRARY_NAME_SET = set(_LIBRARY_NAMES.keys())

            # 分词正则：按非字母数字分割，提取连续的字母数字串
            _TOKEN_PATTERN = re.compile(r'[a-zA-Z][a-zA-Z0-9_+-]*')

            # lib 前缀匹配正则
            _LIB_PREFIX_PATTERN = re.compile(
                r'lib([a-zA-Z][a-zA-Z0-9_+-]*?)(?:\.so|\.a|\.dylib|\.dll|[._-]\d)',
                re.IGNORECASE
            )

            logger.info(f"Loaded {len(_LIBRARY_NAMES)} library names for matching")
        except Exception as e:
            logger.warning(f"Failed to load library names: {e}")
            _LIBRARY_NAMES = {}
            _LIBRARY_NAME_SET = set()
            _LIB_PREFIX_PATTERN = None
            _TOKEN_PATTERN = None
    else:
        logger.debug(f"Library names file not found: {hash_file_path}")
        _LIBRARY_NAMES = {}
        _LIBRARY_NAME_SET = set()
        _LIB_PREFIX_PATTERN = None
        _TOKEN_PATTERN = None

    return _LIBRARY_NAMES


def get_library_info(name_lower: str) -> Optional[dict]:
    """获取库信息"""
    library_names = _load_library_names()
    return library_names.get(name_lower)


def find_hint_library_names(
    binary_name: str = None,
    strings: List[str] = None,
    function_names: List[str] = None,
    max_strings: int = 2000,
    max_functions: int = 2000
) -> Set[str]:
    """
    从二进制信息中查找可能的库名（hint）

    Args:
        binary_name: 二进制文件名
        strings: 字符串列表
        function_names: 函数名列表
        max_strings: 最多检查的字符串数量
        max_functions: 最多检查的函数名数量

    Returns:
        Set[str]: 可能的库名集合（小写）
    """
    library_names = _load_library_names()
    if not library_names:
        return set()

    matched_names = set()

    # 1. 检查二进制文件名
    if binary_name:
        matched_names.update(_match_from_filename(binary_name, library_names))

    # 2. 检查字符串
    if strings:
        matched_names.update(_match_from_strings(strings, library_names, max_strings))

    # 3. 检查函数名
    if function_names:
        matched_names.update(_match_from_function_names(function_names, library_names, max_functions))

    if matched_names:
        logger.debug(f"Found {len(matched_names)} hint library names: {sorted(matched_names)[:10]}...")

    return matched_names


def _match_from_filename(binary_name: str, library_names: dict) -> Set[str]:
    """从二进制文件名匹配库名"""
    matched = set()

    # 处理文件名：去掉扩展名，处理 lib 前缀
    name_lower = binary_name.lower()
    base_name = name_lower.split('.')[0]

    # 去掉 lib 前缀
    if base_name.startswith('lib') and len(base_name) > 6:
        base_name_without_lib = base_name[3:]
        if base_name_without_lib in library_names:
            matched.add(base_name_without_lib)

    # 直接匹配
    if base_name in library_names:
        matched.add(base_name)

    # 分词匹配：提取所有 token，检查是否在库名集合中
    if _TOKEN_PATTERN and _LIBRARY_NAME_SET:
        tokens = _TOKEN_PATTERN.findall(name_lower)
        for token in tokens:
            token_lower = token.lower()
            if len(token_lower) > 3 and token_lower in _LIBRARY_NAME_SET:
                matched.add(token_lower)

    return matched


def _match_from_strings(strings: List[str], library_names: dict, max_count: int) -> Set[str]:
    """从字符串列表匹配库名"""
    if not _TOKEN_PATTERN or not _LIBRARY_NAME_SET:
        return set()

    matched = set()

    # 优先检查更可能包含库名的字符串
    priority_strings = []
    other_strings = []
    for s in strings:
        if len(s) < 4 or len(s) > 500:
            continue
        # 路径或包含常见分隔符的更可能包含库名
        if '/' in s or '\\' in s or '.so' in s or '.a' in s or 'lib' in s.lower():
            priority_strings.append(s)
        elif len(s) < 100:
            priority_strings.append(s)
        else:
            other_strings.append(s)

    strings_to_check = (priority_strings + other_strings)[:max_count]

    for s in strings_to_check:
        s_lower = s.lower()

        # 分词匹配：提取所有 token，检查是否在库名集合中
        tokens = _TOKEN_PATTERN.findall(s_lower)
        for token in tokens:
            if len(token) > 3 and token in _LIBRARY_NAME_SET:
                matched.add(token)

        # lib 前缀匹配：libcurl.so → curl
        if _LIB_PREFIX_PATTERN:
            lib_matches = _LIB_PREFIX_PATTERN.findall(s)
            for lib_match in lib_matches:
                lib_name = lib_match.lower()
                if len(lib_name) > 3 and lib_name in _LIBRARY_NAME_SET:
                    matched.add(lib_name)

    return matched


def _match_from_function_names(function_names: List[str], library_names: dict, max_count: int) -> Set[str]:
    """从函数名列表匹配库名"""
    if not _TOKEN_PATTERN or not _LIBRARY_NAME_SET:
        return set()

    matched = set()

    # 只检查一定数量的函数名
    functions_to_check = function_names[:max_count]

    for func in functions_to_check:
        if len(func) < 4 or len(func) > 200:
            continue

        func_lower = func.lower()

        # 分词匹配：curl_easy_init → [curl, easy, init]，检查是否在库名集合中
        tokens = _TOKEN_PATTERN.findall(func_lower)
        for token in tokens:
            if len(token) > 3 and token in _LIBRARY_NAME_SET:
                matched.add(token)

    return matched
