# BLADE — ISSTA 2026

BLADE detects which open-source third-party libraries (TPLs) are reused inside compiled,
stripped C/C++ binaries. It retrieves candidate libraries by string/symbol feature matching and
then has an LLM verify each candidate against structured evidence.

This branch contains the code, benchmark ground truth, experiment results and reproduction
scripts for the ISSTA 2026 paper. Ongoing development happens on
[`main`](https://github.com/OpenBinarySCA/blade/tree/main).

See **[REPRODUCE.md](REPRODUCE.md)** to reproduce the results. Quick check:

```bash
python3 reproduce.py --check
```

## Layout

| Path | Contents |
|------|----------|
| `app/services/tpl_detection/` | Detection pipeline: `feature_matching/` (candidate retrieval), `composition_analysis/` (LLM verification) |
| `app/` | Configuration, database access, API service |
| `evaluation/` | Benchmark evaluation and analyses |
| `evaluation_runner.py` | Runs the experiments |
| `reproduce.py` | Recomputes the paper's tables from the results in `data/benchmarks/` |
| `data/benchmarks/` | Benchmark ground truth and experiment results |
| `data/` | String / function-name filters and library list used by retrieval |
| `data_management/benchmark_management/` | Benchmark construction scripts |
| `scripts/`, `compose/` | TPL database restore and local infrastructure |

## Citation

```bibtex
@article{liu2026blade,
  title   = {Beyond Similarity Scores: Evidence-Based Third-Party Library Detection for C/C++ Binaries},
  author  = {Liu, Chengyue and Xu, Zhengzi and Zhang, Lyuye and Wu, Jiahui and Li, Kaixuan and Liu, Yang},
  journal = {Proceedings of the ACM on Software Engineering},
  volume  = {3},
  number  = {ISSTA},
  articleno = {ISSTA034},
  year    = {2026},
  doi     = {10.1145/3832125}
}
```

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)
