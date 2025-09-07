#!/usr/bin/env python
import sys
from pathlib import Path as _P
ROOT_DIR = _P(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import argparse
import json
import time
from pathlib import Path
from typing import Optional

from medal import load_dotenv_if_present, require_env


def human_status(s: str) -> str:
    return s.replace("_", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit and monitor OpenAI Batch job for chat completions")
    parser.add_argument("--input-jsonl", required=True, help="Batch input JSONL prepared by batch_prepare.py")
    parser.add_argument("--display-name", default=None, help="Optional display name for batch job")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Polling interval in seconds")
    parser.add_argument("--timeout-seconds", type=int, default=36000, help="Max wait in seconds (default 10h)")
    parser.add_argument("--out-dir", default="data/runs", help="Directory to write batch metadata and outputs")
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    input_path = Path(args.input_jsonl)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Detect endpoint from first JSONL line (defaults to chat completions)
    detected_endpoint = "/v1/chat/completions"
    try:
        with input_path.open("r", encoding="utf-8") as rf:
            for line in rf:
                line = line.strip()
                if not line:
                    continue
                try:
                    first_obj = json.loads(line)
                    detected_endpoint = first_obj.get("url", detected_endpoint)
                except Exception:
                    pass
                break
    except Exception:
        pass

    # Upload the file for batch processing
    file_obj = client.files.create(file=input_path.open("rb"), purpose="batch")

    # Create the batch job targeting the detected endpoint
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint=detected_endpoint,
        completion_window="24h",
        display_name=args.display_name or f"MEDAL batch {input_path.name}",
    )

    meta_path = out_dir / f"{batch.id}.json"
    with meta_path.open("w", encoding="utf-8") as w:
        json.dump({"batch_id": batch.id, "file_id": file_obj.id}, w, indent=2)
    print(f"Submitted batch: {batch.id}; input file: {file_obj.id}; metadata: {meta_path}")

    # Poll for completion
    start = time.time()
    while True:
        b = client.batches.retrieve(batch.id)
        status = b.status
        print(f"Status: {human_status(status)} | succeeded={b.request_counts.completed} failed={b.request_counts.failed}")
        if status in {"completed", "failed", "expired", "cancelling", "cancelled"}:
            break
        if time.time() - start > args.timeout_seconds:
            print("Timeout reached; exiting.")
            return
        time.sleep(args.poll_seconds)

    # Download results if available
    if getattr(b, "output_file_id", None):
        out_file = client.files.retrieve(b.output_file_id)
        content = client.files.content(b.output_file_id)
        out_path = out_dir / f"{batch.id}.results.jsonl"
        with out_path.open("wb") as w:
            w.write(content.read())
        print(f"Saved results to: {out_path}")
    else:
        print("No output_file_id on batch; check status and errors.")

    # Save error file if present
    if getattr(b, "error_file_id", None):
        err_content = client.files.content(b.error_file_id)
        err_path = out_dir / f"{batch.id}.errors.jsonl"
        with err_path.open("wb") as w:
            w.write(err_content.read())
        print(f"Saved errors to: {err_path}")


if __name__ == "__main__":
    main()


