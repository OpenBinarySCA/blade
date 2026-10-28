"""
License Processor - License 检测与提取

检测和提取仓库中的 license 文件
"""
import hashlib
import os
import re
from typing import List, Optional

from loguru import logger

from .interface import LicenseInfo


class LicenseProcessor:
    """License 处理器"""

    # 常见 license 文件名（按优先级排序）
    LICENSE_FILE_PATTERNS = [
        'LICENSE',
        'LICENSE.txt',
        'LICENSE.md',
        'LICENSE.rst',
        'LICENCE',
        'LICENCE.txt',
        'COPYING',
        'COPYING.txt',
        'COPYING.md',
        'MIT-LICENSE',
        'MIT-LICENSE.txt',
        'Apache-2.0.txt',
        'Apache-2.0',
        'NOTICE',
        'NOTICE.txt',
        'UNLICENSE',
        'UNLICENSE.txt',
    ]

    # License 类型识别模式
    LICENSE_TYPE_PATTERNS = [
        (r'MIT License', 'MIT'),
        (r'Permission is hereby granted.*MIT', 'MIT'),
        (r'Apache License.*Version 2\.0', 'Apache-2.0'),
        (r'GNU GENERAL PUBLIC LICENSE.*Version 3', 'GPL-3.0'),
        (r'GNU GENERAL PUBLIC LICENSE.*Version 2', 'GPL-2.0'),
        (r'GNU LESSER GENERAL PUBLIC LICENSE.*Version 3', 'LGPL-3.0'),
        (r'GNU LESSER GENERAL PUBLIC LICENSE.*Version 2\.1', 'LGPL-2.1'),
        (r'BSD 3-Clause License', 'BSD-3-Clause'),
        (r'BSD 2-Clause License', 'BSD-2-Clause'),
        (r'Redistribution and use in source and binary forms.*provided that', 'BSD'),
        (r'Mozilla Public License.*2\.0', 'MPL-2.0'),
        (r'Eclipse Public License.*2\.0', 'EPL-2.0'),
        (r'ISC License', 'ISC'),
        (r'Boost Software License', 'BSL-1.0'),
        (r'The Unlicense', 'Unlicense'),
        (r'WTFPL', 'WTFPL'),
        (r'Creative Commons', 'CC'),
        (r'Public Domain', 'Public Domain'),
        (r'zlib/libpng License', 'Zlib'),
        (r'This is free and unencumbered software', 'Unlicense'),
    ]

    def __init__(self, max_license_size: int = 100 * 1024):
        """
        初始化 License 处理器

        Args:
            max_license_size: 最大 license 文件大小（字节）
        """
        self.max_license_size = max_license_size

    def detect_licenses(self, repo_path: str) -> List[LicenseInfo]:
        """
        检测仓库中的 license 文件

        Args:
            repo_path: 仓库路径

        Returns:
            License 信息列表
        """
        licenses = []

        if not os.path.exists(repo_path):
            logger.warning(f"仓库路径不存在: {repo_path}")
            return licenses

        # 首先查找根目录的 license 文件
        for filename in self.LICENSE_FILE_PATTERNS:
            file_path = os.path.join(repo_path, filename)
            if os.path.isfile(file_path):
                license_info = self._read_license_file(file_path, filename)
                if license_info:
                    licenses.append(license_info)

        # 如果根目录没找到，搜索一级子目录
        if not licenses:
            for item in os.listdir(repo_path):
                item_path = os.path.join(repo_path, item)
                if os.path.isdir(item_path):
                    for filename in self.LICENSE_FILE_PATTERNS[:4]:  # 只检查常见的
                        file_path = os.path.join(item_path, filename)
                        if os.path.isfile(file_path):
                            relative_path = os.path.join(item, filename)
                            license_info = self._read_license_file(file_path, relative_path)
                            if license_info:
                                licenses.append(license_info)
                                break  # 每个子目录只取一个

        return licenses

    def _read_license_file(self, file_path: str, relative_path: str) -> Optional[LicenseInfo]:
        """
        读取 license 文件

        Args:
            file_path: 文件绝对路径
            relative_path: 相对路径（用于记录）

        Returns:
            LicenseInfo 或 None
        """
        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size > self.max_license_size:
                logger.warning(f"License 文件过大，跳过: {file_path} ({file_size} bytes)")
                return None

            # 读取内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if not content.strip():
                return None

            # 计算 hash
            content_hash = self._compute_hash(content)

            # 识别 license 类型
            license_type = self.identify_license_type(content)

            return LicenseInfo(
                name=license_type,
                content=content,
                file_path=relative_path,
                content_hash=content_hash,
            )

        except Exception as e:
            logger.error(f"读取 license 文件失败 {file_path}: {e}")
            return None

    def identify_license_type(self, content: str) -> str:
        """
        识别 license 类型

        Args:
            content: License 文件内容

        Returns:
            License 类型名称
        """
        for pattern, license_type in self.LICENSE_TYPE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                return license_type

        return 'Unknown'

    def _compute_hash(self, content: str) -> str:
        """
        计算内容的 SHA256 hash

        Args:
            content: 文本内容

        Returns:
            hash 字符串
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def find_license_in_readme(self, repo_path: str) -> Optional[str]:
        """
        尝试从 README 中识别 license

        Args:
            repo_path: 仓库路径

        Returns:
            License 类型或 None
        """
        readme_patterns = ['README.md', 'README.rst', 'README.txt', 'README']

        for readme_name in readme_patterns:
            readme_path = os.path.join(repo_path, readme_name)
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # 查找 license badge 或 section
                    badge_patterns = [
                        r'!\[.*license.*\]\(.*shields\.io.*license.*/([\w\-\.]+)',
                        r'License:\s*(\w[\w\-\.]*)',
                        r'licensed under.*?(\w+(?:\s+\d+\.\d+)?)',
                    ]

                    for pattern in badge_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            return match.group(1).strip()

                except Exception as e:
                    logger.debug(f"读取 README 失败: {e}")
                    continue

        return None
