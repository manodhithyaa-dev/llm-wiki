import re
from pathlib import Path
from typing import List, Tuple

from pipelines.utils import append_log

CITATION_PATTERN = re.compile(r"\[.*?\]\(.*?\)")
WIKI_LINK_PATTERN = re.compile(r"\[\[(.*?)\]\]")
ANY_CITATION = re.compile(r"\[.*?\]\(.*?\)|\[\[.*?\]\]")


def lint() -> None:
    wiki_root = Path("wiki")

    if not wiki_root.exists():
        print("[LINT] Wiki directory not found")
        return

    issues: List[Tuple[Path, str, str]] = []

    all_md_files = list(wiki_root.rglob("*.md"))
    all_page_names = {p.stem for p in all_md_files}
    linked_to: set = set()

    print(f"[LINT] Scanning {len(all_md_files)} markdown files...")

    for md_file in all_md_files:
        text = md_file.read_text(encoding="utf-8")
        rel_path = md_file.relative_to(wiki_root)
        folder = rel_path.parts[0] if len(rel_path.parts) > 0 else ""

        if not text.strip():
            issues.append((rel_path, "empty", "File is empty"))
            continue

        # Source pages: require at least one citation OR wikilink anywhere in the page
        if folder == "sources":
            if not ANY_CITATION.search(text):
                issues.append((rel_path, "missing_citation", "No citations or wiki links found in source page"))

        for match in re.finditer(WIKI_LINK_PATTERN, text):
            target = match.group(1).strip()
            linked_to.add(target)

    for md_file in all_md_files:
        rel = md_file.relative_to(wiki_root)
        name = md_file.stem
        if name in ("index", "log", "_contradictions", "readme"):
            continue
        if rel.parts[0] in ("images", "assets"):
            continue
        if name not in linked_to:
            issues.append((rel, "orphan", f"No incoming links to [{name}]"))

    concept_dir = wiki_root / "concepts"
    if concept_dir.exists():
        seen_concepts: dict = {}
        for cf in sorted(concept_dir.glob("*.md")):
            text = cf.read_text(encoding="utf-8")
            first_line = text.splitlines()[0] if text.splitlines() else ""
            title = (
                first_line.lstrip("# ").strip()
                if first_line.startswith("#")
                else cf.stem
            )
            if title.lower() in seen_concepts:
                issues.append(
                    (
                        cf.relative_to(wiki_root),
                        "duplicate_concept",
                        f"Duplicate concept '{title}' also in {seen_concepts[title.lower()]}",
                    )
                )
            else:
                seen_concepts[title.lower()] = cf.relative_to(wiki_root)

    if issues:
        print("\n=== Lint Report ===\n")
        issue_counts: dict = {}
        for _, t, _ in issues:
            issue_counts[t] = issue_counts.get(t, 0) + 1

        print("Issue Summary:")
        for t, count in sorted(issue_counts.items()):
            print(f"  {t}: {count}")
        print()

        for rel, t, msg in issues:
            print(f"[{t}] {rel}: {msg}")

        print(f"\nTotal issues: {len(issues)}")
        append_log(f"Lint completed: {len(issues)} issues found")
    else:
        print("[LINT] No issues found. Wiki is clean.")
        append_log("Lint completed: no issues found")


if __name__ == "__main__":
    lint()
