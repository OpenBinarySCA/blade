"""C++ symbol demangling utilities.

This module provides functions to demangle C++ mangled symbols (Itanium ABI)
back to their human-readable form.

Example:
    >>> demangle_symbol("_ZN5boost6detail15sp_counted_base7destroyEv")
    'boost::detail::sp_counted_base::destroy()'

    >>> extract_function_name("_ZN5boost6detail15sp_counted_base7destroyEv")
    'destroy'
"""

import re
from typing import List, Optional, Set, Tuple

import cxxfilt


def demangle_symbol(symbol: str) -> str:
    """Demangle a single C++ mangled symbol.

    Args:
        symbol: The mangled symbol name (e.g., "_ZN5boost6detail...")

    Returns:
        The demangled symbol name, or the original symbol if demangling fails.
    """
    if not symbol:
        return symbol

    # Quick check: if it doesn't look like a mangled C++ symbol, return as-is
    if not _is_likely_mangled(symbol):
        return symbol

    try:
        demangled = cxxfilt.demangle(symbol)
        return demangled
    except Exception:
        # If demangling fails, return original symbol
        return symbol


def demangle_symbols(symbols: List[str]) -> List[str]:
    """Demangle a list of C++ symbols.

    Args:
        symbols: List of potentially mangled symbol names.

    Returns:
        List of demangled symbol names (original names preserved for non-C++ symbols).
    """
    return [demangle_symbol(s) for s in symbols]


def _is_likely_mangled(symbol: str) -> bool:
    """Check if a symbol is likely a mangled C++ symbol.

    Mangled symbols typically start with:
    - _Z (Itanium ABI, used by GCC/Clang on Linux/macOS)
    - ?  (MSVC ABI on Windows)
    - __Z (macOS sometimes adds extra underscore)
    """
    return (
        symbol.startswith("_Z") or
        symbol.startswith("__Z") or
        symbol.startswith("?")
    )


def extract_function_name(symbol: str) -> Optional[str]:
    """Extract the base function name from a mangled or demangled symbol.

    This extracts just the function name without namespace, class, or parameters.

    Args:
        symbol: A mangled or demangled symbol name.

    Returns:
        The base function name, or None if extraction fails.

    Examples:
        >>> extract_function_name("_ZN5boost6detail15sp_counted_base7destroyEv")
        'destroy'
        >>> extract_function_name("boost::detail::sp_counted_base::destroy()")
        'destroy'
        >>> extract_function_name("simple_function")
        'simple_function'
    """
    if not symbol:
        return None

    # First, demangle if needed
    demangled = demangle_symbol(symbol)

    # If demangling didn't change it (not a mangled symbol), return as-is
    # unless it contains special characters
    if demangled == symbol and not _is_likely_mangled(symbol):
        # Clean up any trailing/leading underscores
        clean = symbol.strip("_")
        return clean if clean else symbol

    # Parse the demangled name to extract function name
    return _extract_name_from_demangled(demangled)


def _extract_name_from_demangled(demangled: str) -> Optional[str]:
    """Extract the function name from a demangled symbol.

    Handles various formats:
    - "namespace::class::function(args)" -> "function"
    - "namespace::function(args)" -> "function"
    - "function(args)" -> "function"
    - "operator++()" -> "operator++"
    - "class::~class()" -> "~class" (destructor)
    """
    if not demangled:
        return None

    # Remove template arguments first (they complicate parsing)
    demangled = _remove_template_args(demangled)

    # Find the opening parenthesis (start of function parameters)
    paren_pos = demangled.find("(")
    if paren_pos != -1:
        demangled = demangled[:paren_pos]

    # Handle const/volatile qualifiers that might appear after function name
    demangled = demangled.rstrip()

    # Split by :: to get the last component (the function name)
    parts = demangled.split("::")
    if parts:
        name = parts[-1].strip()
        # Handle operator overloads
        if "operator" in parts[-2] if len(parts) >= 2 else False:
            name = parts[-2].strip() + "::" + name
        return name if name else None

    return None


def _remove_template_args(s: str) -> str:
    """Remove template arguments from a demangled name.

    E.g., "std::vector<int, std::allocator<int>>" -> "std::vector"
    """
    result = []
    depth = 0
    for char in s:
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif depth == 0:
            result.append(char)
    return "".join(result)


def extract_all_function_names(symbols: List[str]) -> Set[str]:
    """Extract all unique function names from a list of symbols.

    This combines demangling and function name extraction to get a set
    of all unique base function names.

    Args:
        symbols: List of symbol names (mangled or not).

    Returns:
        Set of unique function names.
    """
    names = set()
    for symbol in symbols:
        name = extract_function_name(symbol)
        if name and len(name) >= 2:  # Filter out very short names
            names.add(name)
    return names


def get_demangled_and_original(symbols: List[str]) -> List[Tuple[str, str]]:
    """Get both original and demangled forms for each symbol.

    Useful for matching against databases that might store either form.

    Args:
        symbols: List of symbol names.

    Returns:
        List of (original, demangled) tuples.
    """
    return [(s, demangle_symbol(s)) for s in symbols]


def collect_matchable_names(symbols: List[str]) -> Set[str]:
    """Collect all names that could be used for matching.

    For each symbol, this collects:
    1. The original symbol name
    2. The demangled name (if different)
    3. The extracted function name (if different from above)

    This maximizes the chance of matching against a database.

    Args:
        symbols: List of symbol names.

    Returns:
        Set of all matchable names.
    """
    names = set()

    for symbol in symbols:
        if not symbol:
            continue

        # Add original
        names.add(symbol)

        # Add demangled (may be same as original)
        demangled = demangle_symbol(symbol)
        if demangled and demangled != symbol:
            names.add(demangled)

        # Add extracted function name
        func_name = extract_function_name(symbol)
        if func_name and func_name not in (symbol, demangled):
            names.add(func_name)

    return names
