from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from config import GPT_MINI_MODEL
from pipelines.utils import append_log
from pipelines.retriever import retrieve, load_all_chunks

load_dotenv()

client = OpenAI()


def ask(question: str, context: str) -> str:
    system_prompt = """You are a knowledge assistant analyzing ingested documents.
Answer the user's question based ONLY on the document content provided below.
If the answer cannot be found in the provided content, say so clearly.
You MUST cite the exact source document name AND page number for every claim you make.
Use the format: **[Source: Document Name, Page N]**
Example: "Appointments can be booked by phone **[Source: BRD - Mongo ver 1.04, Page 1]**"
Cite every claim."""

    user_prompt = f"""Document Content (each section is tagged with [Source / Page]):

{context}

Question: {question}

Rules:
- Base your answer ONLY on the document content above.
- For EACH specific claim, add a citation like **[Source: Document Name, Page N]**.
- If the page marker says "[BRD - Mongo ver 1.04 / Page 1]", cite as **[Source: BRD - Mongo ver 1.04, Page 1]**.
- If you cannot find the answer, say "The document does not contain this information."
- Be precise and structured."""

    response = client.responses.create(
        model=GPT_MINI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.output_text


def cmd_query(args) -> None:
    question = " ".join(args.question) if args.question else ""
    if not question:
        print("Please provide a question.")
        return

    total_docs = (
        len(list(Path("processed/documents").iterdir()))
        if Path("processed/documents").exists()
        else 0
    )

    all_chunks = load_all_chunks()
    total_chunks = len(all_chunks)

    print(f"[QUERY] Loading processed documents...")
    print(f"[QUERY] Total documents on disk: {total_docs}")
    print(f"[QUERY] Total chunks (pages) available: {total_chunks}")

    context, results = retrieve(question)

    if not context:
        print("[QUERY] No processed documents found. Run `python main.py ingest` first.")
        return

    print(f"[QUERY] Context assembled: {len(context):,} chars from {len(results)} chunks")

    print(f"\n=== RETRIEVAL RESULTS ===")
    for i, r in enumerate(results, 1):
        print(f"\n  Rank {i}")
        print(f"  Document: {r['doc_name']}")
        print(f"  Page:     {r['page']}")
        print(f"  Score:    {r['score']}")
        print(f"  Preview:  {r['preview'][:100]}...")

    print(f"\n[QUERY] Asking: {question}\n")

    answer = ask(question, context)

    print(answer)
    print()
    append_log(f"Query: {question}")
