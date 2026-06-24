import os
import subprocess
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from config import SUPPORTED_VIDEO_FORMATS, WHISPER_MODEL
from pipelines.utils import ensure_dir, append_log

load_dotenv()

client = OpenAI()
VIDEOS_DIR = "raw/videos"


def extract_audio(video_path: str, audio_path: str) -> None:
    print(f"  Extracting audio...")
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path, "-y",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")
    print(f"  Audio extracted: {audio_path}")


def transcribe(audio_path: str) -> str:
    print(f"  Transcribing audio with Whisper...")
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=f,
        )
    return result.text


def extract_keyframes(video_path: str, out_dir: str) -> None:
    print(f"  Extracting keyframes (1 frame per 10 seconds)...")
    ensure_dir(out_dir)

    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", "fps=1/10",
            f"{out_dir}/frame_%04d.jpg",
            "-y",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  [WARN] Keyframe extraction had issues: {result.stderr}")

    frame_count = len(list(Path(out_dir).glob("frame_*.jpg")))
    print(f"  Extracted {frame_count} keyframes to {out_dir}")


def ingest_video(video_path: str) -> None:
    name = Path(video_path).stem
    print(f"[VIDEO] Processing {name}...")

    base = f"processed/videos/{name}"
    ensure_dir(base)

    audio_file = f"{base}/audio.wav"
    transcript_file = f"{base}/transcript.md"
    keyframes_dir = f"{base}/keyframes"

    if not Path(audio_file).exists():
        extract_audio(video_path, audio_file)
    else:
        print(f"  Audio already exists, skipping extraction")

    if not Path(transcript_file).exists():
        transcript = transcribe(audio_file)
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(f"# Video: {name}\n\n")
            f.write(f"**Source:** {Path(video_path).name}\n\n")
            f.write("## Transcript\n\n")
            f.write(transcript)
            f.write("\n")
        print(f"  Transcript saved: {transcript_file}")
    else:
        print(f"  Transcript already exists, skipping")

    extract_keyframes(video_path, keyframes_dir)

    print(f"[VIDEO] Processed {name}")
    append_log(f"Ingested video: {name}")


def process_videos() -> None:
    videos_dir = Path(VIDEOS_DIR)

    if not videos_dir.exists():
        print(f"[WARN] Videos directory not found: {VIDEOS_DIR}")
        return

    files_found = False

    for filename in os.listdir(str(videos_dir)):
        path = str(videos_dir / filename)
        ext = Path(path).suffix.lower()

        if ext in SUPPORTED_VIDEO_FORMATS:
            files_found = True
            try:
                ingest_video(path)
            except Exception as e:
                print(f"[ERROR] Failed to process video {filename}: {e}")
                append_log(f"ERROR: Failed to process video {filename}: {e}")
        else:
            print(f"[SKIP] Unknown video format: {filename}")

    if not files_found:
        print(f"[INFO] No videos found in {VIDEOS_DIR}")


if __name__ == "__main__":
    process_videos()
