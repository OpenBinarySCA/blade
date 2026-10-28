"""
Result Query Tools - JMESPath-based universal query tool for TPL detection results
"""

from typing import Any, Optional
import jmespath
from agno.tools import Toolkit


class ResultQueryTools(Toolkit):
    """
    Universal query tool for accessing TPL detection result data using JMESPath expressions.

    This tool provides a simple interface to query any part of the batch detection result
    structure using JMESPath query language.
    """

    def __init__(self, result_data: dict):
        """
        Initialize the query tools with result data.

        Args:
            result_data: The complete batch detection result as a dictionary
        """
        super().__init__(name="result_query_tools")
        self.data = result_data

        # Register the query function
        self.register(self.query)

    def query(self, jmespath_expression: str, limit: Optional[int] = 100) -> Any:
        """
        Execute a JMESPath query on the detection result data.

        Args:
            jmespath_expression: JMESPath expression to query the data
            limit: Maximum number of items to return if result is a list (default: 100)

        Returns:
            Query result (can be dict, list, string, number, bool, or None)

        Examples:
            # Get basic info
            query("input_file.file_name")
            query("extraction.extracted_file_num")

            # Get detection summary
            query("detection_results[*].{binary: binary_name, main: main_program.name}")

            # Find specific binary
            query("detection_results[?binary_name=='libssl.so'] | [0]")

            # Get all detected libraries (flattened)
            query("detection_results[*].detected_libraries[*].name | []")

            # Filter with conditions
            query("detection_results[0].detected_libraries[?versions[0].confidence > `0.8`]")

            # Get nested data with limit
            query("detection_results[0].analysis_data.target_binary.strings", limit=50)
        """
        try:
            # Execute JMESPath query
            result = jmespath.search(jmespath_expression, self.data)

            # Apply limit if result is a list
            if isinstance(result, list) and limit is not None and len(result) > limit:
                original_count = len(result)
                result = result[:limit]
                # Add truncation info
                return {
                    "data": result,
                    "truncated": True,
                    "total_count": original_count,
                    "returned_count": limit,
                    "note": f"Result truncated to {limit} items (total: {original_count}). Increase 'limit' parameter if needed."
                }

            return result

        except Exception as e:
            # Return error information to help the agent debug the query
            return {
                "error": "JMESPath query failed",
                "expression": jmespath_expression,
                "message": str(e),
                "hint": "Check JMESPath syntax. Common issues: missing backticks for literals (`true`, `false`, `null`), incorrect filter syntax, invalid path."
            }
