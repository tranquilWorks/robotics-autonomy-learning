#!/usr/bin/env python3
"""Local learner CLI for a MATLAB learning harness."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "curriculum" / "modules.json"
STATE_DIR = ROOT / ".learning"
STATE_FILE = STATE_DIR / "progress.json"

def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

def load_state():
    if not STATE_FILE.exists():
        return {"current": None, "completed": {}, "notes": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

def resolve_module(manifest, ref):
    modules = manifest["modules"]
    if ref is None:
        state = load_state()
        if state.get("current"):
            ref = state["current"]
        else:
            ref = next((m["id"] for m in modules if m["status"] == "implemented"), modules[0]["id"])
    ref_text = str(ref).strip().upper()
    for module in modules:
        if ref_text in {module["id"], str(module["number"]), f"{module['number']:02d}", module["slug"].upper()}:
            return module
    raise SystemExit(f"Unknown module: {ref}")

def print_start(module):
    folder = ROOT / module["folder"]
    print(f"{module['id']} — {module['title']}")
    print(f"Status: {module['status']}")
    print(f"Guiding question: {module['guiding_question']}")
    print(f"Folder: {folder.relative_to(ROOT)}")
    if module["status"] != "implemented":
        print("This module is scaffolded. Activate its governed implementation batch before tutor use.")
        return 2
    print("\nMATLAB:")
    print(f"  launch_lesson('{module['id']}')")
    print("\nTutor files:")
    for name in ["README.md", "lesson.md", "walkthrough.md", "checks.md"]:
        path = folder / name
        if path.exists():
            print(f"  {path.relative_to(ROOT)}")
    return 0

def cmd_start(args):
    manifest = load_manifest()
    module = resolve_module(manifest, args.module)
    state = load_state()
    state["current"] = module["id"]
    save_state(state)
    return print_start(module)

def cmd_continue(_args):
    manifest = load_manifest()
    state = load_state()
    return print_start(resolve_module(manifest, state.get("current")))

def cmd_list(_args):
    manifest = load_manifest()
    state = load_state()
    completed = state.get("completed", {})
    for m in manifest["modules"]:
        marker = "✓" if completed.get(m["id"]) else ("●" if m["status"] == "implemented" else "○")
        print(f"{marker} {m['id']}  Phase {m['phase']}  {m['title']} [{m['status']}]")
    return 0

def cmd_status(_args):
    manifest = load_manifest()
    state = load_state()
    complete = len(state.get("completed", {}))
    implemented = sum(m["status"] == "implemented" for m in manifest["modules"])
    print(f"Track: {manifest['title']}")
    print(f"Modules: {manifest['module_count']} total, {implemented} implemented, {complete} completed")
    print(f"Current: {state.get('current') or 'none'}")
    return 0

def cmd_complete(args):
    manifest = load_manifest()
    module = resolve_module(manifest, args.module)
    if module["status"] != "implemented":
        raise SystemExit("Cannot complete a scaffolded module.")
    state = load_state()
    state.setdefault("completed", {})[module["id"]] = True
    if args.note:
        state.setdefault("notes", {})[module["id"]] = args.note
    state["current"] = module["id"]
    save_state(state)
    print(f"Marked {module['id']} complete.")
    return 0

def cmd_check(args):
    manifest = load_manifest()
    module = resolve_module(manifest, args.module)
    folder = ROOT / module["folder"]
    if not (folder / "run_checks.m").exists():
        raise SystemExit(f"{module['id']} has no executable checks.")
    print(f"Run in MATLAB: run_module_checks('{module['id']}')")
    return 0

def main():
    parser = argparse.ArgumentParser(prog="learn")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start"); p.add_argument("module", nargs="?"); p.set_defaults(func=cmd_start)
    p = sub.add_parser("continue"); p.set_defaults(func=cmd_continue)
    p = sub.add_parser("list"); p.set_defaults(func=cmd_list)
    p = sub.add_parser("status"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("complete"); p.add_argument("module"); p.add_argument("--note", default=""); p.set_defaults(func=cmd_complete)
    p = sub.add_parser("check"); p.add_argument("module", nargs="?"); p.set_defaults(func=cmd_check)
    args = parser.parse_args()
    raise SystemExit(args.func(args))

if __name__ == "__main__":
    main()
