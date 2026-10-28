import hashlib


def calculate_sha256(file_path):
    """
    计算文件的SHA-256哈希值

    参数:
        file_path (str): 文件的路径

    返回:
        str: 文件的SHA-256哈希值（十六进制字符串）
    """
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            # 逐块读取文件以处理大文件
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except IOError as e:
        print(f"无法读取文件: {e}")
        return None