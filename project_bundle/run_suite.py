"""
CLI wrapper to execute CAM scenario evaluations.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cam_agent.evaluation.judges import JudgeManager, build_default_judges
from cam_agent.evaluation.runner import CAMSuiteRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CAM evaluation scenarios.")
    parser.add_argument("--store_dir", type=Path, default=Path("project_bundle") / "rag_store")
    parser.add_argument("--questions_file", type=Path, required=True)
    parser.add_argument(
        "--scenarios",
        default=None,
        help="Comma-separated list of scenario IDs to run (default: all A–F).",
    )
    parser.add_argument("--audit_log", type=Path, default=Path("project_bundle") / "cam_suite_audit.jsonl")
    parser.add_argument("--html_out", type=Path, default=Path("project_bundle") / "cam_suite_report.html")
    parser.add_argument("--json_out", type=Path, default=Path("project_bundle") / "cam_suite_report.json")
    parser.add_argument("--digest_path", type=Path, default=Path("project_bundle") / "regulatory_digest.md")
    parser.add_argument("--enable_med_judge", action="store_true", help="Include medgemma3-27B judge")
    parser.add_argument("--enable_gemini_judge", action="store_true", help="Include Gemini Flash judge")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    questions = [
        line.strip()
        for line in args.questions_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    scenario_ids = (
        [token.strip() for token in args.scenarios.split(",") if token.strip()]
        if args.scenarios
        else None
    )

    judges = build_default_judges(
        enable_med_judge=args.enable_med_judge,
        enable_gemini_judge=args.enable_gemini_judge,
    )
    judge_manager = JudgeManager(judges, digest_path=args.digest_path) if judges else None

    runner = CAMSuiteRunner(
        store_dir=args.store_dir,
        questions=questions,
        audit_log_path=args.audit_log,
        scenario_ids=scenario_ids,
        judge_manager=judge_manager,
    )

    results = runner.run()
    runner.write_outputs(results, html_path=args.html_out, json_path=args.json_out)

    print(f"[suite] Report written to {args.html_out}")
    print(f"[suite] JSON results written to {args.json_out}")
    print(f"[suite] Audit log appended at {args.audit_log}")
    if judge_manager:
        judge_ids = ", ".join(judge.judge_id for judge in judge_manager.judges)
        print(f"[suite] Judges executed: {judge_ids}")


if __name__ == "__main__":
    main()
