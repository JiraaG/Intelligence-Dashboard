#!/usr/bin/env python3
"""Sync Radar ECC skill mirrors: .agents/skills/*/SKILL.md → radar/.ecc/skills/<name>.md

Usage (from monorepo root):
  python radar/.ecc/scripts/sync_skills.py --check
  python radar/.ecc/scripts/sync_skills.py --write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def repo_root() -> Path:
    # radar/.ecc/scripts/sync_skills.py → parents[3] = monorepo root
    return Path(__file__).resolve().parents[3]


def skill_pairs(root: Path) -> list[tuple[str, Path, Path]]:
    agents = root / ".agents" / "skills"
    mirror_dir = root / "radar" / ".ecc" / "skills"
    pairs: list[tuple[str, Path, Path]] = []
    if not agents.is_dir():
        return pairs
    for skill_dir in sorted(agents.iterdir()):
        if not skill_dir.is_dir():
            continue
        sot = skill_dir / "SKILL.md"
        if not sot.is_file():
            continue
        name = skill_dir.name
        pairs.append((name, sot, mirror_dir / f"{name}.md"))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if all mirrors match SoT; exit 1 on drift or missing mirror",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Copy each SoT SKILL.md to radar/.ecc/skills/<name>.md",
    )
    args = parser.parse_args()

    root = repo_root()
    pairs = skill_pairs(root)
    if not pairs:
        print(f"ERROR: no skills under {root / '.agents' / 'skills'}", file=sys.stderr)
        return 1

    mirror_dir = root / "radar" / ".ecc" / "skills"
    drifted: list[str] = []
    missing: list[str] = []
    written: list[str] = []

    for name, sot, mirror in pairs:
        sot_text = sot.read_text(encoding="utf-8")
        if args.write:
            mirror_dir.mkdir(parents=True, exist_ok=True)
            mirror.write_text(sot_text, encoding="utf-8", newline="\n")
            written.append(name)
            continue
        if not mirror.is_file():
            missing.append(name)
            continue
        if mirror.read_text(encoding="utf-8") != sot_text:
            drifted.append(name)

    if args.write:
        for name in written:
            print(f"wrote radar/.ecc/skills/{name}.md")
        print(f"OK: synced {len(written)} skill(s)")
        return 0

    ok = True
    for name in missing:
        print(f"MISSING mirror: radar/.ecc/skills/{name}.md", file=sys.stderr)
        ok = False
    for name in drifted:
        print(f"DRIFT: {name} (.agents/skills/{name}/SKILL.md ≠ radar/.ecc/skills/{name}.md)", file=sys.stderr)
        ok = False

    # Orphan mirrors (in .ecc but not in .agents)
    known = {name for name, _, _ in pairs}
    if mirror_dir.is_dir():
        for orphan in sorted(mirror_dir.glob("*.md")):
            if orphan.stem not in known:
                print(f"ORPHAN mirror: {orphan.relative_to(root)} (no .agents/skills/{orphan.stem}/)", file=sys.stderr)
                ok = False

    if ok:
        print(f"OK: {len(pairs)} skill mirror(s) in sync")
        return 0
    print("HINT: python radar/.ecc/scripts/sync_skills.py --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
