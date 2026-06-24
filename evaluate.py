#!/usr/bin/env python3
"""Fixed evaluation harness for auto-research.

DO NOT MODIFY THIS FILE — it is the read-only metric that judges
the agent's changes to pipelines/retriever.py.

Usage:
    python evaluate.py

Output: prints a single float (retrieval_score 0.0 - 1.0) as the last line.
        Higher is better.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from pipelines.retriever import retrieve_scored
except ImportError as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)


QUERIES_PATH = Path(__file__).resolve().parent / "test_queries.json"


def load_queries():
    if not QUERIES_PATH.exists():
        print(f"ERROR: test_queries.json not found at {QUERIES_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(QUERIES_PATH) as f:
        return json.load(f)


def evaluate():
    queries = load_queries()
    total = len(queries)
    if total == 0:
        print("0.0")
        return

    doc_hits = 0
    keyword_hits = 0
    keyword_total = 0
    latencies = []

    for q in queries:
        query_text = q["query"]
        expected_doc = q["expected_doc"].lower()
        expected_keywords = [kw.lower() for kw in q["expected_keywords"]]

        start = time.perf_counter()
        scored = retrieve_scored(query_text, top_k=5)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

        top_docs = set()
        found_text = ""

        for chunk, score in scored:
            top_docs.add(chunk.doc_name.lower())
            found_text += chunk.text.lower() + " "

        match_doc = any(expected_doc in d for d in top_docs)
        if match_doc:
            doc_hits += 1

        kw_matched = 0
        for kw in expected_keywords:
            keyword_total += 1
            if kw in found_text:
                kw_matched += 1
        keyword_hits += kw_matched

    doc_accuracy = doc_hits / total if total else 0
    keyword_recall = keyword_hits / keyword_total if keyword_total else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    recall_weight = 0.6
    precision_weight = 0.3
    latency_penalty = min(avg_latency / 10.0, 0.1)

    retrieval_score = (
        recall_weight * keyword_recall
        + precision_weight * doc_accuracy
        - latency_penalty
    )
    retrieval_score = max(0.0, min(1.0, retrieval_score))

    print(f"retrieval_score={retrieval_score:.4f}")
    print(f"doc_accuracy={doc_accuracy:.4f}", file=sys.stderr)
    print(f"keyword_recall={keyword_recall:.4f}", file=sys.stderr)
    print(f"avg_latency_ms={avg_latency*1000:.1f}", file=sys.stderr)
    print(f"queries={total}", file=sys.stderr)


if __name__ == "__main__":
    evaluate()
