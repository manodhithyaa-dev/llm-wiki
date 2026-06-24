# Auto-Research Program: LLM Wiki Retrieval Optimization

You are an autonomous research agent. Your goal is to improve the **retrieval accuracy** of a file-based LLM Wiki system by making targeted changes to `pipelines/retriever.py`.

## Setup

1. Create a new git branch for each experiment:
   `git checkout -b exp/<brief-description>`
2. Read these files to understand the system:
   - `pipelines/retriever.py` — your experiment file
   - `evaluate.py` — the read-only evaluation harness
   - `test_queries.json` — ground-truth test queries
3. Verify the Wiki build exists and `venv/bin/python evaluate.py` runs successfully
4. Create `results.tsv` with header:
   `commit\tval_score\tdoc_acc\tkw_recall\tlatency_ms\tstatus\tdescription`

## Experimentation Rules

- **You may ONLY modify:** `pipelines/retriever.py`
- **You may NOT modify:** `evaluate.py`, `test_queries.json`, any other pipeline file, or any file outside this repo
- **You may NOT add new dependencies** — use only Python standard library
- **You may NOT rename or restructure** the `pipelines/` package
- **Goal:** maximize `retrieval_score` printed by `venv/bin/python evaluate.py`
- The metric is **retrieval_score** — a float between 0.0 and 1.0 (higher = better)
- Additional metrics on stderr: doc_accuracy, keyword_recall, avg_latency_ms

## What You Can Change in retriever.py

- Keyword scoring algorithm (`score_chunks`, `score_text`)
- Wiki router thresholds and logic (`route_via_wiki`, `MIN_CONFIDENCE`)
- Tokenization approach (`tokenize`, `tokenize_query`)
- Stop word list (`STOP_WORDS`)
- Chunk assembly strategy (`_assemble`)
- Title bonus and frequency weight coefficients

## The Infinite Loop

```
1.  venv/bin/python evaluate.py         # measure baseline
2.  git add -A && git commit -m "..."   # record it
3.  LOOP:
4.    modify pipelines/retriever.py     # implement your idea
5.    venv/bin/python evaluate.py       # measure result
6.    read the score (last stdout line)
7.    if score > best_val_score:
8.      git add -A && git commit -m "..."
9.      append row to results.tsv with status="keep"
10.     update best_val_score
11.   else:
12.     git checkout -- pipelines/retriever.py  # discard
13.     append row to results.tsv with status="discard"
14.   goto LOOP
```

## Crash Handling

If `venv/bin/python evaluate.py` crashes:
- Append row to results.tsv with status="crash" and the error
- Run `git checkout -- pipelines/retriever.py` to restore
- Continue the loop

## Simplicity Criterion

Small improvements that add ugly complexity are not worth it. The best
agent is one that achieves high accuracy with clean, simple code.

## NEVER STOP

Do NOT ask for permission to continue. Do NOT stop after one experiment.
Keep iterating until manually interrupted (Ctrl+C).

## Typical Performance

- Each experiment cycle: ~5-30 seconds (no API calls)
- Current baseline score: **0.8469** (doc_accuracy=1.0, keyword_recall=0.91)
- Target: find improvements that consistently raise the score
