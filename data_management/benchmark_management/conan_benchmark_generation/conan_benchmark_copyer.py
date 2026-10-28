import os
import sys

from environs import Env
from loguru import logger
from tqdm import tqdm


import subprocess
from tqdm import tqdm

from evaluation.tpl_detection_evaluation.interface import Benchmark as GeneralBenchmark

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")



def copy_test_cases_from_to(benchmark: GeneralBenchmark, from_dir: str, to_dir: str):

    for test_case in tqdm(benchmark.test_cases, desc="Copying test cases"):
        rel_path = test_case.test_binary.relative_path
        from_path = os.path.join(from_dir, rel_path)
        to_path = os.path.join(to_dir, rel_path)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(to_path), exist_ok=True)

        # Copy the file if it exists
        if os.path.exists(to_path):
            continue
        if os.path.exists(from_path):
            os.system(f"cp '{from_path}' '{to_path}'")
        else:
            print(f"Warning: {from_path} does not exist, skipping copy.")



def strip_all(benchmark_test_case_dir: str):
    """
    递归遍历目录，对所有二进制文件执行strip操作
    根据文件架构自动选择合适的strip工具
    """

    def get_file_arch(file_path):
        """使用file命令获取文件架构信息"""
        try:
            result = subprocess.run(['file', file_path],
                                    capture_output=True, text=True, check=True)
            file_info = result.stdout.lower()
            if 'x86-64' in file_info or 'x86_64' in file_info:
                return 'x86_64'
            elif 'arm aarch64' in file_info or 'aarch64' in file_info:
                return 'aarch64'
            elif 'arm' in file_info and ('32-bit' in file_info or 'armhf' in file_info):
                return 'arm32'
            else:
                return 'unknown'
        except subprocess.CalledProcessError:
            return 'unknown'

    def strip_file(file_path, arch):
        """根据架构选择合适的strip工具"""
        strip_commands = {
            'x86_64': 'strip',
            'aarch64': 'aarch64-linux-gnu-strip',
            'arm32': 'arm-linux-gnueabihf-strip'
        }

        if arch not in strip_commands:
            return False, f"不支持的架构: {arch}"

        strip_cmd = strip_commands[arch]

        # 检查文件权限
        if not os.access(file_path, os.W_OK):
            return False, "文件无写权限"

        try:
            result = subprocess.run([strip_cmd, file_path],
                                    capture_output=True, text=True, check=True)
            return True, "成功"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()

            # 处理常见错误情况
            if "has no sections" in error_msg:
                return False, "文件已被压缩(UPX)或无sections"
            elif "Permission denied" in error_msg:
                return False, "权限不足"
            elif "file format not recognized" in error_msg:
                return False, "文件格式不支持strip"
            else:
                return False, f"strip错误: {error_msg}"
        except FileNotFoundError:
            return False, f"strip工具未找到: {strip_cmd}"

    # 统计信息
    success_count = 0
    upx_compressed_count = 0
    permission_denied_count = 0
    unknown_count = 0
    other_error_count = 0

    print(f"开始处理目录: {benchmark_test_case_dir}")
    print("正在收集文件信息...")

    # 首先收集所有文件用于进度条
    all_files = []
    for root, dirs, files in os.walk(benchmark_test_case_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                all_files.append(file_path)

    print(f"找到 {len(all_files)} 个文件，开始处理...")

    # 使用tqdm显示进度
    with tqdm(total=len(all_files), desc="Strip文件", unit="files") as pbar:
        for file_path in all_files:
            # 获取文件架构
            arch = get_file_arch(file_path)

            if arch == 'unknown':
                unknown_count += 1
                pbar.set_postfix({
                    "成功": success_count,
                    "UPX压缩": upx_compressed_count,
                    "权限": permission_denied_count,
                    "未知": unknown_count
                })
            else:
                # 执行strip操作
                success, error_msg = strip_file(file_path, arch)
                if success:
                    success_count += 1
                else:
                    # 根据错误类型分类统计
                    if "文件已被压缩(UPX)" in error_msg:
                        upx_compressed_count += 1
                        # UPX压缩文件不需要打印错误，这是正常情况
                    elif "权限不足" in error_msg:
                        permission_denied_count += 1
                        print(f"\n⚠️  权限问题: {file_path}")
                    else:
                        other_error_count += 1
                        print(f"\n✗ {file_path}: {error_msg}")

                pbar.set_postfix({
                    "成功": success_count,
                    "UPX压缩": upx_compressed_count,
                    "权限": permission_denied_count,
                    "其他错误": other_error_count
                })

            pbar.update(1)

    # 输出统计结果
    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"总文件数: {len(all_files)}")
    print(f"✅ 成功strip: {success_count}")
    print(f"📦 UPX压缩文件(跳过): {upx_compressed_count}")
    print(f"🔒 权限不足: {permission_denied_count}")
    print(f"❓ 未知文件类型: {unknown_count}")
    print(f"❌ 其他错误: {other_error_count}")
    print("=" * 60)

    # 如果有权限问题，给出解决建议
    if permission_denied_count > 0:
        print("\n💡 权限问题解决方案:")
        print("   可以尝试: chmod +w <文件路径>")
        print("   或者以管理员权限运行")




def main():
    # paths
    from data_management.benchmark_management.conan_benchmark_generation import paths
    conan_benchmark_path = paths.LIBRARY_BENCHMARK_JSON
    general_benchmark_path = paths.BENCHMARK_JSON
    conan_libs_builder_output_dir = paths.BUILDER_OUTPUT_DIR
    conan_benchmark_test_case_dir = paths.TEST_CASE_DIR

    benchmark = GeneralBenchmark.load_from_json_file(general_benchmark_path)

    # 复制文件
    copy_test_cases_from_to(benchmark, conan_libs_builder_output_dir, conan_benchmark_test_case_dir)

    # strip二进制文件
    strip_all(conan_benchmark_test_case_dir)

    # 更新sha256
    benchmark.update_sha256(conan_benchmark_test_case_dir)

    # 保存更新后的benchmark
    benchmark.dump_to_json_file(general_benchmark_path)

if __name__ == '__main__':
    """
    先运行generator 生成数据
    然后运行convert 转换格式
    最后，运行这个脚本：
        1. 二进制文件复制到目录
        2. Strip
        3. 重新计算sha256
        4. 更新到benchmark中。
    """
    main()