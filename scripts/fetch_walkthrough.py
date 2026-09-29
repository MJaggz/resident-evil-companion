#!/usr/bin/env python3

"""Fetch the Resident Evil walkthrough from Fandom's MediaWiki API."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import dataclass
from pathlib import Path
from re import Match, escape, search, sub
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://residentevil.fandom.com/api.php"
PAGE_TITLE = "Walkthrough:Resident_Evil"
SOURCE_PAGE_URL = f"https://residentevil.fandom.com/wiki/{PAGE_TITLE}"
KNOWLEDGE_DIR = Path("knowledge/resident-evil-1996")
USER_AGENT = "resident-evil-companion/0.1"
TIMEOUT_SECONDS = 30
GENERATED_MARKER = "generated_by: fetch_walkthrough.py"


@dataclass(frozen=True)
class WalkthroughSection:
    title: str
    slug: str
    source_anchor: str
    wikitext: str


def api_get(params: dict[str, str]) -> dict[str, Any]:
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def fetch_sections() -> dict[str, Any]:
    data = api_get(
        {
            "action": "parse",
            "page": PAGE_TITLE,
            "prop": "sections",
            "format": "json",
        }
    )

    if "error" in data:
        raise RuntimeError(data["error"].get("info", "Fandom API parse request failed"))

    return data["parse"]


def fetch_wikitext() -> tuple[dict[str, Any], dict[str, Any], str]:
    data = api_get(
        {
            "action": "query",
            "titles": PAGE_TITLE,
            "prop": "revisions",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "formatversion": "2",
            "format": "json",
        }
    )

    if "error" in data:
        raise RuntimeError(data["error"].get("info", "Fandom API revision request failed"))

    page = data["query"]["pages"][0]
    if page.get("missing"):
        raise RuntimeError(f"Page not found: {PAGE_TITLE}")

    revision = page["revisions"][0]
    wikitext = revision["slots"]["main"]["content"]

    return page, revision, wikitext


def slugify(title: str) -> str:
    slug = title.lower()
    slug = slug.replace("&", " and ")
    slug = "".join(character if character.isalnum() else "-" for character in slug)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug


def heading_pattern(level: int, title: str) -> str:
    marker = "=" * level
    return rf"(?m)^{marker}\s*{escape(title)}\s*{marker}\s*$"


def major_walkthrough_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        section
        for section in sections
        if section.get("level") == "3" and str(section.get("number", "")).startswith("2.")
    ]


def split_walkthrough_sections(
    sections: list[dict[str, Any]], wikitext: str
) -> list[WalkthroughSection]:
    major_sections = major_walkthrough_sections(sections)
    parsed_sections: list[WalkthroughSection] = []

    for index, section in enumerate(major_sections):
        title = section["line"]
        current_heading = search(heading_pattern(3, title), wikitext)
        if current_heading is None:
            raise RuntimeError(f"Could not find heading in wikitext: {title}")

        if index + 1 < len(major_sections):
            next_title = major_sections[index + 1]["line"]
            next_heading = search(heading_pattern(3, next_title), wikitext[current_heading.end() :])
            if next_heading is None:
                raise RuntimeError(f"Could not find heading in wikitext: {next_title}")
            end = current_heading.end() + next_heading.start()
        else:
            category_marker = search(r"(?m)^\[\[Category:", wikitext[current_heading.end() :])
            end = (
                current_heading.end() + category_marker.start()
                if category_marker is not None
                else len(wikitext)
            )

        parsed_sections.append(
            WalkthroughSection(
                title=title,
                slug=slugify(title),
                source_anchor=section["anchor"],
                wikitext=wikitext[current_heading.end() : end].strip(),
            )
        )

    return parsed_sections


def markdown_link_text(match: Match[str]) -> str:
    target = match.group(1)
    return target.split("|", 1)[1] if "|" in target else target


def unwrap_paragraph_lines(markdown: str) -> str:
    blocks = markdown.split("\n\n")
    unwrapped_blocks = []

    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue

        if any(is_structural_markdown_line(line) for line in lines):
            unwrapped_blocks.append("\n".join(lines))
        else:
            unwrapped_blocks.append(" ".join(line.strip() for line in lines))

    return "\n\n".join(unwrapped_blocks)


def is_structural_markdown_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("- ")
        or stripped == "---"
    )


def wikitext_to_markdown(wikitext: str) -> str:
    markdown = wikitext
    markdown = sub(r"(?m)^======\s*(.*?)\s*======\s*$", r"#### \1", markdown)
    markdown = sub(r"(?m)^=====\s*(.*?)\s*=====\s*$", r"### \1", markdown)
    markdown = sub(r"(?m)^====\s*(.*?)\s*====\s*$", r"## \1", markdown)
    markdown = sub(r"(?m)^===\s*(.*?)\s*===\s*$", r"## \1", markdown)
    markdown = sub(r"(?m)^==\s*(.*?)\s*==\s*$", r"## \1", markdown)
    markdown = sub(r"\[\[([^\]]+)\]\]", markdown_link_text, markdown)
    markdown = sub(r"'''([^'].*?)'''", r"**\1**", markdown)
    markdown = sub(r"''([^'].*?)''", r"*\1*", markdown)
    markdown = sub(r"(?m)^----\s*$", "---", markdown)
    markdown = sub(r"(?m)^;(.+)$", r"**\1**", markdown)
    markdown = sub(r"(?m)^\*(?!\s)(.+)$", r"- \1", markdown)
    markdown = sub(r"(?m)^VARIATIONS?$", "## Variations", markdown)
    markdown = sub(r"(?m)^JILL-(.+)$", r"### Jill\n\n\1", markdown)
    markdown = sub(r"(?m)^CHRIS-(.+)$", r"### Chris\n\n\1", markdown)
    markdown = sub(r"(?m)^IMPORTANT-(.+)$", r"**Important:** \1", markdown)
    markdown = sub(r"(?m)^THIS IS IMPORTANT!\s*(.+)$", r"**Important:** \1", markdown)
    markdown = sub(r"\n{3,}", "\n\n", markdown)
    return unwrap_paragraph_lines(markdown.strip())


def section_markdown(section: WalkthroughSection, payload: dict[str, Any]) -> str:
    body = wikitext_to_markdown(section.wikitext)

    return f"""---
{GENERATED_MARKER}
game: Resident Evil
version: "1996"
section: "{section.title}"
character: both
source: "{SOURCE_PAGE_URL}"
source_title: "{payload["title"]}"
source_pageid: {payload["pageid"]}
source_revision_id: {payload["revision_id"]}
source_timestamp: "{payload["timestamp"]}"
source_anchor: "{section.source_anchor}"
---

# {section.title}

Source: Resident Evil Wiki, Walkthrough:Resident Evil

{body}
"""


def generated_file(path: Path) -> bool:
    if not path.is_file():
        return False

    try:
        return GENERATED_MARKER in path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False


def expected_knowledge_files(
    payload: dict[str, Any], parsed_sections: list[WalkthroughSection]
) -> dict[Path, str]:
    return {
        KNOWLEDGE_DIR / f"{section.slug}.md": section_markdown(section, payload)
        for section in parsed_sections
    }


def remove_stale_generated_files(expected_paths: set[Path]) -> list[str]:
    if not KNOWLEDGE_DIR.exists():
        return []

    removed_paths = []
    for path in KNOWLEDGE_DIR.glob("*.md"):
        if path not in expected_paths and generated_file(path):
            path.unlink()
            removed_paths.append(str(path))

    return removed_paths


def write_knowledge_files(
    payload: dict[str, Any], parsed_sections: list[WalkthroughSection]
) -> list[dict[str, str]]:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    expected_files = expected_knowledge_files(payload, parsed_sections)
    remove_stale_generated_files(set(expected_files))
    written_files = []

    for path, markdown in expected_files.items():
        path.write_text(markdown, encoding="utf-8")
        written_files.append({"path": str(path)})

    return written_files


def check_knowledge_files(
    payload: dict[str, Any], parsed_sections: list[WalkthroughSection]
) -> dict[str, Any]:
    expected_files = expected_knowledge_files(payload, parsed_sections)
    expected_paths = set(expected_files)
    stale_paths = []
    changed_paths = []
    missing_paths = []

    for path, expected_markdown in expected_files.items():
        if not path.exists():
            missing_paths.append(str(path))
            continue

        if path.read_text(encoding="utf-8") != expected_markdown:
            changed_paths.append(str(path))

    if KNOWLEDGE_DIR.exists():
        stale_paths = [
            str(path)
            for path in KNOWLEDGE_DIR.glob("*.md")
            if path not in expected_paths and generated_file(path)
        ]

    return {
        "up_to_date": not missing_paths and not changed_paths and not stale_paths,
        "missing": missing_paths,
        "changed": changed_paths,
        "stale": stale_paths,
    }


def fetch_walkthrough_payload() -> dict[str, Any]:
    sections = fetch_sections()
    page, revision, wikitext = fetch_wikitext()

    return {
        "source_api": API_URL,
        "source_page": SOURCE_PAGE_URL,
        "title": page["title"],
        "pageid": page["pageid"],
        "revision_id": revision["revid"],
        "timestamp": revision["timestamp"],
        "sections": sections["sections"],
        "wikitext": wikitext,
    }


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Fetch the Resident Evil walkthrough from Fandom.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""examples:
  python3 scripts/fetch_walkthrough.py --raw
      Print the full fetched Fandom payload, including page metadata and wikitext.

  python3 scripts/fetch_walkthrough.py --sections
      Print the parsed major walkthrough sections as JSON.

  python3 scripts/fetch_walkthrough.py --write
      Generate Markdown files in knowledge/resident-evil-1996/.

  python3 scripts/fetch_walkthrough.py --check
      Check whether generated Markdown files match the current Fandom source.

  python3 -m py_compile scripts/fetch_walkthrough.py
      Validate Python syntax without calling the Fandom API.
""",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw fetched payload, including page metadata and wikitext.",
    )
    mode.add_argument(
        "--sections",
        action="store_true",
        help="Print major walkthrough sections split from the fetched wikitext.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write major walkthrough sections as Markdown files in knowledge/.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Check whether generated Markdown files match the current source.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = fetch_walkthrough_payload()

    if args.sections or args.write or args.check:
        parsed_sections = split_walkthrough_sections(
            payload["sections"], payload["wikitext"]
        )

    if args.sections:
        result: Any = [
            {
                "title": section.title,
                "slug": section.slug,
                "source_anchor": section.source_anchor,
                "wikitext": section.wikitext,
            }
            for section in parsed_sections
        ]
    elif args.write:
        result = {
            "knowledge_dir": str(KNOWLEDGE_DIR),
            "written": write_knowledge_files(payload, parsed_sections),
        }
    elif args.check:
        result = check_knowledge_files(payload, parsed_sections)
    else:
        result = payload

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
