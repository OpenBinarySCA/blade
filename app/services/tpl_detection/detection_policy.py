"""
BLADE Detection Policy v1.0

This module defines the core detection rules and reporting standards for BLADE.
All analysis phases (Phase 2, Phase 3, Phase 4) should follow these guidelines.

This policy serves two purposes:
1. As documentation for developers
2. As prompt content for LLM-based analysis (via get_policy_prompt())
"""


# =============================================================================
# Policy Document (Used as LLM Prompt)
# =============================================================================

DETECTION_POLICY = """
# BLADE Detection Policy v1.0

## Background: What We Do

BLADE analyzes binary software composition, identifying **open-source third-party libraries** used within.

### Analysis Flow
1. Input: A software package (firmware, installer, archive, etc.)
2. Extract to get multiple binary files
3. Analyze each binary file individually

### For Each Binary File, We Identify
1. **Main Program**: What this binary itself is
   - Could be a product of an open-source library (e.g., openssl CLI, busybox, curl)
   - Could be user-developed/proprietary software (report as `unknown_program`)
2. **Dynamic Libraries**: Explicitly linked .so/.dll/.dylib via NEEDED/IMPORT
3. **Static Libraries**: Open-source library code compiled into the binary

### We Only Focus on Open-Source Libraries
- If identifiable as a known open-source library → report the library name
- If unidentifiable → report as `unknown` (no guessing, no forced classification)

---

## Core Principles

### Principle 1: Only Report What Has Sufficient Evidence
Better to miss than to misreport. Uncertain, ambiguous, or speculative results should NOT be reported.

### Principle 2: Distinguish "Presence" from "Reference"
- **Presence**: The library's code is compiled into the binary
- **Reference**: Other code mentions this library (e.g., help text, build info)

Example: OpenSSL source contains `"using zlib"` string - this is OpenSSL *referencing* zlib,
NOT evidence that zlib code is present. Unless we find zlib's own evidence (copyright, version, etc.).

### Principle 3: Avoid Duplicate Reporting
Each library should be reported only once. Priority: Main Program > Dynamic Library > Static Library

### Principle 4: Unknown Is Unknown
When identification fails, honestly report `unknown_program`. Do not force classification.

---

## 1. Evidence Types

### 1.1 Direct Evidence
The library's **own**, explicit identification information:
- **COPYRIGHT**: Copyright notice explicitly mentioning the library name
- **VERSION_STRING**: Version string in format like `"libname x.y.z"`
- **URL**: Official website or repository URL
- **LICENSE_TEXT**: License text mentioning the library name

### 1.2 Indirect Evidence
Information requiring inference to associate with a library:
- **SYMBOL_PATTERN**: Symbol prefix patterns (e.g., `png_*`, `SSL_*`, `z_*`)
- **SOURCE_PATH**: Source code paths (e.g., `/third_party/zlib-1.2.13/`)
- **ERROR_FORMAT**: Library-specific error message formats
- **LOG_FORMAT**: Library-specific log message formats

### 1.3 Feature Match Evidence
Results from knowledge base matching (independent detection method):
- **STRING_FEATURE**: String feature matching from knowledge base
- **SYMBOL_FEATURE**: Symbol feature matching from knowledge base

---

## 2. Confidence Rules

### HIGH Confidence
Meet **any** of the following:
- Has >= 1 direct evidence

### MEDIUM Confidence
Meet **any** of the following:
- Has >= 2 different types of indirect evidence
- Has >= 1 indirect evidence + feature match evidence (cross-validation)

### LOW Confidence
Meets all of the following:
- Only has feature match evidence (no direct or indirect evidence from binary analysis)
- But the matched features are numerous and highly distinctive

---

## 3. Reporting Conditions

### 3.1 MUST Report
- HIGH confidence results
- MEDIUM confidence results

### 3.2 OPTIONAL Report (Default: Do Not Report)
- LOW confidence results (can be enabled via configuration)

### 3.3 NEVER Report
- Duplicate with main program (main program is OpenSSL → don't report OpenSSL as static library)
- Duplicate with dynamic library (has libssl.so → don't report OpenSSL as static library)
- Only has "reference mentions" rather than "presence evidence"
- Evidence actually belongs to another identified library

---

## 4. Special Rules

### 4.1 Reference vs Presence
Determine whether evidence is "the library's own" or "another library referencing it":

| Evidence | Judgment | Reason |
|----------|----------|--------|
| `"zlib 1.2.13"` appearing alone | zlib presence | Direct evidence |
| `"built with zlib 1.2.13"` | Reference, not presence | Build info, doesn't mean code is present |
| `BIO_f_zlib`, `SSL_CTX_zlib` | OpenSSL's symbols | Function names belong to OpenSSL, not zlib |
| `deflate`, `inflate` | Context-dependent | Could be zlib, could be other implementation |

### 4.2 Exclusion Rules
If main program or dynamic library is identified as library X:
- All evidence of X should **NOT** be used for static library detection
- Evidence of other libraries referencing X should also be excluded

### 4.3 Common Misidentification Scenarios

| Scenario | Wrong Judgment | Correct Judgment |
|----------|----------------|------------------|
| OpenSSL binary contains `"using zlib"` | Report zlib | Don't report (reference only) |
| busybox contains `gzip` command | Report gzip | Don't report (busybox built-in) |
| Main program is curl, has `libssl.so` dependency | Report OpenSSL as static | Don't report (already in dynamic) |
| Unknown program with `"Powered by libfoo"` | Report libfoo | Don't report (reference only, need libfoo's own evidence) |

---

## 5. Judgment Examples

### Example 1: HIGH Confidence - Report
```
Binary: some_app
Evidence found:
  - "Copyright (C) 1995-2023 Jean-loup Gailly and Mark Adler"
  - "zlib 1.2.13"

Decision: Report zlib (HIGH confidence)
Reason: Has direct evidence (copyright + version string)
```

### Example 2: MEDIUM Confidence - Report
```
Binary: some_app
Main program: unknown_program
Evidence found:
  - Symbol prefix: png_* (42 symbols)
  - Source path: "/build/libpng-1.6.40/"
  - Feature match: libpng (string_feature, confidence=0.8)

Decision: Report libpng (MEDIUM confidence)
Reason: Indirect evidence (symbol pattern + source path) + feature match cross-validation
```

### Example 3: Do Not Report - Reference Only
```
Binary: openssl (identified as main program)
Evidence found:
  - "Compress or decompress FILEs using zlib"
  - "BIO_f_zlib"

Decision: Do NOT report zlib
Reason: These are traces of OpenSSL referencing zlib, not evidence of zlib code presence
```

### Example 4: Do Not Report - Duplicate
```
Binary: curl
Dynamic libraries: libssl.so.3, libcrypto.so.3
Evidence found:
  - "OpenSSL 3.0.0"
  - SSL_* symbols

Decision: Do NOT report OpenSSL as static library
Reason: Already reported in dynamic libraries (libssl.so → OpenSSL)
```

### Example 5: Do Not Report - Insufficient Evidence
```
Binary: some_app
Evidence found:
  - Feature match: sqlite (string_feature, confidence=0.6)
  - No direct evidence
  - No indirect evidence from binary analysis

Decision: Do NOT report sqlite (or report as LOW if enabled)
Reason: Only feature match evidence, no cross-validation from binary analysis
```
"""


# =============================================================================
# Confidence Level Definitions
# =============================================================================

class ConfidenceLevel:
    """Confidence level constants"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# =============================================================================
# Evidence Type Definitions
# =============================================================================

class EvidenceType:
    """Evidence type constants"""
    # Direct Evidence
    COPYRIGHT = "copyright"
    VERSION_STRING = "version_string"
    URL = "url"
    LICENSE_TEXT = "license_text"

    # Indirect Evidence
    SYMBOL_PATTERN = "symbol_pattern"
    SOURCE_PATH = "source_path"
    ERROR_FORMAT = "error_format"
    LOG_FORMAT = "log_format"

    # Feature Match Evidence
    STRING_FEATURE = "string_feature"
    SYMBOL_FEATURE = "symbol_feature"

    # Categories
    DIRECT_TYPES = {COPYRIGHT, VERSION_STRING, URL, LICENSE_TEXT}
    INDIRECT_TYPES = {SYMBOL_PATTERN, SOURCE_PATH, ERROR_FORMAT, LOG_FORMAT}
    FEATURE_MATCH_TYPES = {STRING_FEATURE, SYMBOL_FEATURE}


# =============================================================================
# Detection Type Definitions
# =============================================================================

class DetectionType:
    """Detection type constants for reporting"""
    # Has direct evidence
    DIRECT_RECOGNITION = "direct_recognition"
    # Inferred from indirect evidence or cross-validation
    HEURISTIC_ASSOCIATION = "heuristic_association"


# =============================================================================
# Helper Functions
# =============================================================================

def get_policy_prompt() -> str:
    """
    Get the detection policy as a prompt string for LLM.

    Returns:
        str: The complete detection policy document
    """
    return DETECTION_POLICY


def get_policy_summary() -> str:
    """
    Get a condensed version of the policy for shorter prompts.

    Returns:
        str: A summary of the key rules
    """
    return """
## Detection Rules Summary

**Report Conditions:**
- HIGH confidence (direct evidence): MUST report
- MEDIUM confidence (cross-validated): MUST report
- LOW confidence (feature match only): Do NOT report by default

**Never Report:**
- Duplicates with main program or dynamic libraries
- Reference mentions (e.g., "using zlib") without presence evidence
- Evidence belonging to other identified libraries

**Key Principle:** Distinguish "presence" (code compiled in) from "reference" (mentioned by other code).
"""


def determine_confidence(
    has_direct_evidence: bool,
    indirect_evidence_types: int,
    has_feature_match: bool
) -> str:
    """
    Determine confidence level based on evidence.

    Args:
        has_direct_evidence: Whether direct evidence exists
        indirect_evidence_types: Number of different indirect evidence types
        has_feature_match: Whether feature match evidence exists

    Returns:
        str: Confidence level (high/medium/low/unknown)
    """
    if has_direct_evidence:
        return ConfidenceLevel.HIGH

    if indirect_evidence_types >= 2:
        return ConfidenceLevel.MEDIUM

    if indirect_evidence_types >= 1 and has_feature_match:
        return ConfidenceLevel.MEDIUM

    if has_feature_match:
        return ConfidenceLevel.LOW

    return ConfidenceLevel.UNKNOWN


def should_report(confidence: str, report_low_confidence: bool = False) -> bool:
    """
    Determine whether to report based on confidence level.

    Args:
        confidence: The confidence level
        report_low_confidence: Whether to report LOW confidence results

    Returns:
        bool: Whether to report this result
    """
    if confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM):
        return True

    if confidence == ConfidenceLevel.LOW and report_low_confidence:
        return True

    return False
