#!/usr/bin/env python3
"""
Conan包和版本搜索工具
"""
import json
import os
import subprocess

from environs import Env

env = Env()
env.read_env()

def get_raw_output():
    """调用命令，获取原始输出，保存到txt"""
    try:
        cmd = ['conan', 'search', '*', '-r=conancenter']
        print(f"执行命令: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        print(f"返回码: {result.returncode}")
        print(f"输出长度: {len(result.stdout)} 字符")

        return result.stdout

    except Exception as e:
        print(f"获取输出失败: {e}")
        return ""


def parse_to_json(raw_output, json_path):
    """解析输出，生成JSON"""
    packages = {}
    for line in raw_output.split('\n')[1:]:
        line = line.strip()

        if "/" in line:
            lib,ver = line.split('/')
            packages[lib].append(ver)
        else:
            lib = line
            packages[lib] = []

    # 移除空的包
    packages = {k: v for k, v in packages.items() if v}

    # 保存JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(packages, f, indent=2, ensure_ascii=False)

    print(f"找到 {len(packages)} 个包")
    print(f"JSON已保存到: {json_path}")

    return packages


def main():
    # 从conan官方获取列表，然后保存到json
    from data_management.benchmark_management.conan_benchmark_generation.paths import CONAN_LIBS_JSON
    conan_libs_json = CONAN_LIBS_JSON

    # 1. 获取原始输出
    raw_output = get_raw_output()
    parse_to_json(raw_output, conan_libs_json)


if __name__ == '__main__':
    main()