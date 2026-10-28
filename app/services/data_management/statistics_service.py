"""
Statistics Service

Business logic layer for data management statistics.
"""
from typing import Dict, Any
from loguru import logger

from ...databases.postgres.repository import library_repository


class StatisticsService:
    """Service for data management statistics"""

    @staticmethod
    def get_library_statistics() -> Dict[str, Any]:
        """
        Get comprehensive library statistics including source codes, binaries, and vulnerabilities.

        Returns:
            Dict with nested structure:
            - library: Library-level statistics (total, completeness counts)
            - source_code: Source code statistics (total, averages, distribution)
            - binary: Binary statistics (total, averages, distribution)
            - vulnerability: Vulnerability statistics (total, risk levels)
        """
        try:
            # Get all statistics from repository (already calculated)
            stats = library_repository.get_library_statistics()

            logger.info(f"Generated library statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get library statistics: {e}")
            raise
