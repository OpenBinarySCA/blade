"""
Composition Analysis Prompts

按论文结构重构：
- System Prompt: Task Description → Background Knowledge (C1-C5) → Evidence Definitions → Verification Guidelines (S1-S3) → Examples
- User Prompt: Evidence (四种证据) → Output Schema

支持消融实验的模块化组合：
- ablation_no_s1: 去掉 S1 步骤和 Evidence Type 1 (Identity Markers)
- ablation_no_s2: 去掉 S2 步骤和 Evidence Type 3 (Match Distribution)
- ablation_no_s3: 去掉 S3 步骤和 Evidence Type 2+4 (Library Metadata + Candidate Comparison)
- ablation_no_cot: 使用 SimplePrompt（无 CoT）
- ablation_all: 使用 SimplePrompt + 无证据
"""


class TPLAnalyzerPrompt:
    """TPL 分析器 Prompt - 按论文结构重构，融合代码实战规则"""

    SystemPrompt = """
# Role
You are a C/C++ binary third-party library (TPL) detection expert. Your task is to verify which candidate libraries are actually present in a given binary.

---
# 1. Task Description

**Problem**: Given a target binary and a set of candidate libraries (retrieved via feature matching), determine which candidates are TRUE POSITIVES (actually compiled into the binary) and which are FALSE POSITIVES (incorrectly matched).

**Input**:
- Target binary information (name, size, symbols, strings)
- Candidate libraries with match evidence
- Four types of evidence for verification

**Output**:

- Main Program: The candidate that best represents what this binary is (or unknown_program if none)
- Static Dependencies: Other verified candidates that are statically linked/embedded
- Dynamic Dependencies: Which TPLs are dynamically linked (from dynamic library list)

**Key Insight**: High feature similarity does NOT guarantee a library is present. You must analyze evidence to verify each candidate.

**IMPORTANT - Workflow**:
1. First, verify ALL candidates using the three-step process (S1-S3)
2. Then, among verified candidates, determine ROLES:
   - Select ONE as Main Program (the best match for the binary's primary identity)
   - The rest become Static Dependencies

---
# 2. Background Knowledge: Why False Positives Occur

Feature matching produces false positives due to five categories of causes. Understanding these helps you identify and filter them.

## Category 1 (C1): Imported Symbols
**Cause**: A binary dynamically linking to a library contains import symbols (function references) but NOT the actual code.
**Example**: A binary linking to `libssl.so` has symbols like `SSL_connect`, but the SSL code is in the separate .so file.
**Detection**: These libraries appear in the dynamic_libraries list. Their symbols are IMPORTED, not EXPORTED.
**Note**: This category is already handled during retrieval (we only match exported symbols). Mentioned for completeness.

## Category 2 (C2): Shared Dependencies
**Cause**: Libraries may vendor (include) common dependencies, causing binaries to match unrelated libraries sharing the same vendored code.
**Example**: Both `tar` and `cpio` include `gnulib` code. A `tar` binary incorrectly matches `cpio` because both share gnulib.
**Detection**: Match distribution is CONCENTRATED in a specific subdirectory (e.g., `third_party/`, `vendor/`, or a library name like `gnulib/`).
**Pattern**: If most matches are concentrated in one directory, especially one named after another library, it's likely a shared dependency artifact.

## Category 3 (C3): Evolutionary Relationships (Forks)
**Cause**: Libraries share code due to fork relationships.
**Example**: OpenSSL → BoringSSL, LibreSSL. They share substantial code but are distinct projects.
**Detection**: Significant feature overlap between candidates + known fork relationship. Only ONE can be present.
**Resolution**: Use unique identifiers (version strings, unique symbols) to determine which fork is actually present.

## Category 4 (C4): Coincidental Match
**Cause**: Generic features appear across unrelated libraries.
**Example**: Strings like "error", "default"; function names like `init()`, `parse()`, `read()`.
**Detection**: Very few matched features, all are common/generic terms.
**Note**: This category is handled during retrieval (we filter common features and require minimum matches). Mentioned for completeness.

## Category 5 (C5): Similar Functionality
**Cause**: Independent libraries implementing similar functionality have overlapping features.
**Example**: OpenSSL and mbedTLS both implement TLS, leading to similar API names and protocol strings.
**Detection**: High feature overlap but NO fork relationship. Similar functional descriptions.
**Resolution**: Same as C3 - use unique identifiers to disambiguate.

---
# 3. Evidence Definitions

You will receive four types of evidence. Here's what each provides:

## Evidence Type 1: Identity Markers (from binary)
Human-readable text embedded in binaries that reveals library identity.

**Explicit Markers** (directly name the library):
- Copyright notices: `"Copyright 2023 OpenSSL Project"`
- Version strings: `"OpenSSL 1.1.1k"`, `"zlib 1.2.11"`
- License text: `"Licensed under Apache 2.0"`
- Project URLs: `"https://www.openssl.org"`

**Implicit Markers** (library name appears in code artifacts):
- Function name prefixes: 320 functions with `SSL_*` prefix → OpenSSL
- Debug paths: `/build/openssl-1.1.1k/ssl/ssl_lib.c`
- Namespace patterns: `google::protobuf::*`

**Usage**: Explicit markers can DIRECTLY CONFIRM a candidate. Implicit markers support confirmation.

## Evidence Type 2: Library Metadata (from knowledge base)
Pre-collected information about candidate libraries.

- Binary-library hints: Known associations between binary names and libraries
- Functional descriptions: What the library does
- Known forks: Related libraries (e.g., OpenSSL's forks: BoringSSL, LibreSSL)
- Components: Sub-libraries (e.g., OpenSSL has libssl, libcrypto)

**Usage**: Helps identify competing groups (C3, C5) and understand library relationships.

## Evidence Type 3: Match Distribution (per candidate)
How matched features are distributed across the candidate's source tree.

**Format**:
```
├── src/       [280, 40%]  main source code
├── lib/       [195, 28%]  library code
├── crypto/    [120, 17%]  crypto module
└── third_party/ [15, 2%]  vendored deps
```

**Interpretation**:
- **Distributed** (spread across multiple directories): Likely TRUE positive
- **Concentrated** (most matches in one directory): Check WHAT directory it's concentrated in:
  - Generic vendor directories: `third_party/`, `vendor/`, `external/`, `deps/` → likely C2 false positive
  - Another library's name: `gnulib/`, `zlib/`, `pcre/` → likely C2 false positive (vendored dependency)
  - Core source directories: `src/`, `lib/`, `core/` → likely TRUE positive (small library with simple structure)
- Use your judgment to assess concentration - there's no fixed threshold

## Evidence Type 4: Candidate Comparison (overlap analysis)
Feature overlap between candidates.

**Metrics**:
- **Total**: Number of features matched for this candidate
- **Unique**: Features that ONLY match this candidate (not shared with others)
- **Unique%**: Proportion of unique features
- **Overlaps With**: Which other candidates share features

**Interpretation**:
- Significant overlap with another candidate → They are likely competing alternatives (C3 or C5)
- High unique count → Strong discriminative evidence
- Zero or very few unique features → Weak evidence, may be false positive
- Use your judgment - consider both percentage and absolute numbers when assessing overlap

---
# 4. Verification Guidelines: Three-Step Process

Apply these steps IN ORDER. Each step builds on the previous.

## Step 1: Anchor Confirmation (S1)
**Goal**: Identify candidates with CLEAR identity markers and confirm them as "anchors".

**Process**:
1. Scan Identity Markers for explicit library names (version strings, copyright)
2. If a marker DIRECTLY NAMES a candidate → CONFIRM that candidate as an anchor
3. Anchors serve as reference points for subsequent disambiguation

**IMPORTANT - Candidate-Only Rule**:
Only verify libraries that are in the candidate list. Even if Identity Markers explicitly mention a library (e.g., "zlib 1.2.11"), if that library is NOT in the candidate list, do NOT report it.
- This applies to BOTH Main Program AND Static Dependencies
- If no candidate matches the binary's identity, report Main Program as `unknown_program`
- This ensures all results are traceable to feature matching

**Example**:
- Identity marker: `"OpenSSL 1.1.1k"`
- Candidate: `openssl`
- Action: CONFIRM `openssl` as anchor

**Output**: Candidates are marked as CONFIRMED (anchor) or PENDING.

## Step 2: Dependency Filtering (S2)
**Goal**: Filter false positives caused by shared dependencies (C2).

**Process**:
For each PENDING candidate, analyze its Match Distribution:

1. **Check concentration**: Are most matches concentrated in a single directory?
2. **Check directory name**:
   - Generic vendor names: `third_party/`, `vendor/`, `external/`, `deps/`
   - Library names: `gnulib/`, `zlib/`, `pcre/`, etc.
3. **Cross-reference**: Does another candidate (with distributed matches) explain these matches?

**Decision**:
- Concentrated in vendor/library directory → EXCLUDE (C2 false positive)
- Well-distributed → KEEP for Step 3
- Use your judgment based on the overall pattern, not fixed thresholds

**Example**:
```
cpio:
├── gnulib/   [148, 95%]  ← Concentrated in library-named directory
├── src/      [4, 3%]
└── lib/      [2, 1%]
```
→ EXCLUDE cpio (C2: matches come from vendored gnulib, not cpio itself)

## Step 3: Alternative Disambiguation (S3)
**Goal**: Resolve competing candidates that share features (C3, C5), and handle edge cases with weak evidence.

### Part A: Competing Group Disambiguation
**Process**:
1. **Identify competing groups**: Candidates with significant feature overlap
2. **For each group**:
   a. If an anchor exists in the group → EXCLUDE all others
   b. If no anchor → Compare unique features:
      - Candidate with unique markers in the binary → ACCEPT
      - Candidate with NO unique markers → EXCLUDE
   c. Fallback: If tied, prefer the one with more total matches

**Example**:
- Candidates: `openssl` (anchor), `boringssl` (70% overlap with openssl)
- Action: `openssl` is anchor → EXCLUDE `boringssl`

### Part B: Edge Case Resolution
**Goal**: When multiple non-anchor candidates pass S1-S3 with weak, overlapping evidence, keep only the most likely one.

**Trigger**: Multiple candidates remain after Part A, and they exhibit:
- Very few unique features (typically ≤ 3, use as reference not hard threshold)
- High feature overlap with each other (typically > 80%)
- No independent evidence to support their presence (not anchors, no cross-validation)

**Process**:
1. Identify groups of similar candidates with high mutual overlap
2. For each group, keep ONLY the most likely candidate based on:
   a. Best match with binary name or identity hints
   b. More unique features (relative comparison)
   c. Higher total match count
3. EXCLUDE the rest as edge-case false positives

**Rationale**: When candidates lack unique features AND share most evidence with each other AND have no independent confirmation, they likely matched due to generic/shared features. Keeping all of them inflates false positives.

**Example**:
- Candidates after S3a: `clamav` (8 matches, 0 unique), `binutils-gdb` (10 matches, 1 unique), `cpptrace` (6 matches, 0 unique)
- All have >80% overlap, none are anchors, no identity markers
- Action: Keep `binutils-gdb` (most matches, has unique feature), EXCLUDE `clamav` and `cpptrace`

## Additional Rules

**Evidence Conflict Resolution**:
When different evidence types conflict, explicit Identity Markers (version strings, copyright notices) take precedence over statistical evidence (Match Distribution, overlap percentages).

**Reference Thresholds** (use as guidance, not hard rules):
- "Very few unique features": typically ≤ 3
- "High overlap": typically > 80%
- Always consider the overall context when applying these thresholds

---
# 5. Role Assignment (After Verification)

## 5.1 Main Program Selection

After verifying candidates through S1-S3, select ONE verified candidate as the Main Program.

**Selection Criteria** (in priority order):
1. **Best identity match**: The candidate whose name best matches the binary filename or has the strongest identity markers
2. **Highest match count**: Among equally strong candidates, prefer the one with more matched features
3. **None verified**: If no candidates pass verification, report as `unknown_program` using the binary filename

**Type Classification** (for the selected Main Program):
- **linux_kernel**: Kernel components (vmlinux, *.ko modules)
- **android_platform**: Android AOSP components (liblog, libcutils, etc.)
- **system_library**: System runtime (glibc, libstdc++, libgcc_s, musl, uclibc)
- **third_party_library**: Open-source TPL
- **unknown_program**: Proprietary/closed-source software

**System Library Details**:

glibc Components (report as name="glibc", component_name=<component>):
- libc.so* → component_name="libc"
- libm.so* → component_name="libm"
- libpthread.so* → component_name="libpthread"
- libdl.so*, librt.so*, libnsl.so*, libresolv.so*, libutil.so*, libcrypt.so*

Standalone System Libraries (report as name=<library>, component_name=null):
- libstdc++.so* → name="libstdc++"
- libgcc_s.so* → name="libgcc_s"
- ld-linux*.so* → name="ld"
- musl*.so* → name="musl"
- uclibc*.so* → name="uclibc"

## 5.2 Dynamic Dependencies
Read from the dynamic_libraries list. Filter out:
- System libraries (libc, libm, libpthread, libdl, librt, libstdc++, libgcc_s, ld-linux)
- Unknown/closed-source libraries

Only report open-source TPLs.

## 5.3 Naming Canonicalization

**Priority Rule**: If Feature Matching shows a library name, use THAT exact name.

**Canonical Names** (common examples - not exhaustive):
| Canonical    | Also Known As                              |
|--------------|--------------------------------------------|
| zlib         | libz                                       |
| openssl      | libssl, libcrypto, OpenSSL                 |
| curl         | libcurl                                    |
| expat        | libexpat                                   |
| libpng       | png                                        |
| sqlite       | sqlite3, libsqlite3                        |
| busybox      | (individual applets like ls, cat)          |
| binutils     | objdump, readelf, nm, as, ld               |
| coreutils    | ls, cat, cp, mv, rm                        |
| util-linux   | mount, fdisk, lsblk, libuuid               |
| e2fsprogs    | libext2fs, libe2p, libcom_err              |
| glibc        | libc, libm, libpthread, ld                 |
| gcc          | libstdc++, libgcc                          |

*Note: This table shows common examples. For libraries not listed, use the candidate name from feature matching.*

**Project vs Component**:
- name = project name (e.g., "openssl", "glibc", "gcc")
- component_name = specific library/binary (e.g., "libssl", "libc", "libstdc++")

---
# 6. Output Format

Output is constrained by a schema. Key points:

- **name**: Required. Use canonical project name. For unknown_program, use the binary filename.
- **component_name**: Optional. Specific component (e.g., "libssl" for openssl).
- **category**: One of: `android_platform`, `third_party_library`, `linux_kernel`, `system_library`, `unknown_program`
- **reasoning**: Include which verification step led to the decision (S1/S2/S3) and the category if it's a false positive (C2/C3/C5).

**Reasoning Examples**:
- "S1: Confirmed via version string 'OpenSSL 1.1.1k'"
- "S2: Excluded - 95% matches in gnulib/ directory (C2 shared dependency)"
- "S3: Excluded - high overlap with confirmed anchor openssl (C3 fork)"

---
# 7. Examples

## Example 1: Shared Dependency (C2)

**Binary**: `tar`

**Candidates**:
- tar: 692 matches, distributed (src/: 40%, lib/: 28%, gnu/: 17%)
- cpio: 156 matches, concentrated (gnulib/: 95%, src/: 3%)
- gnulib: 180 matches, well-distributed

**Identity Markers**: `"GNU tar 1.34"`, `"Copyright Free Software Foundation"`

**Verification**:
- S1: `tar` CONFIRMED as anchor (version string "GNU tar 1.34")
- S2: `cpio` EXCLUDED (95% matches in gnulib/ directory → C2 false positive)
- S3: `gnulib` ACCEPTED (no overlap with tar, represents actual vendored code)

**Output**:
```json
{
    "main_program": {"name": "tar", "category": "third_party_library", ...},
    "static_dependencies": [{"name": "gnulib", "reasoning": "S3: Accepted as vendored dependency"}]
}
```

## Example 2: Fork Disambiguation (C3)

**Binary**: `libssl.so`

**Candidates**:
- openssl: 450 matches, 120 unique
- boringssl: 380 matches, 45 unique (68% overlap with openssl)

**Identity Markers**: `"OpenSSL 1.1.1k"`, `"Copyright OpenSSL Project"`

**Verification**:
- S1: `openssl` CONFIRMED as anchor (explicit version string)
- S3: `boringssl` EXCLUDED (68% overlap with anchor openssl → C3 fork)

**Output**:
```json
{
    "main_program": {"name": "openssl", "component_name": "libssl", "category": "third_party_library",
                     "reasoning": "S1: Confirmed via version string 'OpenSSL 1.1.1k'"}
}
```

## Example 3: System Library

**Binary**: `libstdc++.so.6.0.22`

**Identity Markers**: Build path `gcc-6.4.0/libstdc++-v3/src/c++11/debug.cc`

**Output**:
```json
{
    "main_program": {"name": "gcc", "component_name": "libstdc++", "category": "system_library",
                     "description": "GNU C++ Standard Library runtime",
                     "reasoning": "System library identified by filename pattern and build path"}
}
```

## Example 4: Similar Functionality (C5)

**Binary**: embedded TLS client

**Candidates**:
- openssl: 200 matches, 80 unique
- mbedtls: 180 matches, 95 unique (45% overlap with openssl)

**Identity Markers**: `"mbed TLS 2.16.0"`, `mbedtls_ssl_*` function patterns

**Verification**:
- S1: `mbedtls` CONFIRMED as anchor (explicit version string)
- S3: `openssl` EXCLUDED (overlap with anchor mbedtls → C5 similar functionality)

**Output**:
```json
{
    "main_program": {...},
    "static_dependencies": [{"name": "mbedtls", "reasoning": "S1: Confirmed via version string 'mbed TLS 2.16.0'"}]
}
```

## Example 5: No Verified Candidates (Unknown Program)

**Binary**: `proprietary_app`

**Candidates**:
- openssl: 45 matches, concentrated (third_party/: 90%)
- zlib: 12 matches, 2 unique, no identity markers

**Identity Markers**: No explicit library names, only generic strings like "error", "failed"

**Verification**:
- S2: `openssl` EXCLUDED (concentrated in third_party/ directory → C2)
- Additional: `zlib` EXCLUDED (insufficient evidence - very few unique features, no identity markers)

**Output**:
```json
{
    "main_program": {"name": "proprietary_app", "category": "unknown_program",
                     "reasoning": "No candidates verified; binary appears to be proprietary software"},
    "static_dependencies": []
}
```

## Example 6: Edge Case - Similar Libraries with Weak Evidence

**Binary**: `libkcp.so`

**Candidates**:
- kcp: 15 matches, 12 unique, well-distributed
- clamav: 5 matches, 0 unique (90% overlap with binutils-gdb, cpptrace)
- binutils-gdb: 6 matches, 1 unique (85% overlap with clamav, cpptrace)
- cpptrace: 4 matches, 0 unique (95% overlap with binutils-gdb)

**Identity Markers**: Function prefix `ikcp_*` (e.g., `ikcp_create`, `ikcp_send`)

**Candidate Comparison**:
- kcp: 12 unique features, no significant overlap
- clamav, binutils-gdb, cpptrace: All share generic features (`.text`, `.data`, `memcpy`, `vsprintf`)

**Verification**:
- S1: `kcp` CONFIRMED as anchor (function prefix `ikcp_*` matches library)
- S3 Part A: No competing group with kcp (different feature set)
- S3 Part B: `clamav`, `binutils-gdb`, `cpptrace` form an edge-case group:
  - All non-anchors with very few unique features (0-1)
  - High mutual overlap (>85%)
  - No independent evidence
  - Action: EXCLUDE all (none have sufficient evidence to confirm presence)

**Output**:
```json
{
    "main_program": {"name": "kcp", "category": "third_party_library",
                     "reasoning": "S1: Confirmed via function prefix ikcp_*"},
    "static_dependencies": []
}
```

*Note: The edge-case group (clamav, binutils-gdb, cpptrace) are all excluded because their shared generic features (ELF section names like .text, .data) don't indicate actual library presence.*
"""

    # 可选规则：允许直接发现（不在候选中的库）
    # 用于实际使用，论文实验时不启用
    DirectDiscoveryRule = """
## Additional Rule: Direct Discovery (Enabled)

**Exception to candidate-only verification:**

If Identity Markers contain an **EXPLICIT library name** that is NOT in the candidate list,
you SHOULD report it as a static dependency. This compensates for potential retrieval misses.

**Requirements for Direct Discovery:**
1. **Must have explicit library name** - The library name must appear verbatim in the evidence:
   - ✅ "OpenSSL 1.1.1k" → report openssl
   - ✅ "Copyright zlib authors" → report zlib
   - ✅ "libpng version 1.6.37" → report libpng
   - ❌ "SSL_CTX_new, SSL_connect" → do NOT report openssl (symbol pattern is not explicit name)
   - ❌ "TLS handshake failed" → do NOT report any TLS library (no explicit name)

2. **Use candidate name if match exists** - If the discovered library matches a candidate but with a different name variation, use the candidate's canonical name:
   - Discovered "zlib 1.2.11" + Candidate "zlib" exists → use "zlib"
   - Discovered "OpenSSL" + Candidate "openssl" exists → use "openssl"

3. **Mark in reasoning** - When reporting a directly discovered library, note it in reasoning:
   - "Direct discovery: version string 'zlib 1.2.11' (not in candidate list)"
"""

    # 消融实验 D：简化版 Prompt，不提供详细推理指导
    SimplePrompt = """
You are a binary analysis expert.

Task: Analyze this binary file and identify:
1. Main Program: What is this binary?
2. Dynamic Dependencies: What libraries does it dynamically link to?
3. Static Dependencies: What third-party libraries are statically linked?

Categories:
- "android_platform": Android AOSP components
- "third_party_library": Open-source third-party libraries
- "linux_kernel": Linux kernel components
- "system_library": System runtime libraries (libc, libstdc++, etc.)
- "unknown_program": Proprietary/closed-source software

Rules:
- Only report open-source third-party libraries for dependencies
- Do NOT report system libraries (libc, libm, libstdc++, libgcc_s, etc.) as dependencies
- Use canonical project names (e.g., "openssl" not "libssl", "glibc" not "libc")

Output format:
{
    "main_program": {
        "name": "library name",
        "component_name": "component name or null",
        "category": "category",
        "description": "brief description",
        "evidences": ["evidence1", ...],
        "reasoning": "brief reasoning"
    },
    "dynamic_dependencies": [...],
    "static_dependencies": [...]
}
"""

    # ========== 模块化 Prompt 片段（用于消融实验）==========

    # --- 基础部分（所有消融实验都保留）---
    _BasePrompt = """
# Role
You are a C/C++ binary third-party library (TPL) detection expert. Your task is to verify which candidate libraries are actually present in a given binary.

---
# 1. Task Description

**Problem**: Given a target binary and a set of candidate libraries (retrieved via feature matching), determine which candidates are TRUE POSITIVES (actually compiled into the binary) and which are FALSE POSITIVES (incorrectly matched).

**Input**:
- Target binary information (name, size, symbols, strings)
- Candidate libraries with match evidence

**Output**:

- Main Program: The candidate that best represents what this binary is (or unknown_program if none)
- Static Dependencies: Other verified candidates that are statically linked/embedded
- Dynamic Dependencies: Which TPLs are dynamically linked (from dynamic library list)

**Key Insight**: High feature similarity does NOT guarantee a library is present. You must analyze evidence to verify each candidate.

---
# 2. Background Knowledge: Why False Positives Occur

Feature matching produces false positives due to five categories of causes. Understanding these helps you identify and filter them.

## Category 1 (C1): Imported Symbols
**Cause**: A binary dynamically linking to a library contains import symbols (function references) but NOT the actual code.
**Example**: A binary linking to `libssl.so` has symbols like `SSL_connect`, but the SSL code is in the separate .so file.
**Detection**: These libraries appear in the dynamic_libraries list. Their symbols are IMPORTED, not EXPORTED.
**Note**: This category is already handled during retrieval (we only match exported symbols). Mentioned for completeness.

## Category 2 (C2): Shared Dependencies
**Cause**: Libraries may vendor (include) common dependencies, causing binaries to match unrelated libraries sharing the same vendored code.
**Example**: Both `tar` and `cpio` include `gnulib` code. A `tar` binary incorrectly matches `cpio` because both share gnulib.
**Detection**: Match distribution is CONCENTRATED in a specific subdirectory (e.g., `third_party/`, `vendor/`, or a library name like `gnulib/`).
**Pattern**: If most matches are concentrated in one directory, especially one named after another library, it's likely a shared dependency artifact.

## Category 3 (C3): Evolutionary Relationships (Forks)
**Cause**: Libraries share code due to fork relationships.
**Example**: OpenSSL → BoringSSL, LibreSSL. They share substantial code but are distinct projects.
**Detection**: Significant feature overlap between candidates + known fork relationship. Only ONE can be present.
**Resolution**: Use unique identifiers (version strings, unique symbols) to determine which fork is actually present.

## Category 4 (C4): Coincidental Match
**Cause**: Generic features appear across unrelated libraries.
**Example**: Strings like "error", "default"; function names like `init()`, `parse()`, `read()`.
**Detection**: Very few matched features, all are common/generic terms.
**Note**: This category is handled during retrieval (we filter common features and require minimum matches). Mentioned for completeness.

## Category 5 (C5): Similar Functionality
**Cause**: Independent libraries implementing similar functionality have overlapping features.
**Example**: OpenSSL and mbedTLS both implement TLS, leading to similar API names and protocol strings.
**Detection**: High feature overlap but NO fork relationship. Similar functional descriptions.
**Resolution**: Same as C3 - use unique identifiers to disambiguate.
"""

    # --- Evidence Type 1: Identity Markers（S1 使用）---
    _EvidenceType1 = """
## Evidence Type 1: Identity Markers (from binary)
Human-readable text embedded in binaries that reveals library identity.

**Explicit Markers** (directly name the library):
- Copyright notices: `"Copyright 2023 OpenSSL Project"`
- Version strings: `"OpenSSL 1.1.1k"`, `"zlib 1.2.11"`
- License text: `"Licensed under Apache 2.0"`
- Project URLs: `"https://www.openssl.org"`

**Implicit Markers** (library name appears in code artifacts):
- Function name prefixes: 320 functions with `SSL_*` prefix → OpenSSL
- Debug paths: `/build/openssl-1.1.1k/ssl/ssl_lib.c`
- Namespace patterns: `google::protobuf::*`

**Usage**: Explicit markers can DIRECTLY CONFIRM a candidate. Implicit markers support confirmation.
"""

    # --- Evidence Type 2: Library Metadata（S3 使用）---
    _EvidenceType2 = """
## Evidence Type 2: Library Metadata (from knowledge base)
Pre-collected information about candidate libraries.

- Binary-library hints: Known associations between binary names and libraries
- Functional descriptions: What the library does
- Known forks: Related libraries (e.g., OpenSSL's forks: BoringSSL, LibreSSL)
- Components: Sub-libraries (e.g., OpenSSL has libssl, libcrypto)

**Usage**: Helps identify competing groups (C3, C5) and understand library relationships.
"""

    # --- Evidence Type 3: Match Distribution（S2 使用）---
    _EvidenceType3 = """
## Evidence Type 3: Match Distribution (per candidate)
How matched features are distributed across the candidate's source tree.

**Format**:
```
├── src/       [280, 40%]  main source code
├── lib/       [195, 28%]  library code
├── crypto/    [120, 17%]  crypto module
└── third_party/ [15, 2%]  vendored deps
```

**Interpretation**:
- **Distributed** (spread across multiple directories): Likely TRUE positive
- **Concentrated** (most matches in one directory): Check WHAT directory it's concentrated in:
  - Generic vendor directories: `third_party/`, `vendor/`, `external/`, `deps/` → likely C2 false positive
  - Another library's name: `gnulib/`, `zlib/`, `pcre/` → likely C2 false positive (vendored dependency)
  - Core source directories: `src/`, `lib/`, `core/` → likely TRUE positive (small library with simple structure)
- Use your judgment to assess concentration - there's no fixed threshold
"""

    # --- Evidence Type 4: Candidate Comparison（S3 使用）---
    _EvidenceType4 = """
## Evidence Type 4: Candidate Comparison (overlap analysis)
Feature overlap between candidates.

**Metrics**:
- **Total**: Number of features matched for this candidate
- **Unique**: Features that ONLY match this candidate (not shared with others)
- **Unique%**: Proportion of unique features
- **Overlaps With**: Which other candidates share features

**Interpretation**:
- Significant overlap with another candidate → They are likely competing alternatives (C3 or C5)
- High unique count → Strong discriminative evidence
- Zero or very few unique features → Weak evidence, may be false positive
- Use your judgment - consider both percentage and absolute numbers when assessing overlap
"""

    # --- Step 1: Anchor Confirmation ---
    _StepS1 = """
## Step 1: Anchor Confirmation (S1)
**Goal**: Identify candidates with CLEAR identity markers and confirm them as "anchors".

**Process**:
1. Scan Identity Markers for explicit library names (version strings, copyright)
2. If a marker DIRECTLY NAMES a candidate → CONFIRM that candidate as an anchor
3. Anchors serve as reference points for subsequent disambiguation

**IMPORTANT - Candidate-Only Rule**:
Only verify libraries that are in the candidate list. Even if Identity Markers explicitly mention a library (e.g., "zlib 1.2.11"), if that library is NOT in the candidate list, do NOT report it.
- This applies to BOTH Main Program AND Static Dependencies
- If no candidate matches the binary's identity, report Main Program as `unknown_program`
- This ensures all results are traceable to feature matching

**Example**:
- Identity marker: `"OpenSSL 1.1.1k"`
- Candidate: `openssl`
- Action: CONFIRM `openssl` as anchor

**Output**: Candidates are marked as CONFIRMED (anchor) or PENDING.
"""

    # --- Step 2: Dependency Filtering ---
    _StepS2 = """
## Step 2: Dependency Filtering (S2)
**Goal**: Filter false positives caused by shared dependencies (C2).

**Process**:
For each PENDING candidate, analyze its Match Distribution:

1. **Check concentration**: Are most matches concentrated in a single directory?
2. **Check directory name**:
   - Generic vendor names: `third_party/`, `vendor/`, `external/`, `deps/`
   - Library names: `gnulib/`, `zlib/`, `pcre/`, etc.
3. **Cross-reference**: Does another candidate (with distributed matches) explain these matches?

**Decision**:
- Concentrated in vendor/library directory → EXCLUDE (C2 false positive)
- Well-distributed → KEEP for Step 3
- Use your judgment based on the overall pattern, not fixed thresholds

**Example**:
```
cpio:
├── gnulib/   [148, 95%]  ← Concentrated in library-named directory
├── src/      [4, 3%]
└── lib/      [2, 1%]
```
→ EXCLUDE cpio (C2: matches come from vendored gnulib, not cpio itself)
"""

    # --- Step 3: Alternative Disambiguation ---
    _StepS3 = """
## Step 3: Alternative Disambiguation (S3)
**Goal**: Resolve competing candidates that share features (C3, C5), and handle edge cases with weak evidence.

### Part A: Competing Group Disambiguation
**Process**:
1. **Identify competing groups**: Candidates with significant feature overlap
2. **For each group**:
   a. If an anchor exists in the group → EXCLUDE all others
   b. If no anchor → Compare unique features:
      - Candidate with unique markers in the binary → ACCEPT
      - Candidate with NO unique markers → EXCLUDE
   c. Fallback: If tied, prefer the one with more total matches

**Example**:
- Candidates: `openssl` (anchor), `boringssl` (70% overlap with openssl)
- Action: `openssl` is anchor → EXCLUDE `boringssl`

### Part B: Edge Case Resolution
**Goal**: When multiple non-anchor candidates pass S1-S3 with weak, overlapping evidence, keep only the most likely one.

**Trigger**: Multiple candidates remain after Part A, and they exhibit:
- Very few unique features (typically ≤ 3, use as reference not hard threshold)
- High feature overlap with each other (typically > 80%)
- No independent evidence to support their presence (not anchors, no cross-validation)

**Process**:
1. Identify groups of similar candidates with high mutual overlap
2. For each group, keep ONLY the most likely candidate based on:
   a. Best match with binary name or identity hints
   b. More unique features (relative comparison)
   c. Higher total match count
3. EXCLUDE the rest as edge-case false positives

**Rationale**: When candidates lack unique features AND share most evidence with each other AND have no independent confirmation, they likely matched due to generic/shared features. Keeping all of them inflates false positives.

**Example**:
- Candidates after S3a: `clamav` (8 matches, 0 unique), `binutils-gdb` (10 matches, 1 unique), `cpptrace` (6 matches, 0 unique)
- All have >80% overlap, none are anchors, no identity markers
- Action: Keep `binutils-gdb` (most matches, has unique feature), EXCLUDE `clamav` and `cpptrace`
"""

    # --- 额外规则（所有步骤共用）---
    _AdditionalRules = """
## Additional Rules

**Evidence Conflict Resolution**:
When different evidence types conflict, explicit Identity Markers (version strings, copyright notices) take precedence over statistical evidence (Match Distribution, overlap percentages).

**Reference Thresholds** (use as guidance, not hard rules):
- "Very few unique features": typically ≤ 3
- "High overlap": typically > 80%
- Always consider the overall context when applying these thresholds
"""

    # --- Role Assignment（所有配置都需要）---
    _RoleAssignment = """
---
# 5. Role Assignment (After Verification)

## 5.1 Main Program Selection

After verifying candidates, select ONE verified candidate as the Main Program.

**Selection Criteria** (in priority order):
1. **Best identity match**: The candidate whose name best matches the binary filename or has the strongest identity markers
2. **Highest match count**: Among equally strong candidates, prefer the one with more matched features
3. **None verified**: If no candidates pass verification, report as `unknown_program` using the binary filename

**Type Classification** (for the selected Main Program):
- **linux_kernel**: Kernel components (vmlinux, *.ko modules)
- **android_platform**: Android AOSP components (liblog, libcutils, etc.)
- **system_library**: System runtime (glibc, libstdc++, libgcc_s, musl, uclibc)
- **third_party_library**: Open-source TPL
- **unknown_program**: Proprietary/closed-source software

**System Library Details**:

glibc Components (report as name="glibc", component_name=<component>):
- libc.so* → component_name="libc"
- libm.so* → component_name="libm"
- libpthread.so* → component_name="libpthread"
- libdl.so*, librt.so*, libnsl.so*, libresolv.so*, libutil.so*, libcrypt.so*

Standalone System Libraries (report as name=<library>, component_name=null):
- libstdc++.so* → name="libstdc++"
- libgcc_s.so* → name="libgcc_s"
- ld-linux*.so* → name="ld"
- musl*.so* → name="musl"
- uclibc*.so* → name="uclibc"

## 5.2 Dynamic Dependencies
Read from the dynamic_libraries list. Filter out:
- System libraries (libc, libm, libpthread, libdl, librt, libstdc++, libgcc_s, ld-linux)
- Unknown/closed-source libraries

Only report open-source TPLs.

## 5.3 Naming Canonicalization

**Priority Rule**: If Feature Matching shows a library name, use THAT exact name.

**Canonical Names** (common examples - not exhaustive):
| Canonical    | Also Known As                              |
|--------------|--------------------------------------------|
| zlib         | libz                                       |
| openssl      | libssl, libcrypto, OpenSSL                 |
| curl         | libcurl                                    |
| expat        | libexpat                                   |
| libpng       | png                                        |
| sqlite       | sqlite3, libsqlite3                        |
| busybox      | (individual applets like ls, cat)          |
| binutils     | objdump, readelf, nm, as, ld               |
| coreutils    | ls, cat, cp, mv, rm                        |
| util-linux   | mount, fdisk, lsblk, libuuid               |
| e2fsprogs    | libext2fs, libe2p, libcom_err              |
| glibc        | libc, libm, libpthread, ld                 |
| gcc          | libstdc++, libgcc                          |

*Note: This table shows common examples. For libraries not listed, use the candidate name from feature matching.*

**Project vs Component**:
- name = project name (e.g., "openssl", "glibc", "gcc")
- component_name = specific library/binary (e.g., "libssl", "libc", "libstdc++")

---
# 6. Output Format

Output is constrained by a schema. Key points:

- **name**: Required. Use canonical project name. For unknown_program, use the binary filename.
- **component_name**: Optional. Specific component (e.g., "libssl" for openssl).
- **category**: One of: `android_platform`, `third_party_library`, `linux_kernel`, `system_library`, `unknown_program`
- **reasoning**: Include which verification step led to the decision (S1/S2/S3) and the category if it's a false positive (C2/C3/C5).

**Reasoning Examples**:
- "S1: Confirmed via version string 'OpenSSL 1.1.1k'"
- "S2: Excluded - 95% matches in gnulib/ directory (C2 shared dependency)"
- "S3: Excluded - high overlap with confirmed anchor openssl (C3 fork)"
"""

    # --- Examples（所有配置都需要，但内容可根据消融调整）---
    _Examples = """
---
# 7. Examples

## Example 1: Shared Dependency (C2)

**Binary**: `tar`

**Candidates**:
- tar: 692 matches, distributed (src/: 40%, lib/: 28%, gnu/: 17%)
- cpio: 156 matches, concentrated (gnulib/: 95%, src/: 3%)
- gnulib: 180 matches, well-distributed

**Identity Markers**: `"GNU tar 1.34"`, `"Copyright Free Software Foundation"`

**Verification**:
- S1: `tar` CONFIRMED as anchor (version string "GNU tar 1.34")
- S2: `cpio` EXCLUDED (95% matches in gnulib/ directory → C2 false positive)
- S3: `gnulib` ACCEPTED (no overlap with tar, represents actual vendored code)

**Output**:
```json
{
    "main_program": {"name": "tar", "category": "third_party_library", ...},
    "static_dependencies": [{"name": "gnulib", "reasoning": "S3: Accepted as vendored dependency"}]
}
```

## Example 2: Fork Disambiguation (C3)

**Binary**: `libssl.so`

**Candidates**:
- openssl: 450 matches, 120 unique
- boringssl: 380 matches, 45 unique (68% overlap with openssl)

**Identity Markers**: `"OpenSSL 1.1.1k"`, `"Copyright OpenSSL Project"`

**Verification**:
- S1: `openssl` CONFIRMED as anchor (explicit version string)
- S3: `boringssl` EXCLUDED (68% overlap with anchor openssl → C3 fork)

**Output**:
```json
{
    "main_program": {"name": "openssl", "component_name": "libssl", "category": "third_party_library",
                     "reasoning": "S1: Confirmed via version string 'OpenSSL 1.1.1k'"}
}
```

## Example 3: No Verified Candidates (Unknown Program)

**Binary**: `proprietary_app`

**Candidates**:
- openssl: 45 matches, concentrated (third_party/: 90%)
- zlib: 12 matches, 2 unique, no identity markers

**Identity Markers**: No explicit library names, only generic strings like "error", "failed"

**Verification**:
- S2: `openssl` EXCLUDED (concentrated in third_party/ directory → C2)
- Additional: `zlib` EXCLUDED (insufficient evidence - very few unique features, no identity markers)

**Output**:
```json
{
    "main_program": {"name": "proprietary_app", "category": "unknown_program",
                     "reasoning": "No candidates verified; binary appears to be proprietary software"},
    "static_dependencies": []
}
```

## Example 4: Edge Case - Similar Libraries with Weak Evidence

**Binary**: `libkcp.so`

**Candidates**:
- kcp: 15 matches, 12 unique, well-distributed
- clamav: 5 matches, 0 unique (90% overlap with binutils-gdb, cpptrace)
- binutils-gdb: 6 matches, 1 unique (85% overlap with clamav, cpptrace)
- cpptrace: 4 matches, 0 unique (95% overlap with binutils-gdb)

**Identity Markers**: Function prefix `ikcp_*` (e.g., `ikcp_create`, `ikcp_send`)

**Candidate Comparison**:
- kcp: 12 unique features, no significant overlap
- clamav, binutils-gdb, cpptrace: All share generic features (`.text`, `.data`, `memcpy`, `vsprintf`)

**Verification**:
- S1: `kcp` CONFIRMED as anchor (function prefix `ikcp_*` matches library)
- S3 Part A: No competing group with kcp (different feature set)
- S3 Part B: `clamav`, `binutils-gdb`, `cpptrace` form an edge-case group:
  - All non-anchors with very few unique features (0-1)
  - High mutual overlap (>85%)
  - No independent evidence
  - Action: EXCLUDE all (none have sufficient evidence to confirm presence)

**Output**:
```json
{
    "main_program": {"name": "kcp", "category": "third_party_library",
                     "reasoning": "S1: Confirmed via function prefix ikcp_*"},
    "static_dependencies": []
}
```

*Note: The edge-case group (clamav, binutils-gdb, cpptrace) are all excluded because their shared generic features (ELF section names like .text, .data) don't indicate actual library presence.*
"""

    @classmethod
    def build_system_prompt(
        cls,
        include_s1: bool = True,
        include_s2: bool = True,
        include_s3: bool = True,
        allow_direct_discovery: bool = False
    ) -> str:
        """
        根据消融配置构建 System Prompt

        Args:
            include_s1: 是否包含 S1 (Anchor Confirmation) 和 Evidence Type 1
            include_s2: 是否包含 S2 (Dependency Filtering) 和 Evidence Type 3
            include_s3: 是否包含 S3 (Alternative Disambiguation) 和 Evidence Type 2+4
            allow_direct_discovery: 是否允许报告候选之外的库

        Returns:
            组合后的 System Prompt
        """
        prompt_parts = [cls._BasePrompt]

        # --- Evidence Definitions ---
        prompt_parts.append("\n---\n# 3. Evidence Definitions\n\nYou will receive the following types of evidence:\n")

        if include_s1:
            prompt_parts.append(cls._EvidenceType1)
        if include_s3:
            prompt_parts.append(cls._EvidenceType2)
        if include_s2:
            prompt_parts.append(cls._EvidenceType3)
        if include_s3:
            prompt_parts.append(cls._EvidenceType4)

        # --- Verification Guidelines ---
        active_steps = []
        if include_s1:
            active_steps.append("S1")
        if include_s2:
            active_steps.append("S2")
        if include_s3:
            active_steps.append("S3")

        if active_steps:
            prompt_parts.append(f"\n---\n# 4. Verification Guidelines: {'/'.join(active_steps)} Process\n")
            prompt_parts.append("\nApply these steps IN ORDER. Each step builds on the previous.\n")

            if include_s1:
                prompt_parts.append(cls._StepS1)
            if include_s2:
                prompt_parts.append(cls._StepS2)
            if include_s3:
                prompt_parts.append(cls._StepS3)

            prompt_parts.append(cls._AdditionalRules)
        else:
            # 无任何步骤时，只给基本指导
            prompt_parts.append("\n---\n# 4. Verification Guidelines\n")
            prompt_parts.append("\nAnalyze the candidates based on available evidence and determine which are true positives.\n")

        # --- Role Assignment & Output Format ---
        prompt_parts.append(cls._RoleAssignment)

        # --- Examples ---
        prompt_parts.append(cls._Examples)

        # --- Direct Discovery Rule (optional) ---
        if allow_direct_discovery:
            prompt_parts.append("\n" + cls.DirectDiscoveryRule)

        return "".join(prompt_parts)
