# BLADE

[![ISSTA 2026](https://img.shields.io/badge/ISSTA-2026-blue)](https://doi.org/10.1145/3832125)
[![ACM SIGSOFT Distinguished Paper Award](https://img.shields.io/badge/ACM%20SIGSOFT-Distinguished%20Paper%20Award-gold)](https://doi.org/10.1145/3832125)
[![DOI](https://img.shields.io/badge/DOI-10.1145%2F3832125-blue)](https://doi.org/10.1145/3832125)
[![Reproduce](https://img.shields.io/badge/reproduce-issta2026%20branch-brightgreen)](https://github.com/OpenBinarySCA/blade/tree/issta2026)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-lightgrey)](LICENSE)

BLADE detects third-party libraries (TPLs) reused in compiled C/C++ binaries. It retrieves
candidate libraries by string and symbol feature matching, then uses an LLM to verify each
candidate against structured evidence. BLADE was published at ISSTA 2026
([paper](https://chengyueliu.github.io/files/papers/issta2026-blade.pdf)) and received an
ACM SIGSOFT Distinguished Paper Award.

> **Reproducing the paper?** Use the [`issta2026`](https://github.com/OpenBinarySCA/blade/tree/issta2026)
> branch. It is frozen at the version used in the paper and includes the data, results and
> reproduction instructions. This `main` branch is under active development.

[Usage](#usage) · [Citation](#citation) · [License](#license)

## Usage

Requirements: Python 3.12, Docker, an LLM API key (OpenAI, Anthropic, OpenRouter or Ollama),
and the TPL feature database (a database snapshot is available on request — please open an issue).

### Web platform

```bash
cp compose/.env.production.example .env            # set the LLM provider and API key
./scripts/deploy_prod_infra.sh                       # PostgreSQL, Redis, MinIO
./scripts/restore_tpl_data.sh --prod <tpl_data_backup>.sql
./scripts/start_prod_app.sh                          # API, worker and web UI
```

Open http://localhost to upload a binary or firmware image. API documentation is at
http://localhost/api/docs.

### Python

```bash
cp .env.example .env                                 # set the LLM provider, API key and database
./scripts/deploy_debug_infra.sh
./scripts/restore_tpl_data.sh --debug <tpl_data_backup>.sql
pip install -r requirements.txt
python examples/analyze_single_binary.py             # analyzes a sample binary from examples/test_cases/
```

See [`examples/`](examples/) for batch analysis and firmware extraction.

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

[PolyForm Noncommercial License 1.0.0](LICENSE): free for non-commercial use such as research,
teaching and evaluation. For commercial use, please contact the authors by opening an issue.
