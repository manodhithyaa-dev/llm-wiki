import io
from contextlib import redirect_stdout

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

from pipelines.ingest_document import process_documents
from pipelines.ingest_image import process_images
from pipelines.ingest_video import process_videos
from pipelines.wiki_builder import build_all
from pipelines.linter import lint
from pipelines.retriever import retrieve, cmd_test_retrieval
from pipelines.query import ask

app = FastAPI(title="LLM Wiki Web UI")

HERE = __file__.rsplit("/", 1)[0]
HTML_PATH = HERE + "/templates/index.html"


def _capture(func, *args, **kwargs):
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


class QueryBody(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(HTML_PATH) as f:
        return f.read()


@app.post("/api/ingest")
async def api_ingest():
    output = _capture(lambda: [process_documents(), process_images(), process_videos()])
    return {"output": output}


@app.post("/api/build")
async def api_build():
    output = _capture(build_all)
    return {"output": output}


@app.post("/api/lint")
async def api_lint():
    output = _capture(lint)
    return {"output": output}


@app.post("/api/test-retrieval")
async def api_test_retrieval():
    output = _capture(cmd_test_retrieval, None)
    return {"output": output}


@app.post("/api/query")
async def api_query(body: QueryBody):
    question = body.question

    buf = io.StringIO()
    with redirect_stdout(buf):
        context, results = retrieve(question)
    retrieve_output = buf.getvalue()

    if not context:
        return {
            "output": "No processed documents found. Run ingest and build first.",
            "answer": "",
            "results": [],
        }

    answer = ask(question, context)

    return {
        "output": retrieve_output,
        "answer": answer,
        "results": [
            {
                "rank": i + 1,
                "doc_name": r["doc_name"],
                "page": r["page"],
                "score": r["score"],
                "preview": r["preview"],
            }
            for i, r in enumerate(results[:10])
        ],
    }
