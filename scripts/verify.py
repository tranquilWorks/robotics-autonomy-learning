#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []
manifest_path = ROOT / "curriculum" / "modules.json"
if not manifest_path.exists():
    errors.append("missing curriculum/modules.json")
else:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    modules = manifest.get("modules", [])
    if manifest.get("module_count") != len(modules):
        errors.append("module_count does not match modules length")
    ids = [m.get("id") for m in modules]
    if len(ids) != len(set(ids)):
        errors.append("duplicate module IDs")
    for m in modules:
        folder = ROOT / m["folder"]
        for required in ["README.md", "lesson.m", "experiment.m", "lesson.md", "walkthrough.md", "checks.md"]:
            if not (folder / required).exists():
                errors.append(f"{m['id']}: missing {required}")
        if m["status"] == "implemented":
            for required in ["model.m", "interactive.m", "run_checks.m"]:
                if not (folder / required).exists():
                    errors.append(f"{m['id']}: implemented module missing {required}")
            text = (folder / "experiment.m").read_text(encoding="utf-8")
            for token in ["%%", "broken", "sweep"]:
                if token not in text.lower():
                    errors.append(f"{m['id']}: experiment missing token {token!r}")
        else:
            text = (folder / "experiment.m").read_text(encoding="utf-8")
            if "scaffolded" not in text.lower():
                errors.append(f"{m['id']}: scaffold should fail clearly")

for required in ["README.md", "AGENTS.md", "launch_lesson.m", "run_module_checks.m", "bin/learn.py"]:
    if not (ROOT / required).exists():
        errors.append(f"missing root file {required}")

if errors:
    print("VERIFY FAIL")
    for err in errors:
        print(" -", err)
    sys.exit(1)
print(f"VERIFY PASS: {len(json.loads(manifest_path.read_text())['modules'])} modules")
