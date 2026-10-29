#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Release Link & Asset Verification Script

Parses README.md and documentation files to ensure all markdown links,
image paths, and code references point to valid, existing files on disk.
"""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
README_PATH = ROOT_DIR / "README.md"


def check_markdown_links(filepath: Path):
    content = filepath.read_text(encoding="utf-8")
    # Matches [text](link) and ![caption](image_path)
    links = re.findall(r'\[.*?\]\((?!http|#)(.*?)\)', content)

    missing = []
    for raw_link in links:
        # Strip anchor if present
        clean_link = raw_link.split("#")[0].strip()
        if not clean_link:
            continue
        
        target = (filepath.parent / clean_link).resolve()
        if not target.exists():
            missing.append((raw_link, target))

    return missing


def main():
    print("=" * 80)
    print("EIAP RELEASE LINK & ASSET VERIFICATION")
    print(f"Target: {README_PATH.name}")
    print("=" * 80)

    missing = check_markdown_links(README_PATH)

    if missing:
        print(f"[FAIL] Found {len(missing)} broken relative links in README.md:")
        for raw, resolved in missing:
            print(f"  - Link: '{raw}' -> Missing at: {resolved}")
        sys.exit(1)
    else:
        print("[PASS] All relative links and asset paths in README.md exist and are verified!")

    # Check documentation index
    docs_readme = ROOT_DIR / "docs" / "README.md"
    if docs_readme.exists():
        missing_docs = check_markdown_links(docs_readme)
        if missing_docs:
            print(f"[FAIL] Found {len(missing_docs)} broken links in docs/README.md")
            sys.exit(1)
        else:
            print("[PASS] All links in docs/README.md are verified!")

    print("=" * 80)


if __name__ == "__main__":
    main()

