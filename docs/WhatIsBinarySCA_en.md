# Binary Software Composition Analysis

## 1. Core Concept Definitions

### 1.1 Third-Party Library (TPL)

A third-party library refers to a software library developed and maintained by external developers or organizations and released under an open-source license. These libraries are typically hosted on public code repositories (such as GitHub, GitLab) and are freely available for other developers to use.

**Characteristics**:
- Not developed by the project itself
- Publicly accessible source code
- Clear open-source license
- Version management and release history

### 1.2 Library Name

Library names can be determined in several ways:

1. **Source code repository name**: such as the repository name `openssl/openssl` on GitHub
2. **Official project name**: the formal name declared in the project documentation
3. **Package name in package managers**: such as `libssl-dev` in apt, package names in npm

In SCA reports, priority is given to using the **official project name** or **source code repository name** to ensure accuracy and consistency.

### 1.3 Library Version

Version numbers can be determined by:

1. **Git tag**: release versions marked in the source code repository, such as `v1.1.1k`, `release-1.2.11`
2. **Semantic versioning**: following the format `major.minor.patch`, such as `1.2.11`
3. **Commit hash**: in some cases, Git commit hash may be used to identify a specific version

Version identification is one of the most challenging parts of SCA, as version information in binary files may be optimized away or incomplete.

### 1.4 Library Component

A component refers to an **independently distributable and usable artifact** produced after compiling and building an open-source project.

**Component types**:
1. **Executable files**: such as the `openssl` command-line tool
2. **Static libraries**: such as `libz.a` (Linux), `zlib.lib` (Windows)
3. **Dynamic/shared libraries**: such as `libssl.so` (Linux), `ssl.dll` (Windows), `libssl.dylib` (macOS)
4. **Header-only components**: modules containing only header files, such as some Boost sub-libraries

**Importance of component identification**:
- Different components may have different functionalities and dependencies
- Certain known vulnerabilities may only affect specific components
- License compliance analysis requires knowing which specific components are used

**OpenSSL Project Example**:

After compiling the OpenSSL source code, three main components are produced:
- `openssl`: command-line tool program
- `libssl`: SSL/TLS protocol implementation library
- `libcrypto`: cryptographic algorithm implementation library

A web server program may only link to `libssl` and `libcrypto`, without including the `openssl` command-line tool. SCA reports should accurately identify which specific components are used.

**Other examples**:
- **Boost**: contains multiple sub-library components such as Boost.Filesystem, Boost.Thread, Boost.Regex
- **FFmpeg**: contains multiple library components such as libavcodec, libavformat, libavutil
- **Qt**: contains multiple module components such as QtCore, QtGui, QtNetwork

## 2. Code Sources in C/C++ Binary Programs

A compiled C/C++ binary file does not simply come from code written by developers, but is a comprehensive product of various code sources after compilation and linking. Understanding these code sources is the foundation for conducting software composition analysis.

### 2.1 Code Sources in the Source Code Stage

```
【Source Code Stage】

+-----------+     Clone/Copy      +----------------+
| Third     | ----------------> |                |
| Party     |                    |  Your Source   |
| Open      |                    |  Code          |
| Source    |                    |  .cpp/.c       |
| Code      |                    |                |
+-----------+                    |                |
                                 |                |
+-----------+     #include       |                |
| Header    | ----------------> |                |
| Only      |     (Insert)       +----------------+
| Libraries |                          |
+-----------+          |               |
                       |               |
+-----------+          |               |
| System    | ---------+               |
| Headers   |     (Insert)             |
| stdio.h   |                          |
+-----------+                          |
```

In the source code stage, code mainly comes from the following parts:

1. **Developer-written source code**: the project's own .cpp, .c, .h files
2. **Cloned third-party open-source code**: third-party library source code directly copied into the project
3. **Header-only libraries**: header-only libraries introduced via #include (such as Eigen, some Boost components), whose code is completely expanded and inserted into source files during preprocessing
4. **System header files**: standard library header files (such as stdio.h, vector), similarly inserted via #include

### 2.2 Code Sources in the Compilation and Linking Stage

```
                        +---------------------------+
                        |      Preprocessor         |
                        | Macro expansion,          |
                        | conditional compilation   |
                        | Template instantiation    |
                        +---------------------------+
                                       |
                                       v
                        +---------------------------+
                        |      Compiler             |
           +---------->| Insert: Exception         |
           |            |         handling code     |
Compiler   |            |         Type info (RTTI)  |
Auto-      |            |         Constructors/     |
generated  |            |         Destructors       |
           |            |         Virtual tables    |
           +---------->+---------------------------+
                                       |
                                       v
                        +---------------------------+
                        |    Object files           |
                        |    .o/.obj                |
                        +---------------------------+
                                       |
+-----------+                          |
| Static    | -------------------------+
| Libraries |      Linking              |
| .a/.lib   |      (Embed code)        |
+-----------+                          |
                                       |
+-----------+                          |
| Startup   | -------------------------+
| Code      |      (Program entry)     |
| crt0.o    |                          |
+-----------+                          |
                                       v
                        +---------------------------+
                        |      Linker               |
           +---------->|  Insert: Symbol tables    |
           |            |          Relocation info  |
Linker     |            |          Debug info       |
Inserted   |            |                           |
Content    +---------->+---------------------------+
                                       |
                                       v
                        +---------------------------+
                        |      Final Binary File    |
                        +---------------------------+
                                       ^
                                       |
+-----------+                          |
| Dynamic   | -------------------------+
| Libraries |  Symbol references        |
| .so/.dll  |  (Runtime loading, not embedded)
+-----------+
```

In the compilation and linking stage, additional code is added:

5. **Compiler-generated code**:
   - Exception handling mechanism code
   - Runtime Type Information (RTTI)
   - Default constructors and destructors
   - Virtual function tables (vtable)

6. **Statically linked third-party libraries**: .a (Linux) or .lib (Windows) format library files, whose code is completely embedded into the final binary

7. **System runtime libraries**: such as libc, libstdc++, which may be linked statically or dynamically

8. **Program startup code**: such as crt0.o, responsible for initialization before the main function executes

9. **Linker-inserted metadata**: symbol tables, relocation information, debug information, etc.

10. **Dynamic library references**: .so (Linux), .dll (Windows), .dylib (macOS) format shared libraries, whose code **is not embedded in the binary**, only symbol references are retained, and are dynamically loaded at program runtime

### 2.3 Summary of Code Composition

According to whether code is embedded in the final binary file, we can classify the composition into two major categories:

**Embedded Components** (code exists inside the binary file):
- Self-written source code
- Cloned third-party open-source source code
- Header-only libraries
- Statically linked third-party libraries
- Compiler and linker auto-generated code

**Referenced Components** (only references retained, loaded at runtime):
- Dynamically linked third-party libraries
- Dynamically linked system libraries

## 3. What is Software Composition Analysis

Software Composition Analysis (SCA) is a technique for identifying and analyzing open-source components and third-party code used in software. For binary programs, the goal of SCA is to analyze compiled binary files without source code to answer the following three core questions:

### 3.1 Analysis Objectives

1. **Primary program identification**: Is this binary file compiled from an open-source third-party library, and if so, what is it?

2. **Static dependency identification**: Besides the primary program, what other open-source third-party library code has been directly compiled or statically linked into the binary file? This code is now part of the binary file.

3. **Dynamic dependency identification**: What open-source third-party libraries are depended on by this program through dynamic linking? These libraries are only loaded at program runtime.

The final output of software composition analysis is a detailed report listing all identifiable third-party components in the binary program. This report is commonly referred to as a **Software Bill of Materials (SBOM)**.

## 4. Granularity of Analysis Reports

A complete SCA report needs to describe each identified third-party library in three dimensions:

### 4.1 Library Name

The library name typically refers to the **source code repository name** or official project name of the open-source project.

**Examples**:
- OpenSSL
- zlib  
- libcurl
- Boost

### 4.2 Library Version

Version numbers typically correspond to **Git tags** or official release version numbers published in the source code repository.

**Examples**:
- OpenSSL 1.1.1k
- zlib 1.2.11
- libcurl 7.68.0
- Boost 1.75.0

Version information is crucial because different versions may have different security vulnerabilities. An important application of SCA is to identify the versions of third-party libraries used in binary programs to determine whether known vulnerabilities exist.

### 4.3 Library Component

An open-source project often produces multiple **independently usable artifacts** after compilation, which are called components. A binary program typically does not use all components of a library, but only depends on one or several of them.

**OpenSSL Project Example**:

After compiling the OpenSSL source code, three main components are produced:
- `openssl`: command-line tool program
- `libssl.so`: shared library implementing SSL/TLS protocol
- `libcrypto.so`: shared library implementing cryptographic algorithms

A web server program may only link to `libssl.so` and `libcrypto.so`, without including the `openssl` command-line tool. SCA reports should accurately identify which specific components are used.

**Other examples**:
- **Boost**: contains multiple sub-library components such as Boost.Filesystem, Boost.Thread, Boost.Regex
- **FFmpeg**: contains multiple library components such as libavcodec, libavformat, libavutil
- **Qt**: contains multiple module components such as QtCore, QtGui, QtNetwork

### 4.4 Report Example

A typical SCA report entry may look like this:

| Library Name | Version | Component | Linking Method |
|--------------|---------|-----------|----------------|
| OpenSSL | 1.1.1k | libssl | Dynamic linking |
| OpenSSL | 1.1.1k | libcrypto | Dynamic linking |
| zlib | 1.2.11 | libz | Static linking |
| Boost | 1.75.0 | Boost.Filesystem | Header-only/Static linking |

Note: The "Component" column in the table uses component names from the source code (such as libssl, libcrypto), not the file names of compiled artifacts (such as libssl.so, libcrypto.dll). This is because the same component may have different file names when compiled on different platforms, but the component names in the source code are uniform.

## 5. Application Scenarios of SCA

### 5.1 Security Vulnerability Detection

By identifying third-party libraries and their versions used in binary programs, known vulnerability databases (such as CVE, NVD) can be queried to determine whether the program is affected by publicly disclosed vulnerabilities.

**Typical scenarios**:
- Detecting whether a program uses a version of OpenSSL with the Heartbleed vulnerability
- Identifying whether a version of Log4j library with the Log4Shell vulnerability is used (Java scenario)

### 5.2 Open-Source License Compliance

Different open-source licenses (such as GPL, Apache, MIT) have different requirements for the use, modification, and distribution of software. SCA can help identify the licenses of all third-party libraries used in a program to ensure compliant use.

### 5.3 Software Supply Chain Management

Modern software development highly depends on third-party components. The SBOM provided by SCA is the foundation for managing software supply chains, helping organizations understand the composition of their software assets and respond to supply chain attack risks.

### 5.4 Legacy System Maintenance

For legacy binary systems lacking source code or documentation, SCA can help reverse engineers understand the technology stack and dependencies of the system, providing a basis for system maintenance and upgrades.

## 6. Challenges of Binary SCA

Compared to source code SCA, binary SCA faces greater technical challenges:

1. **Information loss**: The compilation and linking process removes a large amount of metadata, such as variable names, comments, file structure, etc.
2. **Code optimization**: Compiler optimizations (such as inlining, dead code elimination) change code structure
3. **Version identification difficulty**: Version strings may be optimized away or not exist
4. **Blurred component boundaries**: Static linking mixes code from multiple libraries together, making it difficult to distinguish
5. **Obfuscation and packing**: Some programs may be obfuscated or packed, increasing analysis difficulty

Despite these challenges, binary SCA remains an indispensable technology in software security and supply chain management, especially in scenarios where source code cannot be obtained.