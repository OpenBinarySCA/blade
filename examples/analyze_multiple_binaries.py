#!/usr/bin/env python3
"""
Batch Analysis Script for BLADE - Binary Library Analysis and Detection Engine

This script demonstrates how to use BLADE to analyze multiple binary files in batch.
It automatically scans all binaries in the data/test_cases directory and processes
them concurrently for improved performance.

Usage:
    python examples/analyze_multiple_binaries.py
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.services.tpl_detection.batch_workflow import BatchDetectionWorkflow


def get_binary_files(directory: Path) -> List[str]:
    """
    Scan directory for binary files.

    Args:
        directory: Path to the directory to scan

    Returns:
        List of file paths (as strings)
    """
    binary_files = []

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Iterate through all files in directory
    for file_path in directory.iterdir():
        # Skip directories and non-binary files
        if file_path.is_file() and file_path.name != "README.md":
            binary_files.append(str(file_path))

    return binary_files


def save_batch_results(results, output_path: Path):
    """
    Save batch analysis results to JSON file.

    Args:
        results: List of AnalysisResult objects
        output_path: Path where to save the results
    """
    # Serialize results
    serialized_results = []
    for result in results:
        if result is None:
            serialized_results.append(None)
        elif isinstance(result, str):
            # Error message string
            serialized_results.append({"error": result})
        elif hasattr(result, 'customer_serialize'):
            # AnalysisResult object
            serialized_results.append(result.customer_serialize())
        else:
            serialized_results.append(str(result))

    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serialized_results, f, ensure_ascii=False, indent=2)


def print_result_summary(results, file_paths: List[str]):
    """
    Print a summary of batch analysis results.

    Args:
        results: List of AnalysisResult objects
        file_paths: List of analyzed file paths
    """
    print()
    print("=" * 70)
    print("📊 BATCH ANALYSIS SUMMARY")
    print("=" * 70)
    print()

    success_count = 0
    failed_count = 0

    for idx, (file_path, result) in enumerate(zip(file_paths, results), 1):
        file_name = Path(file_path).name

        if result is None:
            print(f"{idx}. ❌ {file_name}: No result")
            failed_count += 1
        elif isinstance(result, str):
            print(f"{idx}. ❌ {file_name}: Error - {result}")
            failed_count += 1
        elif hasattr(result, 'succeed') and result.succeed:
            lib_count = len(result.detected_libraries) if hasattr(result, 'detected_libraries') else 0
            print(f"{idx}. ✅ {file_name}: Success ({lib_count} libraries detected)")
            success_count += 1
        else:
            error_msg = getattr(result, 'error_message', 'Unknown error')
            print(f"{idx}. ❌ {file_name}: Failed - {error_msg}")
            failed_count += 1

    print()
    print("-" * 70)
    print(f"Total: {len(results)} | Success: {success_count} | Failed: {failed_count}")
    print("-" * 70)




def main():
    """
    Main batch analysis function.
    """
    print("=" * 70)
    print("BLADE - Batch Binary Analysis")
    print("=" * 70)
    print()

    # Get binary files from test cases directory
    test_cases_dir = project_root / "examples" / "test_cases" / "binaries"

    try:
        binary_files = get_binary_files(test_cases_dir)
        print(f"📁 Scanning directory: {test_cases_dir}")
        print(f"🔍 Found {len(binary_files)} binary file(s)")
        print()

        if not binary_files:
            print("❌ No binary files found to analyze")
            sys.exit(1)

        # Display file list
        print("Files to analyze:")
        for idx, file_path in enumerate(binary_files, 1):
            print(f"  {idx}. {Path(file_path).name}")
        print()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Prepare output directory and path
    output_dir = project_root / "examples" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "batch_analysis_result.json"

    # Run core batch analysis logic
    print("🔧 Initializing batch detection workflow...")
    print(f"⚙️  Concurrency: 4 workers")
    print()
    print("🔍 Starting batch analysis...")
    print("-" * 70)

    start_time = time.time()

    try:
        results = analyze_binaries_batch(
            file_paths=binary_files,
            output_path=str(result_path),
        )
    except Exception as e:
        print(f"\n❌ Batch analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed_time = time.time() - start_time

    print("-" * 70)
    print(f"⏱️  Total time: {elapsed_time:.2f} seconds")

    # Print summary
    print_result_summary(results, binary_files)

    # Verify results saved
    print()
    print("💾 Saving results...")
    if result_path.exists():
        file_size = result_path.stat().st_size
        print(f"✅ Results saved successfully ({file_size:,} bytes)")
        print()
        print("=" * 70)
        print("📄 BATCH ANALYSIS RESULTS SAVED")
        print("=" * 70)
        print(f"📍 Location: {result_path}")
        print(f"📂 Directory: {output_dir}")
        print()
        print("You can view the detailed batch analysis results in the JSON file.")
    else:
        print("⚠️  Warning: Result file was not created")

    print()
    print("=" * 70)
    print("✨ Batch analysis completed!")
    print("=" * 70)


def analyze_binaries_batch(file_paths: List[str], output_path: str):
    """
    Core function to analyze multiple binary files in batch and save results.

    This is the main batch analysis logic that you can call directly in your code.

    Args:
        file_paths (List[str]): List of binary file paths to analyze
        output_path (str): Path where to save the batch analysis results (JSON format)

    Returns:
        List: List of AnalysisResult objects (or None/error strings for failed analyses)

    """
    # Initialize batch workflow
    batch_workflow = BatchDetectionWorkflow(
        concurrency=4,
        retrieval_top_n=5,
        debug_mode=False,
        verbose=False
    )

    # Run batch analysis
    results = batch_workflow.run_batch(file_paths)

    # Save results to file
    save_batch_results(results, Path(output_path))

    return results


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Batch analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
