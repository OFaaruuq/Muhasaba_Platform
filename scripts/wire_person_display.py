#!/usr/bin/env python3
"""Replace name display patterns with display_name in templates (not form fields)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"

SKIP_LINE = re.compile(
    r"(value=|name=\"full_name|name='full_name|placeholder=|id=\"newTeacherName|full_name_ar:|label:)",
    re.I,
)

PATTERNS = [
  (re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\.full_name_ar\s+or\s+\1\.full_name\s*\}\}"), r"{{ \1.display_name }}"),
  (re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\.full_name_ar\s*\}\}"), r"{{ \1.display_name }}"),
  (re.compile(r"\{\{\s*current_user\.full_name_ar\s+or\s+current_user\.full_name\s*\}\}"), r"{{ current_user.display_name }}"),
]


def transform(text):
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        if SKIP_LINE.search(line):
            out.append(line)
            continue
        new_line = line
        for pattern, repl in PATTERNS:
            new_line = pattern.sub(repl, new_line)
        out.append(new_line)
    return "".join(out)


def main():
    changed = 0
    for path in sorted(TEMPLATES.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(path.relative_to(ROOT))
    print(f"Updated {changed} template(s)")


if __name__ == "__main__":
    main()
