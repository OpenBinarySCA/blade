"""
Binary Info Parser - 二进制信息解析器

职责：从二进制文件中提取原始信息，生成 TargetBinary
- 使用 strings 命令提取字符串
- 使用 lief 解析符号和动态库
- 计算文件哈希

不做任何分类或匹配，只负责提取原始数据
"""

import hashlib
import os
import re
import subprocess
import time
import traceback
from pathlib import Path
from typing import List, Dict, Any, Tuple

import lief
from loguru import logger

from ....interface import TargetBinary
from ..exceptions import FileAccessError, BinaryParseError, StringExtractionError


def calculate_file_sha256(file_path: str) -> str:
    """
    计算指定文件的SHA256哈希值

    Args:
        file_path: 文件路径

    Returns:
        文件的SHA256哈希值（十六进制字符串）
    """
    if not os.path.exists(file_path):
        raise FileAccessError(f"文件不存在: {file_path}", {"path": file_path})

    if not os.path.isfile(file_path):
        raise FileAccessError(f"路径不是文件: {file_path}", {"path": file_path})

    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(4096), b""):
                sha256_hash.update(chunk)
    except PermissionError:
        raise FileAccessError(f"没有读取文件的权限: {file_path}", {"path": file_path})
    except OSError as e:
        raise FileAccessError(f"读取文件时发生错误: {e}", {"path": file_path, "original_error": str(e)})

    return sha256_hash.hexdigest()


class BinaryInfoParser:
    """
    二进制信息解析器

    职责：从二进制文件中提取原始信息，生成 TargetBinary
    不做任何分类或匹配，只负责提取原始数据
    """

    def parse(self, file_path: str, root_path: str = None) -> TargetBinary:
        """
        解析二进制文件，提取所有信息

        Args:
            file_path: 二进制文件路径
            root_path: 根目录路径，用于计算相对路径

        Returns:
            TargetBinary: 包含提取结果的对象
        """
        logger.debug(f"Parsing binary: {file_path}")
        start_time = time.perf_counter()

        # 1. 提取文件基本信息
        file_info = self._get_file_info(file_path, root_path)

        # 2. 提取字符串
        strings_list = self._extract_strings(file_path)

        # 3. 提取符号和动态库
        dynamic_libraries, imported_symbols, exported_symbols = \
            self._extract_symbols_and_libraries(file_path)

        # 4. 分析符号前缀
        imported_symbol_analysis = self._analyze_symbol_prefixes(imported_symbols)
        exported_symbol_analysis = self._analyze_symbol_prefixes(exported_symbols)

        # 调整分析结果格式
        if imported_symbol_analysis['total'] > 0:
            imported_symbol_analysis = {
                'total_imported': imported_symbol_analysis['total'],
                'significant_prefixes': imported_symbol_analysis['prefix_categories']
            }
        else:
            imported_symbol_analysis = {'total_imported': 0, 'significant_prefixes': {}}

        if exported_symbol_analysis['total'] > 0:
            exported_symbol_analysis = {
                'total_exported': exported_symbol_analysis['total'],
                'prefix_categories': exported_symbol_analysis['prefix_categories']
            }
        else:
            exported_symbol_analysis = {'total_exported': 0, 'prefix_categories': {}}

        # 5. 创建 TargetBinary 对象
        target_binary = TargetBinary(
            binary_name=file_info['binary_name'],
            hash_sha256=file_info['hash_sha256'],
            relative_path=file_info['relative_path'],
            absolute_path=file_info['absolute_path'],
            file_size_kb=file_info['file_size_kb'],
            strings=list(set(strings_list)),
            dynamic_libraries=dynamic_libraries,
            imported_symbols=list(set(imported_symbols)),
            exported_symbols=list(set(exported_symbols)),
            imported_symbol_analysis=imported_symbol_analysis,
            exported_symbol_analysis=exported_symbol_analysis,
        )

        duration = time.perf_counter() - start_time
        logger.debug(f"Binary parsed in {duration:.2f}s")

        return target_binary

    def _extract_strings(self, file_path: str, min_length: int = 5) -> List[str]:
        """
        使用 strings 命令提取二进制文件中的字符串

        Args:
            file_path: 二进制文件路径
            min_length: 最小字符串长度

        Returns:
            提取的字符串列表（已排序去重）
        """
        try:
            result = subprocess.run(
                ['strings', '-n', str(min_length), file_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                strings = sorted([line.strip() for line in result.stdout.split('\n') if line.strip()])
                return strings
            else:
                logger.debug(f"strings命令执行失败: {result.stderr}")
                return []

        except subprocess.TimeoutExpired:
            logger.debug(f"strings命令执行超时: {file_path}")
            return []
        except FileNotFoundError:
            logger.debug("strings命令未找到，请确保系统已安装strings工具")
            return []
        except Exception as e:
            logger.error(f"提取字符串时发生错误: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def _extract_symbols_and_libraries(self, file_path: str) -> Tuple[List[str], List[str], List[str]]:
        """
        使用 lief 解析二进制文件，提取动态库、导入符号、导出符号

        Args:
            file_path: 二进制文件路径

        Returns:
            Tuple of (dynamic_libraries, imported_symbols, exported_symbols)
        """
        try:
            binary = lief.parse(file_path)
            if binary is None:
                return [], [], []

            dynamic_libraries = sorted(list(binary.libraries))
            imported_symbols = sorted([s.name for s in binary.imported_symbols if s.name])
            exported_symbols = sorted([s.name for s in binary.exported_symbols if s.name])

            return dynamic_libraries, imported_symbols, exported_symbols
        except Exception as e:
            logger.debug(f"lief解析失败: {e}")
            return [], [], []

    def _analyze_symbol_prefixes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        分析符号的前缀模式

        Args:
            symbols: 符号列表

        Returns:
            前缀分析结果
        """
        if not symbols:
            return {'total': 0, 'prefix_categories': {}}

        prefix_categories = {}

        for symbol in symbols:
            if '_' in symbol:
                prefix = symbol.split('_')[0]
            else:
                match = re.match(r'^[a-zA-Z]+', symbol)
                prefix = match.group()[:4] if match else 'other'

            if len(prefix) >= 2:
                if prefix not in prefix_categories:
                    prefix_categories[prefix] = []
                prefix_categories[prefix].append(symbol)

        result = {
            'total': len(symbols),
            'prefix_categories': {}
        }

        for prefix in sorted(prefix_categories.keys()):
            syms = prefix_categories[prefix]
            if len(syms) >= 1:
                result['prefix_categories'][prefix] = {
                    'count': len(syms),
                    'examples': sorted(syms)[:3]
                }

        return result

    def _get_file_info(self, file_path: str, root_path: str = None) -> Dict[str, Any]:
        """
        获取文件基本信息

        Args:
            file_path: 文件路径
            root_path: 根目录路径（用于计算相对路径）

        Returns:
            文件基本信息字典
        """
        if not os.path.exists(file_path):
            raise FileAccessError(f"文件不存在: {file_path}", {"path": file_path})

        file_path_obj = Path(file_path)
        file_path_absolute = file_path_obj.absolute()

        # 计算相对路径
        if root_path is None:
            root_path = file_path
        root_path_obj = Path(root_path)
        root_path_absolute = root_path_obj.absolute()

        if file_path_absolute == root_path_absolute:
            relative_path = root_path_obj.name
        else:
            try:
                relative_path = str(file_path_absolute.relative_to(root_path_absolute))
            except ValueError:
                relative_path = file_path_obj.name

        return {
            'binary_name': file_path_obj.name,
            'hash_sha256': calculate_file_sha256(file_path),
            'relative_path': relative_path,
            'absolute_path': str(file_path_absolute),
            'file_size_kb': file_path_obj.stat().st_size // 1024
        }
