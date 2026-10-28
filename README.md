# BLADE — ISSTA 2026

This branch is frozen at the version of BLADE used in the ISSTA 2026 paper
*Beyond Similarity Scores: Evidence-Based Third-Party Library Detection for C/C++ Binaries*
(ACM SIGSOFT Distinguished Paper Award). It contains the code, data and results needed to
reproduce the paper. For the latest version of BLADE, see
[`main`](https://github.com/OpenBinarySCA/blade/tree/main).

[What's included](#whats-included) · [Reproducing the results](#reproducing-the-results) · [Citation](#citation)

## What's included

| What | Where |
|------|-------|
| BLADE (tool) | `app/` |
| Experiment scripts | `evaluation_runner.py` |
| Evaluation code | `evaluation/`, `reproduce.py` |
| Benchmark ground truth (3,403 binaries) | `data/benchmarks/conan_bench/conan_benchmark.json` |
| Benchmark construction scripts | `data_management/benchmark_management/` |
| Results for Tables 3–5 and Figure 10 | `data/benchmarks/*/results/` |

The benchmark binaries and the TPL database snapshot are large and are provided separately
(see [REPRODUCE.md](REPRODUCE.md)). The in-vehicle dataset used in Table 5 is proprietary and
is not distributed; its aggregate result is included.

## Reproducing the results

[REPRODUCE.md](REPRODUCE.md) covers three steps: (1) rebuilding the benchmark, (2) re-running
the experiments, and (3) recomputing the paper's tables and figure. The experiment results
used in the paper are included, so step 3 can be run directly (Python 3.11+, no LLM or database
needed):

```bash
python3 reproduce.py
```

## Citation

```bibtex
@article{liu2026blade,
  title     = {Beyond Similarity Scores: Evidence-Based Third-Party Library Detection for C/C++ Binaries},
  author    = {Liu, Chengyue and Xu, Zhengzi and Zhang, Lyuye and Wu, Jiahui and Li, Kaixuan and Liu, Yang},
  journal   = {Proceedings of the ACM on Software Engineering},
  volume    = {3},
  number    = {ISSTA},
  articleno = {ISSTA034},
  year      = {2026},
  doi       = {10.1145/3832125}
}
```

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)
