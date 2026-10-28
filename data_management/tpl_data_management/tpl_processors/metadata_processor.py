"""
Metadata Processor - 元数据处理

解析 Git URL，构建库元数据信息
支持：
- Homepage 推断
- PURL (Package URL) 生成
- 编程语言检测
- Description 提取（接口预留）
"""
import os
import re
from collections import Counter
from typing import Optional, Tuple, List

from loguru import logger

from .interface import LibraryInfo


class MetadataProcessor:
    """元数据处理器"""

    # GitHub URL 模式
    GITHUB_PATTERNS = [
        r'github\.com[/:]([^/]+)/([^/.]+)(?:\.git)?',
        r'github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$',
    ]

    # 其他 Git 平台模式
    OTHER_GIT_PATTERNS = [
        (r'gitlab\.com[/:]([^/]+)/([^/.]+)', 'gitlab'),
        (r'bitbucket\.org[/:]([^/]+)/([^/.]+)', 'bitbucket'),
        (r'android\.googlesource\.com/platform/([^/]+)/([^/.]+)', 'aosp'),
        (r'android\.googlesource\.com/([^/]+)', 'aosp'),
    ]

    def parse_github_url(self, git_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析 GitHub URL，提取 owner 和 repo

        Args:
            git_url: Git 仓库 URL

        Returns:
            (owner, repo_name) 或 (None, None)
        """
        if not git_url:
            return None, None

        for pattern in self.GITHUB_PATTERNS:
            match = re.search(pattern, git_url)
            if match:
                owner = match.group(1)
                repo = match.group(2)
                # 移除 .git 后缀
                if repo.endswith('.git'):
                    repo = repo[:-4]
                return owner, repo

        return None, None

    def parse_git_url(self, git_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        解析任意 Git URL

        Args:
            git_url: Git 仓库 URL

        Returns:
            (owner, repo_name, platform) 或 (None, None, None)
        """
        if not git_url:
            return None, None, None

        # 先尝试 GitHub
        owner, repo = self.parse_github_url(git_url)
        if owner and repo:
            return owner, repo, 'github'

        # 尝试其他平台
        for pattern, platform in self.OTHER_GIT_PATTERNS:
            match = re.search(pattern, git_url)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return groups[0], groups[1], platform
                elif len(groups) == 1:
                    return None, groups[0], platform

        return None, None, None

    def build_homepage_url(self, git_url: str) -> Optional[str]:
        """
        从 Git URL 构建 homepage URL

        Args:
            git_url: Git 仓库 URL

        Returns:
            homepage URL 或 None
        """
        owner, repo, platform = self.parse_git_url(git_url)

        if not repo:
            return None

        if platform == 'github' and owner:
            return f"https://github.com/{owner}/{repo}"
        elif platform == 'gitlab' and owner:
            return f"https://gitlab.com/{owner}/{repo}"
        elif platform == 'bitbucket' and owner:
            return f"https://bitbucket.org/{owner}/{repo}"
        elif platform == 'aosp':
            if owner:
                return f"https://android.googlesource.com/platform/{owner}/{repo}"
            else:
                return f"https://android.googlesource.com/{repo}"

        return None

    def generate_purl(self, git_url: str, name: str, version: Optional[str] = None) -> Optional[str]:
        """
        生成 Package URL (PURL)

        PURL 格式: pkg:type/namespace/name@version
        例如: pkg:github/oatpp/oatpp-libressl@1.3.0

        Args:
            git_url: Git 仓库 URL
            name: 库名称
            version: 版本号（可选）

        Returns:
            PURL 字符串或 None
        """
        owner, repo, platform = self.parse_git_url(git_url)

        if not platform:
            return None

        # 构建 PURL
        if platform == 'github':
            purl_type = 'github'
        elif platform == 'gitlab':
            purl_type = 'gitlab'
        elif platform == 'bitbucket':
            purl_type = 'bitbucket'
        else:
            purl_type = 'generic'

        # 使用 owner 作为 namespace
        if owner:
            purl = f"pkg:{purl_type}/{owner}/{repo or name}"
        else:
            purl = f"pkg:{purl_type}/{name}"

        # 添加版本
        if version:
            purl += f"@{version}"

        return purl

    def extract_description(self, repo_path: str) -> Optional[str]:
        """
        从仓库提取描述信息

        TODO: 待实现，可以从以下来源提取：
        - README.md 的第一段
        - package.json 的 description
        - setup.py 的 description
        - GitHub API

        Args:
            repo_path: 仓库本地路径

        Returns:
            描述字符串或 None
        """
        # TODO: 实现描述提取逻辑
        return None

    def suggest_categories(self, repo_path: str, name: str) -> List[str]:
        """
        建议分类标签

        TODO: 待实现，可以从以下来源推断：
        - 库名称关键词
        - README 内容分析
        - 依赖项分析

        Args:
            repo_path: 仓库本地路径
            name: 库名称

        Returns:
            分类列表
        """
        # TODO: 实现分类建议逻辑
        return []

    def detect_language_from_repo(self, repo_path: str) -> List[str]:
        """
        从仓库目录检测编程语言

        扫描仓库中的源文件，统计各语言占比

        Args:
            repo_path: 仓库本地路径

        Returns:
            语言列表（按占比排序）
        """
        if not os.path.exists(repo_path):
            return []

        extension_counts = Counter()

        # 遍历仓库目录
        for root, dirs, files in os.walk(repo_path):
            # 跳过隐藏目录和常见的非源代码目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                'node_modules', 'vendor', 'third_party', 'build', 'dist', 'target',
                '__pycache__', '.git', 'venv', 'env'
            ]]

            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext:
                    extension_counts[ext] += 1

        # 转换为语言列表
        extensions = [ext for ext, _ in extension_counts.most_common()]
        languages = self.detect_language_from_files(extensions)

        return languages

    def build_library_info(
        self,
        name: str,
        git_url: str,
        vendor: Optional[str] = None,
        homepage: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        purl: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> LibraryInfo:
        """
        构建库元数据

        Args:
            name: 库名称
            git_url: Git 仓库 URL
            vendor: 供应商（如果为 None，尝试从 URL 解析）
            homepage: 主页 URL（如果为 None，尝试从 git URL 推断）
            description: 描述
            language: 编程语言列表
            categories: 分类列表
            purl: Package URL（如果为 None，自动生成）
            alias: 库别名

        Returns:
            LibraryInfo 对象
        """
        # 如果没有提供 vendor，尝试从 URL 解析
        if not vendor:
            owner, _, _ = self.parse_git_url(git_url)
            vendor = owner

        # 如果没有提供 homepage，从 git URL 推断
        if not homepage:
            homepage = self.build_homepage_url(git_url)

        # 如果没有提供 purl，自动生成
        if not purl:
            purl = self.generate_purl(git_url, name)

        return LibraryInfo(
            name=name,
            git_url=git_url,
            vendor=vendor,
            homepage=homepage,
            description=description,
            language=language or [],
            categories=categories or [],
            purl=purl,
            alias=alias,
        )

    def detect_language_from_files(self, file_extensions: List[str]) -> List[str]:
        """
        根据文件扩展名推断编程语言

        Args:
            file_extensions: 文件扩展名列表

        Returns:
            语言列表
        """
        extension_to_language = {
            '.c': 'C',
            '.h': 'C',
            '.cpp': 'C++',
            '.cc': 'C++',
            '.cxx': 'C++',
            '.hpp': 'C++',
            '.py': 'Python',
            '.java': 'Java',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
        }

        languages = set()
        for ext in file_extensions:
            ext_lower = ext.lower()
            if ext_lower in extension_to_language:
                languages.add(extension_to_language[ext_lower])

        return sorted(list(languages))
