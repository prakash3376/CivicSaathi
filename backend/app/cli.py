"""Command-line tools for the document index.

    python -m app.cli sources               list the curated sources and what is indexed
    python -m app.cli verify [ID ...]       download and check sources (indexes nothing)
    python -m app.cli ingest [ID ...]       verify, chunk, embed and index sources
    python -m app.cli search "question"     find the passages closest in meaning to a question
    python -m app.cli ask "question"        answer a question from the documents, with citations
    python -m app.cli assistant-check       check the index, the API key and the language model
    python -m app.cli schemes               list the schemes, their courses or groups and rules
    python -m app.cli schemes-check         check every rule's quote against the indexed documents
    python -m app.cli fetch-text ID ...     download sources and save their text (indexes nothing)
    python -m app.cli catalogue             the programmes and budget records, by sector
    python -m app.cli catalogue-check       check every catalogue and budget quote in the documents
    python -m app.cli eval                  run the benchmark: retrieval, and with --answer, answers
    python -m app.cli kb-health             records, documents and passages per sector
    python -m app.cli index-check           read-only: do index, records and registry agree?
    python -m app.cli index-backups         list the snapshots of the index taken before rebuilds
    python -m app.cli index-restore [NAME]  put a snapshot back (the newest by default)

Exit status: 0 on success, 1 if any source was rejected (or a question could not be answered, or a
check failed), 2 if something went wrong with the tools themselves (for example the embedding
model could not be downloaded), 3 if another ingestion is already running.
"""

import argparse
import os
import sys
import textwrap
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from app.core.config import BUDGET_DIR, CATALOGUE_DIR, SOURCES_DIR, Settings, get_settings
from app.core.logging_config import configure_logging
from app.domain.assistant import Answer, Passage
from app.domain.catalogue import BudgetRecord, Entry
from app.domain.documents import VerificationCheck, VerificationReport
from app.domain.eligibility import SECTORS
from app.domain.errors import AssistantError, IndexingError, IngestionError, SchemeDataError
from app.domain.sources import SourceSpec
from app.services.assistant.factory import build_model, build_runtime
from app.services.assistant.selfcheck import probe
from app.services.catalogue.consistency import check_consistency
from app.services.catalogue.loader import load_budget, load_catalogue
from app.services.catalogue.verify import all_labelled, check_cites
from app.services.eligibility.loader import SchemeBook, load_schemes
from app.services.eligibility.verify import all_evidence, check_evidence
from app.services.ingestion.backup import list_snapshots, restore_snapshot, snapshot_index
from app.services.ingestion.fetcher import Fetcher
from app.services.ingestion.jobs import Job, JobLog, ingest_with_retry
from app.services.ingestion.lock import IngestBusyError, IngestLock
from app.services.ingestion.pipeline import IngestionPipeline, IngestResult
from app.services.ingestion.reconcile import reconcile
from app.services.ingestion.registry import load_registry, select_sources
from app.services.ingestion.storage import ArtifactStore
from app.services.ingestion.verifier import SourceVerifier
from app.services.retrieval.embedder import OnnxE5Embedder
from app.services.retrieval.store import VectorStore

_MARKS = {"pass": "[ ok ]", "warn": "[warn]", "fail": "[FAIL]"}
_SNIPPET_CHARS = 320


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_output()
    args = _parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")  # no usage pings when fetching models
    try:
        return int(args.handler(args, settings))
    except IngestBusyError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 3
    except (IngestionError, AssistantError, SchemeDataError) as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Official-source ingestion tools."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sources = commands.add_parser("sources", help="list curated sources and what is indexed")
    sources.set_defaults(handler=_sources)

    verify = commands.add_parser("verify", help="download and check sources; indexes nothing")
    verify.add_argument("ids", nargs="*", metavar="ID", help="source ids (default: all)")
    verify.set_defaults(handler=_verify)

    ingest = commands.add_parser("ingest", help="verify, chunk, embed and index sources")
    ingest.add_argument("ids", nargs="*", metavar="ID", help="source ids (default: all)")
    ingest.add_argument("--force", action="store_true", help="re-process even if nothing changed")
    ingest.add_argument(
        "--rebuild",
        action="store_true",
        help="discard the index first (needed after changing EMBEDDING_MODEL)",
    )
    ingest.set_defaults(handler=_ingest)

    commands.add_parser(
        "index-check", help="read-only: do the index, the records and the registry agree?"
    ).set_defaults(handler=_index_check)
    commands.add_parser(
        "index-backups", help="list the snapshots of the index taken before rebuilds"
    ).set_defaults(handler=_index_backups)
    restore = commands.add_parser(
        "index-restore", help="put a snapshot of the index back (stop the API first)"
    )
    restore.add_argument("name", nargs="?", help="snapshot name (default: the newest)")
    restore.set_defaults(handler=_index_restore)

    search = commands.add_parser(
        "search", help="find passages by meaning, in any supported language"
    )
    search.add_argument("question")
    search.add_argument("-k", "--top", type=int, default=5, help="how many passages (default 5)")
    search.add_argument("--source", metavar="ID", help="only search one source")
    search.set_defaults(handler=_search)

    ask = commands.add_parser("ask", help="answer a question from the documents, with citations")
    ask.add_argument("question")
    ask.add_argument(
        "--language",
        choices=("auto", "en", "bn", "hi"),
        default="auto",
        help="language of the answer",
    )
    ask.add_argument(
        "--source", action="append", metavar="ID", help="only answer from this source (repeatable)"
    )
    ask.set_defaults(handler=_ask)

    check = commands.add_parser(
        "assistant-check", help="check the index, the API key and the language model"
    )
    check.set_defaults(handler=_assistant_check)

    schemes = commands.add_parser("schemes", help="list the schemes and their rules")
    schemes.set_defaults(handler=_schemes)

    verify_rules = commands.add_parser(
        "schemes-check", help="check every rule's quote against the indexed documents"
    )
    verify_rules.set_defaults(handler=_schemes_check)

    fetch = commands.add_parser(
        "fetch-text", help="download sources and save their text for checking quotes"
    )
    fetch.add_argument("ids", nargs="*", metavar="ID", help="source ids (default: all)")
    fetch.add_argument(
        "--registry", type=Path, default=SOURCES_DIR, help="a registry file or folder"
    )
    fetch.add_argument("--out", type=Path, help="where to write <id>.txt (default: storage/text)")
    fetch.set_defaults(handler=_fetch_text)

    report = commands.add_parser("catalogue", help="the programmes and budget records, by sector")
    report.set_defaults(handler=_catalogue)

    check_catalogue = commands.add_parser(
        "catalogue-check", help="check every catalogue and budget quote against the documents"
    )
    check_catalogue.add_argument("--registry", type=Path, default=SOURCES_DIR)
    check_catalogue.add_argument("--catalogue", type=Path, default=CATALOGUE_DIR)
    check_catalogue.add_argument("--budget", type=Path, default=BUDGET_DIR)
    check_catalogue.add_argument(
        "--texts", type=Path, help="a folder of <id>.txt from fetch-text (default: the index)"
    )
    check_catalogue.set_defaults(handler=_catalogue_check)

    evaluate = commands.add_parser(
        "eval", help="run the benchmark: does retrieval find the evidence, do answers rest on it"
    )
    evaluate.add_argument("--strategy", choices=("dense", "knowledge"), default="knowledge")
    evaluate.add_argument("-k", type=int, default=5, help="passages that count (default 5)")
    evaluate.add_argument("--group", help="only this group (colloquial, numeric, ...)")
    evaluate.add_argument("--sector", help="only this sector")
    evaluate.add_argument("--language", choices=("en", "hi", "bn"))
    evaluate.add_argument("--origin", choices=("handwritten", "derived"))
    evaluate.add_argument("--answer", action="store_true", help="also ask the model (costs calls)")
    evaluate.add_argument("--limit", type=int, help="at most this many cases for --answer")
    evaluate.add_argument("--ids", help="only these case ids, comma separated (for --answer)")
    evaluate.add_argument("--pause", type=float, default=3.0, help="seconds between model calls")
    evaluate.add_argument("--compare", type=Path, help="a earlier report to compare with")
    evaluate.add_argument(
        "--features",
        help="of history,router,keywords,sector,diverse (default: history,router,sector)",
    )
    evaluate.add_argument(
        "--hint",
        choices=("none", "right", "wrong"),
        default="none",
        help="tell the search the sector of each question (right), another one (wrong), or none",
    )
    evaluate.set_defaults(handler=_eval)

    health = commands.add_parser("kb-health", help="records, documents and passages per sector")
    health.set_defaults(handler=_kb_health)
    return parser


def _sources(_args: argparse.Namespace, settings: Settings) -> int:
    counts = _open_store(settings).counts()
    row = "{:<36} {:<12} {:<6} {:>8}  {}"
    print(row.format("ID", "TYPE", "FORMAT", "PASSAGES", "TITLE"))
    for spec in load_registry():
        print(row.format(spec.id, spec.doc_type, spec.format, counts.get(spec.id, 0), spec.title))
    return 0


def _verify(args: argparse.Namespace, settings: Settings) -> int:
    verifier = _verifier(settings)
    rejected = 0
    for spec in select_sources(load_registry(), args.ids):
        result = verifier.verify(spec)
        _print_report(result.report)
        if result.fetched and result.document:
            print(
                f"      {result.fetched.size_bytes:,} bytes, sha256 {result.fetched.sha256[:12]}; "
                f"{len(result.document.text):,} characters in {len(result.document.blocks)} blocks "
                f"({result.document.extractor})"
            )
        rejected += result.report.status == "rejected"
        print()
    return 1 if rejected else 0


def _ingest(args: argparse.Namespace, settings: Settings) -> int:
    specs = select_sources(load_registry(), args.ids)
    artifacts = ArtifactStore(settings.data_dir)
    # One ingestion at a time: two writing the same index at once damaged it once.
    with IngestLock(settings.data_dir / "jobs" / "ingest.lock"):
        if args.rebuild:
            # A rebuild empties the index first. If the sources then fail to download, the visitors
            # would have nothing to search: so keep a copy that has been read back, and say how to
            # return to it.
            try:
                saved = snapshot_index(
                    artifacts.chroma_dir,
                    settings.data_dir / "backups",
                    embedding_model=settings.embedding_model,
                )
            except IndexingError as error:
                print(f"Not rebuilding: {error.message}", file=sys.stderr)
                return 2
            if saved is not None:
                print(f"Backed up the current index as {saved.name} (checked by reading it back).")
        store = VectorStore(
            artifacts.chroma_dir, embedding_model=settings.embedding_model, rebuild=args.rebuild
        )
        pipeline = IngestionPipeline(
            verifier=_verifier(settings),
            embedder=OnnxE5Embedder(settings.embedding_model, artifacts.models_dir),
            store=store,
            artifacts=artifacts,
        )
        log = JobLog(settings.data_dir / "jobs" / "ingest.json")
        results = []
        try:
            for spec in specs:
                log.update(Job(spec.id, "running"))
                results.append(
                    ingest_with_retry(lambda s: pipeline.ingest(s, force=args.force), spec, log=log)
                )
            log.finish()
        finally:
            store.close()  # an open index cannot be moved or restored while this process holds it
    for spec, result in zip(specs, results, strict=True):
        _print_result(spec, result)
    indexed = sum(result.outcome == "indexed" for result in results)
    unchanged = sum(result.outcome == "unchanged" for result in results)
    rejected = sum(result.outcome == "rejected" for result in results)
    print(f"{indexed} indexed, {unchanged} unchanged, {rejected} rejected.")
    if args.rebuild and rejected:
        print(
            "The rebuilt index is missing the rejected sources. To go back to the index from "
            "before the rebuild: stop the API, then run  python -m app.cli index-restore",
            file=sys.stderr,
        )
    return 1 if rejected else 0


def _index_check(_args: argparse.Namespace, settings: Settings) -> int:
    artifacts = ArtifactStore(settings.data_dir)
    store = _open_store(settings)
    try:
        indexed = store.counts()
    finally:
        store.close()
    findings = reconcile(
        registered={spec.id for spec in load_registry()}, indexed=indexed, artifacts=artifacts
    )
    for finding in findings:
        print(finding)
    errors = sum(finding.severity == "error" for finding in findings)
    print(
        f"{sum(indexed.values())} passages in {len(indexed)} sources; {errors} errors, "
        f"{len(findings) - errors} warnings. Nothing was changed."
    )
    return 1 if errors else 0


def _index_backups(args: argparse.Namespace, settings: Settings) -> int:
    snapshots = list_snapshots(settings.data_dir / "backups")
    if not snapshots:
        print("No snapshots yet: one is taken at the start of every `ingest --rebuild`.")
        return 0
    for path in snapshots:
        print(path.name)
    return 0


def _index_restore(args: argparse.Namespace, settings: Settings) -> int:
    backups = settings.data_dir / "backups"
    snapshots = list_snapshots(backups)
    if args.name:
        chosen = backups / args.name
    elif snapshots:
        chosen = snapshots[-1]
    else:
        print("There is no snapshot to restore.", file=sys.stderr)
        return 1
    with IngestLock(settings.data_dir / "jobs" / "ingest.lock"):
        replaced = restore_snapshot(
            chosen,
            ArtifactStore(settings.data_dir).chroma_dir,
            embedding_model=settings.embedding_model,
        )
    print(f"Restored {chosen.name}.")
    if replaced is not None:
        print(
            f"The index it replaced was kept as {replaced.name} "
            "(safe to delete once you have checked)."
        )
    return 0


def _search(args: argparse.Namespace, settings: Settings) -> int:
    artifacts = ArtifactStore(settings.data_dir)
    store = _open_store(settings)
    if not store.counts():
        print("The index is empty. Run: python -m app.cli ingest", file=sys.stderr)
        return 1
    embedder = OnnxE5Embedder(settings.embedding_model, artifacts.models_dir)
    hits = store.search(
        embedder.embed_query(args.question),
        k=args.top,
        source_ids=[args.source] if args.source else None,
    )
    for rank, hit in enumerate(hits, start=1):
        meta = hit.metadata
        pages = f"page {meta['page_start']}" if meta["page_start"] else "web page"
        where = " | ".join(
            part
            for part in (
                pages,
                str(meta["section"]),
                f"clause {meta['clause']}" if meta["clause"] else "",
            )
            if part
        )
        print(f"{rank}. [{hit.score:.3f}] {meta['title']}")
        print(f"   {where}")
        print(f"   {meta['verification']} | {meta['source_id']} | {meta['url']}")
        snippet = " ".join(hit.text.split())
        if len(snippet) > _SNIPPET_CHARS:
            snippet = snippet[:_SNIPPET_CHARS].rstrip() + "..."
        print(textwrap.indent(textwrap.fill(snippet, width=100), "   > "))
        print()
    return 0


def _scheme_book() -> SchemeBook:
    return load_schemes(sources={spec.id: spec.url for spec in load_registry()})


def _schemes(_args: argparse.Namespace, _settings: Settings) -> int:
    book = _scheme_book()
    for scheme in book.schemes:
        print(f"{scheme.id}: {scheme.name} ({scheme.level})")
        for track in scheme.tracks:
            rules = book.criteria(scheme, track)
            questions = book.questions(scheme, track)
            print(f"    {track.id:<10} {len(rules)} rules, {len(questions)} questions")
    return 0


def _schemes_check(_args: argparse.Namespace, settings: Settings) -> int:
    """The rules are loaded (their figures match their quotes); now check the quotes themselves."""
    book = _scheme_book()
    artifacts = ArtifactStore(settings.data_dir)

    def text_of(source_id: str) -> str | None:
        record = artifacts.load_record(source_id)
        return record.document.text if record else None

    problems = check_evidence(book, text_of)
    quotes = sum(1 for scheme in book.schemes for _ in all_evidence(scheme))
    for problem in problems:
        print(f"[FAIL] {problem}")
    print(f"{len(book.schemes)} schemes, {quotes} quotes checked, {len(problems)} problems.")
    return 1 if problems else 0


def _fetch_text(args: argparse.Namespace, settings: Settings) -> int:
    """Run the same checks as ``verify`` and keep the text, so that quotes can be checked offline.

    ``<id>.txt`` is exactly the text the index would hold (a quote must be a slice of it);
    ``<id>.pages.txt`` is the same text with the page of each block, for finding "page 4".
    """
    out = args.out or settings.data_dir / "text"
    out.mkdir(parents=True, exist_ok=True)
    verifier = _verifier(settings)
    rejected = 0
    for spec in select_sources(load_registry(args.registry), args.ids):
        result = verifier.verify(spec)
        _print_report(result.report)
        rejected += result.report.status == "rejected"
        if result.report.status != "rejected" and result.document:
            (out / f"{spec.id}.txt").write_text(result.document.text, encoding="utf-8")
            pages = "\n\n".join(
                f"[page {block.page}] {block.text}" if block.page else block.text
                for block in result.document.blocks
            )
            (out / f"{spec.id}.pages.txt").write_text(pages, encoding="utf-8")
            saved = out / f"{spec.id}.txt"
            print(f"      saved {len(result.document.text):,} characters to {saved}")
        print()
    return 1 if rejected else 0


def _data(registry: Path, catalogue: Path, budget: Path) -> tuple[list[Entry], list[BudgetRecord]]:
    urls = {spec.id: spec.url for spec in load_registry(registry)}
    entries = load_catalogue(catalogue, sources=urls) if catalogue.exists() else []
    records = load_budget(budget, sources=urls) if budget.exists() else []
    return entries, records


def _catalogue(_args: argparse.Namespace, _settings: Settings) -> int:
    """How many records each sector has, counted from the data (not written down anywhere)."""
    entries, records = _data(SOURCES_DIR, CATALOGUE_DIR, BUDGET_DIR)
    book = _scheme_book()
    row = "{:<18} {:>8} {:>7} {:>9}  {}"
    print(row.format("SECTOR", "SCHEMES", "BUDGET", "RECORDS", "STATUS"))
    for sector in SECTORS:
        schemes = sum(sector in scheme.sectors for scheme in book.schemes)
        programmes = sum(sector in entry.sectors for entry in entries)
        # The Budget sector lists every record, including taxation and whole-budget ones.
        budget = len(records) if sector == "budget" else sum(r.sector == sector for r in records)
        total = schemes + programmes + budget
        status = "populated" if total else "EMPTY"
        print(row.format(sector, schemes + programmes, budget, total, status))
    print(
        f"\n{len(book.schemes)} schemes with a check, {len(entries)} programmes and services, "
        f"{len(records)} budget records."
    )
    return 0


def _catalogue_check(args: argparse.Namespace, settings: Settings) -> int:
    entries, records = _data(args.registry, args.catalogue, args.budget)
    artifacts = ArtifactStore(settings.data_dir)

    def text_of(source_id: str) -> str | None:
        if args.texts:
            path = args.texts / f"{source_id}.txt"
            return path.read_text(encoding="utf-8") if path.exists() else None
        record = artifacts.load_record(source_id)
        return record.document.text if record else None

    labelled = all_labelled(entries, records)
    problems = check_cites(labelled, text_of)
    for problem in problems:
        print(f"[FAIL] {problem}")
    # Records are also read against each other: duplicates, figures that disagree, impossible dates.
    findings = check_consistency(entries, records, today=date.today())
    for finding in findings:
        print(finding)
    errors = [finding for finding in findings if finding.severity == "error"]
    print(
        f"{len(entries)} programmes, {len(records)} budget records, "
        f"{len(labelled)} quotes checked, {len(problems)} problems; "
        f"{len(findings)} consistency findings."
    )
    return 1 if problems or errors else 0


def _eval(args: argparse.Namespace, settings: Settings) -> int:
    import json

    from app.services.assistant.search import DEFAULT_FEATURES, KnowledgeSearch
    from app.services.evaluation.cases import Case, load_cases
    from app.services.evaluation.runner import (
        details_of,
        evaluate_answers,
        evaluate_retrieval,
        summarise_answers,
        summarise_retrieval,
        write_report,
    )

    entries, records = _data(SOURCES_DIR, CATALOGUE_DIR, BUDGET_DIR)
    cases: list[Case] = load_cases(entries, records, SOURCES_DIR.parent / "eval")
    for key in ("group", "sector", "language", "origin"):
        wanted = getattr(args, key)
        if wanted:
            cases = [c for c in cases if wanted in (getattr(c, key), c.extras.get("kind"))]
    if not cases:
        print("No benchmark case matches.", file=sys.stderr)
        return 1

    artifacts = ArtifactStore(settings.data_dir)
    store = _open_store(settings)
    embedder = OnnxE5Embedder(settings.embedding_model, artifacts.models_dir)
    search = KnowledgeSearch(store, embedder, entries=entries, records=records)

    features = (
        frozenset(part for part in args.features.split(",") if part)
        if args.features is not None
        else DEFAULT_FEATURES
    )

    def find(case: Case) -> list[Passage]:
        if args.strategy == "dense":
            return search.dense(case.question)
        sector = None
        if args.hint == "right":
            sector = case.sector
        elif args.hint == "wrong":  # a sector the question is not about: must not hide the answer
            sector = "transport" if case.sector != "transport" else "education"
        return search.search(
            case.question, history=case.history, sector=sector, features=features
        ).passages

    retrieval = evaluate_retrieval(cases, find)
    summary = summarise_retrieval(retrieval, args.k)
    answers: list = []  # type: ignore[type-arg]
    answer_summary = None
    if args.answer:
        runtime = build_runtime(settings)
        pool = [c for c in cases if c.origin == "handwritten"]
        if args.ids:
            wanted = set(args.ids.split(","))
            pool = [c for c in pool if c.id in wanted]
        pool = pool[: args.limit]

        def ask(case: Case) -> Answer:
            return runtime.service.ask(
                case.question, language=case.language, history=list(case.history)
            )

        answers = evaluate_answers(pool, ask, pause=args.pause)
        answer_summary = summarise_answers(answers)

    path = write_report(
        settings.data_dir / "eval",
        strategy=args.strategy,
        retrieval=summary,
        answers=answer_summary,
        details=details_of(retrieval, answers),
    )
    _print_eval(summary, answer_summary, args.k)
    if args.compare and args.compare.exists():
        before = json.loads(args.compare.read_text(encoding="utf-8"))["retrieval"]["overall"]
        print("\nagainst", args.compare.name)
        for key, value in summary["overall"].items():
            print(f"  {key:<18} {before.get(key)} -> {value}")
    print(f"\nreport: {path}")
    return 0


def _kb_health(_args: argparse.Namespace, settings: Settings) -> int:
    """The knowledge base sector by sector, counted from the data and the index."""
    from app.services.admin.knowledge import build_report, latest_evaluations
    from app.services.assistant.catalog import SourceCatalog

    entries, records = _data(SOURCES_DIR, CATALOGUE_DIR, BUDGET_DIR)
    specs = load_registry()
    catalog = SourceCatalog(_open_store(settings), specs)
    report = build_report(
        schemes=_scheme_book().schemes,
        entries=entries,
        records=records,
        specs=specs,
        indexed=catalog.sources(),
        stats={},
        provider={
            "configured": settings.gemini_api_key is not None,
            "model": settings.gemini_model,
        },
        evaluations=latest_evaluations(settings.data_dir / "eval"),
    )
    row = "{:<16} {:<11} {:>7} {:>10} {:>7} {:>9} {:>8} {:>6} {:>5}"
    print(
        row.format(
            "SECTOR",
            "STATUS",
            "SCHEMES",
            "PROGRAMMES",
            "BUDGET",
            "DOCUMENTS",
            "PASSAGES",
            "STALE",
            "DUE",
        )
    )
    for sector in report["sectors"]:
        print(
            row.format(
                sector["sector"],
                sector["status"],
                sector["schemes"],
                sector["programmes"],
                sector["budget_records"],
                f"{sector['indexed_sources']}/{sector['sources']}",
                sector["passages"],
                sector["stale_sources"],
                sector["due_sources"],
            )
        )
    totals = report["totals"]
    print(
        f"\n{totals['indexed_sources']} of {totals['registered_sources']} documents indexed, "
        f"{totals['passages']} passages; last verified {totals['last_verified_at']}."
    )
    if report["failed_ingestion"]:
        print("not indexed:", ", ".join(report["failed_ingestion"]))
    return 1 if report["failed_ingestion"] else 0


def _print_eval(summary: dict, answers: dict | None, k: int) -> None:  # type: ignore[type-arg]
    row = "  {:<18} {:>6} {:>12} {:>12} {:>7}"
    for title, key in (
        ("overall", None),
        ("by group", "by_group"),
        ("by sector", "by_sector"),
        ("by language", "by_language"),
        ("by origin", "by_origin"),
    ):
        print(f"\n{title}")
        print(row.format("", "cases", f"source@{k}", f"evidence@{k}", "mrr"))
        blocks = {"overall": summary["overall"]} if key is None else summary[key]
        for name, block in blocks.items():
            shown = (
                block["cases"],
                block[f"source_recall@{k}"],
                block[f"evidence_hit@{k}"],
                block["mrr"],
            )
            # A group with nothing to score (the questions that must not be answered) has no rate.
            print(row.format(name, *("-" if value is None else str(value) for value in shown)))
    print(f"\nintent accuracy {summary['intent_accuracy']} on {summary['intent_cases']} labelled")
    print(f"retrieval latency {summary['latency_ms']}")
    if answers:
        print("\nanswers", answers)


def _ask(args: argparse.Namespace, settings: Settings) -> int:
    answer = build_runtime(settings).service.ask(
        args.question, language=args.language, source_ids=args.source
    )
    _print_answer(answer)
    return 0 if answer.answerable else 1


def _assistant_check(_args: argparse.Namespace, settings: Settings) -> int:
    """Each thing the assistant needs, with what to do if it is missing."""
    failed = 0

    def report(passed: bool, name: str, detail: str) -> None:
        nonlocal failed
        failed += not passed
        _print_check(
            VerificationCheck(name=name, status="pass" if passed else "fail", detail=detail)
        )

    counts = _open_store(settings).counts()
    report(
        bool(counts),
        "index",
        f"{sum(counts.values())} passages from {len(counts)} sources."
        if counts
        else "The index is empty. Run: python -m app.cli ingest",
    )
    model = build_model(settings)
    report(
        model is not None,
        "api key",
        f"GEMINI_API_KEY is set; asking {settings.gemini_model}."
        if model is not None
        else "GEMINI_API_KEY is not set. Put it in backend/.env (see backend/.env.example).",
    )
    if model is not None:
        for language in ("en", "bn", "hi"):
            result = probe(model, language)
            report(result.ok, f"model ({language})", result.detail)
    return 1 if failed else 0


def _print_answer(answer: Answer) -> None:
    """The answer as plain text: claims with their citation numbers, then the sources."""

    def paragraph(text: str, *, bullet: str = "") -> None:
        print(textwrap.fill(bullet + text, width=100, subsequent_indent=" " * len(bullet)))

    if answer.answerable:
        for claim in answer.claims:
            numbers = "".join(f" [{number}]" for number in claim.citations)
            paragraph(f"{claim.text}{numbers}", bullet="- ")
    else:
        paragraph(answer.text)
    if answer.not_stated:
        print("\nThe documents do not say:")
        for item in answer.not_stated:
            paragraph(item, bullet="- ")
    if answer.citations:
        print("\nSources:")
    for citation in answer.citations:
        where = " | ".join(
            part
            for part in (
                f"page {citation.page_start}" if citation.page_start else "web page",
                citation.section,
                f"clause {citation.clause}" if citation.clause else "",
            )
            if part
        )
        print(f"[{citation.number}] {citation.title} ({where})")
        quote = " ".join(citation.quote.split())
        print(textwrap.indent(textwrap.fill(f'"{quote}"', width=94), "      "))
        dated = citation.document_date.isoformat() if citation.document_date else "date unknown"
        checked = citation.verified_at.date().isoformat() if citation.verified_at else "never"
        print(f"      dated {dated}; verified {checked} ({citation.verification}); {citation.url}")
    if answer.warnings:
        print()
    for warning in answer.warnings:
        paragraph(warning.message, bullet="! ")
    print(f"\n{answer.disclaimer}")


def _print_check(check: VerificationCheck) -> None:
    """One line per check; a long explanation wraps under itself, not under the marker."""
    prefix = f"  {_MARKS[check.status]} {check.name:<16} "
    print(
        textwrap.fill(
            check.detail,
            width=110,
            initial_indent=prefix,
            subsequent_indent=" " * len(prefix),
        )
    )


def _print_report(report: VerificationReport) -> None:
    print(f"{report.source_id}: {report.status.replace('_', ' ').upper()}")
    print(f"      {report.url}")
    for check in report.checks:
        _print_check(check)


def _print_result(spec: SourceSpec, result: IngestResult) -> None:
    print(f"[{result.outcome.upper()}] {spec.id}: {result.chunks} passages ({result.seconds:.1f}s)")
    for check in result.report.checks:
        if check.status != "pass":
            _print_check(check)


def _verifier(settings: Settings) -> SourceVerifier:
    max_bytes = settings.max_document_mb * 1024 * 1024
    fetcher = Fetcher(timeout_seconds=settings.fetch_timeout_seconds, max_bytes=max_bytes)
    return SourceVerifier(fetcher=fetcher, max_bytes=max_bytes)


def _open_store(settings: Settings) -> VectorStore:
    return VectorStore(
        ArtifactStore(settings.data_dir).chroma_dir, embedding_model=settings.embedding_model
    )


def _use_utf8_output() -> None:
    """Indian-language text must not crash a Windows console that defaults to a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure: Callable[..., None] | None = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    sys.exit(main())
