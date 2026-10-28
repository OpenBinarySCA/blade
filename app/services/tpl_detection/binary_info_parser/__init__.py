# Binary Info Parser Module
#
# 职责：从二进制文件提取信息，生成 TargetBinary
# - 使用 strings 命令提取字符串
# - 使用 lief 解析符号和动态库
# - 计算文件哈希

from .parser import BinaryInfoParser, calculate_file_sha256

__all__ = [
    'BinaryInfoParser',
    'calculate_file_sha256',
]
