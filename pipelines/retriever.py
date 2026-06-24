import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "no", "nor", "so", "if", "than", "that", "this", "these", "those",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "they", "them", "their", "what", "which", "who", "whom",
    "when", "where", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "only", "own",
    "same", "too", "very", "just", "about", "above", "after", "again",
    "against", "below", "between", "through", "during", "before",
    "after", "up", "down", "out", "off", "over", "under", "then",
    "once", "here", "there", "into", "onto", "upon",
}

MIN_CONFIDENCE = 1.5


class Chunk:
    def __init__(self, doc_name: str, page_label: str, text: str):
        self.doc_name = doc_name
        self.page_label = page_label
        self.text = text

    @property
    def full_text(self) -> str:
        return f"[{self.doc_name} / Page {self.page_label}]\n{self.text}"

    @property
    def searchable_text(self) -> str:
        return f"{self.doc_name} {self.text}"

    def __repr__(self) -> str:
        return f"Chunk({self.doc_name}, Page {self.page_label}, {len(self.text)} chars)"


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


def tokenize_query(text: str) -> List[str]:
    tokens = tokenize(text)
    return [t for t in tokens if t not in STOP_WORDS]


def load_doc_chunks(doc_name: str) -> List[Chunk]:
    pages = []
    pages_dir = Path(f"processed/documents/{doc_name}/pages")
    if pages_dir.exists():
        for page_file in sorted(pages_dir.glob("*.md")):
            page_num = re.search(r"p(\d+)", page_file.stem)
            page_label = page_num.group(1).lstrip("0") if page_num else "?"
            text = page_file.read_text(encoding="utf-8").strip()
            if text:
                pages.append((page_label, text))

    chunks = []
    i = 0
    while i < len(pages):
        label, text = pages[i]
        if len(text) < 500:
            merged_text = text
            merged_label = label
            j = i + 1
            while j < len(pages) and len(merged_text) < 500:
                merged_text += "\n\n" + pages[j][1]
                merged_label += f"-{pages[j][0]}"
                j += 1
            chunks.append(Chunk(doc_name, merged_label, merged_text))
            i = j
        else:
            chunks.append(Chunk(doc_name, label, text))
            i += 1

    img_dir = Path(f"wiki/images/{doc_name}")
    if img_dir.exists():
        for img_file in sorted(img_dir.glob("*.md")):
            text = img_file.read_text(encoding="utf-8").strip()
            if text:
                img_name = img_file.stem
                chunks.append(Chunk(doc_name, f"Image: {img_name}", text))

    return chunks


def load_all_chunks() -> List[Chunk]:
    chunks = []
    docs_root = Path("processed/documents")
    if not docs_root.exists():
        return chunks
    for doc_dir in sorted(docs_root.iterdir()):
        if not doc_dir.is_dir():
            continue
        chunks.extend(load_doc_chunks(doc_dir.name))
    return chunks


def load_wiki_sources() -> List[Dict]:
    sources = []
    src_dir = Path("wiki/sources")
    if not src_dir.exists():
        return sources
    for src_file in sorted(src_dir.glob("*.md")):
        text = src_file.read_text(encoding="utf-8")
        doc_name = src_file.stem
        summary = ""
        concepts = ""
        m = re.search(r"## Summary\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        if m:
            summary = m.group(1).strip()
        m = re.search(r"## Key Concepts\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        if m:
            concepts = m.group(1).strip()
        searchable = f"{doc_name} {summary} {concepts}"
        sources.append({"doc_name": doc_name, "searchable": searchable})
    return sources


def score_text(text: str, query_tokens: List[str], query_set: set) -> float:
    if not query_set:
        return 0.0
    tokens = tokenize(text)
    token_set = set(tokens)
    counter = Counter(tokens)
    term_overlap = len(query_set & token_set)
    freq_score = sum(counter[t] for t in query_tokens if t in counter)
    return term_overlap ** 2 + (freq_score * 0.5)


def score_chunks(chunks: List[Chunk], query: str) -> List[Tuple[Chunk, float]]:
    query_tokens = tokenize_query(query)
    query_set = set(query_tokens)
    if not query_set:
        return [(c, 0.0) for c in chunks]

    scored = []
    for chunk in chunks:
        ct = tokenize(chunk.searchable_text)
        cs = set(ct)
        cnt = Counter(ct)
        term_overlap = len(query_set & cs)
        tt = set(tokenize_query(chunk.doc_name))
        title_bonus = len(query_set & tt) * 2
        freq_score = sum(cnt[t] for t in query_tokens if t in cnt)
        total_score = term_overlap ** 2 + title_bonus + (freq_score * 0.5)
        scored.append((chunk, total_score))

    def _page_sort_key(x):
        label = x[0].page_label or "0"
        try:
            return int(label)
        except ValueError:
            return 99999

    scored.sort(key=lambda x: (-x[1], x[0].doc_name, _page_sort_key(x)))
    return scored


def _assemble(results_list: List, scored: List[Tuple[Chunk, float]],
              max_chars: int, top_k: int) -> Tuple[str, List[Dict]]:
    results = []
    selected_texts = []
    total_chars = 0

    for chunk, score in scored:
        if score <= 0 and len(selected_texts) > 0:
            continue
        chunk_text = chunk.full_text
        chunk_len = len(chunk_text) + 2
        if total_chars + chunk_len > max_chars:
            continue
        total_chars += chunk_len
        selected_texts.append(chunk_text)
        results.append({
            "doc_name": chunk.doc_name,
            "page": chunk.page_label,
            "score": score,
            "preview": chunk.text[:120].strip().replace("\n", " "),
        })
        if len(results) >= top_k:
            break

    context = "\n\n".join(selected_texts)
    return context, results


def route_via_wiki(query: str, verbose: bool = True) -> Optional[str]:
    sources = load_wiki_sources()
    if not sources:
        return None

    query_tokens = tokenize_query(query)
    query_set = set(query_tokens)
    if not query_set:
        return None

    scored_sources = []
    for src in sources:
        score = score_text(src["searchable"], query_tokens, query_set)
        scored_sources.append((src["doc_name"], score))

    scored_sources.sort(key=lambda x: -x[1])

    top_name, top_score = scored_sources[0]
    runner_up_score = scored_sources[1][1] if len(scored_sources) > 1 else 0

    if verbose:
        print(f"  [ROUTER] Top wiki source: {top_name} (score={top_score})")
        print(f"  [ROUTER] Runner-up score: {runner_up_score}")

    if top_score >= MIN_CONFIDENCE and top_score > runner_up_score:
        if verbose:
            print(f"  [ROUTER] Routed to document: {top_name}")
        return top_name

    if verbose:
        print(f"  [ROUTER] No clear route — falling back to brute-force across all documents")
    return None


def retrieve(
    query: str,
    max_chars: int = 55000,
    top_k: int = 20,
    verbose: bool = True,
) -> Tuple[str, List[Dict]]:
    target_doc = route_via_wiki(query, verbose=verbose)

    if target_doc:
        chunks = load_doc_chunks(target_doc)
        if chunks:
            scored = score_chunks(chunks, query)
            context, results = _assemble([], scored, max_chars, top_k)
            if context:
                return context, results

    chunks = load_all_chunks()
    if not chunks:
        return "", []
    scored = score_chunks(chunks, query)
    return _assemble([], scored, max_chars, top_k)


def retrieve_scored(query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
    """Returns scored chunks for a query, with no printing side effects.
    Used by the evaluation harness (evaluate.py)."""
    target_doc = route_via_wiki(query, verbose=False)

    if target_doc:
        chunks = load_doc_chunks(target_doc)
        if chunks:
            scored = score_chunks(chunks, query)
            if scored:
                return scored[:max(top_k, 15)]

    chunks = load_all_chunks()
    if not chunks:
        return []
    scored = score_chunks(chunks, query)
    return scored[:max(top_k, 15)]


def cmd_test_retrieval(args) -> None:
    queries = [
        "Rackmount DVRS",
        "Philips Screwdriver",
        "Favorite channel list",
        "Treadmill",
    ]
    expected = [
        "Motorola solutions DVR-LX",
        "Motorola solutions DVR-LX",
        "STB - Nagra_DCS 5000",
        "Treadmill service manual",
    ]

    print("=== RETRIEVAL SANITY TEST (wiki-routed) ===\n")
    all_pass = True

    for q, exp in zip(queries, expected):
        _, results = retrieve(q, max_chars=999999, top_k=1)
        top_doc = results[0]["doc_name"] if results else "(none)"
        match = exp.lower() in top_doc.lower()
        status = "PASS" if match else "FAIL"
        if not match:
            all_pass = False
        print(f"  Query:      {q}")
        print(f"  Expected:   {exp}")
        print(f"  Top result: {top_doc}")
        print(f"  Status:     {status}")
        print()

    if all_pass:
        print("All retrieval tests PASSED.")
    else:
        print("Some tests FAILED.")
