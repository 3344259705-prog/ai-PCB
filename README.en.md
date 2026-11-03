# PCBLoop

**Move PCB design forward through conversation, with clear evidence, checks and handoffs.**

[中文](README.md) · [Usage guide](docs/skill.md) · [Architecture](docs/architecture.md) · [Data specification](docs/dataset.md) · [Roadmap](ROADMAP.md) · [Contributing](CONTRIBUTING.md)

PCBLoop is an open-source project for AI-assisted PCB design. It turns lessons from hands-on human–AI collaboration into an installable **skill** that guides an agent to verify the current design, respect editing boundaries, work in manageable batches and leave useful records for the next session.

Use it to help with component preparation, footprint and pin-net review, layout and routing planning, and DRC issue handling. Provide the project location, task and permitted changes so the agent can follow a consistent workflow without repeatedly rebuilding the same context.

The current release, **`v0.2.0-skill`**, includes the workflow skill, an installer, a draft episode format and local validation tools. Actual CAD access requires separate tools. The first planned integration is 嘉立创EDA专业版 (EasyEDA Professional Edition).

## What the skill helps with

- **Identify the right design:** check the target PCB, component revision, footprints and pin-net mapping before relying on old information.
- **Follow your chosen division of work:** prepare components for manual layout, or continue design work within the current task and authorization.
- **Preserve existing work:** check live changes before editing, retain human contributions and avoid replaying stale scripts or restoring old snapshots over newer work.
- **Plan connected tasks together:** consider current paths, signal returns and module dependencies, then execute multiple modules with checkpoints.
- **Report what was actually checked:** distinguish connectivity, clearance, short-circuit and netlist issues rather than treating a lower DRC count as proof of a finished board.
- **Make the next session easier:** record changes, saved versions and remaining tasks so work can resume from a known state.

These are instructions for the agent. Results still depend on the model, available CAD tools, project conditions and human review. Independent multi-model, multi-board behavioral evaluation has not yet been completed.

## Quick start

Use Python 3.10 or later. Clone the repository and install the skill:

```bash
git clone https://github.com/3344259705-prog/ai-PCB.git
cd ai-PCB
python tools/install_skill.py
```

The installer uses only the Python standard library and copies the skill into your personal skills directory. It refuses to overwrite a different version or local edits.

Start a new Codex conversation and provide the actual project location:

```text
Use $pcbloop.
Project location: [your project directory or target PCB].
Read the latest handoff reports and verify the current design first.
Preserve component models, footprints, pin-net mapping and existing routes;
layout and copper optimization are allowed.
Continue unfinished modules in priority order, save and check each module,
and produce a handoff report at the end.
```

For preparation only:

```text
Use $pcbloop to organize the selected component revision and review pin-net
mapping and ratsnest visibility. Preserve the existing layout and do not route.
List any circuit changes that need authorization, with supporting evidence.
```

Installation does not connect CAD, grant editing permissions or upload projects. See the [usage guide](docs/skill.md) for custom locations, upgrades and session-resumption examples.

## What's included

| Component | Purpose |
|---|---|
| [`pcbloop` skill](skills/pcbloop/SKILL.md) | Design identification, authorization scope, batch work, checkpoints and handoffs |
| [Supporting references](docs/skill.md) | Task-specific notes on EasyEDA operations, power and mixed-signal work, and recovery reports |
| [Draft episode schema](schemas/episode.schema.json) | Tasks, constraints, actions, validation and usage rights |
| [Synthetic example](examples/synthetic_episode.json) | A fictional record demonstrating the format |
| [Local validator](docs/validator.md) | JSON structure and selected metadata consistency checks |
| Tests and CI | Installer behavior, package structure and validator checks |

A standalone CAD adapter, automated state guards and rollback, an autorouter, a community database and model-training services are not implemented. A check required by the skill is not necessarily a checker supplied by this repository.

## From individual work to shared experience

Our long-term goal is to make authorized, verified design experience reusable. Useful records include successful approaches, failed attempts, human corrections and the conditions under which each approach applies.

The planned loop is:

**Task and constraints → design review and planning → scoped CAD actions → checks and human review → local records → optional, reviewed sharing → case retrieval.**

We plan to improve workflows, tools and curated retrieval before pursuing separate model-training experiments. Training requires suitable source and usage rights, fixed dataset versions and evaluation split by project family. Adding cases to a database does not automatically update model parameters, and volume does not replace quality review. See the [roadmap](ROADMAP.md).

## Validate examples and run tests

Development dependencies are separate from skill installation. In a Python virtual environment, run:

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_episode.py examples/synthetic_episode.json
python tools/validate_episode.py --for-publication examples/synthetic_episode.json
python -m unittest discover -s tests -v
```

The validator checks JSON and selected metadata conventions. It does not inspect CAD geometry, establish legal rights, validate real DRC, or assess electrical performance or fabrication conditions. User acceptance, CAD checks and hardware validation must be recorded separately. See the [validator notes](docs/validator.md) and [data specification](docs/dataset.md).

## Data and privacy

This repository contains no real PCB projects or private conversation transcripts. It has no background collection, telemetry or automatic uploads. Public sharing, retrieval use and model training require their respective authorizations.

Do not submit access tokens, personal information, customer material or unauthorized third-party designs. Private model chain-of-thought is not collected. Collection and review procedures for real cases are still being designed.

## Repository structure

```text
skills/pcbloop/  Workflow skill, references and project brief template
docs/            Architecture, usage guide and data specification
schemas/         Draft episode format
examples/        Synthetic examples
tools/           Local installer and metadata validator
tests/           Installer, package and validator tests
.github/         CI and contribution templates
```

## Help improve PCBLoop

Contributions are welcome: usage feedback, workflow improvements, synthetic tests, CAD adapter designs and validation methods. Include the task conditions, expected behavior and observed result so others can assess the issue.

Read [CONTRIBUTING](CONTRIBUTING.md) before submitting changes, or explore the [roadmap](ROADMAP.md) for areas to work on.

## License and attribution

Original repository content is [MIT-licensed](LICENSE). Third-party designs, extensions, models and future datasets retain their own rights; see [NOTICE](NOTICE.md).

PCBLoop is an independent community project, not an official product of a CAD or AI vendor. Its workflow and tools do not certify a board's electrical safety, manufacturability or hardware performance.
