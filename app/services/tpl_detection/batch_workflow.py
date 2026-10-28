import os
import concurrent.futures
from typing import List, Optional, Callable

from loguru import logger
from func_timeout import func_timeout, FunctionTimedOut
from tqdm import tqdm

from .models import SoftwareContext
from .workflow import DetectionWorkflow
from ...interface import AnalysisResult


def _process_single_file_core(args):
    """
    核心处理逻辑（不含超时控制）
    args: (idx, file_path, detection_kwargs, software_context)
    """
    idx, file_path, detection_kwargs, software_context = args
    workflow = DetectionWorkflow(**detection_kwargs)
    result = workflow.run(file_path, software_context=software_context)
    if not result.succeed:
        logger.warning(
            f"File {file_path} analysis failed: {result.error_message}, try again with retry"
        )
        workflow = DetectionWorkflow(**detection_kwargs)
        result = workflow.run(file_path, software_context=software_context)
        if not result.succeed:
            logger.error(
                f"File {file_path} analysis failed again: {result.error_message}, skipped."
            )
        else:
            logger.success(f"File {file_path} analysis succeeded on retry.")
    return idx, result


def _process_single_file(args, timeout_seconds: int, max_retries: int = 3):
    """
    带超时控制和重试机制的单文件处理
    args: (idx, file_path, detection_kwargs, software_context)
    timeout_seconds: 超时时间（秒）
    max_retries: 最大重试次数
    """
    idx, file_path, detection_kwargs, software_context = args
    binary_name = os.path.basename(file_path)

    for attempt in range(1, max_retries + 1):
        try:
            return func_timeout(timeout_seconds, _process_single_file_core, args=(args,))
        except FunctionTimedOut:
            if attempt < max_retries:
                logger.warning(f"File {file_path} analysis timed out (attempt {attempt}/{max_retries}), retrying...")
            else:
                logger.warning(f"File {file_path} analysis timed out after {max_retries} attempts, skipped.")
                return idx, AnalysisResult(
                    binary_name=binary_name,
                    binary_sha256="",
                    binary_path=file_path,
                    succeed=False,
                    error_message=f"Analysis timed out after {max_retries} attempts ({timeout_seconds}s each)"
                )
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"File {file_path} analysis failed (attempt {attempt}/{max_retries}): {e}, retrying...")
            else:
                logger.error(f"File {file_path} analysis failed after {max_retries} attempts: {e}, skipped.")
                return idx, AnalysisResult(
                    binary_name=binary_name,
                    binary_sha256="",
                    binary_path=file_path,
                    succeed=False,
                    error_message=f"Analysis failed after {max_retries} attempts: {str(e)}"
                )


class BatchDetectionWorkflow:
    def __init__(
        self,
        concurrency: int = 4,
        progress_hook=None,
        phase_hook=None,
        cancel_check: Callable[[], bool] = None,
        timeout: int = 300,
        max_retries: int = 3,
        **detection_kwargs
    ):
        """
        concurrency: 并发数量
        progress_hook: 进度回调函数,签名为 progress_hook(completed, total, current_file, result)
        phase_hook: 阶段回调函数,签名为 phase_hook(phase, file_path)
        cancel_check: 取消检查函数,返回 True 表示任务被取消
        timeout: 单个任务的超时时间（秒），默认 300 秒（5 分钟）
        max_retries: 超时/失败后的最大重试次数，默认 3 次
        detection_kwargs: 传递给 DetectionWorkflow 的参数
        """
        self.concurrency = concurrency
        self.progress_hook = progress_hook
        self.cancel_check = cancel_check
        self.timeout = timeout
        self.max_retries = max_retries
        self._cancelled = False
        # 将 phase_hook 传递给 DetectionWorkflow
        if phase_hook:
            detection_kwargs['phase_hook'] = phase_hook
        self.detection_kwargs = detection_kwargs

    def run_batch(self, file_paths: List[str], software_context: SoftwareContext = None) -> List[
        Optional[AnalysisResult]]:
        """
        并发分析多个二进制文件
        file_paths: 待分析的二进制文件路径列表
        返回: 每个文件的 AnalysisResult，失败则为 None

        支持通过 cancel_check 回调函数检测取消请求。
        取消时会尝试取消尚未开始的任务，但正在执行的任务需要等待完成或超时。
        """
        results = [None] * len(file_paths)
        error_count = 0  # 错误计数
        self._cancelled = False

        # 准备参数列表
        args_list = [
            (idx, file_path, self.detection_kwargs, software_context)
            for idx, file_path in enumerate(file_paths)
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_args = {
                executor.submit(_process_single_file, args, self.timeout, self.max_retries): args
                for args in args_list
            }

            pbar = tqdm(concurrent.futures.as_completed(future_to_args), total=len(file_paths),
                        desc="批量分析进度")
            for future in pbar:
                # Check for cancellation after each file completes
                if self.cancel_check and self.cancel_check():
                    if not self._cancelled:
                        self._cancelled = True
                        logger.warning("检测到取消请求，正在停止批处理...")

                        # Cancel all pending futures (only works for not-yet-started tasks)
                        cancelled_count = 0
                        for f in future_to_args:
                            if f.cancel():
                                cancelled_count += 1
                        logger.info(f"已取消 {cancelled_count} 个排队中的任务")

                    # Still process the current completed future result
                    # but break after to stop processing more results

                args = future_to_args[future]
                idx, file_path = args[0], args[1]
                binary_name = os.path.basename(file_path)

                try:
                    _, result = future.result()
                    results[idx] = result

                    # 统计错误
                    if not result.succeed or result.error_message:
                        error_count += 1

                    # 更新进度条显示错误数量
                    pbar.set_postfix(errors=error_count)

                    # 调用进度回调函数
                    if self.progress_hook:
                        completed = sum(1 for r in results if r is not None)
                        current_file = file_paths[idx] if isinstance(file_paths[idx], str) else file_paths[idx][0]
                        self.progress_hook(
                            completed=completed,
                            total=len(file_paths),
                            current_file=current_file,
                            result=result
                        )
                except concurrent.futures.CancelledError:
                    # Task was cancelled before it started
                    logger.info(f"任务 {file_path} 被取消")
                    results[idx] = AnalysisResult(
                        binary_name=binary_name,
                        binary_sha256="",
                        binary_path=file_path,
                        succeed=False,
                        error_message="Task was cancelled"
                    )
                except Exception as e:
                    logger.exception(f"Future execution failed: {e}")
                    error_count += 1
                    pbar.set_postfix(errors=error_count)
                    results[idx] = AnalysisResult(
                        binary_name=binary_name,
                        binary_sha256="",
                        binary_path=file_path,
                        succeed=False,
                        error_message=str(e)
                    )

                # If cancelled, break after processing the current result
                if self._cancelled:
                    logger.info("批处理已停止，跳过剩余任务")
                    break

        # 运行结束后打印统计
        logger.info(f"批量分析完成: 总计 {len(file_paths)} 个, 成功 {len(file_paths) - error_count} 个, 失败 {error_count} 个")

        return results

    @property
    def is_cancelled(self) -> bool:
        """Check if the batch was cancelled"""
        return self._cancelled
