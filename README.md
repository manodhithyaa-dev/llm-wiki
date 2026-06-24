# File-Based Multi-Modal LLM Wiki

A zero-database, file-based wiki system that ingests documents (PDF/DOCX), images, and videos; builds an Obsidian-compatible knowledge graph with source summaries, concept pages, entity pages, and image caption pages; and answers free-form questions with **exact source citations** — all using nothing but the filesystem and markdown.

**No PostgreSQL. No SQLite. No vector databases. No external search services.** Just files, folders, and OpenAI API calls.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Setup](#setup)
5. [Web UI](#web-ui)
6. [CLI Commands](#cli-commands)
7. [Ingestion Pipeline](#ingestion-pipeline)
   - [PDF Ingestion](#pdf-ingestion)
   - [DOCX Ingestion](#docx-ingestion)
   - [Image Ingestion](#image-ingestion)
   - [Video Ingestion](#video-ingestion)
8. [Wiki Build Pipeline](#wiki-build-pipeline)
   - [Source Pages](#source-pages)
   - [Image Caption Pages](#image-caption-pages)
   - [Concept Pages](#concept-pages)
   - [Entity Pages](#entity-pages)
   - [Contradiction Detection](#contradiction-detection)
   - [Index Generation](#index-generation)
9. [Query Pipeline](#query-pipeline)
   - [Wiki Router](#wiki-router)
   - [Keyword Scoring](#keyword-scoring)
   - [Context Assembly](#context-assembly)
   - [Answer Generation](#answer-generation)
   - [Image Citation Support](#image-citation-support)
10. [Linter](#linter)
11. [Testing](#testing)
    - [Evaluation Harness](#evaluation-harness)
    - [Retrieval Sanity Tests](#retrieval-sanity-tests)
    - [Ambiguity Test Script](#ambiguity-test-script)
    - [Manual Testing](#manual-testing)
12. [Configuration Reference](#configuration-reference)
13. [Data Flow Diagrams](#data-flow-diagrams)
14. [File Reference](#file-reference)
15. [Design Decisions](#design-decisions)
16. [Troubleshooting](#troubleshooting)
17. [Performance Notes](#performance-notes)

---

## Overview

This system transforms raw input files (PDF manuals, DOCX specifications, photographs, video recordings) into a browsable, searchable, queryable wiki. It is designed for knowledge workers who need to:

- Centralize information from multiple file formats into one place
- Ask natural-language questions and get answers with **which page in which document** the answer came from
- Browse concepts and entities across documents via Obsidian-compatible `[[wikilinks]]`
- Detect contradictions between different sources covering the same topic
- Keep everything in plain markdown — no lock-in, no database migrations

### Key Capabilities

| Capability | How It Works |
|---|---|
| **PDF ingestion** | PyMuPDF extracts text per page; embedded images extracted via `page.get_images()` → `doc.extract_image()`, captioned by GPT-4o |
| **DOCX ingestion** | python-docx preserves headings, bullet lists, numbered lists, and tables as markdown; embedded images extracted via zipfile |
| **Image ingestion** | GPT-4o vision generates description, OCR text, and relevance classification; irrelevant images flagged |
| **Video ingestion** | FFmpeg extracts audio (Whisper transcription) + keyframes every 10 seconds (GPT-4o captioned) |
| **Wiki building** | GPT-4.1-mini generates source summaries, extracts concepts/entities, builds pages with `[[backlinks]]` |
| **Q&A** | Keyword-based retrieval across 458+ chunks (pages + image captions); GPT answers with `**[Source: ..., Page N]**` citations |
| **Contradiction detection** | Compares concepts shared across ≥2 sources; writes report to `_contradictions.md` |
| **Linting** | Detects missing citations, orphan pages, broken wikilinks, duplicate concepts |
| **Obsidian compatibility** | All wiki pages use `[[wikilinks]]` for cross-references — open the `wiki/` folder in Obsidian directly |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Filesystem (no databases)                        │
│                                                                          │
│  raw/ ──────────► processed/ ──────────► wiki/                          │
│  │                    │                      │                           │
│  ├── documents/       ├── documents/{name}/   ├── sources/              │
│  │   └── *.pdf        │   ├── pages/*.md      │   └── {doc_name}.md     │
│  │   └── *.docx       │   ├── images/*.{png}  ├── concepts/             │
│  ├── images/          │   └── source_metadata  │   └── {concept}.md     │
│  │   └── *.jpg        ├── images/*.caption.md ├── entities/             │
│  └── videos/          │                        │   └── {entity}.md      │
│      └── *.mp4        │                        ├── images/{doc_name}/   │
│                        │                        │   └── {img}.md        │
│                        │                        ├── index.md            │
│                        │                        ├── _contradictions.md  │
│                        │                        └── log.md              │
└─────────────────────────────────────────────────────────────────────────┘
          │                         │                          │
          ▼                         ▼                          ▼
    Ingestion step           Build step               Query / Browse step
    (extract text,           (GPT generates            (keyword scoring
     save images,             wiki pages)               + GPT answer)
     caption images)
```

### Separation of Concerns

| Layer | Contents | Purpose |
|---|---|---|
| `raw/` | Original source files | Immutable input archive — never modified |
| `processed/` | Cleaned text + extracted images + captions | Intermediate representation between ingest and build |
| `wiki/` | Final wiki pages (source/concept/entity/image/index) | The browsable, queryable output — regenerable from `processed/` |

---

## Directory Structure

```
.
├── main.py                              # CLI entry point
├── app.py                               # FastAPI web UI (alternative to CLI)
├── config.py                            # Model names, paths, constants
├── evaluate.py                          # Retrieval evaluation harness
├── program.md                           # Auto-research agent program
├── requirements.txt                     # Python dependencies
├── test_queries.json                    # 15 ground-truth test queries
├── test.sh                              # Ambiguity test script (20 queries)
├── test_openai.py                       # OpenAI API connectivity test
├── .env                                 # OPENAI_API_KEY (not committed)
├── .gitignore                           # Git ignore rules
├── ambiguity_test_results.txt           # Ambiguity test output
│
├── pipelines/
│   ├── __init__.py
│   ├── utils.py                         # ensure_dir(), append_log()
│   ├── ingest_document.py              # PDF & DOCX ingestion
│   ├── ingest_image.py                 # Image captioning via GPT-4o
│   ├── ingest_video.py                 # FFmpeg + Whisper video processing
│   ├── wiki_builder.py                 # Source/concept/entity/index generation
│   ├── retriever.py                    # Chunk loading, keyword scoring, wiki router
│   ├── query.py                        # ask() and cmd_query()
│   └── linter.py                       # Wiki health checks
│
├── templates/
│   └── index.html                       # Web UI frontend (served by app.py)
│
├── raw/
│   ├── assets/            ← Place additional raw assets here
│   ├── documents/          ← Place .pdf and .docx files here
│   ├── images/             ← Place .jpg/.png/.gif/.bmp/.webp here
│   └── videos/             ← Place .mp4/.avi/.mov/.mkv here
│
├── processed/
│   ├── documents/{name}/
│   │   ├── pages/          ← One .md per document page (text + image refs)
│   │   ├── images/         ← Extracted embedded images (PDF/DOCX)
│   │   └── source_metadata.md
│   ├── images/             ← GPT-4o caption files for *all* processed images
│   │   └── {img_name}.caption.md
│   └── videos/             ← Video transcripts and keyframes
│
├── wiki/
│   ├── sources/            ← GPT-generated source summaries
│   ├── concepts/           ← Concept pages with [[backlinks]]
│   ├── entities/           ← Named entity pages with [[backlinks]]
│   ├── images/{doc_name}/  ← Caption pages organized by source document
│   ├── index.md            ← Auto-generated wiki index
│   ├── _contradictions.md  ← Cross-source contradiction report
│   └── log.md              ← Timestamped event log
│
├── .obsidian/              ← Obsidian workspace (graph, plugins, appearance)
│
└── venv/                   ← Python virtual environment
```

---

## Setup

### Prerequisites

- **Python 3.10+** (tested on 3.10-3.12)
- **OpenAI API key** with access to `gpt-4.1-mini` and `gpt-4o` models
- **FFmpeg** (only needed for video ingestion):
  ```bash
  sudo apt install ffmpeg    # Ubuntu/Debian
  brew install ffmpeg         # macOS
  ```

### Step-by-Step

```bash
# 1. Clone and enter the project
cd llm_wiki_claude_idea

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your OpenAI API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# 5. Place input files in raw/ directories:
#    - PDF/DOCX files → raw/documents/
#    - Images → raw/images/
#    - Videos → raw/videos/
#    (Embedded images inside PDF/DOCX are extracted automatically)

# 6. Run the full pipeline
python main.py ingest          # Extract text + images, caption images
python main.py build           # Generate all wiki pages
python main.py lint            # Verify wiki health

# 7. Ask questions (CLI)
python main.py query "What tools are needed to replace the running belt?"

# 8. (Optional) Start the web UI instead
uvicorn app:app --reload
# Open http://localhost:8000
```

---

## Web UI

**File**: `app.py` + `templates/index.html`

An alternative to the CLI — a FastAPI web interface that exposes all pipeline operations through a browser:

```bash
# Start the web server
uvicorn app:app --reload

# Open http://localhost:8000 in your browser
```

The UI provides buttons for **Ingest**, **Build**, **Lint**, and **Test Retrieval**, plus a query input for asking questions. Results and answers are rendered in-page with markdown formatting.

## CLI Commands

### `python main.py ingest`
Ingests **all** file types (documents, images, videos) in one pass.

Low-level equivalents:
- `python main.py ingest-docs` — process only `raw/documents/`
- `python main.py ingest-images` — process only `raw/images/`
- `python main.py ingest-videos` — process only `raw/videos/`

### `python main.py build`
Generates the complete wiki from `processed/` data:
1. Cleans `wiki/` directories
2. Generates source pages (one per document, via GPT)
3. Processes image captions into per-document image pages
4. Extracts concepts and entities from source pages
5. Builds concept pages with summaries and `[[backlinks]]`
6. Builds entity pages with `[[backlinks]]`
7. Detects contradictions across shared concepts
8. Generates the index page

### `python main.py query "your question"`
The primary Q&A command. Outputs:
- Retrieval results (ranked chunks with scores and previews)
- AI-generated answer with inline source citations

### `python main.py lint`
Scans all `wiki/*.md` files for:
- **missing_citation**: Source pages lacking `[[wikilinks]]` or markdown links
- **orphan**: Pages with zero incoming wikilinks (excludes `index`, `log`, `_contradictions`, `readme`, and `images/` directory)
- **duplicate_concept**: Concept pages with identical titles
- **empty**: Empty markdown files

### `python main.py test-retrieval`
Runs 4 sanity checks to verify the retrieval pipeline:
| Query | Expected Document |
|---|---|
| `"Rackmount DVRS"` | Motorola DVR-LX |
| `"Philips Screwdriver"` | Motorola DVR-LX |
| `"Favorite channel list"` | STB Nagra DCS 5000 |
| `"Treadmill"` | Treadmill service manual |

Each test routes via the wiki router, retrieves the top result, and reports PASS/FAIL.

---

## Ingestion Pipeline

### PDF Ingestion

**File**: `pipelines/ingest_document.py` → `ingest_pdf()`

Per-page processing:

```
┌──────────────┐     ┌───────────────┐     ┌─────────────────┐
│ Open PDF via  │────►│ Extract text  │────►│ Save p{NNN}.md  │
│ PyMuPDF       │     │ page.get_text()│     │ # Page N + text  │
└──────┬───────┘     └───────┬───────┘     └────────┬────────┘
       │                     │                       │
       ▼                     ▼                       ▼
┌──────────────┐     ┌───────────────┐     ┌─────────────────┐
│ page.get_    │────►│ doc.extract_  │────►│ Save to         │
│ images()     │     │ image(xref)   │     │ images/ dir     │
└──────────────┘     └───────┬───────┘     └────────┬────────┘
                             │                       │
                             ▼                       ▼
                     ┌────────────────┐     ┌─────────────────┐
                     │ ingest_image() │────►│ Append md ref   │
                     │ (GPT-4o        │     │ ![Image](path)  │
                     │  caption)      │     │ to page .md     │
                     └────────────────┘     └─────────────────┘
```

**Output per page**: A `.md` file containing:
```markdown
# Page 34

HS Consumer Treadmill
How To… Replace The Running Belt and Deck  

Tools Required: Allen key set, Phillips screwdriver...

![Page 34 Image](../images/p034_img001.png)

![Page 34 Image](../images/p034_img002.png)
```

**Image naming**: `p{page:03d}_img{idx:03d}.{ext}` — embedded image count per page.

### DOCX Ingestion

**File**: `pipelines/ingest_document.py` → `ingest_docx()`

Features:
- **Headings** (`Heading 1`–`Heading 6`) → `#`–`######`
- **Bullet lists** → `- item` with indentation for nested levels
- **Numbered lists** → `1. item` with correct nesting via `w:ilvl`
- **Tables** → Markdown pipe tables with header separator row
- **Embedded images** → Extracted from `word/media/` inside the DOCX zip archive, captioned via GPT-4o
- **Source metadata** → `source_metadata.md` with file size, dates, type

All content goes into a single page file `p001.md` (DOCX documents are not page-structured like PDFs).

### Image Ingestion

**File**: `pipelines/ingest_image.py` → `ingest_image()`

**Supported formats**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`

**Processing**:

1. **Base64 encode** the image
2. **Send to GPT-4o** with a structured vision prompt requesting:
   - **Description**: What the image depicts
   - **OCR text**: Any visible text in the image
   - **Relevance classification**: `Evidence-bearing` (contains critical data) or `Illustrative` (supplementary only)
3. **Save caption** to `processed/images/{img_name}.caption.md` in this format:

````markdown
# Image: p034_img001.png

**Dimensions:** 1751x473

```markdown
## Description
The image is a black and white diagram showing an assembly of components...

## OCR Text
- End Cap Bottom(L)
- End Cap Screw(6)
- Deck Guard(2)
- Deck Guard Screw(4)
- End Cap Bottom(R)
- End Cap Screw(2)

## Relevance Classification
Evidence-bearing
```

_Source: 136_Treadmill service manual_
Relevance filtering: Images classified as Irrelevant are skipped (not saved to processed/images/). This avoids captioning meaningless decorative images or blank scans.
Video Ingestion
File: pipelines/ingest_video.py → ingest_video()
Supported formats: .mp4, .avi, .mov, .mkv
Processing pipeline:
┌──────────────┐     ┌─────────────────┐     ┌────────────────────┐
│ Input video  │────►│ FFmpeg: extract  │────►│ Whisper:           │
│ (file)       │     │ audio → .wav     │     │ transcribe audio   │
└──────┬───────┘     └─────────────────┘     └─────────┬──────────┘
       │                                                │
       ▼                                                ▼
┌─────────────────┐                            ┌────────────────────┐
│ FFmpeg: extract  │                            │ transcription.txt  │
│ keyframes every  │                            │                    │
│ 10 seconds       │                            │ "Press the power   │
└─────────┬───────┘                            │ button to start..."│
          │                                     └────────────────────┘
          ▼
┌─────────────────┐
│ Each keyframe   │
│ → ingest_image()│
│ (GPT-4o caption)│
└─────────────────┘
Output:
- Audio transcription saved alongside the video
- Keyframe images saved and captioned like standalone images
- Video file renamed to .processed after completion
Wiki Build Pipeline
File: pipelines/wiki_builder.py → build_all()
Source Pages
For each processed document, GPT-4.1-mini receives:
- The first 8000 characters of the document content
- Source metadata (file size, dates, type)
The prompt requests these sections:
# {Document Name}

## Summary
A 3-5 sentence summary of the document.

## Key Concepts
- Bullet list of 3-10 key concepts (2-5 words each)

## Key Entities
- Named entities (people, organizations, technologies, places)

## Citations
- Notable references mentioned in the text

## Raw Source
`raw/documents/{doc_name}`

[[{doc_name}]]
The final [[wikilink]] ensures the source page is cross-referenced in the wiki.
Image Caption Pages
File: wiki_builder.py → process_image_captions()
Image captions from processed/images/*.caption.md are placed into per-document subdirectories:
wiki/images/
├── 136_Treadmill service manual/
│   ├── p034_img001.md
│   ├── p034_img002.md
│   └── ...
├── Motorola solutions DVR-LX P25 Installation Manual/
│   ├── p001_img001.md
│   └── ...
└── 120_1.1 STB - Nagra_DCS 5000 (With Physical Smartcard) User Manual/
    └── ...
The mapping from image filename → source document is built by scanning processed/documents/*/images/ directories. Each caption page has a _Source: {doc_name} footer that is used by the retriever for citation generation.
Concept Pages
Concepts are extracted from the ## Key Concepts section of each source page. When duplicate concepts exist across documents, the source lists are merged:
# How-to_service_and_repair_instructions

References to How-to service and repair instructions found in source documents.

## Backlinks
- [[136_Treadmill service manual]]
- [[Motorola solutions DVR-LX P25 Installation Manual]]
Each concept gets a 2-3 sentence GPT-generated description summarizing what the concept means across all source contexts.
Entity Pages
Entities are extracted from the ## Key Entities section. Like concept pages, they have backlinks:
# Healthstream_Taiwan_Inc.

## Backlinks
- [[136_Treadmill service manual]]
Contradiction Detection
File: wiki_builder.py → detect_contradictions()
Trigger: Concepts that appear in ≥2 source documents.
Process:
1. Identify shared concepts from the concept map
2. Read each source document's summary from wiki/sources/
3. Send a GPT prompt comparing the sources on that topic:
"Do any specific claims contradict each other? If yes, list each contradiction with the conflicting claims. Use format: [Source Name] for each source reference."
4. If GPT reports any contradictions, write them to wiki/_contradictions.md
Output format:
# Contradictions

## Treadmill_Maintenance_Interval

- [[136_Treadmill service manual]]: "Lubricate the belt every 30 days"
- [[Motorola solutions DVR-LX P25 Installation Manual]]: "No regular lubrication needed"
Preservation: _contradictions.md is excluded from linter orphan checks and preserved during wiki rebuilds.
Index Generation
Auto-generated index with sections for Sources, Concepts, and Entities — all using [[wikilinks]]:
# Wiki Index

_Generated: 2026-06-18 12:34:56_

## Sources
- [[120_1.1 STB - Nagra_DCS 5000 (With Physical Smartcard) User Manual]]
- [[136_Treadmill service manual]]
- [[BRD - Mongo ver 1.04]]
- [[Motorola solutions DVR-LX P25 Installation Manual]]

## Concepts
- [[Appointment_Scheduling_Process]]
- [[Billing_and_Payment_Integration]]
- [[Customer_Data_Management]]
...

## Entities
- [[Healthstream_Taiwan_Inc.]]
- [[Motorola_Solutions,_Inc.]]
...
Query Pipeline
File: pipelines/retriever.py + pipelines/query.py
┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌────────────┐
│ User     │────►│ Wiki router  │────►│ Keyword score │────►│ Assemble   │
│ query    │     │ (source      │     │ all page-     │     │ context    │
│          │     │  summaries)  │     │ chunks + img  │     │ (≤55K char)│
└──────────┘     └──────────────┘     │ chunks        │     └─────┬──────┘
                                       └───────────────┘           │
                                                                    ▼
                                                            ┌────────────┐
                                                            │ GPT-4.1-   │
                                                            │ mini:      │
                                                            │ answer +   │
                                                            │ citations  │
                                                            └────────────┘
Wiki Router (Step 1)
File: retriever.py → route_via_wiki()
1. Loads all source summaries from wiki/sources/*.md
2. Tokenizes both the query and each summary
3. Scores each summary by term overlap (shared non-stop-word tokens)
4. If top score ≥ 1.5 and > runner-up score → route to that document's chunks only
5. Otherwise → brute-force fallback: score against all 458+ chunks across all documents
This avoids expensive brute-force scoring when the query clearly targets one document.
Keyword Scoring (Step 2)
File: retriever.py → score_chunks()
Each chunk (page or image caption) is scored against the query:
score = term_overlap + title_bonus + (frequency_score × 0.5)

Where:
  term_overlap   = count of query tokens present in chunk (set intersection)
  title_bonus    = shared tokens between query and document name × 2
  frequency_score = sum of occurrence counts for each query token in chunk
Tokenization: Lowercasing, regex [a-z0-9]+ extraction, stop-word filtering.
Stop words: 100+ common English words filtered out (a, an, the, and, or, but, in, on, at, to, for, of, with, by, from, as, is, are...)
Context Assembly (Step 3)
File: retriever.py → _assemble()
- Chunks sorted by descending score, then document name, then page number
- Added to context until either:
- Character limit reached (55,000 by default)
- Top K chunks selected (20 by default)
- Remaining chunks have score ≤ 0
- Each chunk is formatted as:
[{Doc Name} / Page {N}]
{page content}
- Image chunks are formatted as:
[{Doc Name} / Image: {img_name}]
{image caption content}
Answer Generation (Step 4)
File: query.py → ask()
The assembled context is sent to GPT-4.1-mini with a system prompt:
You are a knowledge assistant analyzing ingested documents.
Answer the user's question based ONLY on the document content provided below.
If the answer cannot be found in the provided content, say so clearly.
You MUST cite the exact source document name AND page number for every claim you make.
Use the format: **[Source: Document Name, Page N]**
Example: "Appointments can be booked by phone **[Source: BRD - Mongo ver 1.04, Page 1]**"
Cite every claim.
The user prompt includes the context and rules for citation format.
Image Citation Support
Since image caption chunks use the format {Doc Name} / Image: {img_name}, GPT automatically cites them as:
**[Source: 136_Treadmill service manual, Image: p034_img001]**
This means image caption data (OCR text, descriptions) is:
1. Retrievable via keyword scoring (terms like "End Cap Screw(6)" match queries about screw counts)
2. Citable with exact image references (not lumped under the page citation)
3. Scored on equal footing with page chunks (image captions often rank in top 5 for visual/mechanical queries)
Linter
File: pipelines/linter.py → lint()
Checks
Check	Description
missing_citation	Source pages must contain at least one [[wikilink]] or markdown link
orphan	Every page must be linked-to by at least one other page
duplicate_concept	Concept pages with same title (case-insensitive)
empty	Zero-length markdown files
Exclusions
The following are never flagged as orphans:
- index.md — stand-alone index page
- log.md — event log
- _contradictions.md — contradiction report
- readme.md — optional readme
- Any file under wiki/images/ — image caption pages (referenced via markdown ![]() syntax, not wikilinks)
Testing
Evaluation Harness
Files: evaluate.py + test_queries.json
A quantitative evaluation suite for retrieval optimization. Contains 15 ground-truth queries across 4 documents, each specifying an expected source document and expected keywords. The harness measures:
- doc_accuracy — fraction of queries where the expected document appears in top-5 results
- keyword_recall — fraction of expected keywords found in retrieved chunks
- avg_latency_ms — average retrieval time per query
python evaluate.py
Output: retrieval_score (0.0–1.0), a weighted combination of recall (60%), precision (30%), minus a latency penalty.
Retrieval Sanity Tests
python main.py test-retrieval
Four tests verify that the wiki router correctly identifies the target document for each query:
1. Rackmount DVRS → Motorola DVR-LX (score ≥ 1.5, clear route)
2. Philips Screwdriver → Motorola DVR-LX (low scores, brute-force fallback, correct result)
3. Favorite channel list → STB Nagra DCS 5000 (clear route)
4. Treadmill → Treadmill service manual (clear route)
Ambiguity Test Script
File: test.sh
A bash script that runs 20 natural-language queries covering all 4 documents, piping each through python main.py query and printing the full output. Useful for manual inspection of answer quality:
./test.sh
Results can be redirected:
./test.sh > ambiguity_test_results.txt
Manual Testing
# Ask questions that span text + images
python main.py query "How many end cap screws per side?"

# Ask questions about image-only data
python main.py query "What OCR text appears on page 34 images?"

# Verify answer quality
python main.py query "What are the dimensions of the DVR-LX?"
Configuration Reference
File: config.py
Setting	Default
GPT_MINI_MODEL	gpt-4.1-mini
GPT_VISION_MODEL	gpt-4o
DOCUMENTS_DIR	raw/documents
IMAGES_DIR	raw/images
VIDEOS_DIR	raw/videos
IMAGE_EXTENSIONS	{jpg, jpeg, png, gif, bmp, webp, tiff}
VIDEO_EXTENSIONS	{mp4, avi, mov, mkv}
MAX_CONTEXT_CHARS	55000
TOP_K_RESULTS	20
MIN_CONFIDENCE	1.5
GPT_SUMMARY_TRUNCATE	8000
Model Selection
Task
Image captioning
Source summaries
Concept descriptions
Answer generation
Contradiction detection
Modifying the 55K Context Limit
In config.py, change MAX_CONTEXT_CHARS. The effective limit is constrained by the model's maximum context window. For gpt-4.1-mini (1M context), higher values are safe. Do not modify the answer-generation prompts in query.py — they are tuned for citation format compliance.
Data Flow Diagrams
Full Pipeline
raw/documents/          raw/images/           raw/videos/
      │                     │                     │
      │ ingest-pdf()        │ ingest-image()      │ ingest-video()
      │ ingest-docx()       │                     │
      ▼                     ▼                     ▼
processed/documents/    processed/images/     processed/images/
  ├── pages/*.md          ├── {name}.caption    ├── {name}_kf*.caption
  ├── images/*.{png}      ├── ...               ├── ...
  └── source_metadata.md                        └── {name}_transcript.txt
      │                     │                     │
      └─────────────────────┼─────────────────────┘
                            │
                            ▼
                    build_all()
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
         wiki/sources/   wiki/images/   wiki/concepts/
              │             │             │
              ▼             ▼             ▼
         wiki/entities/  wiki/index.md  wiki/_contradictions.md
              │
              ▼
         query "question"
              │
              ▼
         Final answer with **[Source: ...]** citations
Query Data Flow
User Query: "How many end cap screws?"
        │
        ▼
┌───────────────────────┐
│ tokenize_query()       │  → ["end", "cap", "screws"]
│ (lowercase, regex,     │
│  stop-word filter)     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ route_via_wiki()       │  → score each wiki/sources/ summary
│                        │  → top=136_Treadmill (2.0), runner=0.0
│                        │  → ROUTED to 136_Treadmill
│                        │  → load_doc_chunks("136_Treadmill...")
│                        │     loads pages/ + wiki/images/{doc}/
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ score_chunks()         │  → 20 page chunks + 316 image chunks scored
│                        │  → Rank #1: p34 (score 20.0)
│                        │  → Rank #2: Image: p034_img001 (score 20.0)
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ _assemble()            │  → Top 20 chunks, ~43K chars
│                        │  → Includes image caption OCR data
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ ask(query, context)    │  → GPT-4.1-mini
│                        │  → "6 screws on one side, 2 on the other
│                        │     **[Source: ..., Page 34]**
│                        │     **[Source: ..., Image: p034_img001]**"
└───────────────────────┘
File Reference
main.py (CLI Entry Point)
Argument	Subcommand
ingest	—
ingest-docs	—
ingest-images	—
ingest-videos	—
build	—
lint	—
query	question
test-retrieval	—
app.py (FastAPI Web UI)
Endpoint	Method	Description
/	GET	Serve index.html
/api/ingest	POST	Run full ingestion pipeline
/api/build	POST	Build wiki from processed files
/api/lint	POST	Lint wiki pages
/api/test-retrieval	POST	Run retrieval sanity tests
/api/query	POST	Answer a question (JSON body: {"question": "..."})
evaluate.py (Evaluation Harness)
Function	Description
evaluate()	Load test_queries.json, run retrieve_scored(), compute retrieval_score
doc_accuracy	Fraction of queries where expected doc appears in top-5
keyword_recall	Fraction of expected keywords found in retrieved chunks
avg_latency_ms	Average retrieval time per query
retrieval_score	Weighted composite (recall×0.6 + accuracy×0.3 − latency_penalty)
program.md (Auto-Research Agent Program)
Section	Description
Setup	Branch, evaluate, results.tsv header
Experimentation Rules	Only modify retriever.py, maximize retrieval_score
Infinite Loop	measure → commit → modify → evaluate → keep/discard → repeat
Crash Handling	Restore retriever.py on crash, log to results.tsv
pipelines/utils.py
Function
ensure_dir(path)
append_log(message)
pipelines/ingest_document.py
Function
process_documents()
ingest_pdf(path)
ingest_docx(path)
_extract_pdf_images(doc, name, page)
_extract_docx_images(path, name)
_generate_source_metadata(path, name)
_table_to_markdown(table)
_is_bullet(para)
_has_list_numbering(para)
_get_list_level(para)
pipelines/ingest_image.py
Function
process_images()
ingest_image(path)
pipelines/ingest_video.py
Function
process_videos()
ingest_video(path)
pipelines/wiki_builder.py
Function
build_all()
_clean_wiki_dirs()
build_source_pages()
generate_source_page(name, content, metadata)
process_image_captions()
build_concept_pages(concept_map)
build_entity_pages(entity_map)
detect_contradictions(concept_map, sources)
build_index(sources, concepts, entities)
extract_concepts_from_source(markdown)
get_concept_summary(concept, contexts)
pipelines/retriever.py
Class/Function
Chunk(doc_name, page_label, text)
load_doc_chunks(doc_name)
load_all_chunks()
load_wiki_sources()
score_chunks(chunks, query)
route_via_wiki(query)
retrieve(query, max_chars, top_k)
cmd_test_retrieval(args)
pipelines/query.py
Function
ask(question, context)
cmd_query(args)
pipelines/linter.py
Function
lint()
Design Decisions
Why No Database?
Every prior iteration used PostgreSQL + pgvector for semantic search. This added complexity:
- Schema migrations when requirements changed
- Vector index tuning (IVFFlat vs HNSW, ef_search, probes)
- Connection management, pooling, failover
- Docker or system-level dependency
By using the filesystem as the database, we get:
- Portability: rsync the project directory to any machine
- Observability: Every data file is human-readable markdown
- No migrations: Adding a field? Just add a line to the markdown template
- Backup simplicity: tar czf backup.tar.gz ./wiki/
- Version control friendly: Wiki pages can be committed to git
Why Keyword Scoring Instead of Vector Search?
For technical/mechanical documents, keyword overlap is surprisingly effective:
- "end cap screw(6)" versus "screws(2)" — exact token matching captures the distinction
- "DVR-LX Rackmount" — unique named entities don't need semantic understanding
- "Phillips screwdriver" → "Phillips" and "screwdriver" are distinct markers
Vector search would add:
- Embedding API costs per chunk (458+ chunks × ~$0.0001 = $0.05 per re-index)
- Slower retrieval (API call per query)
- No significant accuracy gain for factoid questions on technical docs
The wiki router compensates for keyword scoring's main weakness: distinguishing between documents with overlapping vocabulary. By scoring summaries first, we bias retrieval toward the most relevant document before looking at individual pages.
Why Per-Document Image Directories in Wiki?
Image captions are stored in wiki/images/{doc_name}/{img_name}.md rather than flat wiki/images/{img_name}.md:
1. Retrieval grouping: When the wiki router routes to a specific document, only that document's image captions are loaded (fewer chunks to score)
2. Citation accuracy: The doc_name embedded in the chunk metadata ensures GPT cites the correct document
3. Cleaner file listing: 316 flat files in one directory is unwieldy; split by document it's manageable
4. Linter simplicity: The images/ folder exclusion catches all image caption directories at once
Why 55K Character Context Limit?
The original design used GPT-4 with an 8K context. With gpt-4.1-mini (1M context), the limit can be increased. 55K was chosen as a balance:
- High enough to include ~20 chunks (enough for multi-topic queries)
- Low enough to keep API costs reasonable (~$0.02 per query)
- Prevents the blind concatenation bug that plagued an earlier version (126K Treadmill content drowning out all other documents)
Troubleshooting
"No documents found" when running ingest
raw/documents/ directory not found
Fix: Create the directory and add files:
mkdir -p raw/documents
# Copy your PDF/DOCX files there
"No processed documents found" when running query
[QUERY] No processed documents found. Run `python main.py ingest` first.
Fix: Run ingestion first:
python main.py ingest && python main.py build
Wiki pages exist but query returns wrong answers
Likely cause: The wiki router is routing to the wrong document.
Check:
1. Run python main.py test-retrieval to verify the router works for known queries
2. Inspect the source summaries in wiki/sources/*.md — do they accurately summarize the document?
3. Check the router output: "Routed to: {doc_name}" — is it the right document?
4. If not, re-run python main.py build to regenerate source summaries
Image captions not appearing in query results
Likely cause: Wiki was not rebuilt after image ingestion, or images were ingested before the wiki build change.
Fix:
python main.py ingest    # Re-caption images (skips already captioned)
python main.py build     # Regenerate wiki with per-doc image directories
"invalid literal for int() with base 10" error
ValueError: invalid literal for int() with base 10: 'Image: p001_img001'
Fix: This was a known bug fixed in the sort key. Ensure you have the latest version of retrieval.py:
grep "_page_sort_key" pipelines/retriever.py
If not present, the fix added a try/except around int(x[0].page_label) that defaults to 99999 for non-numeric labels.
GPT-4o rate limiting during image ingestion
If you have many images (50+), you may hit OpenAI rate limits.
Symptoms: openai.RateLimitError or progressively slower responses.
Workarounds:
- Add a time.sleep(1) between API calls in ingest_image.py
- Run ingest with a subset of documents first
- Images that fail captioning are silently skipped (the page image ref is still written)
"FFmpeg not found" error during video ingestion
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
Fix: Install FFmpeg:
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffmpeg -version
Memory issues with large PDFs
PyMuPDF loads the entire PDF into memory. For 500+ page documents with many embedded images, you may hit memory limits.
Workaround: Process large PDFs separately:
python -c "from pipelines.ingest_document import ingest_pdf; ingest_pdf('raw/documents/large_doc.pdf')"
Existing captions have old flat structure
If you see wiki/images/p034_img001.md directly (not in a subdirectory), a rebuild may leave stale files.
Fix: Run python main.py build with the updated _clean_wiki_dirs() that removes both flat files and nested directories:
python main.py build
Performance Notes
Ingestion Times (Approximate)
File Type	Size
Treadmill PDF	8.2 MB
DVR-LX PDF	1.5 MB
STB PDF	2.1 MB
BRD DOCX	45 KB
Bottleneck: GPT-4o vision API calls for image captioning (~3-5 seconds per image with current rate limits).
Build Times
# Sources	# Images
4	316
Query Times
Operation
Wiki router (4 summaries)
Score 458 chunks
Assemble context
GPT-4.1-mini answer
Total
Storage
Directory
raw/
processed/
wiki/
Total
Requirements
openai>=1.0.0
python-docx>=1.1.0
PyMuPDF>=1.23.0
Pillow>=10.0.0
python-dotenv>=1.0.0
ffmpeg-python>=0.2.0
Tested with Python 3.10.12 and 3.12.3.