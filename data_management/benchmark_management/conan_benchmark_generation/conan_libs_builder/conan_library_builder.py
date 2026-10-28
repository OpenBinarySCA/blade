#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Dict, List, Any

from environs import Env
from loguru import logger

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")


class ConanBuildError(Exception):
    """Conan编译相关错误"""
    pass


class ConanLibraryBuilder:
    """统一的Conan库编译器 - 全部使用Profile"""

    def __init__(self):
        self.temp_dir = None
        self.conan_version = None

    def __enter__(self):
        """创建临时工作目录"""
        self.temp_dir = tempfile.mkdtemp(prefix='conan_build_')
        logger.info(f"创建临时工作目录: {self.temp_dir}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时目录: {self.temp_dir}")

    def _run_command(self, cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        """执行命令"""
        logger.debug(f"执行命令: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=True,
                cwd=self.temp_dir
            )
            if result.stdout and capture_output:
                logger.debug(f"命令输出: {result.stdout}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"命令执行失败: {e}")
            if e.stderr:
                logger.error(f"错误输出: {e.stderr}")
            raise ConanBuildError(f"命令执行失败: {' '.join(cmd)}")

    def build_library(self,
                      library_name: str,
                      library_version: str,
                      profile: str,
                      output_dir: str) -> Dict[str, Any]:
        """
        统一的编译方法 - 所有配置都使用Profile

        Args:
            library_name: 组件名称 (如 'fmt')
            library_version: 组件版本 (如 '9.1.0')
            profile: profile名称 (如 'x86_64-gcc-release-shared')
            output_dir: 输出目录

        Returns:
            包含编译结果和元信息的字典
        """

        logger.info(f"开始编译库: {library_name}/{library_version}")
        logger.info(f"使用Profile: {profile}")
        logger.info(f"输出目录: {output_dir}")

        # 1. 检查Conan环境
        self._check_conan()

        # 2. 创建conanfile.txt（告诉conan要编译什么库）
        self._create_conanfile(library_name, library_version)

        # 3. 获取库信息
        library_info = self._get_library_info(library_name, library_version)

        # 4. 分析依赖关系
        dependency_info = self._analyze_dependencies(library_name, library_version, profile)

        # 5. 执行编译和部署
        self._install_and_deploy(library_name, library_version, profile, output_dir)

        # 6. 生成完整的元信息
        metadata = self._generate_final_metadata(
            library_info, profile, dependency_info, output_dir
        )

        logger.info(f"编译完成，输出目录: {output_dir}")
        return metadata

    def _check_conan(self):
        """检查Conan是否可用"""
        try:
            result = self._run_command(['conan', '--version'])
            version_line = result.stdout.strip()
            logger.info(f"检测到Conan版本: {version_line}")

            if not version_line.startswith('Conan version 2.'):
                raise ConanBuildError(f"需要Conan 2.x版本，当前版本: {version_line}")

            self.conan_version = version_line
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ConanBuildError("未找到Conan命令，请确保已安装Conan 2.x")

    def _create_conanfile(self, library_name: str, library_version: str):
        """创建conanfile.txt（告诉conan要编译什么库）"""
        conanfile_content = f"""[requires]
{library_name}/{library_version}

[generators]
CMakeDeps
CMakeToolchain
"""
        conanfile_path = os.path.join(self.temp_dir, 'conanfile.txt')
        with open(conanfile_path, 'w') as f:
            f.write(conanfile_content)
        logger.debug(f"创建conanfile.txt: {conanfile_path}")

    def _get_library_info(self, library_name: str, library_version: str) -> Dict[str, Any]:
        """获取库的基本信息"""
        logger.info(f"获取库信息: {library_name}/{library_version}")

        # 创建临时目录获取库信息
        info_temp_dir = tempfile.mkdtemp(prefix='conan_info_')

        try:
            # 创建临时conanfile.py
            conanfile_py = f"""from conan import ConanFile

class TempConan(ConanFile):
    requires = "{library_name}/{library_version}"
"""
            conanfile_path = os.path.join(info_temp_dir, 'conanfile.py')
            with open(conanfile_path, 'w') as f:
                f.write(conanfile_py)

            # 获取库信息
            cmd = [
                'conan', 'graph', 'info', info_temp_dir,
                '--format=json',
                '-r=conancenter'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            graph_data = json.loads(result.stdout)

            # 提取目标库信息
            for node_id, node in graph_data.get('graph', {}).get('nodes', {}).items():
                if node.get('name') == library_name and node.get('version') == library_version:
                    return {
                        'name': node.get('name', library_name),
                        'version': node.get('version', library_version),
                        'description': node.get('description', ''),
                        'license': node.get('license', ''),
                        'homepage': node.get('homepage', ''),
                        'url': node.get('url', ''),
                        'topics': node.get('topics', [])
                    }

            # 如果没找到，返回基本信息
            return {
                'name': library_name,
                'version': library_version,
                'description': '',
                'license': '',
                'homepage': '',
                'url': '',
                'topics': []
            }

        except Exception as e:
            logger.warning(f"无法获取库详细信息: {e}")
            return {
                'name': library_name,
                'version': library_version,
                'description': '',
                'license': '',
                'homepage': '',
                'url': '',
                'topics': []
            }
        finally:
            if os.path.exists(info_temp_dir):
                shutil.rmtree(info_temp_dir)

    def _analyze_dependencies(self, library_name: str, library_version: str, profile: str) -> Dict[str, Any]:
        """分析依赖关系"""
        logger.info(f"分析依赖关系: {library_name}/{library_version}")

        # 构建conan graph info命令（使用profile）
        cmd = [
            'conan', 'graph', 'info', '.',
            '--format=json',
            f'--profile:host={profile}',
            '--profile:build=default',
            '-r=conancenter'
        ]

        try:
            result = self._run_command(cmd)
            graph_data = json.loads(result.stdout)

            # 添加调试输出
            # logger.debug("=== 原始依赖图数据 ===")
            # logger.debug(json.dumps(graph_data, indent=2))


            # 解析依赖图谱
            return self._parse_dependency_graph(graph_data, library_name)

        except Exception as e:
            logger.error(f"分析依赖关系失败: {e}")
            raise ConanBuildError(f"无法分析依赖关系: {e}")

    def _parse_dependency_graph(self, graph_data: Dict[str, Any], target_lib: str) -> Dict[str, Any]:
        """解析依赖图谱"""
        nodes = graph_data.get('graph', {}).get('nodes', {})

        # 找到目标库节点
        target_node_id = None
        for node_id, node in nodes.items():
            if node.get('name') == target_lib and node.get('recipe') != 'Consumer':
                target_node_id = node_id
                break

        if not target_node_id:
            raise ConanBuildError(f"未找到目标库 {target_lib}")

        # 构建依赖关系图 - 修复：使用 dependencies 字段而不是 requires
        adjacency = {}
        for node_id in nodes:
            adjacency[node_id] = []

        for node_id, node in nodes.items():
            dependencies = node.get('dependencies', {})  # 修复：使用正确的字段
            for dep_node_id in dependencies.keys():
                adjacency[node_id].append(dep_node_id)

        # 生成扁平依赖列表
        flat_deps = {}

        def traverse(node_id: str, level: int, path: List[str]):
            node = nodes.get(node_id)
            if not node or not node.get('name'):
                return

            name = node.get('name')
            version = node.get('version')
            key = f"{name}/{version}"

            # 获取链接类型
            shared_option = node.get('options', {}).get('shared', False)
            link_type = 'shared' if shared_option else 'static'

            # 对于 header-only 库，从 package_type 判断
            package_type = node.get('package_type', '')
            if package_type == 'header-library':
                link_type = 'header-only'

            if key not in flat_deps:
                flat_deps[key] = {
                    'name': name,
                    'version': version,
                    'link_type': link_type,
                    'level': level,
                    'paths': []
                }

            flat_deps[key]['paths'].append(' -> '.join(path + [name]))

            # 递归处理依赖
            for child_id in adjacency.get(node_id, []):
                traverse(child_id, level + 1, path + [name])

        traverse(target_node_id, 0, [])

        # 转换为列表并生成汇总
        dependency_list = list(flat_deps.values())

        summary = {
            'total_packages': len(dependency_list),
            'direct_dependencies': len([d for d in dependency_list if d['level'] == 1]),
            'max_depth': max([d['level'] for d in dependency_list]) if dependency_list else 0,
            'shared_libraries': [d['name'] for d in dependency_list if d['link_type'] == 'shared'],
            'static_libraries': [d['name'] for d in dependency_list if d['link_type'] == 'static'],
            'header_only_libraries': [d['name'] for d in dependency_list if d['link_type'] == 'header-only']
        }

        return {
            'dependencies': dependency_list,
            'summary': summary
        }

    def _install_and_deploy(self, library_name: str, library_version: str, profile: str, output_dir: str):
        """执行编译和部署"""
        logger.info(f"开始编译和部署: {library_name}/{library_version}")

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 构建conan install命令（使用profile）
        cmd = [
            'conan', 'install', '.',
            '--build=missing',
            '--deployer=full_deploy',
            f'--deployer-folder={output_dir}',
            f'--profile:host={profile}',
            '--profile:build=default',
            '-r=conancenter'
        ]

        try:
            logger.info(f"执行命令: {' '.join(cmd)}")
            self._run_command(cmd, capture_output=False)
            logger.info("编译和部署完成")

            # 简单验证
            file_count = sum(len(files) for _, _, files in os.walk(output_dir))
            logger.info(f"部署文件数量: {file_count}")

        except Exception as e:
            raise ConanBuildError(f"编译和部署失败: {e}")

    def _generate_final_metadata(self, library_info: Dict[str, Any], profile: str,
                                 dependency_info: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
        """生成完整的元信息"""

        metadata = {
            'target_library': library_info,
            'build_configuration': {
                'profile': profile
            },
            'dependencies': dependency_info,
            'build_info': {
                'timestamp': datetime.now().isoformat(),
                'conan_version': self.conan_version,
                'output_directory': output_dir
            }
        }

        # 保存元信息文件
        metadata_path = os.path.join(output_dir, 'metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"元信息已保存到: {metadata_path}")
        return metadata


# =============================================================================
# 便捷接口函数
# =============================================================================

def build_single_library(library_name: str,
                         library_version: str,
                         profile: str,
                         output_dir: str) -> Dict[str, Any]:
    """
    便捷的单库编译函数

    Args:
        library_name: 组件名称 (如 'fmt')
        library_version: 组件版本 (如 '9.1.0')
        profile: profile名称 (如 'x86_64-gcc-release-shared')
        output_dir: 输出目录

    Returns:
        编译结果和元信息
    """

    with ConanLibraryBuilder() as builder:
        return builder.build_library(
            library_name=library_name,
            library_version=library_version,
            profile=profile,
            output_dir=output_dir
        )


def build_multiple_profiles(library_name: str,
                            library_version: str,
                            profile_dir: str,
                            base_output_dir: str) -> Dict[str, Any]:
    """
    编译多种profile配置

    Args:
        library_name: 库名称
        library_version: 库版本
        profile_dir: profile文件所在目录
        base_output_dir: 基础输出目录

    Returns:
        各profile的编译结果
    """

    # 扫描profile目录，获取所有profile文件
    if not os.path.exists(profile_dir):
        raise ConanBuildError(f"Profile目录不存在: {profile_dir}")

    profile_files = [f for f in os.listdir(profile_dir)
                     if os.path.isfile(os.path.join(profile_dir, f)) and not f.startswith('.')]

    if not profile_files:
        raise ConanBuildError(f"Profile目录中没有找到profile文件: {profile_dir}")

    logger.info(f"找到{len(profile_files)}个profile文件: {profile_files}")

    results = {}

    for profile_file in profile_files:
        profile_name = profile_file  # profile文件名就是profile名称
        profile_path = os.path.join(profile_dir, profile_name)
        logger.info(f"开始编译Profile: {profile_name}")

        # 构建该profile的输出目录
        output_dir = os.path.join(base_output_dir, f"{library_name}_{library_version}_{profile_name}")

        try:
            # 执行编译
            metadata = build_single_library(
                library_name=library_name,
                library_version=library_version,
                profile=profile_path,
                output_dir=output_dir
            )

            results[profile_name] = {
                'status': 'success',
                'profile': profile_name,
                'output_dir': output_dir,
                'metadata': metadata
            }
            logger.info(f"✅ {profile_name} 编译成功")

        except Exception as e:
            results[profile_name] = {
                'status': 'failed',
                'profile': profile_name,
                'output_dir': output_dir,
                'error': str(e)
            }
            logger.error(f"❌ {profile_name} 编译失败: {e}")

    return results
