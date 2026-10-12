"""Command-line entry point.

Context: Wires corpus generation, benchmark, report and workflow export. |
Input: Command-line arguments and .env. |
Output: Files under data/, results/, n8n/ and samples/.

Usage:
    idp corpus --size 250 --seed 2026
    idp benchmark --systems all --concurrency 4
    idp report
    idp workflow
    idp samples
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from idp.benchmark import run_system
from idp.config import Settings
from idp.corpus import generate_corpus, load_corpus, write_corpus
from idp.errors import IdpError
from idp.report import jev_latencies, score_system, write_report
from idp.samples import SHOWCASE
from idp.systems import SYSTEMS, SYSTEMS_BY_KEY, Clients, SystemSpec
from idp.workflow import build_workflow

logger = logging.getLogger("idp")

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_RESULTS = Path("results")


def _select(names: str) -> list[SystemSpec]:
    if names == "all":
        return list(SYSTEMS)
    unknown = [n for n in names.split(",") if n not in SYSTEMS_BY_KEY]
    if unknown:
        raise IdpError(
            f"unknown systems: {', '.join(unknown)}; choose from {', '.join(SYSTEMS_BY_KEY)}"
        )
    return [SYSTEMS_BY_KEY[n] for n in names.split(",")]


def cmd_corpus(args: argparse.Namespace) -> None:
    """Generate and store the labeled corpus."""
    documents = generate_corpus(args.size, args.seed)
    write_corpus(documents, args.out)
    print(f"{len(documents)} documents written to {args.out}")


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Answer the corpus with every selected system."""
    corpus = list(load_corpus(args.corpus))
    if args.limit:
        corpus = corpus[: args.limit]
    clients = Clients(Settings())
    try:
        for spec in _select(args.systems):
            path = run_system(
                spec, corpus, clients, args.results / "raw", concurrency=args.concurrency
            )
            print(f"{spec.key}: answers in {path}")
    finally:
        clients.close()


def cmd_report(args: argparse.Namespace) -> None:
    """Score stored answers and write the comparison tables."""
    corpus = list(load_corpus(args.corpus))
    raw = args.results / "raw"
    metrics = [
        score_system(spec, corpus, raw)
        for spec in _select(args.systems)
        if (raw / f"{spec.key}.jsonl").exists()
    ]
    write_report(metrics, jev_latencies(raw), args.results)
    print((args.results / "benchmark.md").read_text(encoding="utf-8"))


def cmd_workflow(args: argparse.Namespace) -> None:
    """Export the n8n workflow."""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(build_workflow(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"workflow written to {args.out}")


def cmd_samples(args: argparse.Namespace) -> None:
    """Write the three showcase documents as text files."""
    args.out.mkdir(parents=True, exist_ok=True)
    for key, (_, text) in SHOWCASE.items():
        (args.out / f"{key}.txt").write_text(text, encoding="utf-8")
    print(f"{len(SHOWCASE)} samples written to {args.out}")


def build_parser() -> argparse.ArgumentParser:
    """Command-line interface definition."""
    parser = argparse.ArgumentParser(prog="idp", description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    corpus = sub.add_parser("corpus", help="generate the labeled corpus")
    corpus.add_argument("--size", type=int, default=250)
    corpus.add_argument("--seed", type=int, default=2026)
    corpus.add_argument("--out", type=Path, default=DEFAULT_CORPUS)
    corpus.set_defaults(func=cmd_corpus)

    bench = sub.add_parser("benchmark", help="run systems over the corpus")
    bench.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    bench.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    bench.add_argument("--systems", default="all", help="comma-separated keys or 'all'")
    bench.add_argument("--concurrency", type=int, default=4)
    bench.add_argument("--limit", type=int, default=0, help="only the first N documents")
    bench.set_defaults(func=cmd_benchmark)

    report = sub.add_parser("report", help="score answers and write tables")
    report.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    report.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    report.add_argument("--systems", default="all")
    report.set_defaults(func=cmd_report)

    workflow = sub.add_parser("workflow", help="export the n8n workflow")
    workflow.add_argument("--out", type=Path, default=Path("n8n/invoice_pipeline.workflow.json"))
    workflow.set_defaults(func=cmd_workflow)

    samples = sub.add_parser("samples", help="write the showcase documents")
    samples.add_argument("--out", type=Path, default=Path("samples"))
    samples.set_defaults(func=cmd_samples)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        args.func(args)
    except IdpError as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
