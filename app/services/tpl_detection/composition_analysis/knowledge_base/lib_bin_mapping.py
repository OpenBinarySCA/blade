"""
库 → 编译产物映射加载器

提供:
1. get_library_binaries_map() - 获取完整映射
2. get_reverse_mapping() - 获取反向索引 (binary_name → [library_names])
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

_MAPPING_FILE = Path(__file__).parent / "lib_bin_mapping.json"
_CACHE: Dict[str, dict] = {}


def get_library_binaries_map() -> dict:
    """
    加载库→编译产物映射

    Returns:
        dict: {library_name: {"libraries": [...], "executables": [...]}}
    """
    if "map" not in _CACHE:
        with open(_MAPPING_FILE, "r", encoding="utf-8") as f:
            _CACHE["map"] = json.load(f)
    return _CACHE["map"]


def get_reverse_mapping() -> Dict[str, List[str]]:
    """
    构建反向索引: binary_name → [library_names]

    支持:
    - 可执行文件名 → 库名列表 (cplay → [tinycompress])
    - 库文件名 → 库名列表 (libssl.so → [openssl, libressl])

    Returns:
        dict: {binary_name: [library_name1, library_name2, ...]}
    """
    if "reverse" not in _CACHE:
        reverse_map = defaultdict(set)
        for lib_name, info in get_library_binaries_map().items():
            # 添加可执行文件映射
            for exe in info.get("executables", []):
                reverse_map[exe].add(lib_name)

            # 添加库文件映射 (多种变体)
            for lib_file in info.get("libraries", []):
                # libfoo.so → foo
                base_name = lib_file
                if base_name.startswith("lib"):
                    base_name = base_name[3:]  # 去掉 lib 前缀
                base_name = base_name.replace(".so", "")  # 去掉 .so 后缀

                reverse_map[base_name].add(lib_name)
                reverse_map[lib_file].add(lib_name)  # 原始名也加入

        # 转换 set 为 sorted list
        _CACHE["reverse"] = {k: sorted(list(v)) for k, v in reverse_map.items()}
    return _CACHE["reverse"]


def _normalize_binary_name(binary_name: str) -> str:
    """
    规范化二进制文件名，去除版本号和后缀

    Examples:
        ld-2.26.so → ld
        libc-2.26.so → c
        libc.so.6 → c
        libm.so.6 → m
    """
    import re

    name = binary_name

    # 去掉 .so 及其后面的版本号 (.so.6, .so.1.0.0 等)
    name = re.sub(r'\.so(\.\d+)*$', '', name)

    # 去掉 -版本号 (如 -2.26)
    name = re.sub(r'-\d+(\.\d+)*$', '', name)

    # 去掉 lib 前缀
    if name.startswith("lib"):
        name = name[3:]

    return name


def lookup_library_by_binary(binary_name: str) -> List[str]:
    """
    根据二进制名查找所有可能的库（支持带版本号的库名）

    Args:
        binary_name: 二进制文件名 (如 cplay, openssl, ld-2.26.so, libssl.so)

    Returns:
        可能的库名列表（可能为空）

    Examples:
        lookup_library_by_binary("cplay") → ["tinycompress"]
        lookup_library_by_binary("ld-2.26.so") → ["glibc"]
        lookup_library_by_binary("libssl.so") → ["libressl", "openssl"]
    """
    reverse_map = get_reverse_mapping()
    results = set()

    # 1. 精确匹配
    if binary_name in reverse_map:
        results.update(reverse_map[binary_name])

    # 2. 规范化后匹配
    normalized = _normalize_binary_name(binary_name)
    if normalized in reverse_map:
        results.update(reverse_map[normalized])

    return sorted(list(results))


def get_library_info(library_name: str) -> Optional[dict]:
    """
    获取库的详细信息

    Args:
        library_name: 库名

    Returns:
        {"libraries": [...], "executables": [...]} 或 None
    """
    return get_library_binaries_map().get(library_name)
