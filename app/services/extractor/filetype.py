import subprocess


def get_file_type(filepath: str) -> dict:
    """
    检测单个文件的类型，返回 MIME 类型、字符集和人类可读类型。

    :param filepath: 文件路径
    :return: dict, 包含 'mime_type', 'charset', 'readable_type'
    """
    try:
        # 获取 MIME 类型和字符集
        mime_result = subprocess.run(
            ['file', '--mime', filepath],
            capture_output=True, text=True, check=True
        ).stdout.strip()

        # 获取人类可读的文件类型
        readable_result = subprocess.run(
            ['file', filepath],
            capture_output=True, text=True, check=True
        ).stdout.strip()

        # 示例: "data/test_binary/kwrt.bin: application/x-tar; charset=binary"
        mime_info = mime_result.split(": ", 1)[1]
        mime_type, charset = mime_info.split(";")
        mime_type = mime_type.strip()
        charset = charset.replace("charset=", "").strip()

        # 示例: "data/test_binary/kwrt.bin: POSIX tar archive (GNU)"
        readable_type = readable_result.split(": ", 1)[1]

        return {
            "mime_type": mime_type,
            "charset": charset,
            "readable_type": readable_type
        }

    except Exception as e:
        return {
            "mime_type": None,
            "charset": None,
            "readable_type": f"检测失败: {e}"
        }

def get_file_type_by_bytes(file_bytes: bytes) -> dict:
    """
    通过文件字节流检测文件类型，返回 MIME 类型、字符集和人类可读类型。

    :param file_bytes: 文件字节流
    :return: dict, 包含 'mime_type', 'charset', 'readable_type'
    """
    try:
        # 获取 MIME 类型和字符集
        mime_result = subprocess.run(
            ['file', '--mime', '-'],
            input=file_bytes,
            capture_output=True, check=True
        ).stdout.decode().strip()

        # 获取人类可读的文件类型
        readable_result = subprocess.run(
            ['file', '-'],
            input=file_bytes,
            capture_output=True, check=True
        ).stdout.decode().strip()

        # 示例: "standard input: application/x-tar; charset=binary"
        mime_info = mime_result.split(": ", 1)[1]
        mime_type, charset = mime_info.split(";")
        mime_type = mime_type.strip()
        charset = charset.replace("charset=", "").strip()

        # 示例: "standard input: POSIX tar archive (GNU)"
        readable_type = readable_result.split(": ", 1)[1]

        return {
            "mime_type": mime_type,
            "charset": charset,
            "readable_type": readable_type
        }

    except Exception as e:
        return {
            "mime_type": None,
            "charset": None,
            "readable_type": f"检测失败: {e}"
        }