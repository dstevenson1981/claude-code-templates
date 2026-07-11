#!/usr/bin/env python3
"""Build docs/site-catalog.json — the slim component catalog consumed by the
template browser site.

Scans cli-tool/components/ on the filesystem (so newly committed components
appear automatically), extracts descriptions from markdown frontmatter, and
merges descriptions and download counts from docs/components.json when the
filesystem has none. Stdlib only; no secrets required.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "cli-tool" / "components"
LEGACY_CATALOG = ROOT / "docs" / "components.json"
OUT = ROOT / "docs" / "site-catalog.json"

MD_TYPES = {
    "agents": "agent",
    "commands": "command",
    "loops": "loop",
}
JSON_TYPES = {
    "mcps": "mcp",
    "hooks": "hook",
    "settings": "setting",
    "sandbox": "sandbox",
    "templates": "template",
}


def clean_description(text):
    if not text:
        return ""
    text = text.strip().strip('"').strip("'")
    text = text.replace("\\n", " ")
    text = re.sub(r"<example>.*", "", text, flags=re.S)
    text = re.sub(r"Specifically:.*", "", text, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def frontmatter_description(md_path):
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not m:
        return ""
    lines = m.group(1).split("\n")
    desc_lines = []
    capturing = False
    for line in lines:
        if capturing:
            # continuation lines of a folded/multi-line value are indented
            if line.startswith((" ", "\t")):
                desc_lines.append(line.strip())
                continue
            break
        dm = re.match(r"description:\s*(.*)$", line)
        if dm:
            first = dm.group(1).strip()
            if first not in (">", ">-", "|", "|-"):
                desc_lines.append(first)
            capturing = True
    return clean_description(" ".join(desc_lines))


def rel_category(rel_parts):
    return rel_parts[0] if len(rel_parts) > 1 else "general"


def scan():
    catalog = {}

    for folder, type_name in MD_TYPES.items():
        base = COMPONENTS / folder
        items = []
        if base.is_dir():
            for f in sorted(base.rglob("*.md")):
                rel = f.relative_to(base)
                items.append({
                    "name": f.stem,
                    "path": str(rel),
                    "category": rel_category(rel.parts),
                    "type": type_name,
                    "description": frontmatter_description(f),
                    "downloads": 0,
                })
        catalog[folder] = items

    # skills are directories containing SKILL.md
    base = COMPONENTS / "skills"
    items = []
    if base.is_dir():
        for f in sorted(base.rglob("SKILL.md")):
            rel = f.parent.relative_to(base)
            items.append({
                "name": rel.parts[-1],
                "path": str(rel),
                "category": rel_category(rel.parts),
                "type": "skill",
                "description": frontmatter_description(f),
                "downloads": 0,
            })
    catalog["skills"] = items

    for folder, type_name in JSON_TYPES.items():
        base = COMPONENTS / folder
        items = []
        if base.is_dir():
            for f in sorted(base.rglob("*.json")):
                rel = f.relative_to(base)
                items.append({
                    "name": f.stem,
                    "path": str(rel),
                    "category": rel_category(rel.parts),
                    "type": type_name,
                    "description": "",
                    "downloads": 0,
                })
        catalog[folder] = items

    return catalog


def merge_legacy(catalog):
    if not LEGACY_CATALOG.is_file():
        return
    try:
        legacy = json.loads(LEGACY_CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    # sandbox and templates aren't one-file-per-component on disk; keep the
    # legacy catalog's richer entries when the scan finds fewer.
    for key in ("sandbox", "templates"):
        old_items = legacy.get(key, [])
        if len(old_items) > len(catalog.get(key, [])):
            catalog[key] = [{
                "name": o.get("name", ""),
                "path": o.get("path", ""),
                "category": o.get("category", "general"),
                "type": o.get("type", key.rstrip("s")),
                "description": clean_description(o.get("description")),
                "downloads": o.get("downloads", 0) or 0,
            } for o in old_items]

    for key, items in catalog.items():
        by_path = {}
        for old in legacy.get(key, []):
            by_path[old.get("path", "")] = old
        for item in items:
            old = by_path.get(item["path"])
            if not old:
                continue
            item["downloads"] = old.get("downloads", 0) or 0
            if not item["description"]:
                item["description"] = clean_description(old.get("description"))


def main():
    catalog = scan()
    merge_legacy(catalog)
    OUT.write_text(json.dumps(catalog, separators=(",", ":")) + "\n", encoding="utf-8")
    counts = {k: len(v) for k, v in catalog.items()}
    print(f"Wrote {OUT.relative_to(ROOT)}: {counts}")


if __name__ == "__main__":
    main()
