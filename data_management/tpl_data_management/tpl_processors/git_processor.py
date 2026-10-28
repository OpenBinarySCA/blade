"""
Git Processor - Git 相关操作

处理 Git 仓库的克隆、版本获取、checkout 等操作
"""
import os
import shutil
import tempfile
from typing import Optional, Tuple, List

from git import Repo
from git.exc import GitCommandError
from loguru import logger


class GitProcessor:
    """Git 操作处理器"""

    def __init__(self, source_dir: str = "tmp/source_code"):
        """
        初始化 Git 处理器

        Args:
            source_dir: 源代码存储目录
        """
        self.source_dir = source_dir

    def get_repo_path(self, name: str) -> str:
        """获取仓库本地路径"""
        return os.path.join(self.source_dir, name)

    def clone_repository(self, name: str, git_url: str, force: bool = False) -> Tuple[bool, str, bool]:
        """
        Clone 仓库到本地

        Args:
            name: 库名称
            git_url: Git 仓库 URL
            force: 如果存在是否强制重新 clone

        Returns:
            (success, repo_path or error_message, was_skipped)
            - success: 是否成功
            - repo_path or error_message: 成功时返回路径，失败时返回错误信息
            - was_skipped: 是否跳过（仓库已存在）
        """
        repo_path = self.get_repo_path(name)

        try:
            # 检查是否已存在
            if os.path.exists(repo_path):
                if os.path.exists(os.path.join(repo_path, '.git')):
                    if not force:
                        # 跳过，仓库已存在
                        return True, repo_path, True
                    else:
                        logger.debug(f"强制重新 clone，删除旧仓库: {repo_path}")
                        shutil.rmtree(repo_path)
                else:
                    # 目录存在但不是 git 仓库，删除它
                    shutil.rmtree(repo_path)

            # 确保父目录存在
            os.makedirs(self.source_dir, exist_ok=True)

            # Clone
            # logger.debug(f"开始 Clone: {git_url}")
            Repo.clone_from(git_url, repo_path)

            return True, repo_path, False

        except GitCommandError as e:
            error_msg = f"Git 命令错误: {e}"
            logger.error(error_msg)
            return False, error_msg, False
        except Exception as e:
            error_msg = f"Clone 失败: {e}"
            logger.error(error_msg)
            return False, error_msg, False

    def get_all_tags(self, repo_path: str) -> List[str]:
        """
        获取仓库的所有 tags

        Args:
            repo_path: 仓库路径

        Returns:
            排序后的 tag 列表
        """
        try:
            repo = Repo(repo_path)
            tags = sorted([tag.name for tag in repo.tags])
            logger.debug(f"获取到 {len(tags)} 个 tags")
            return tags
        except Exception as e:
            logger.error(f"获取 tags 失败: {e}")
            return []

    def checkout_version(self, repo_path: str, tag: str, stash_first: bool = True) -> bool:
        """
        Checkout 到指定版本

        Args:
            repo_path: 仓库路径
            tag: 版本标签
            stash_first: 是否先 stash 当前更改

        Returns:
            是否成功
        """
        try:
            repo = Repo(repo_path)

            # 尝试 stash
            if stash_first:
                try:
                    repo.git.stash('save', 'auto stash before checkout')
                except:
                    pass

            # Checkout
            if tag == 'HEAD':
                return True

            repo.git.checkout(tag, force=True)
            # logger.debug(f"Checkout 到 {tag}")
            return True

        except Exception as e:
            logger.error(f"Checkout {tag} 失败: {e}")
            return False

    def get_commit_info(self, repo_path: str, tag: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取指定 tag 的 commit 信息

        Args:
            repo_path: 仓库路径
            tag: 版本标签

        Returns:
            (commit_id, commit_datetime_iso) 或 (None, None)
        """
        try:
            repo = Repo(repo_path)

            if tag == 'HEAD':
                commit = repo.head.commit
            else:
                # 查找 tag 对应的 commit
                tag_ref = None
                for t in repo.tags:
                    if t.name == tag:
                        tag_ref = t
                        break

                if not tag_ref:
                    return None, None

                commit = tag_ref.commit

            commit_id = str(commit)
            commit_datetime = commit.committed_datetime.isoformat()
            return commit_id, commit_datetime

        except Exception as e:
            logger.error(f"获取 {tag} commit 信息失败: {e}")
            return None, None

    def get_remote_url(self, repo_path: str) -> Optional[str]:
        """
        获取仓库的 remote URL

        Args:
            repo_path: 仓库路径

        Returns:
            remote URL 或 None
        """
        try:
            repo = Repo(repo_path)
            return repo.remotes.origin.url
        except Exception as e:
            logger.error(f"获取 remote URL 失败: {e}")
            return None

    def copy_to_memory(self, repo_path: str, name: str) -> Tuple[Optional[str], Optional['Repo']]:
        """
        将仓库完整复制到内存临时目录（使用系统 cp 命令优化速度）

        Args:
            repo_path: 源仓库路径
            name: 库名称

        Returns:
            (内存路径, Repo 对象) 或 (None, None)
        """
        try:
            mem_temp_base = self._get_memory_temp_dir()
            mem_temp_dir = tempfile.mkdtemp(dir=mem_temp_base, prefix=f"{name}_")
            mem_repo_path = os.path.join(mem_temp_dir, name)

            # 使用系统 cp -a 命令代替 shutil.copytree（通常更快）
            # -a: 归档模式，保留所有属性，递归复制
            import subprocess
            result = subprocess.run(
                ['cp', '-a', repo_path, mem_repo_path],
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            if result.returncode != 0:
                logger.warning(f"cp 命令失败: {result.stderr}，回退到 shutil.copytree")
                # 清理可能的部分复制
                if os.path.exists(mem_repo_path):
                    shutil.rmtree(mem_repo_path)
                shutil.copytree(repo_path, mem_repo_path, symlinks=True)

            mem_repo = Repo(mem_repo_path)
            return mem_temp_dir, mem_repo

        except subprocess.TimeoutExpired:
            logger.error(f"复制超时（10分钟），仓库可能过大: {repo_path}")
            # 清理临时目录
            if os.path.exists(mem_temp_dir):
                shutil.rmtree(mem_temp_dir, ignore_errors=True)
            return None, None

        except Exception as e:
            logger.error(f"复制到内存失败: {e}")
            return None, None

    def cleanup_memory_dir(self, mem_temp_dir: str):
        """清理内存临时目录"""
        if mem_temp_dir and os.path.exists(mem_temp_dir):
            try:
                shutil.rmtree(mem_temp_dir)
                # logger.debug("已清理内存临时目录")
            except Exception as e:
                logger.warning(f"清理内存目录失败: {e}")

    def _get_memory_temp_dir(self) -> str:
        """获取内存临时目录（Linux 用 /dev/shm，其他用系统默认）"""
        if os.path.exists('/dev/shm'):
            return '/dev/shm'
        return tempfile.gettempdir()

    def delete_repository(self, name: str) -> bool:
        """
        删除本地仓库

        Args:
            name: 库名称

        Returns:
            是否成功
        """
        repo_path = self.get_repo_path(name)
        if os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
                logger.info(f"已删除仓库: {repo_path}")
                return True
            except Exception as e:
                logger.error(f"删除仓库失败: {e}")
                return False
        return True
