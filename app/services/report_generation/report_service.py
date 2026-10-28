"""
Report Service for BLADE

Main service that orchestrates report generation:
- Generates PDF, Excel, and CSV reports
- Packages them into a ZIP file
- Uploads to MinIO for storage
"""

import os
import json
import zipfile
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime

from .pdf_generator import PDFGenerator
from .excel_generator import ExcelGenerator
from .csv_generator import CSVGenerator


class ReportService:
    """Service for generating and managing reports."""

    def __init__(self):
        """Initialize report service."""
        pass

    def generate_reports(
        self,
        result_data: Dict[str, Any],
        task_data: Dict[str, Any],
        output_dir: Optional[str] = None
    ) -> str:
        """
        Generate all reports (PDF, Excel, CSV) and package into ZIP.

        Args:
            result_data: Detection result data dictionary
            task_data: Task metadata dictionary
            output_dir: Optional output directory. If None, uses temp directory.

        Returns:
            Path to the generated ZIP file
        """
        # Use temp directory if not specified
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="blade_report_")

        task_id = task_data.get('task_id', 'unknown')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate individual reports
        pdf_path = os.path.join(output_dir, "report.pdf")
        excel_path = os.path.join(output_dir, "report.xlsx")
        csv_path = os.path.join(output_dir, "tpls.csv")

        # Generate PDF
        pdf_generator = PDFGenerator(result_data, task_data)
        pdf_generator.generate(pdf_path)

        # Generate Excel
        excel_generator = ExcelGenerator(result_data, task_data)
        excel_generator.generate(excel_path)

        # Generate CSV
        csv_generator = CSVGenerator(result_data)
        csv_generator.generate(csv_path)

        # Create ZIP file
        zip_filename = f"blade_report_{task_id[:8]}_{timestamp}.zip"
        zip_path = os.path.join(output_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(pdf_path, "report.pdf")
            zipf.write(excel_path, "report.xlsx")
            zipf.write(csv_path, "tpls.csv")

        # Clean up individual files
        os.remove(pdf_path)
        os.remove(excel_path)
        os.remove(csv_path)

        return zip_path

    @staticmethod
    def load_result_data(result_json_path: str) -> Dict[str, Any]:
        """
        Load result data from JSON file.

        Args:
            result_json_path: Path to the result JSON file

        Returns:
            Result data dictionary
        """
        with open(result_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
