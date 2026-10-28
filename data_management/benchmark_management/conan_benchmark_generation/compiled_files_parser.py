

import json
import os
import sys
from typing import List

from environs import Env
from loguru import logger
from tqdm import tqdm

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")



def list_dirs(path: str) -> List[str]:
    """
    列出来不是mac文件夹的那些文件夹

    :param path:
    :return:
    """
    dirs = []
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path) and not entry.startswith("."):
            dirs.append(entry)

    return dirs


def get_tpl_root_path(path):
    """
    从给定目录开始找，直到找到一个目录，目录下有conaninfo.txt，返回这个目录。
    如果没找到，或者某一层空了，返回None。
    :param path:
    :return:
    """
    if not os.path.exists(path) or not os.path.isdir(path):
        return None

    # 检查当前目录是否有conaninfo.txt
    conaninfo_path = os.path.join(path, "conaninfo.txt")
    if os.path.exists(conaninfo_path):
        return path

    # 递归搜索所有子目录
    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                result = get_tpl_root_path(item_path)
                if result is not None:
                    return result
    except (OSError, PermissionError):
        pass

    return None


def cal_sha256(file_path):
    """
    计算文件的SHA256哈希值
    :param file_path: 文件路径
    :return: SHA256哈希值
    """
    import hashlib

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # 逐块读取文件内容
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def _get_binaries(path):
    """
    获取二进制文件的路径
    :param path:
    :return:
    """
    if not os.path.exists(path):
        return None

    binary_paths = {}
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        # print()
        # print(entry)
        # print(full_path)
        # print(os.path.getsize(full_path))
        # print(f"is file: {os.path.isfile(full_path)}")
        # print(f"is link: {os.path.islink(full_path)}")
        if os.path.isfile(full_path) and not os.path.islink(full_path) and not entry.startswith("."):
            binary_sha256 = cal_sha256(full_path)
            if (binary_info:= binary_paths.get(binary_sha256)) is None:
                binary_paths[binary_sha256] = binary_info = {
                    "size": os.path.getsize(full_path)/1024,
                    "paths": []
                }
            binary_info['paths'].append(full_path)

    return binary_paths


def get_binaries(path):
    bin_path = os.path.join(path, "bin")
    lib_path = os.path.join(path, "lib")

    bin_bin_paths = _get_binaries(bin_path)
    lib_bin_paths = _get_binaries(lib_path)
    return bin_bin_paths, lib_bin_paths


def parse_tpl_dir(tpl_name, tpl_path: str):
    # 解析模板目录
    tpl_root_path = get_tpl_root_path(tpl_path)

    # 获取二进制文件路径
    bin_bin_paths, lib_bin_paths = get_binaries(tpl_root_path)

    # print(f"bin_bin_paths: {bin_bin_paths}")
    # print(f"lib_bin_paths: {lib_bin_paths}")

    return {
        "tpl_name": tpl_name,
        "bin_bins": bin_bin_paths,
        "lib_bins": lib_bin_paths
    }


def parse_lib_dir(lib_name, lib_dir: str):
    result = {}

    for version in list_dirs(lib_dir):
        lib_ver_dir = os.path.join(lib_dir, version)
        result[version] = {}

        for compile_config in list_dirs(lib_ver_dir):
            compile_config_dir = os.path.join(lib_ver_dir, compile_config)
            # 有可能编译失败，产生空文件夹，跳过。
            if not os.listdir(compile_config_dir):
                continue
            metadata_json = os.path.join(compile_config_dir, "metadata.json")
            full_deploy_dir = os.path.join(compile_config_dir, "full_deploy")
            host_dir = os.path.join(full_deploy_dir, "host")

            result[version][compile_config] = {
                "metadata_json": metadata_json,
                "binary_info": {}
            }

            for tpl_name in list_dirs(host_dir):
                tpl_path = os.path.join(host_dir, tpl_name)
                tpl_info = parse_tpl_dir(tpl_name, tpl_path)

                result[version][compile_config]["binary_info"][tpl_name] = {
                    "tpl_path": tpl_path,
                    "tpl_info": tpl_info
                }

    return result



def main():
    # paths
    from data_management.benchmark_management.conan_benchmark_generation import paths
    os.makedirs(paths.BENCHMARK_META_DIR, exist_ok=True)
    conan_libs_builder_output_dir = paths.BUILDER_OUTPUT_DIR
    conan_lib_info_json = paths.LIB_INFO_JSON

    # 解析每个库的信息
    lib_info_dict= {}
    for lib_name in tqdm(list(list_dirs(conan_libs_builder_output_dir)), desc='Parsing libraries'):
        lib_dir = os.path.join(conan_libs_builder_output_dir, lib_name)
        lib_info = parse_lib_dir(lib_name, lib_dir)
        lib_info_dict[lib_name] = lib_info

    with open(conan_lib_info_json, "w") as f:
        json.dump(lib_info_dict, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()

