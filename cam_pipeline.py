#!/usr/bin/env python3
"""
End-to-end automation driver for the CAM framework.

Coordinates document ingestion, RAG store refresh, digest generation, scenario
evaluations, and judge scoring from a single CLI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from cam_agent.evaluation.judges import JudgeManager, build_default_judges
from cam_agent.evaluation.runner import CAMSuiteRunner
from cam_agent.knowledge import (
    build_faiss_index,
    build_store,
    chunk_documents,
    ensure_documents,
    generate_digest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CAM automation pipeline")
    parser.add_argument("--questions_file", type=Path, required=True, help="Input questions (one per line)")
    parser.add_argument("--download_dir", type=Path, default=Path("health_docs"))
    parser.add_argument("--store_dir", type=Path, default=Path("project_bundle") / "rag_store")
    parser.add_argument("--digest_path", type=Path, default=Path("project_bundle") / "regulatory_digest.md")
    parser.add_argument("--audit_log", type=Path, default=Path("project_bundle") / "cam_suite_audit.jsonl")
    parser.add_argument("--html_out", type=Path, default=Path("project_bundle") / "cam_suite_report.html")
    parser.add_argument("--json_out", type=Path, default=Path("project_bundle") / "cam_suite_report.json")
    parser.add_argument("--scenarios", default=None, help="Comma-separated scenario IDs (default: A-F)")
    parser.add_argument("--refresh-store", action="store_true", help="Rebuild FAISS index and chunks.json")
    parser.add_argument("--force-download", action="store_true", help="Re-download PDFs even if present")
    parser.add_argument("--summariser-model", default=None, help="Optional Ollama model for digest summaries")
    parser.add_argument("--embed-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--chunk-size-words", type=int, default=280)
    parser.add_argument("--overlap-words", type=int, default=60)
    parser.add_argument("--enable-med-judge", action="store_true", help="Include medgemma3-27B judge")
    parser.add_argument("--enable-gemini-judge", action="store_true", help="Include Gemini Flash judge")
    parser.add_argument("--no-judges", action="store_true", help="Skip all judge evaluations")
    parser.add_argument(
        "--skip-ollama-judge",
        action="store_true",
        help="Disable the primary judge LLM even if enable-med-judge is set",
    )
    parser.add_argument(
        "--judge-mode",
        choices=["ollama", "ollama_chat", "openai"],
        help="Override JUDGE_MODE for the judge backend",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip scenario runs after refreshing assets")
    return parser.parse_args()


def print_step(message: str) -> None:
    print(f"[pipeline] {message}")


def build_judge_manager(args: argparse.Namespace) -> Optional[JudgeManager]:
    if args.no_judges:
        print_step("Skipping judge evaluation (no-judges flag)")
        return None

    enable_med = args.enable_med_judge and not args.skip_ollama_judge
    if args.enable_med_judge and args.skip_ollama_judge:
        print_step("Skipping judge (--skip-ollama-judge)")

    judges = build_default_judges(
        enable_med_judge=enable_med,
        enable_gemini_judge=args.enable_gemini_judge,
    )
    if not judges:
        print_step("No judges enabled")
        return None

    return JudgeManager(judges, digest_path=args.digest_path)


def run_pipeline() -> None:
    args = parse_args()

    if args.judge_mode:
        os.environ["JUDGE_MODE"] = args.judge_mode
        print_step(f"Judge mode override: {args.judge_mode}")

    try:
        questions = [
            line.strip()
            for line in args.questions_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        print_step(f"ERROR: questions file not found at {args.questions_file}")
        sys.exit(1)

    if not questions:
        print_step("ERROR: no questions provided")
        sys.exit(1)

    print_step(f"Loaded {len(questions)} questions")
    print_step(f"Download directory: {args.download_dir}")
    print_step(f"RAG store directory: {args.store_dir}")

    try:
        ingestion = ensure_documents(args.download_dir, force=args.force_download)
    except Exception as exc:
        print_step(f"ERROR: failed to ensure documents: {exc}")
        sys.exit(1)

    if args.refresh_store:
        try:
            print_step("Chunking regulatory PDFs …")
            chunks = chunk_documents(
                ingestion.documents,
                chunk_size_words=args.chunk_size_words,
                overlap_words=args.overlap_words,
            )
            print_step(f"Built {len(chunks)} chunks; embedding with {args.embed_model}")
            index, _embeddings = build_faiss_index(chunks, embed_model=args.embed_model)
            build_store(args.store_dir, chunks, index)
        except Exception as exc:
            print_step(f"ERROR: failed to refresh RAG store: {exc}")
            sys.exit(1)
    else:
        print_step("Using existing RAG store (refresh-store flag not set)")

    try:
        if args.refresh_store or not args.digest_path.exists():
            print_step("Generating regulatory digest …")
            generate_digest(
                ingestion.documents,
                digest_path=args.digest_path,
                summariser_model=args.summariser_model,
            )
        else:
            print_step(f"Using existing digest at {args.digest_path}")
    except Exception as exc:
        print_step(f"ERROR: failed to generate digest: {exc}")
        sys.exit(1)

    if args.dry_run:
        print_step("Dry-run complete (skipping scenario evaluation)")
        return

    scenario_ids: Optional[List[str]] = (
        [token.strip() for token in args.scenarios.split(",") if token.strip()]
        if args.scenarios
        else None
    )

    judge_manager = build_judge_manager(args)

    try:
        runner = CAMSuiteRunner(
            store_dir=args.store_dir,
            questions=questions,
            audit_log_path=args.audit_log,
            scenario_ids=scenario_ids,
            judge_manager=judge_manager,
        )
        print_step("Executing scenarios …")
        results = runner.run()
        runner.write_outputs(results, html_path=args.html_out, json_path=args.json_out)
    except Exception as exc:
        print_step(f"ERROR: scenario execution failed: {exc}")
        sys.exit(1)

    print_step(f"Report written to {args.html_out}")
    print_step(f"JSON results written to {args.json_out}")
    print_step(f"Audit log appended at {args.audit_log}")
    if judge_manager and judge_manager.judges:
        judge_ids = ", ".join(judge.judge_id for judge in judge_manager.judges)
        print_step(f"Judges executed: {judge_ids}")


if __name__ == "__main__":
    run_pipeline()
