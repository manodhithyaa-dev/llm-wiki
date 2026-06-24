from pathlib import Path
from datetime import datetime
from typing import Optional


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def append_log(message: str) -> None:
    ensure_dir("wiki")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("wiki/log.md", "a", encoding="utf-8") as f:
        f.write(f"- [{timestamp}] {message}\n")
