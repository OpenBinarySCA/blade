"""
CSV Generator for BLADE Report

Generates a CSV file containing TPL (Third-Party Library) information.
"""

import csv
import os
from typing import Dict, Any, List


class CSVGenerator:
    """Generator for CSV reports containing TPL information."""

    def __init__(self, result_data: Dict[str, Any]):
        """
        Initialize CSV generator with result data.

        Args:
            result_data: The detection result data dictionary
        """
        self.result_data = result_data

    def _extract_tpls(self) -> List[Dict[str, Any]]:
        """Extract TPL information from detection results."""
        tpls = []
        detection_results = self.result_data.get('detection_results', [])

        for result in detection_results:
            # Get binary name from path
            binary_path = (
                result.get('analysis_data', {}).get('target_binary', {}).get('relative_path') or
                result.get('binary_path') or
                'Unknown'
            )
            binary_name = os.path.basename(binary_path)

            # Helper to extract library info
            def extract_lib(lib: Dict[str, Any], lib_type: str) -> Dict[str, Any]:
                version = None
                versions = lib.get('versions', [])
                if versions and versions[0].get('version') != 'unknown':
                    version = versions[0].get('version')

                return {
                    'library_name': lib.get('name', '-'),
                    'module_name': lib.get('component_name') or '-',
                    'version': version or '-',
                    'type': lib_type,
                    'binary_name': binary_name,
                    'description': lib.get('description', '-')
                }

            # Add main program
            main_program = result.get('main_program')
            if main_program and main_program.get('name'):
                tpls.append(extract_lib(main_program, 'Main Program'))

            # Add static linked libraries
            for lib in result.get('detected_libraries', []):
                tpls.append(extract_lib(lib, 'Static Linked'))

            # Add dynamic linked libraries
            for lib in result.get('detected_dynamic_libraries', []):
                tpls.append(extract_lib(lib, 'Dynamic Linked'))

        return tpls

    def generate(self, output_path: str) -> str:
        """
        Generate CSV file with TPL information.

        Args:
            output_path: Path to save the CSV file

        Returns:
            Path to the generated CSV file
        """
        tpls = self._extract_tpls()

        # CSV columns
        fieldnames = ['Index', 'Library Name', 'Module Name', 'Version', 'Type', 'Binary', 'Description']

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for idx, tpl in enumerate(tpls, 1):
                writer.writerow({
                    'Index': idx,
                    'Library Name': tpl['library_name'],
                    'Module Name': tpl['module_name'],
                    'Version': tpl['version'],
                    'Type': tpl['type'],
                    'Binary': tpl['binary_name'],
                    'Description': tpl['description']
                })

        return output_path
