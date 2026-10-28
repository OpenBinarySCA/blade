import os
import shutil
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import CopySource
from loguru import logger

from ...config import settings


# 初始化MinIO客户端
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)




def download_from_minio(minio_file_path: str, download_dir: str = None, bucket: str = None) -> str:
    """
    从MinIO下载文件到本地临时目录

    Args:
        minio_file_path: MinIO中的文件路径（对象key）
        download_dir: 下载目录
        bucket: 指定bucket，默认为OUTPUT_BUCKET

    Returns:
        str: 本地文件的完整路径
    """
    try:
        file_name = os.path.basename(minio_file_path)
        local_file_path = os.path.join(download_dir, file_name)

        # 确定使用哪个bucket
        if bucket is None:
            bucket = settings.MINIO_INPUT_BUCKET

        # 从MinIO下载文件
        minio_client.fget_object(bucket, minio_file_path, local_file_path)

        logger.info(f"File downloaded from MinIO to local: {local_file_path}")
        return local_file_path

    except S3Error as e:
        raise Exception(f"从MinIO下载文件失败: {e}")
    except Exception as e:
        raise Exception(f"下载文件时发生错误: {e}")


def upload_to_minio(local_file_path: str, minio_file_path: str = None, bucket: str = None) -> str:
    """
    将本地文件上传到MinIO

    Args:
        local_file_path: 本地文件的完整路径
        minio_file_path: MinIO中的目标路径（对象key）
        bucket: 指定bucket，默认为INPUT_BUCKET

    Returns:
        str: MinIO中的文件路径
    """
    try:
        # 检查本地文件是否存在
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"本地文件不存在: {local_file_path}")

        # 如果没有指定MinIO路径，使用本地文件名
        if minio_file_path is None:
            minio_file_path = os.path.basename(local_file_path)

        # 确定使用哪个bucket
        if bucket is None:
            bucket = settings.MINIO_OUTPUT_BUCKET

        # 上传文件到MinIO
        minio_client.fput_object(bucket, minio_file_path, local_file_path)

        logger.info(f"File uploaded to MinIO: {minio_file_path}")

        return minio_file_path

    except S3Error as e:
        raise Exception(f"上传文件到MinIO失败: {e}")
    except Exception as e:
        raise Exception(f"上传文件时发生错误: {e}")


def copy_minio_file(source_path: str, dest_path: str, bucket: str = None) -> str:
    """
    在 MinIO 中复制文件（用于缓存结果复用）

    Args:
        source_path: 源文件路径（对象key）
        dest_path: 目标文件路径（对象key）
        bucket: 指定bucket，默认为OUTPUT_BUCKET

    Returns:
        str: 目标文件路径
    """
    try:
        if bucket is None:
            bucket = settings.MINIO_OUTPUT_BUCKET

        # 使用 copy_object 复制文件
        minio_client.copy_object(
            bucket,
            dest_path,
            CopySource(bucket, source_path)
        )

        logger.info(f"File copied in MinIO: {source_path} -> {dest_path}")
        return dest_path

    except S3Error as e:
        raise Exception(f"MinIO 文件复制失败: {e}")
    except Exception as e:
        raise Exception(f"复制文件时发生错误: {e}")


