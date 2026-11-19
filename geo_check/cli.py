"""CLI: python -m geo_check --prompts prompts.yaml --brand toolenix.com
       python -m geo_check --audit https://example.com
       python -m geo_check --prompts prompts.yaml --sample
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, audit as audit_mod, engine, prompts as prompts_mod
from . import report as report_mod, store

SAMPLE_ANSWERS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data", "sample_answers.json")


def load_sample_answers() -> dict[str, str]:
    try:
        with open(SAMPLE_ANSWERS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"error: cannot load sample answers: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="geo_check",
        description="Free GEO visibility checker — track brand mentions in "
                    "AI answers (Gemini free tier) and audit pages for "
                    "citation-readiness.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--prompts", help="prompts.yaml file (brand + 1-50 prompts)")
    p.add_argument("--brand", help="brand/site to track (overrides prompts file)")
    p.add_argument("--out", default="report",
                   help="output directory for the report (default: report)")
    p.add_argument("--db", default="geo_visibility.db",
                   help="SQLite database path (default: geo_visibility.db)")
    p.add_argument("--audit", metavar="URL",
                   help="audit one URL for citation-readiness instead of running prompts")
    p.add_argument("--sample", action="store_true",
                   help="sample mode: use bundled sample answers, no API key needed")
    p.add_argument("--model", default=os.environ.get("GEMINI_MODEL", engine.DEFAULT_MODEL),
                   help=f"Gemini model (default: {engine.DEFAULT_MODEL})")
    p.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY", ""),
                   help="Gemini API key (or set GEMINI_API_KEY)")
    p.add_argument("--no-store", action="store_true",
                   help="do not save this run to the SQLite database")
    return p


def run_prompts(args: argparse.Namespace) -> int:
    if not args.prompts:
        print("error: --prompts is required (or use --audit URL)",
              file=sys.stderr)
        return 2
    try:
        data = prompts_mod.load_prompts(args.prompts)
    except prompts_mod.PromptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    brand = args.brand or data["brand"]
    if not brand:
        print("error: no brand — pass --brand or set 'brand:' in the prompts file",
              file=sys.stderr)
        return 2
    variants = prompts_mod.brand_variants(brand)
    mode = "sample"
    results: list[dict] = []
    if args.sample:
        answers = load_sample_answers()
        print(f"sample mode: using bundled sample answers for "
              f"{len(data['prompts'])} prompts (NOT live measurements)")
        for prompt in data["prompts"]:
            answer = answers.get(prompt, answers.get("__default__", ""))
            results.append(engine.analyse_answer(prompt, answer, variants))
    else:
        if not args.api_key:
            print("error: no Gemini API key — set GEMINI_API_KEY, pass "
                  "--api-key, or re-run with --sample to preview the report "
                  "format", file=sys.stderr)
            return 1
        mode = "live"
        for i, prompt in enumerate(data["prompts"], 1):
            print(f"[{i}/{len(data['prompts'])}] {prompt}")
            try:
                answer = engine.ask(prompt, args.api_key, model=args.model)
            except engine.EngineError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            results.append(engine.analyse_answer(prompt, answer, variants))

    os.makedirs(args.out, exist_ok=True)
    conn = store.connect(args.db)
    run_id = None
    if not args.no_store:
        run_id = store.save_run(conn, brand, "gemini", args.model, mode, results)
    history = store.run_history(conn, brand)
    conn.close()

    csv_path = os.path.join(args.out, "results.csv")
    md_path = os.path.join(args.out, "report.md")
    chart_path = os.path.join(args.out, "trend.png")
    report_mod.write_csv(results, csv_path)
    report_mod.write_markdown(brand, "gemini", args.model, mode, results,
                              history, None, md_path)
    report_mod.write_chart(results, history, chart_path)
    mentioned = sum(1 for r in results if r["mentioned"])
    rate = round(100.0 * mentioned / len(results), 1) if results else 0.0
    print(f"\nDone — {brand}: mentioned in {mentioned}/{len(results)} prompts "
          f"({rate}%) [{mode}]" + (f" · run #{run_id}" if run_id else ""))
    print(f"  report:  {md_path}\n  csv:     {csv_path}\n  chart:   {chart_path}")
    print(f"  db:      {args.db}")
    return 0


def run_audit(args: argparse.Namespace) -> int:
    print(f"auditing {args.audit} ...")
    result = audit_mod.audit_url(args.audit)
    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, "audit.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(audit_mod.audit_markdown(result))
    print(f"\n{result['url']}: {result['score']}/{result['max_score']} — "
          f"{result['grade']}")
    for c in result["checks"]:
        mark = "✅" if c["passed"] else "❌"
        print(f"  {mark} {c['label']} ({c['weight']} pts) — {c['detail']}")
    print(f"  report: {md_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.audit:
        return run_audit(args)
    return run_prompts(args)


if __name__ == "__main__":
    raise SystemExit(main())
