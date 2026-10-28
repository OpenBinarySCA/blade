# Conan benchmark construction

Scripts used to build the Conan benchmark: compile Conan packages under three configurations,
collect the produced binaries with their dependency metadata, and write them in the benchmark
format used by the evaluation. The released benchmark is
`data/benchmarks/conan_bench/conan_benchmark.json`.

| Configuration | Profile |
|---------------|---------|
| gcc + x86_64  | `conan_libs_builder/profiles/x86_64-gcc-release-shared` |
| clang + x86_64 | `conan_libs_builder/profiles/x86_64-clang-release-shared` |
| gcc + arm     | `conan_libs_builder/profiles/arm_64-gcc-release-shared` |

## Requirements

Ubuntu 22.04, Python 3.12, [Conan 2.x](https://conan.io), GCC 11, Clang, and the AArch64
cross toolchain:

```bash
sudo apt install -y build-essential cmake git pkg-config clang gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
pip install conan && conan profile detect --force
```

## Steps

Run from the repository root:

```bash
M=data_management.benchmark_management.conan_benchmark_generation
python -m $M.conan_libs_builder.get_conan_libs          # (optional) refresh conan_libs.json
python -m $M.conan_libs_builder.batch_build_conan_libs  # build every library with the three profiles
python -m $M.compiled_files_parser                      # collect binaries -> benchmark_meta/conan_lib_info.json
python -m $M.conan_benchmark_generater                  # -> benchmark_meta/conan_library_benchmark.json
python -m $M.conan_benchmark_converter                  # -> benchmark_meta/conan_benchmark.json
python -m $M.conan_benchmark_copyer                     # copy and strip binaries into data/benchmarks/conan_bench/test_cases
```

Build outputs go to `conan_libs_builder_output/` and the test binaries to
`data/benchmarks/conan_bench/test_cases/`; set `CONAN_LIBS_BUILDER_OUTPUT` and
`CONAN_BENCHMARK_TEST_CASE_DIR` to use other locations (see `paths.py`).
