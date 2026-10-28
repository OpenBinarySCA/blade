import os
import shutil
from typing import List, Any
from loguru import logger

from app.interface import AnalysisResult
from .batch_workflow import BatchDetectionWorkflow
from ...interface import AnalysisResult
from .models import SoftwareContext
from app.services.extractor.__main__ import do_extract, FileList


class WorkflowWithExtractor:
    """
    WorkflowWithExtractor - Workflow with automatic extraction support

    Can handle any file format (firmware/archives/binaries),
    automatically extracts and batch analyzes all binary files.
    """

    def __init__(self,
                 concurrency: int = 4,
                 progress_callback=None,
                 **detection_kwargs):
        """
        Initialize workflow with extractor

        Args:
            concurrency: Number of concurrent analyses
            progress_callback: Progress callback function
            **detection_kwargs: Additional parameters for DetectionWorkflow
        """
        self.concurrency = concurrency
        self.progress_callback = progress_callback
        self.detection_kwargs = detection_kwargs

    def run(self,
            file_path: str,
            workspace_dir: str,
            software_context: SoftwareContext = None) -> list[Any] | tuple[Any, list[AnalysisResult | None]]:
        """
        Run detection workflow with extraction

        Args:
            file_path: Input file path (firmware/archive/binary)
            workspace_dir: Working directory (required) for extraction
            software_context: Software context (optional)

        Returns:
            List[AnalysisResult]: Batch analysis results

        Process:
            1. Extract files to workspace directory
            2. Extract all binary files
            3. Batch TPL detection
            4. Return results
        """
        # 1. Create workspace directory
        os.makedirs(workspace_dir, exist_ok=True)
        logger.info(f"Using workspace directory: {workspace_dir}")

        # 2. Extract files
        logger.info(f"Extracting file: {file_path}")
        extraction_output_dir = os.path.join(workspace_dir, 'extracted')
        filelist_path = os.path.join(workspace_dir, 'file_list.json')

        filelist = do_extract(
            input_path=file_path,
            output_dir=extraction_output_dir,
            filetypes=None,
            fileexts=None,
            filelist_path=filelist_path,
            calc_md5=True,
            calc_sha1=True,
            dry_run=False
        )

        logger.info(f"Extraction successful, {len(filelist.files)} files found")

        # 3. Extract binary file paths
        binary_file_paths = [file['absolute_path'] for file in filelist.files]

        if not binary_file_paths:
            logger.warning("No binary files found")
            return []

        # 4. Batch TPL detection
        logger.info(f"Starting batch analysis of {len(binary_file_paths)} files")

        batch_workflow = BatchDetectionWorkflow(
            concurrency=self.concurrency,
            progress_hook=self.progress_callback,
            **self.detection_kwargs
        )

        results = batch_workflow.run_batch(
            file_paths=binary_file_paths,
            software_context=software_context
        )

        logger.info(f"Batch analysis completed, {len(results)} results")

        return filelist, results
