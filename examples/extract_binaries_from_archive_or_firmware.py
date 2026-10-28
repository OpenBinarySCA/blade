#!/usr/bin/env python3
"""
Firmware Extraction Script for BLADE - Binary Library Analysis and Detection Engine

This script demonstrates how to use BLADE's extractor to recursively extract
firmware images, archives, and compressed files. It automatically unpacks nested
file systems and saves all extracted binaries.

Usage:
    python examples/extract_firmware.py
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.services.extractor.__main__ import do_extract


def get_firmware_file():
    """
    Get the test firmware/archive file path.

    Returns:
        str: Path to the firmware file
    """
    test_cases_dir = project_root / "examples" / "test_cases"
    firmware_file = test_cases_dir / "binaries.zip"

    if not firmware_file.exists():
        raise FileNotFoundError(
            f"Test file not found: {firmware_file}\n"
            f"Please ensure binaries.zip exists in the examples/test_cases directory."
        )

    return str(firmware_file)


def main():
    """
    Main demo function that extracts firmware and displays results.
    """
    print("=" * 70)
    print("BLADE - Firmware Extraction Tool")
    print("=" * 70)
    print()

    # Get firmware file
    try:
        firmware_path = get_firmware_file()
        print(f"📁 Using firmware file: {Path(firmware_path).name}")
        print(f"   Full path: {firmware_path}")
        print()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Prepare output directories
    output_dir = project_root / "examples" / "outputs" / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)

    filelist_path = project_root / "examples" / "outputs" / "extracted_filelist.json"

    # Run core extraction logic
    print("🔧 Initializing firmware extractor...")
    print()
    print("🔍 Starting firmware extraction...")
    print("   This may take a while for large firmware images...")
    print("-" * 70)

    try:
        filelist = extract_firmware_file(
            file_path=firmware_path,
            output_dir=str(output_dir),
            filelist_path=str(filelist_path)
        )
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("-" * 70)
    print()

    # Display extraction results
    if filelist:
        print("📊 Extraction Results:")
        print("=" * 70)
        print(filelist)
        print()

        # Verify results saved
        print("💾 Saving file list...")
        if filelist_path.exists():
            file_size = filelist_path.stat().st_size
            print(f"✅ File list saved successfully ({file_size:,} bytes)")
            print()
            print("=" * 70)
            print("📄 EXTRACTION RESULTS SAVED")
            print("=" * 70)
            print(f"📍 Extracted files: {output_dir}")
            print(f"📍 File list: {filelist_path}")
            print()
            print("You can:")
            print("  1. Browse extracted files in the outputs/extracted directory")
            print("  2. View the file list JSON for detailed information")
            print("  3. Use extracted binaries for TPL detection analysis")
        else:
            print("⚠️  Warning: File list was not created")
    else:
        print("⚠️  No files were extracted")

    print()
    print("=" * 70)
    print("✨ Firmware extraction completed!")
    print("=" * 70)


def extract_firmware_file(file_path: str, output_dir: str, filelist_path: str):
    """
    Core function to extract firmware/archive file and save results.

    This is the main extraction logic that you can call directly in your code.

    Args:
        file_path (str): Path to the firmware/archive file to extract
        output_dir (str): Directory where extracted files will be saved
        filelist_path (str): Path where to save the file list (JSON format)

    Returns:
        FileList: The file list object containing extraction results

    """
    # Run extraction
    filelist = do_extract(
        input_path=file_path,
        output_dir=output_dir,
        filelist_path=filelist_path,
        calc_md5=True,
        calc_sha1=True,
        dry_run=False,
        del_unpacked=False,  # Keep all extracted files
        use_fileter=True
    )

    return filelist


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Extraction interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
