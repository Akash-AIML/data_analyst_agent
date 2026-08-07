# 🤝 Zero-Conflict Git Integration & Merge Guide

Follow this guide to merge Member 1 (Profiler), Member 2 (Analysis), and Member 3 (Insight) into `main` without git or code conflicts.

---

## 1. Directory Isolation (Folder-Per-Member Rule)

Each member works exclusively inside their isolated folder. **Do not modify files outside your directory.**

```text
├── state.py                  # SHARED CONTRACT (DO NOT EDIT WITHOUT TEAM CONSENSUS)
├── graph.py                  # PIPELINE INTEGRATOR
├── agents/
│   ├── profiler/             # MEMBER 1 ONLY
│   ├── analysis/             # MEMBER 2 ONLY
│   └── insight/              # MEMBER 3 ONLY
```

---

## 2. Shared State Ownership Rules (`state.py`)

- **Member 1 (Profiler)** writes ONLY: `profile`, `profile_report_path`
- **Member 2 (Analysis)** reads `profile`, writes ONLY: `analysis_plan`, `analysis_results`, `generated_files`, `execution_log`, `reflection_notes`
- **Member 3 (Insight)** reads `profile`, `analysis_results`, `generated_files`, writes ONLY: `validation_report`, `insights`, `recommendations`, `report_path`, `pdf_path`, `report_status`

---

## 3. Recommended Git Commands for Each Member

### Member 1 (Profiler Agent)
```bash
git checkout main
git pull origin main
git checkout -b feature/member-1-profiler
# Add files under agents/profiler/
git add agents/profiler/
git commit -m "feat(profiler): add profiler node and tools"
git push -u origin feature/member-1-profiler
```

### Member 2 (Analysis Agent)
```bash
git checkout main
git pull origin main
git checkout -b feature/member-2-analysis
# Add files under agents/analysis/
git add agents/analysis/
git commit -m "feat(analysis): add planner, executor, and reflector nodes"
git push -u origin feature/member-2-analysis
```

### Member 3 (Insight Agent)
```bash
git checkout main
git pull origin main
git checkout -b feature/member-3-insight
# Add files under agents/insight/
git add agents/insight/
git commit -m "feat(insight): add insight node, validator, and HTML generator"
git push -u origin feature/member-3-insight
```

---

## 4. Pipeline Integration Check (`graph.py`)

Once all 3 PRs are merged into `main`, test the complete end-to-end pipeline:

```bash
venv/bin/python -m pytest agents/*/tests -v
```
