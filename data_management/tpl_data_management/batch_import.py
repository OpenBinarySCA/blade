"""
批量导入 TPL 库
从 JSON 文件读取库列表，批量添加到数据库
"""
import sys
import json
from pathlib import Path

# 强制关闭 stdout 缓冲，确保日志实时输出
sys.stdout.reconfigure(line_buffering=True)

from tpl_manager import TPLManager


def batch_import_from_json(
    json_file: str = "tpl_data_public_meta_libraries.json",
    skip_existing: bool = True,
    max_feature_versions: int = 10,
    process_num: int = 4,
):
    """
    从 JSON 文件批量导入库

    Args:
        json_file: JSON 文件路径（相对于当前目录或绝对路径）
        skip_existing: 是否跳过已存在的库
        max_feature_versions: 每个库最多提取特征的版本数
        process_num: 并行进程数
    """
    # 读取 JSON 文件
    json_path = Path(__file__).parent / json_file
    with open(json_path, 'r', encoding='utf-8') as f:
        libraries_data = json.load(f)

    print(f"读取到 {len(libraries_data)} 个库")

    # 转换为 (name, vendor, giturl) 格式
    libraries = [
        (lib['name'], lib['vendor'], lib['giturl'])
        for lib in libraries_data
    ]

    # 创建 TPLManager 并批量添加
    manager = TPLManager(
        source_dir="tmp/source_code",
        features_dir="tmp/features",
        max_feature_versions=max_feature_versions,
        process_num=process_num,
        show_progress=True,
        filter_prerelease=True,
    )
    results = manager.batch_add_libraries(libraries, skip_existing=skip_existing)
    return results

def main():
    batch_import_from_json(
        json_file=str(Path(__file__).resolve().parent / "tpl_data_public_meta_libraries.json"),
        skip_existing = True,
        max_feature_versions = 10,
        process_num = 32,
    )


if __name__ == '__main__':
    main()