import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from openai import OpenAI
from dotenv import load_dotenv

from config import GPT_MINI_MODEL, GPT_VISION_MODEL
from pipelines.utils import ensure_dir, append_log

load_dotenv()

client = OpenAI()


def _clean_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|#]', "_", name)
    name = re.sub(r'\s+', "_", name)
    name = name.strip("_")
    return name if name else "unknown"


def read_processed_document(doc_name: str) -> str:
    pages_dir = Path(f"processed/documents/{doc_name}/pages")
    if not pages_dir.exists():
        return ""

    merged = []
    for file in sorted(pages_dir.glob("*.md")):
        merged.append(file.read_text(encoding="utf-8"))

    return "\n\n".join(merged)


def read_metadata(doc_name: str) -> str:
    meta_path = Path(f"processed/documents/{doc_name}/source_metadata.md")
    if meta_path.exists():
        return meta_path.read_text(encoding="utf-8")
    return ""


def generate_source_page(doc_name: str, content: str, metadata: str) -> Dict:
    print(f"  Generating source page for {doc_name}...")

    truncated = content[:8000] if len(content) > 8000 else content

    prompt = f"""Analyze the following document and create a structured wiki source page.

Document: {doc_name}

Content:
{truncated}

Metadata:
{metadata}

Create a structured markdown page with these sections:

## Summary
A concise 3-5 sentence summary of this source.

## Key Concepts
List 3-10 key concepts found in this source as a markdown bullet list. Each concept should be 2-5 words.

## Key Entities
List important named entities (people, organizations, technologies, places, etc.) as a markdown bullet list.

## Citations
List any notable citations, references, or sources mentioned in the text.

## Raw Source
`raw/documents/{doc_name}`

Return ONLY valid markdown."""

    try:
        response = client.responses.create(
            model=GPT_MINI_MODEL,
            input=prompt,
        )
        raw = response.output_text
        raw = re.sub(r"^```markdown\s*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE)
        raw = "\n".join(line.rstrip() for line in raw.splitlines())
        raw = raw.strip() + f"\n\n[[{doc_name}]]"
        return {"markdown": raw}

    except Exception as e:
        print(f"  [ERROR] Failed to generate source page: {e}")
        return {
            "markdown": (
                f"# {doc_name}\n\n"
                f"## Summary\n\n{content[:500]}\n\n"
                f"## Raw Source\n\n`raw/documents/{doc_name}`\n\n"
                f"[[{doc_name}]]"
            )
        }


def extract_concepts_from_source(source_markdown: str) -> Tuple[List[str], List[str]]:
    concepts = []
    entities = []

    concepts_match = re.search(
        r"## Key Concepts\s*\n(.*?)(?=\n##|\Z)", source_markdown, re.DOTALL
    )
    if concepts_match:
        concepts = [
            c.strip().lstrip("-* ").strip()
            for c in concepts_match.group(1).strip().split("\n")
            if c.strip().lstrip("-* ").strip()
        ]

    entities_match = re.search(
        r"## Key Entities\s*\n(.*?)(?=\n##|\Z)", source_markdown, re.DOTALL
    )
    if entities_match:
        entities = [
            e.strip().lstrip("-* ").strip()
            for e in entities_match.group(1).strip().split("\n")
            if e.strip().lstrip("-* ").strip()
        ]

    return concepts, entities


def get_concept_summary(concept: str, source_contexts: List[str]) -> str:
    prompt = f"""Concept: {concept}

Context from sources:
{chr(10).join(f'- {ctx[:500]}' for ctx in source_contexts[:3])}

Write a 2-3 sentence description of this concept based on the context provided. Be concise and informative."""

    try:
        response = client.responses.create(
            model=GPT_MINI_MODEL,
            input=prompt,
        )
        return response.output_text.strip()
    except Exception:
        return f"References to {concept} found in source documents."


def build_concept_page(concept: str, sources: List[str], description: str) -> str:
    lines = [f"# {concept}", "", description, "", "## Backlinks", ""]
    for source in sorted(sources):
        lines.append(f"- [[{source}]]")
    lines.append("")
    return "\n".join(lines)


def build_entity_page(entity: str, sources: List[str]) -> str:
    lines = [f"# {entity}", "", "## Backlinks", ""]
    for source in sorted(sources):
        lines.append(f"- [[{source}]]")
    lines.append("")
    return "\n".join(lines)


def build_source_pages() -> Tuple[Set[str], Dict[str, List[str]], Dict[str, List[str]]]:
    docs_root = Path("processed/documents")
    if not docs_root.exists():
        print("[WARN] No processed documents found")
        return set(), {}, {}

    all_concepts: Dict[str, List[str]] = defaultdict(list)
    all_entities: Dict[str, List[str]] = defaultdict(list)
    sources_generated: Set[str] = set()

    for doc_dir in sorted(docs_root.iterdir()):
        if not doc_dir.is_dir():
            continue

        doc_name = doc_dir.name
        print(f"[BUILD] Processing source: {doc_name}")

        content = read_processed_document(doc_name)
        metadata = read_metadata(doc_name)

        if not content:
            print(f"  [WARN] No content found for {doc_name}")
            continue

        result = generate_source_page(doc_name, content, metadata)
        source_md = result["markdown"]

        ensure_dir("wiki/sources")
        source_file = f"wiki/sources/{doc_name}.md"
        with open(source_file, "w", encoding="utf-8") as f:
            f.write(source_md)

        concepts, entities = extract_concepts_from_source(source_md)
        for c in concepts:
            all_concepts[c].append(doc_name)
        for e in entities:
            all_entities[e].append(doc_name)

        sources_generated.add(doc_name)
        print(f"  Source page created: wiki/sources/{doc_name}.md")
        append_log(f"Generated source page: {doc_name}")

    return sources_generated, dict(all_concepts), dict(all_entities)


def build_concept_pages(concept_map: Dict[str, List[str]]) -> None:
    if not concept_map:
        return

    print("[BUILD] Generating concept pages...")
    ensure_dir("wiki/concepts")

    for concept, sources in concept_map.items():
        file_name = _clean_name(concept)
        concept_path = f"wiki/concepts/{file_name}.md"
        description = get_concept_summary(concept, sources)
        page = build_concept_page(concept, sources, description)

        with open(concept_path, "w", encoding="utf-8") as f:
            f.write(page)

        print(f"  Concept page: wiki/concepts/{file_name}.md")
        append_log(f"Generated concept page: {concept}")


def build_entity_pages(entity_map: Dict[str, List[str]]) -> None:
    if not entity_map:
        return

    print("[BUILD] Generating entity pages...")
    ensure_dir("wiki/entities")

    for entity, sources in entity_map.items():
        file_name = _clean_name(entity)
        entity_path = f"wiki/entities/{file_name}.md"
        page = build_entity_page(entity, sources)

        with open(entity_path, "w", encoding="utf-8") as f:
            f.write(page)

        print(f"  Entity page: wiki/entities/{file_name}.md")
        append_log(f"Generated entity page: {entity}")


def build_index(
    sources: Set[str],
    concepts: Dict[str, List[str]],
    entities: Dict[str, List[str]],
) -> None:
    print("[BUILD] Generating index page...")

    lines = [
        "# Wiki Index",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        "",
        "## Sources",
        "",
    ]
    for source in sorted(sources):
        lines.append(f"- [[{source}]]")
    lines.append("")

    if concepts:
        lines.append("## Concepts")
        lines.append("")
        for concept in sorted(concepts.keys()):
            file_name = _clean_name(concept)
            lines.append(f"- [[{file_name}]]")
        lines.append("")

    if entities:
        lines.append("## Entities")
        lines.append("")
        for entity in sorted(entities.keys()):
            file_name = _clean_name(entity)
            lines.append(f"- [[{file_name}]]")
        lines.append("")

    with open("wiki/index.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[BUILD] Index page generated: wiki/index.md")
    append_log("Generated index page")


def _build_image_doc_map() -> dict:
    image_doc_map = {}
    docs_root = Path("processed/documents")
    if not docs_root.exists():
        return image_doc_map
    for doc_dir in docs_root.iterdir():
        if not doc_dir.is_dir():
            continue
        img_dir = doc_dir / "images"
        if not img_dir.exists():
            continue
        for img_file in img_dir.iterdir():
            if img_file.is_file():
                image_doc_map[img_file.stem] = doc_dir.name
    return image_doc_map


def process_image_captions() -> None:
    images_dir = Path("processed/images")
    if not images_dir.exists():
        return

    print("[BUILD] Processing image captions...")
    image_doc_map = _build_image_doc_map()

    for caption_file in sorted(images_dir.glob("*.caption.md")):
        content = caption_file.read_text(encoding="utf-8")
        image_name = caption_file.stem.replace(".caption", "")
        source_doc = image_doc_map.get(image_name, "Unknown")
        content += f"\n_Source: {source_doc}_\n"
        wiki_img_dir = ensure_dir(f"wiki/images/{source_doc}")
        wiki_path = wiki_img_dir / f"{image_name}.md"
        wiki_path.write_text(content, encoding="utf-8")
        print(f"  Image page: wiki/images/{source_doc}/{image_name}.md")
        append_log(f"Generated image page: {image_name} (from {source_doc})")


def _clean_wiki_dirs() -> None:
    preserve = {"index.md", "log.md", "_contradictions.md"}
    for subdir in ["sources", "concepts", "entities", "images"]:
        d = Path(f"wiki/{subdir}")
        if d.exists():
            if subdir == "images":
                for item in list(d.iterdir()):
                    if item.is_dir():
                        for f in item.iterdir():
                            if f.is_file() and f.name.endswith(".md"):
                                f.unlink()
                        if not any(item.iterdir()):
                            item.rmdir()
                    elif item.is_file() and item.name.endswith(".md"):
                        item.unlink()
            else:
                for f in d.iterdir():
                    if f.is_file() and f.name.endswith(".md"):
                        f.unlink()
            print(f"  Cleaned wiki/{subdir}")


def _read_source_summary(source_name: str) -> str:
    path = Path(f"wiki/sources/{source_name}.md")
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"## Summary\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def detect_contradictions(
    concept_map: Dict[str, List[str]],
    sources_set: Set[str],
) -> None:
    if len(sources_set) < 2:
        print("[BUILD] Fewer than 2 sources — skipping contradiction detection")
        return

    shared = {c: srcs for c, srcs in concept_map.items() if len(srcs) >= 2}
    if not shared:
        print("[BUILD] No shared concepts across sources — no contradictions possible")
        ensure_dir("wiki")
        with open("wiki/_contradictions.md", "w", encoding="utf-8") as f:
            f.write("# Contradictions\n\n")
            f.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
            f.write("No overlapping topics found across sources.\n")
        return

    print(f"[BUILD] Checking {len(shared)} shared concepts for contradictions...")

    contradictions = []

    for concept, sources in sorted(shared.items()):
        summaries = {}
        for s in sources:
            sm = _read_source_summary(s)
            if sm:
                summaries[s] = sm

        if len(summaries) < 2:
            continue

        prompt = (
            f'Compare these sources on the topic "{concept}".\n\n'
            + "\n\n".join(
                f'Source: [[{s}]]\n{sm[:1000]}' for s, sm in summaries.items()
            )
            + '\n\nDo any specific claims contradict each other? '
            "If yes, list each contradiction with the conflicting claims. "
            "Use format: [[Source Name]] for each source reference. "
            'If no contradictions, respond: "No contradictions found."'
        )

        try:
            response = client.responses.create(
                model=GPT_MINI_MODEL,
                input=prompt,
            )
            result = response.output_text.strip()
            if "no contradictions" not in result.lower():
                contradictions.append((concept, result))
                append_log(f"Contradiction detected in concept: {concept}")
        except Exception as e:
            print(f"  [WARN] Contradiction check failed for '{concept}': {e}")

    ensure_dir("wiki")
    with open("wiki/_contradictions.md", "w", encoding="utf-8") as f:
        f.write("# Contradictions\n\n")
        f.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
        if contradictions:
            for concept, details in contradictions:
                f.write(f"## {concept}\n\n")
                f.write(details + "\n\n")
        else:
            f.write("No contradictions detected across sources.\n")

    print(f"[BUILD] Contradiction check complete")
    append_log("Contradiction check completed")



def build_all() -> None:
    print("[BUILD] Starting wiki build...\n")

    _clean_wiki_dirs()

    sources, concepts, entities = build_source_pages()

    process_image_captions()

    if concepts:
        build_concept_pages(concepts)
    else:
        print("[BUILD] No concepts extracted")

    if entities:
        build_entity_pages(entities)
    else:
        print("[BUILD] No entities extracted")

    detect_contradictions(concepts, sources)

    build_index(sources, concepts, entities)

    print("\n[BUILD] Wiki build complete")
    append_log("Wiki build complete")


if __name__ == "__main__":
    build_all()
