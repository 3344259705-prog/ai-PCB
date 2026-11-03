# PCBLoop

**Conversational PCB collaboration with verifiable engineering experience.**

[中文](README.md)

Status: **v0.2.0-skill**. This repository provides an installable PCB workflow skill,
architecture documents, a draft episode schema, a synthetic example and a local metadata validator.
There is **no working CAD adapter, autorouter, community database or model-training service yet**.

## Vision

A user explains a PCB task and its constraints. An AI reads the current design,
proposes changes within the granted scope, and uses a CAD adapter to execute them.
State guards, diffs, connectivity checks, DRC, checkpoints and human review produce
an auditable engineering episode. Approved and appropriately licensed episodes
can later support retrieval, evaluation and separate model-training experiments.

The first intended CAD integration is 嘉立创EDA专业版 (EasyEDA Professional Edition).
No third-party bridge, real PCB source, private conversation or collected dataset
is distributed in this repository. There is no telemetry or upload service.

## Run the local validator

Use Python 3.10+ in a virtual environment:

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_episode.py examples/synthetic_episode.json
python tools/validate_episode.py --for-publication examples/synthetic_episode.json
python -m unittest discover -s tests -v
```

This tool checks JSON structure and selected metadata consistency rules only.
It does not inspect CAD geometry, establish legal rights, validate real DRC,
authorize tool use, or certify a board for fabrication or operation.
All values in the supplied example are fictional.

## Install the workflow skill

```bash
python tools/install_skill.py
```

The standard-library installer copies `skills/pcbloop` to `$CODEX_HOME/skills`
or `~/.codex/skills`. Existing local edits are never overwritten. Start a new
Codex conversation and invoke `$pcbloop` with your project and task.
See the [usage guide](docs/skill.md) for examples and custom locations.

The skill instructs the agent to check live state, respect authorization, plan
dependent nets together, execute multiple modules with checkpoints, and write
honest verification and handoff reports. These are workflow instructions, not
implemented CAD guards. Actual CAD access needs separate tools; installation
does not connect a bridge, grant editing rights or upload data. The bundled
skill has not yet undergone independent multi-board behavioral evaluation.

## Learning loop

Start with curated retrieval and better execution tools. Model fine-tuning is a
separate future workflow requiring suitable data, explicit rights and held-out
project-family evaluation. Adding records to a database does not update model
parameters automatically.

See [architecture](docs/architecture.md), [dataset design](docs/dataset.md),
[roadmap](ROADMAP.md) and [contributing](CONTRIBUTING.md).

Original repository content is MIT-licensed. Third-party designs, extensions,
models and future datasets retain their own rights; see [NOTICE](NOTICE.md).
