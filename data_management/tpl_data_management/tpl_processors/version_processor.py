"""
Version Processor - 版本处理

获取、过滤和选择版本
支持：
- 从 Git 获取所有版本
- 过滤预发布版本
- 智能选择版本提取特征
- 解析标准化版本号 (semantic version)
"""
import re
from datetime import datetime
from typing import List, Optional, Tuple

from git import Repo
from loguru import logger

from .interface import VersionInfo


class VersionProcessor:
    """版本处理器"""

    # 预发布版本关键词
    PRERELEASE_KEYWORDS = [
        'alpha', 'beta', 'rc', 'pre', 'dev', 'snapshot',
        'nightly', 'canary', 'preview', 'test', 'cve'
    ]

    # 版本号解析模式（按优先级排序）
    VERSION_PATTERNS = [
        # 标准 semver: v1.2.3, 1.2.3, v1.2.3-beta
        r'v?(\d+)\.(\d+)\.(\d+)(?:[.\-_](\d+))?',
        # 两段版本: v1.2, 1.2
        r'v?(\d+)\.(\d+)(?:[.\-_](\d+))?',
        # release-1.2.3, version-1.2.3
        r'(?:release|version|ver)[.\-_]?v?(\d+)\.(\d+)(?:\.(\d+))?',
        # OpenSSL 风格: openssl-1.1.1k
        r'[a-zA-Z]+[.\-_](\d+)\.(\d+)\.(\d+)([a-z])?',
    ]

    def __init__(self, max_feature_versions: int = 10):
        """
        初始化版本处理器

        Args:
            max_feature_versions: 最多提取特征的版本数量
        """
        self.max_feature_versions = max_feature_versions

    def parse_semantic_version(self, tag: str) -> Optional[str]:
        """
        从 tag 解析标准化版本号

        将各种版本格式标准化为 semver 格式: MAJOR.MINOR.PATCH

        支持的格式:
        - v1.2.3, 1.2.3, v1.2.3-beta -> 1.2.3
        - v1.2, 1.2 -> 1.2.0
        - release-1.2.3, version-1.2.3 -> 1.2.3
        - openssl-1.1.1k -> 1.1.1

        Args:
            tag: 版本标签字符串

        Returns:
            标准化版本号（如 "1.2.3"）或 None
        """
        if not tag:
            return None

        # 尝试各种模式
        for pattern in self.VERSION_PATTERNS:
            match = re.search(pattern, tag, re.IGNORECASE)
            if match:
                groups = match.groups()
                # 提取数字部分
                parts = [g for g in groups if g and g.isdigit()]

                if len(parts) >= 2:
                    major = parts[0]
                    minor = parts[1]
                    patch = parts[2] if len(parts) >= 3 else '0'
                    return f"{major}.{minor}.{patch}"

        return None

    def get_all_versions(self, repo_path: str) -> List[VersionInfo]:
        """
        获取仓库的所有版本信息

        Args:
            repo_path: 仓库路径

        Returns:
            版本信息列表
        """
        versions = []

        try:
            repo = Repo(repo_path)
            tags = sorted(repo.tags, key=lambda t: t.name)

            for tag in tags:
                try:
                    commit = tag.commit
                    commit_id = str(commit)
                    commit_datetime = commit.committed_datetime

                    # 尝试获取 tag 时间
                    tag_datetime = None
                    if hasattr(tag, 'tag') and tag.tag:
                        try:
                            tag_datetime = tag.tag.tagged_date
                            if isinstance(tag_datetime, int):
                                tag_datetime = datetime.fromtimestamp(tag_datetime)
                        except:
                            pass

                    # 解析标准化版本号
                    semantic_version = self.parse_semantic_version(tag.name)

                    version_info = VersionInfo(
                        tag=tag.name,
                        commit_id=commit_id,
                        commit_datetime=commit_datetime,
                        tag_datetime=tag_datetime,
                        semantic_version_str=semantic_version,
                    )
                    versions.append(version_info)

                except Exception as e:
                    logger.warning(f"获取 tag {tag.name} 信息失败: {e}")
                    continue

            return versions

        except Exception as e:
            logger.error(f"获取版本列表失败: {e}")
            return []

    def filter_release_versions(self, versions: List[VersionInfo]) -> List[VersionInfo]:
        """
        过滤预发布版本

        Args:
            versions: 版本列表

        Returns:
            过滤后的版本列表
        """
        filtered = []
        for version in versions:
            tag_lower = version.tag.lower()
            is_prerelease = any(keyword in tag_lower for keyword in self.PRERELEASE_KEYWORDS)
            if not is_prerelease:
                filtered.append(version)

        return filtered

    def select_versions_for_feature_extraction(
        self,
        versions: List[VersionInfo],
        max_count: Optional[int] = None
    ) -> List[VersionInfo]:
        """
        智能选择提取特征的版本（平均分布，必含首尾）

        Args:
            versions: 版本列表
            max_count: 最多选择的版本数（默认使用初始化时的值）

        Returns:
            标记后的版本列表
        """
        if max_count is None:
            max_count = self.max_feature_versions

        if not versions:
            return versions

        # 重置所有版本的选中状态
        for v in versions:
            v.is_selected_for_feature_extraction = False

        if len(versions) <= max_count:
            # 全部选中
            for v in versions:
                v.is_selected_for_feature_extraction = True
            selected_tags = [v.tag for v in versions]
        else:
            # 智能选取：首尾必选，中间平均分布
            selected_indices = [0]  # 最早版本

            # 计算中间需要取多少个
            middle_count = max_count - 2
            if middle_count > 0:
                step = (len(versions) - 2) / (middle_count + 1)
                for i in range(1, middle_count + 1):
                    idx = int(i * step)
                    if idx not in selected_indices:
                        selected_indices.append(idx)

            selected_indices.append(len(versions) - 1)  # 最晚版本

            # 去重并排序
            selected_indices = sorted(set(selected_indices))

            # 标记选中的版本
            selected_tags = []
            for idx in selected_indices:
                versions[idx].is_selected_for_feature_extraction = True
                selected_tags.append(versions[idx].tag)

        # logger.debug(f"选择 {len(selected_tags)}/{len(versions)} 个版本提取特征: {selected_tags}")
        return versions

    def get_selected_versions(self, versions: List[VersionInfo]) -> List[VersionInfo]:
        """
        获取被选中提取特征的版本

        Args:
            versions: 版本列表

        Returns:
            被选中的版本列表
        """
        return [v for v in versions if v.is_selected_for_feature_extraction]

    def get_latest_version(self, versions: List[VersionInfo]) -> Optional[VersionInfo]:
        """
        获取最新版本

        Args:
            versions: 版本列表

        Returns:
            最新版本或 None
        """
        if not versions:
            return None

        # 按 commit_datetime 排序，取最新的
        sorted_versions = sorted(
            versions,
            key=lambda v: v.commit_datetime or datetime.min,
            reverse=True
        )
        return sorted_versions[0]

    def sort_versions_by_time(
        self,
        versions: List[VersionInfo],
        ascending: bool = True
    ) -> List[VersionInfo]:
        """
        按时间排序版本

        Args:
            versions: 版本列表
            ascending: 是否升序

        Returns:
            排序后的版本列表
        """
        return sorted(
            versions,
            key=lambda v: v.commit_datetime or datetime.min,
            reverse=not ascending
        )

    def get_default_branch_as_version(self, repo_path: str) -> List[VersionInfo]:
        """
        获取默认分支作为唯一版本（当没有 tag 时的 fallback）

        Args:
            repo_path: 仓库路径

        Returns:
            包含默认分支版本信息的列表（只有一个元素）
        """
        try:
            repo = Repo(repo_path)

            # 获取默认分支名称
            try:
                # 尝试从 HEAD 获取当前分支
                default_branch = repo.active_branch.name
            except TypeError:
                # HEAD detached，尝试从 remote 获取
                try:
                    default_branch = repo.remotes.origin.refs.HEAD.reference.remote_head
                except:
                    default_branch = "main"  # fallback

            # 获取 HEAD commit 信息
            commit = repo.head.commit
            commit_id = str(commit)
            commit_datetime = commit.committed_datetime

            version_info = VersionInfo(
                tag=default_branch,  # 使用分支名作为 tag
                commit_id=commit_id,
                commit_datetime=commit_datetime,
                tag_datetime=None,
                semantic_version_str=None,  # 分支没有 semantic version
                is_selected_for_feature_extraction=True,  # 直接标记为选中
            )

            # logger.info(f"使用默认分支作为版本: {default_branch} (commit: {commit_id[:8]})")
            return [version_info]

        except Exception as e:
            logger.error(f"获取默认分支版本失败: {e}")
            return []
