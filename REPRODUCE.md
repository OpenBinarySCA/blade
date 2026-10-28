# Reproducing the ISSTA 2026 results

> Chengyue Liu, Zhengzi Xu, Lyuye Zhang, Jiahui Wu, Kaixuan Li, and Yang Liu. 2026.
> *Beyond Similarity Scores: Evidence-Based Third-Party Library Detection for C/C++ Binaries.*
> Proc. ACM Softw. Eng. 3, ISSTA, Article ISSTA034. https://doi.org/10.1145/3832125

## 1. Recompute the tables from the experiment results

No LLM, database or network is needed (Python ≥ 3.11, standard library only; matplotlib is
optional for the Figure 10 PNG).

```bash
python3 reproduce.py --check          # Table 3 and Table 5 headline numbers
python3 reproduce.py --scope full     # all tables, Figure 10, exclusion and error analysis
python3 reproduce.py --only table4    # a single table
```

## 2. Re-run detection

### Data

The benchmark ground truth is `data/benchmarks/conan_bench/conan_benchmark.json`
(3,403 binaries, 1,016 libraries, 3,771 reuse relations). The benchmark binaries and the TPL
database snapshot are large and are provided separately; please open an issue to obtain them.
Place the binaries under `data/benchmarks/conan_bench/test_cases/`. The scripts used to build the
benchmark from Conan packages are in `data_management/benchmark_management/conan_benchmark_generation/`
(see its README).

The in-vehicle dataset (Table 5) is proprietary and is not distributed.

### Environment

```bash
brew install lzo                    # or: apt install liblzo2-dev
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

In `.env`, set the database connection and the LLM:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5466
POSTGRES_USERNAME=tpl_data
POSTGRES_PASSWORD=tpl_data
POSTGRES_DATABASE=tpl_data

LLM_PROVIDER=openai
LLM_MODEL_ID=gpt-5
OPENAI_API_KEY=...
# OPENROUTER_API_KEY=...   # for gpt-oss-120b
```

### TPL database

```bash
scripts/deploy_debug_infra.sh
scripts/restore_tpl_data.sh --debug <tpl_data_backup>.sql
```

### Run

| Paper item | `LLM_PROVIDER` / `LLM_MODEL_ID` | Command |
|------------|---------------------------------|---------|
| Table 3 BLADE-G5 | `openai` / `gpt-5` | `python evaluation_runner.py conan` |
| Table 3 BLADE-G5m | `openai` / `gpt-5-mini` | `python evaluation_runner.py conan` |
| Table 3 BLADE-G4.1 | `openai` / `gpt-4.1` | `python evaluation_runner.py conan` |
| Table 3 BLADE-OSS | `openrouter` / `openai/gpt-oss-120b` | `python evaluation_runner.py conan` |
| Table 4 ablations | `openai` / `gpt-5-mini` | `python evaluation_runner.py ablation` |
| Table 4 w/o Verification, Figure 10 | any | `python evaluation_runner.py topn` |
| Table 5 | `openai` / `gpt-5` | `python evaluation_runner.py car` |

Results are written to `data/benchmarks/<benchmark>/runs/<model or experiment>/<timestamp>/`.
LLM outputs are not fully deterministic, so re-runs give results close to the reported ones.

## Results in this repository

All under `data/benchmarks/`:

| Paper item | Result |
|------------|--------|
| Table 3 BLADE-G5, exclusion and error analysis | `conan_bench/results/gpt-5/` |
| Table 3 BLADE-G5m, Table 4 (BLADE) | `conan_bench/results/gpt-5-mini/` |
| Table 3 BLADE-G4.1 | `conan_bench/results/gpt-4.1/` |
| Table 3 BLADE-OSS | `conan_bench/results/gpt-oss-120b/` |
| Table 3 baselines | `conan_bench/results/baselines/` |
| Table 4 w/o Structured Evidence | `conan_bench/results/wo_structured_evidence/` |
| Table 4 w/o Category-Guided Verification | `conan_bench/results/wo_category_guided_verification/` |
| Table 4 w/o Verification, Figure 10 | `conan_bench/results/retrieval_only/` |
| Table 5 | `car_bench/results/gpt-5/` |
