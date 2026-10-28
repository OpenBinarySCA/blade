import os
import shutil
import traceback
import hashlib
from datetime import datetime
import json
from celery.exceptions import SoftTimeLimitExceeded
from .celery_app import celery_app
from ..databases.redis.redis_clients import tpl_detection_task_redis_client
from ..databases.user_data.repository import task_repository
from ..services.storage.minio_service import download_from_minio, upload_to_minio, copy_minio_file
from ..services.tpl_detection.batch_workflow import BatchDetectionWorkflow
from ..interface import TPLDetectionTaskStatus, TPLDetectionTask, AnalysisResult
from ..config import settings
from app.services.extractor.__main__ import do_extract


def _update_postgres_task_completed(task: TPLDetectionTask):
    """Update PostgreSQL task record when task completes (success or failed)"""
    try:
        task_repository.update_task_completed(
            task_id=task.task_id,
            status=task.status.value,
            result_minio_path=task.result_minio_path,
            report_minio_path=task.report_minio_path,
            error_message=task.error_message,
            analysis_total_files=task.analysis_total_files,
            analysis_completed_files=task.analysis_completed_files
        )
    except Exception as e:
        # Log error but don't fail the task - PostgreSQL is supplementary
        print(f"Warning: Failed to update PostgreSQL task record: {str(e)}")


def _calculate_file_sha256(file_path: str) -> str:
    """计算文件的 SHA256 哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _try_use_cached_result(task: TPLDetectionTask, file_sha256: str) -> bool:
    """
    尝试使用缓存的分析结果

    Args:
        task: 当前任务对象
        file_sha256: 输入文件的 SHA256

    Returns:
        True 如果成功使用缓存，False 如果需要重新分析
    """
    # 查找缓存的成功任务
    cached_task = task_repository.find_cached_task(
        input_file_sha256=file_sha256,
        engine_version=settings.ENGINE_VERSION
    )

    if not cached_task or not cached_task.result_minio_path:
        return False

    print(f"命中缓存！使用任务 {cached_task.task_id} 的结果")

    try:
        # 复制 MinIO 中的结果文件到新任务目录
        task_folder = f"task_{task.task_id}"
        cached_folder = f"task_{cached_task.task_id}"

        # 复制 TPL 检测结果
        new_result_path = f"{task_folder}/TPL_detection_result.json"
        copy_minio_file(
            source_path=cached_task.result_minio_path,
            dest_path=new_result_path,
            bucket=settings.MINIO_OUTPUT_BUCKET
        )

        # 复制 extraction_result.json（如果存在）
        new_filelist_path = f"{task_folder}/extraction_result.json"
        try:
            copy_minio_file(
                source_path=f"{cached_folder}/extraction_result.json",
                dest_path=new_filelist_path,
                bucket=settings.MINIO_OUTPUT_BUCKET
            )
            task.filelist_minio_path = new_filelist_path
        except Exception as e:
            print(f"复制 extraction_result.json 失败（可能不存在）: {e}")

        # 更新任务状态
        task.result_minio_path = new_result_path
        task.status = TPLDetectionTaskStatus.SUCCESS
        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.analysis_total_files = cached_task.analysis_total_files
        task.analysis_completed_files = cached_task.analysis_completed_files

        return True

    except Exception as e:
        print(f"使用缓存失败: {e}，将重新分析")
        return False


def _get_task_from_redis(task_id: str) -> TPLDetectionTask:
    """从Redis中获取任务信息并初始化TPLDetectionTask对象"""
    task_info_json = tpl_detection_task_redis_client.get(task_id)
    if not task_info_json:
        error_msg = f"No task found for task_id: {task_id}"
        print(f"错误: {error_msg}")
        # 创建一个失败的任务对象，记录错误信息
        task = TPLDetectionTask(
            task_id=task_id,
            file_minio_path="",
            status=TPLDetectionTaskStatus.FAILED,
            error_message=error_msg,
            end_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        update_redis_task(task)
        return task
    
    try:
        task_info = json.loads(task_info_json.decode('utf-8'))
        return TPLDetectionTask.init_from_dict(task_info)
    except Exception as e:
        error_msg = f"Failed to parse task info for task_id {task_id}: {str(e)}"
        print(f"错误: {error_msg}")
        # 创建一个失败的任务对象，记录错误信息
        task = TPLDetectionTask(
            task_id=task_id,
            file_minio_path="",
            status=TPLDetectionTaskStatus.FAILED,
            error_message=error_msg,
            end_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        update_redis_task(task)
        return task


def update_redis_task(task: TPLDetectionTask):
    """更新Redis中的任务信息"""
    try:
        task_json = task.customer_serialize()
        tpl_detection_task_redis_client.set(task.task_id, json.dumps(task_json, ensure_ascii=False))
        print(f"任务 {task.task_id} 状态更新为: {task.status.value}")
    except Exception as e:
        print(f"错误: 更新Redis任务信息失败: {str(e)}")


def get_task_workspace_dir(task_id: str) -> str:
    """
    获取任务专用工作目录

    Args:
        task_id: 任务ID

    Returns:
        str: 任务专用目录的完整路径
    """
    task_dir = os.path.join(settings.LOCAL_WORKSPACE_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    return task_dir


def cleanup_task_workspace(task_id: str) -> bool:
    """
    清理任务专用工作目录

    Args:
        task_id: 任务ID

    Returns:
        bool: 清理是否成功
    """
    try:
        task_dir = get_task_workspace_dir(task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            print(f"已清理任务工作目录: {task_dir}")
            return True
        else:
            print(f"任务工作目录不存在: {task_dir}")
            return True
    except Exception as e:
        print(f"清理任务工作目录失败: {e}")
        return False


def format_file_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读的文件大小

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        str: 格式化后的文件大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

@celery_app.task
def tpl_detection_task(task_id: str):
    """TPL检测任务 - 只接收task_id参数"""
    print(f"开始处理任务: {task_id}")
    # 1. 从Redis获取任务信息并初始化对象
    task = _get_task_from_redis(task_id)
    if task.status == TPLDetectionTaskStatus.FAILED:
        # 如果任务初始化就失败了，直接返回task的JSON
        print(f"任务 {task_id} 初始化失败，返回错误信息")
        return task.customer_serialize()
    print(f"获取到任务: {task.task_id}, 文件路径: {task.file_minio_path}")

    try:
        # 2. 设置任务工作目录和开始时间
        task.workspace_dir = get_task_workspace_dir(task_id)
        print(f"设置任务工作目录: {task.workspace_dir}")

        # 3. 从MinIO下载文件到任务专用目录
        print(f"开始下载文件: {task.file_minio_path}")
        task.file_download_start_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.status = TPLDetectionTaskStatus.FILE_DOWNLOADING
        update_redis_task(task)

        # 使用任务ID下载到专用目录
        local_file_path = download_from_minio(task.file_minio_path, task.workspace_dir)

        task.file_local_path = local_file_path
        task.file_download_end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"文件下载完成，本地路径: {local_file_path}")

        # 3.5 计算文件 SHA256 并检查缓存
        print("计算文件 SHA256...")
        file_sha256 = _calculate_file_sha256(local_file_path)
        print(f"文件 SHA256: {file_sha256}")

        if _try_use_cached_result(task, file_sha256):
            # 缓存命中，更新 Redis 和 PostgreSQL，直接返回
            update_redis_task(task)
            _update_postgres_task_completed(task)
            print(f"使用缓存结果完成任务: {task.task_id}")
            return task.customer_serialize()

        # 4. 解压文件（未命中缓存时继续）
        print("开始解压文件")
        task.unpack_start_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.status = TPLDetectionTaskStatus.UNPACKING
        update_redis_task(task)

        # 执行解压
        filelist = do_extract(
            input_path=local_file_path,
            output_dir=task.workspace_dir+'/ext',
            filetypes=None,
            fileexts=None,
            # logfile=task.workspace_dir+'/log.txt',
            filelist_path=task.workspace_dir+'/file_list.json',
            calc_md5=True,
            calc_sha1=True,
            dry_run=False
        )

        local_file_paths = [file['absolute_path'] for file in filelist.files]
        task.unpack_end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"解压成功，解压后文件数: {len(filelist.files)}")


        # 4.1 解压列表上传到MinIO
        print("开始上传解压结果")
        task.upload_unpack_result_start_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.status = TPLDetectionTaskStatus.UNPACKING_RESULT_UPLOADING
        update_redis_task(task)

        # 使用任务文件夹结构
        task_folder = f"task_{task_id}"
        filelist_minio_path = f"{task_folder}/extraction_result.json"
        local_filelist_path = os.path.join(task.workspace_dir, 'file_list.json')
        upload_to_minio(local_filelist_path, filelist_minio_path, bucket=settings.MINIO_OUTPUT_BUCKET)

        task.filelist_local_path = local_filelist_path
        task.filelist_minio_path = filelist_minio_path
        task.upload_unpack_result_end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 5. 开始分析
        print("开始TPL检测分析")
        task.analysis_start_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.status = TPLDetectionTaskStatus.ANALYZING
        task.analysis_total_files = len(local_file_paths)  # 设置总文件数
        task.analysis_completed_files = 0  # 初始化已完成数
        update_redis_task(task)

        # 定义进度回调函数
        def update_analysis_progress(completed:int, total:int, current_file:str, result: AnalysisResult):
            """
            分析进度回调函数
            每完成一个文件的分析就会被调用
            """
            task.analysis_completed_files = completed
            task.current_analyzing_file = current_file
            update_redis_task(task)
            print(f"分析进度: {completed}/{total}, 当前文件: {current_file}")

        # 定义阶段回调函数
        def update_analysis_phase(phase: str, file_path: str):
            """
            分析阶段回调函数
            每个分析阶段变化时被调用
            """
            task.current_analyzing_phase = phase
            task.current_analyzing_file = os.path.basename(file_path)
            update_redis_task(task)

        # 创建workflow实例,传入进度回调
        workflow = BatchDetectionWorkflow(
            concurrency=4,
            progress_hook=update_analysis_progress,  # 传入进度回调函数
            phase_hook=update_analysis_phase,  # 传入阶段回调函数
            enable_bin_info_analysis_web_search=False,
            feature_matching_return_top_n=5,
            debug_mode=False,
            report_unknown_program=True
        )

        # 使用本地文件路径进行分析
        results = workflow.run_batch(local_file_paths)

        task.analysis_end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("分析完成，开始保存结果")

        # 生成文件名（使用任务文件夹结构）
        result_minio_path = f"{task_folder}/TPL_detection_result.json"
        task_info_minio_path = f"{task_folder}/task.json"

        local_result_path = os.path.join(task.workspace_dir, "TPL_detection_result.json")
        local_task_info_path = os.path.join(task.workspace_dir, "task.json")

        # 保存TPL检测结果（公开版，只包含前端需要的字段，隐藏内部分析数据）
        # 过滤掉 None 值（超时或失败的结果）
        detection_results = [result.public_serialize() for result in results if result is not None]
        result_output_dict = {
            'input_file': {
                'file_name': filelist.original_filename,
                'file_size': format_file_size(filelist.original_file_size),
                'file_type': filelist.original_mime_type,
                'readable_type': filelist.original_readable_type,
                'file_md5': filelist.original_file_md5
            },
            'extraction': {
                'extracted_file_num': len(filelist.files),
                'extracted_file_paths': [file['relative_path'] for file in filelist.files]
            },
            'detection_results': detection_results
        }

        with open(local_result_path, 'w', encoding='utf-8') as f:
            json.dump(result_output_dict, f, ensure_ascii=False, indent=4)

        # 6. 上传分析结果到MinIO
        print("上传分析结果到MinIO")
        task.result_upload_start_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.status = TPLDetectionTaskStatus.RESULT_UPLOADING
        task.result_local_path = local_result_path
        task.result_minio_path = result_minio_path
        update_redis_task(task)

        upload_to_minio(local_result_path, result_minio_path, bucket=settings.MINIO_OUTPUT_BUCKET)

        task.result_upload_end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 7. 更新任务状态为成功
        task.status = TPLDetectionTaskStatus.SUCCESS
        for result in results:
            if result is None:
                continue
            if result.error_message:
                task.error_message = result.error_message
                print(f"分析 {result.analysis_data.target_binary.relative_path} 过程中出现错误: {result.error_message}")
                task.status = TPLDetectionTaskStatus.FAILED

        update_redis_task(task)

        # 8. 单独上传任务信息
        print("上传任务信息到MinIO")
        task.task_info_local_path = local_task_info_path
        task.task_info_minio_path = task_info_minio_path
        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_redis_task(task)

        # 保存完整的任务信息
        with open(local_task_info_path, 'w', encoding='utf-8') as f:
            json.dump(task.customer_serialize(), f, ensure_ascii=False, indent=4)

        upload_to_minio(local_task_info_path, task_info_minio_path, bucket=settings.MINIO_OUTPUT_BUCKET)

        print(f"任务完成，结果已保存到 MinIO:")
        print(f"  - TPL检测结果: {result_minio_path}")
        print(f"  - 提取结果: {filelist_minio_path}")
        print(f"  - 任务信息: {task_info_minio_path}")

        # 更新PostgreSQL任务记录
        _update_postgres_task_completed(task)

        # 返回task的JSON
        return task.customer_serialize()

    except SoftTimeLimitExceeded:
        # 处理软超时 - 新添加的异常处理
        error_msg = f"任务超时: 任务执行时间超过600秒限制" # 在celery app 中设置。
        print(error_msg)

        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.error_message = error_msg
        task.status = TPLDetectionTaskStatus.FAILED
        update_redis_task(task)

        # 更新PostgreSQL任务记录
        _update_postgres_task_completed(task)

        # 重要：确保返回task数据
        return task.customer_serialize()

    except Exception as e:
        # 记录失败信息
        error_msg = f"任务执行失败: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        
        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.error_message = f"{error_msg}\n{traceback.format_exc()}"
        task.status = TPLDetectionTaskStatus.FAILED

        # 更新任务状态为失败
        update_redis_task(task)

        # 更新PostgreSQL任务记录
        _update_postgres_task_completed(task)

        # 返回task的JSON
        return task.customer_serialize()
    finally:
        # 8. 根据配置决定是否清理任务工作目录
        if settings.CLEANUP_ANALYSIS_FILES:
            cleanup_task_workspace(task_id)