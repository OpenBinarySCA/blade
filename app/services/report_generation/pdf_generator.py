"""
PDF Generator for BLADE Report

Generates a professionally styled PDF report with:
- BLADE branding (white/light theme)
- Task information
- Input file information
- Statistics
- Extraction details
- TPL table
"""

import os
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class PDFGenerator:
    """Generator for PDF reports with BLADE branding."""

    # BLADE colors
    PURPLE = colors.HexColor("#A855F7")
    PURPLE_LIGHT = colors.HexColor("#E9D5FF")
    PURPLE_DARK = colors.HexColor("#581C87")
    GRAY = colors.HexColor("#6B7280")
    GRAY_LIGHT = colors.HexColor("#F3F4F6")
    GREEN = colors.HexColor("#22C55E")

    def __init__(self, result_data: Dict[str, Any], task_data: Dict[str, Any]):
        """
        Initialize PDF generator.

        Args:
            result_data: The detection result data dictionary
            task_data: Task metadata dictionary
        """
        self.result_data = result_data
        self.task_data = task_data
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.PURPLE_DARK,
            spaceAfter=20,
            alignment=TA_CENTER
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.PURPLE,
            spaceBefore=20,
            spaceAfter=10,
            borderPadding=5
        ))

        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=self.PURPLE_DARK,
            spaceBefore=10,
            spaceAfter=5
        ))

        # Normal text
        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=5
        ))

        # Small text for metadata
        self.styles.add(ParagraphStyle(
            name='MetaText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.GRAY,
            alignment=TA_CENTER
        ))

    def _create_header(self) -> List:
        """Create report header with BLADE branding."""
        elements = []

        # BLADE title
        elements.append(Paragraph("BLADE", self.styles['ReportTitle']))
        elements.append(Paragraph("Binary Library Analysis & Detection Engine", self.styles['MetaText']))
        elements.append(Spacer(1, 10))

        # Report title
        elements.append(Paragraph("Detection Report", self.styles['SectionHeader']))

        # Generation date
        gen_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Generated: {gen_date}", self.styles['MetaText']))

        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(width="100%", thickness=1, color=self.PURPLE_LIGHT))
        elements.append(Spacer(1, 20))

        return elements

    def _create_task_info_section(self) -> List:
        """Create task information section."""
        elements = []

        elements.append(Paragraph("Task Information", self.styles['SectionHeader']))

        data = [
            ["Task ID", self.task_data.get('task_id', '-')],
            ["Status", self.task_data.get('status', '-').upper()],
            ["Start Time", str(self.task_data.get('start_at', '-'))],
            ["End Time", str(self.task_data.get('end_at', '-'))],
        ]

        table = Table(data, colWidths=[2*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.PURPLE_LIGHT),
            ('TEXTCOLOR', (0, 0), (0, -1), self.PURPLE_DARK),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.GRAY_LIGHT),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))

        return elements

    def _create_input_file_section(self) -> List:
        """Create input file information section."""
        elements = []

        elements.append(Paragraph("Input File Information", self.styles['SectionHeader']))

        input_file = self.result_data.get('input_file', {})

        data = [
            ["File Name", input_file.get('file_name', '-')],
            ["File Size", input_file.get('file_size', '-')],
            ["MD5", input_file.get('file_md5', '-')],
            ["File Type", input_file.get('readable_type', '-')],
        ]

        table = Table(data, colWidths=[2*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.PURPLE_LIGHT),
            ('TEXTCOLOR', (0, 0), (0, -1), self.PURPLE_DARK),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.GRAY_LIGHT),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))

        return elements

    def _create_statistics_section(self) -> List:
        """Create statistics section."""
        elements = []

        elements.append(Paragraph("Statistics", self.styles['SectionHeader']))

        extraction = self.result_data.get('extraction', {})
        detection_results = self.result_data.get('detection_results', [])

        # Calculate total libraries
        total_libs = 0
        for result in detection_results:
            if result.get('main_program'):
                total_libs += 1
            total_libs += len(result.get('detected_libraries', []))
            total_libs += len(result.get('detected_dynamic_libraries', []))

        data = [
            ["Files Extracted", str(extraction.get('extracted_file_num', 0))],
            ["Binaries Analyzed", str(len(detection_results))],
            ["Libraries Detected", str(total_libs)],
        ]

        table = Table(data, colWidths=[2*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.PURPLE_LIGHT),
            ('TEXTCOLOR', (0, 0), (0, -1), self.PURPLE_DARK),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTSIZE', (1, 0), (1, -1), 12),
            ('TEXTCOLOR', (1, 0), (1, -1), self.GREEN),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.GRAY_LIGHT),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))

        return elements

    def _create_tpls_section(self) -> List:
        """Create TPLs section with table."""
        elements = []

        elements.append(Paragraph("Detected Third-Party Libraries", self.styles['SectionHeader']))

        detection_results = self.result_data.get('detection_results', [])

        # Build TPL data
        tpl_data = [["#", "Library Name", "Module", "Version", "Type", "Binary"]]

        idx = 1
        for result in detection_results:
            binary_path = (
                result.get('analysis_data', {}).get('target_binary', {}).get('relative_path') or
                result.get('binary_path') or
                'Unknown'
            )
            binary_name = os.path.basename(binary_path)
            # Truncate long binary names
            if len(binary_name) > 20:
                binary_name = binary_name[:17] + "..."

            def add_lib(lib: Dict[str, Any], lib_type: str):
                nonlocal idx
                version = "-"
                versions = lib.get('versions', [])
                if versions and versions[0].get('version') != 'unknown':
                    version = versions[0].get('version')

                lib_name = lib.get('name', '-')
                if len(lib_name) > 25:
                    lib_name = lib_name[:22] + "..."

                module = lib.get('component_name') or '-'
                if len(module) > 15:
                    module = module[:12] + "..."

                tpl_data.append([
                    str(idx),
                    lib_name,
                    module,
                    version,
                    lib_type,
                    binary_name
                ])
                idx += 1

            # Main program
            main_program = result.get('main_program')
            if main_program and main_program.get('name'):
                add_lib(main_program, 'Main')

            # Static linked
            for lib in result.get('detected_libraries', []):
                add_lib(lib, 'Static')

            # Dynamic linked
            for lib in result.get('detected_dynamic_libraries', []):
                add_lib(lib, 'Dynamic')

        if len(tpl_data) > 1:
            table = Table(tpl_data, colWidths=[0.4*inch, 1.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1.5*inch])
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), self.PURPLE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Data rows
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Index
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Version
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Type
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, self.GRAY_LIGHT),
                ('PADDING', (0, 0), (-1, -1), 5),
                # Alternate row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.GRAY_LIGHT]),
            ]))

            elements.append(table)
        else:
            elements.append(Paragraph("No libraries detected.", self.styles['ReportBody']))

        return elements

    def _create_footer(self) -> List:
        """Create report footer."""
        elements = []

        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(width="100%", thickness=1, color=self.PURPLE_LIGHT))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            "This report was generated by BLADE - Binary Library Analysis & Detection Engine",
            self.styles['MetaText']
        ))

        return elements

    def generate(self, output_path: str) -> str:
        """
        Generate PDF report.

        Args:
            output_path: Path to save the PDF file

        Returns:
            Path to the generated PDF file
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        elements = []

        # Add all sections
        elements.extend(self._create_header())
        elements.extend(self._create_task_info_section())
        elements.extend(self._create_input_file_section())
        elements.extend(self._create_statistics_section())
        elements.extend(self._create_tpls_section())
        elements.extend(self._create_footer())

        doc.build(elements)
        return output_path
