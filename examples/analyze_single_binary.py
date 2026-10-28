#!/usr/bin/env python3
"""
Demo script for BLADE - Binary Library Analysis and Detection Engine

This script demonstrates how to use BLADE to analyze binary files.
It automatically uses test cases from the data/test_cases directory
and saves results to result.json in the project root.

Usage:
    python examples/analyze_single_binary.py
"""

import os
import sys
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.services.tpl_detection.workflow import DetectionWorkflow


def get_test_binary():
    """
    Automatically find a test binary from data/test_cases directory.

    Returns:
        str: Path to the test binary file
    """
    test_cases_dir = project_root / "examples" / "test_cases" / "binaries"

    # Check if test_cases directory exists
    if not test_cases_dir.exists():
        raise FileNotFoundError(
            f"Test cases directory not found: {test_cases_dir}\n"
            f"Please ensure the examples/test_cases/binaries directory exists with test binaries."
        )

    # Priority order of test binaries to use
    test_files = ["openssl", "ffmpeg", "ffplay", "libpcap.so.1.10.5"]

    for test_file in test_files:
        test_path = test_cases_dir / test_file
        if test_path.exists() and test_path.is_file():
            return str(test_path)

    # If no priority file found, use the first binary file found
    for file_path in test_cases_dir.iterdir():
        if file_path.is_file() and file_path.name != "README.md":
            return str(file_path)

    raise FileNotFoundError(
        f"No test binary files found in {test_cases_dir}\n"
        f"Please add test binary files to the examples/test_cases/binaries directory."
    )




def main():
    """
    Main demo function that runs binary analysis and saves results.
    """
    print("=" * 70)
    print("BLADE - Binary Library Analysis and Detection Engine")
    print("=" * 70)
    print()

    # Get test binary path
    try:
        binary_path = get_test_binary()
        print(f"📁 Using test binary: {Path(binary_path).name}")
        print(f"   Full path: {binary_path}")
        print()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Prepare output directory and path
    output_dir = project_root / "examples" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)  # Create outputs directory if it doesn't exist
    result_path = output_dir / "analysis_result.json"

    # Run core analysis logic
    print("🔧 Initializing detection workflow...")
    print()
    print("🔍 Starting binary analysis...")
    print("-" * 70)

    try:
        result = analyze_binary(
            binary_path=binary_path,
            output_path=str(result_path),
        )
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("-" * 70)
    print()

    # Preview results
    print("📊 Analysis Results:")
    print("=" * 70)
    result.analysis_data.preview()
    print()

    # Verify results saved
    print(f"💾 Saving results...")
    if result_path.exists():
        file_size = result_path.stat().st_size
        print(f"✅ Results saved successfully ({file_size:,} bytes)")
        print()
        print("=" * 70)
        print("📄 ANALYSIS RESULTS SAVED")
        print("=" * 70)
        print(f"📍 Location: {result_path}")
        print(f"📂 Directory: {output_dir}")
        print()
        print("You can view the detailed analysis results in the JSON file.")
    else:
        print("⚠️  Warning: Result file was not created")

    print()
    print("=" * 70)
    print("✨ Demo completed successfully!")
    print("=" * 70)


def analyze_binary(binary_path, output_path):
    """
    Core function to analyze a binary file and save results.

    This is the main analysis logic that you can call directly in your code.

    Args:
        binary_path (str): Path to the binary file to analyze
        output_path (str): Path where to save the analysis results (JSON format)

    Returns:
        DetectionResult: The analysis result object

    """
    # Initialize detection workflow
    workflow = DetectionWorkflow(
        retrieval_top_n=5,
        debug_mode=False,
        verbose=True
    )

    # Run binary analysis
    result = workflow.run(binary_path)

    # Save results to file
    result.dump_to_file(output_path)

    return result

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
