"""star-crawl CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from star_crawl.db import migrate as db_migrate
from star_crawl.sources.loader import SourceLoadError, load_all, load_one_by_name

app = typer.Typer(
    name="star-crawl",
    help="Universal web crawler with content extraction.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database operations.", no_args_is_help=True)
app.add_typer(db_app, name="db")

console = Console()
err_console = Console(stderr=True)


def _data_dir(value: str | None) -> Path:
    return Path(value) if value else Path("data")


@app.command()
def list_sources(
    config_dir: str = typer.Option("configs/sources", "--config-dir"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List all configured sources."""
    try:
        sources = load_all(Path(config_dir))
    except SourceLoadError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=3) from None

    if json_out:
        import json

        out = {
            name: {
                "display_name": s.display_name,
                "fetcher": s.fetcher,
                "seed_strategy": s.seed.strategy,
                "categories": s.categories,
            }
            for name, s in sources.items()
        }
        typer.echo(json.dumps(out, indent=2))
        return

    table = Table(title=f"Configured sources ({len(sources)})")
    table.add_column("Name", style="cyan")
    table.add_column("Display")
    table.add_column("Fetcher")
    table.add_column("Strategy")
    table.add_column("Categories", style="dim")
    for name, s in sources.items():
        table.add_row(
            name,
            s.display_name,
            s.fetcher,
            s.seed.strategy,
            ", ".join(s.categories) or "—",
        )
    console.print(table)


@db_app.command("migrate")
def db_migrate_cmd(
    data_dir: str | None = typer.Option(None, "--data-dir"),
    check: bool = typer.Option(False, "--check", help="Exit 1 if pending migrations"),
) -> None:
    """Apply pending schema migrations (idempotent)."""
    path = _data_dir(data_dir)
    if check:
        n = db_migrate.pending_count(path)
        if n == 0:
            console.print("[green]up-to-date[/green]")
        else:
            console.print(f"[yellow]{n} pending migration(s)[/yellow]")
            raise typer.Exit(code=1)
        return

    applied = db_migrate.migrate(path)
    if applied:
        console.print(f"[green]applied[/green] {len(applied)} migration(s): {applied}")
    else:
        console.print("[dim]up-to-date[/dim]")


@app.command()
def run(
    source_name: str | None = typer.Argument(None, help="Source name (omit with --all)"),
    all_sources: bool = typer.Option(False, "--all", help="Run every configured source"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
    config_dir: str = typer.Option("configs/sources", "--config-dir"),
    allow_policy_blocked: bool = typer.Option(False, "--allow-policy-blocked"),
    limit: int | None = typer.Option(None, "--limit", help="Stop after N new articles per source"),
) -> None:
    """Crawl one or all sources."""
    import asyncio as _asyncio

    from star_crawl.core import pipeline

    if not source_name and not all_sources:
        err_console.print("[red]error:[/red] pass <source-name> or --all")
        raise typer.Exit(code=3)

    try:
        all_configs = load_all(Path(config_dir))
    except SourceLoadError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=3) from None

    if all_sources:
        sources = list(all_configs.values())
    else:
        if source_name not in all_configs:
            err_console.print(f"[red]error:[/red] unknown source '{source_name}'")
            err_console.print(f"available: {', '.join(all_configs) or '<none>'}")
            raise typer.Exit(code=3)
        sources = [all_configs[source_name]]

    path = _data_dir(data_dir)
    db_migrate.migrate(path)

    results = _asyncio.run(
        pipeline.run_all(
            sources,
            data_dir=path,
            allow_policy_blocked=allow_policy_blocked,
            limit=limit,
        )
    )

    table = Table(title="Crawl summary")
    table.add_column("Source", style="cyan")
    table.add_column("Status")
    table.add_column("Discovered", justify="right")
    table.add_column("New", justify="right")
    table.add_column("Dup", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Duration", justify="right")

    for r in results:
        status_style = {
            "success": "green",
            "partial": "yellow",
            "failed": "red",
            "skipped": "dim",
        }.get(r.status, "white")
        table.add_row(
            r.source_name,
            f"[{status_style}]{r.status}[/{status_style}]",
            str(r.discovered),
            str(r.extracted_new),
            str(r.extracted_dup),
            str(r.error_count),
            f"{r.duration_seconds:.1f}s",
        )
    console.print(table)

    # Exit code per contracts/cli.md
    if any(r.status == "failed" for r in results):
        raise typer.Exit(code=2)
    if any(r.status == "partial" for r in results):
        raise typer.Exit(code=1)


@app.command("extract-keywords")
def extract_keywords_cmd(
    method: str = typer.Option("keybert", "--method",
                               help="keybert | llm (uses STAR_CRAWL_LLM_* env vars)"),
    model: str | None = typer.Option(None, "--model",
                                     help="(llm only) override the LLM router model slug"),
    source: str | None = typer.Option(None, "--source"),
    rebuild: bool = typer.Option(False, "--rebuild"),
    top_n: int = typer.Option(15, "--top-n", help="(keybert only)"),
    min_score: float = typer.Option(0.35, "--min-score", help="(keybert only)"),
    no_glossary: bool = typer.Option(False, "--no-glossary"),
    config_dir: str = typer.Option("configs/graph", "--config-dir"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Run keyword extraction over the corpus.

    --method keybert   (default) local semantic extractor, free, ~50 articles/s
    --method llm       OpenAI-compatible LLM via STAR_CRAWL_LLM_BASE_URL.
                       Defaults to 9router at http://localhost:20128/v1 with
                       model xiaomi/mimo-v2.5-pro. Results cached by
                       content hash → re-runs cost zero.
    """
    from star_crawl.graph.glossary import Glossary, load as load_glossary
    from star_crawl.graph.runner import extract_corpus

    path = _data_dir(data_dir)
    db_migrate.migrate(path)
    glossary = load_glossary(Path(config_dir)) if not no_glossary else Glossary()

    if method == "llm":
        from star_crawl.graph.extract_llm import LLMConfig, LLMExtractor

        cfg = LLMConfig.from_env(model=model)
        extractor = LLMExtractor(cfg)
        console.print(
            f"[dim]LLM extractor: {cfg.model} via {cfg.base_url}"
            + (f" · budget ${cfg.budget_usd:.2f}" if cfg.budget_usd else "")
            + "[/dim]"
        )
    elif method == "keybert":
        from star_crawl.graph.extract import KeyBertExtractor

        extractor = KeyBertExtractor(top_n=top_n, min_score=min_score)
        console.print("[dim]KeyBERT extractor (first run downloads ~80MB)…[/dim]")
    else:
        err_console.print(f"[red]error:[/red] --method must be 'keybert' or 'llm'")
        raise typer.Exit(code=3)

    stats = extract_corpus(
        extractor=extractor,
        glossary=glossary,
        config_dir=Path(config_dir),
        data_dir=path,
        source=source,
        rebuild=rebuild,
    )
    console.print(
        f"extracted: [green]{stats.articles_processed}[/green] articles · "
        f"keywords [bold]{stats.keywords_total}[/bold] "
        f"({stats.keywords_glossary} glossary, {stats.keywords_keybert} keybert/llm) · "
        f"skipped {stats.articles_skipped} (lang filter)"
    )
    if method == "llm":
        # Show running spend so the user knows the cost.
        from star_crawl.graph.extract_llm import SPEND_FILE
        if SPEND_FILE.exists():
            import json as _json
            sp = _json.loads(SPEND_FILE.read_text())
            console.print(
                f"[dim]cumulative LLM spend: ${sp['total_usd']:.4f} "
                f"({sp['calls']} calls · {sp['in_tokens']:,} in · {sp['out_tokens']:,} out)[/dim]"
            )


@app.command("build-graph")
def build_graph_cmd(
    min_doc_freq: int = typer.Option(3, "--min-doc-freq"),
    min_co_count: int = typer.Option(2, "--min-co-count"),
    min_npmi: float = typer.Option(0.15, "--min-npmi"),
    max_edges_per_node: int = typer.Option(30, "--max-edges-per-node"),
    cluster_resolution: float = typer.Option(1.0, "--cluster-resolution"),
    cluster_seed: int = typer.Option(42, "--cluster-seed"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Build the keyword co-occurrence graph from existing article_keywords."""
    from star_crawl.graph.builder import build_graph

    path = _data_dir(data_dir)
    db_migrate.migrate(path)

    res = build_graph(
        data_dir=path,
        min_doc_freq=min_doc_freq,
        min_co_count=min_co_count,
        min_npmi=min_npmi,
        max_edges_per_node=max_edges_per_node,
        cluster_resolution=cluster_resolution,
        cluster_seed=cluster_seed,
    )
    console.print(
        f"graph: [green]{res.n_keywords}[/green] keywords · "
        f"[green]{res.n_edges}[/green] edges · "
        f"[green]{res.n_clusters}[/green] clusters"
    )
    if res.cluster_labels:
        for cid in sorted(res.cluster_labels):
            console.print(f"  cluster {cid} — [cyan]{res.cluster_labels[cid]}[/cyan]")


graph_app = typer.Typer(help="Inspect the keyword graph.", no_args_is_help=True)
app.add_typer(graph_app, name="graph")


@graph_app.command("stats")
def graph_stats_cmd(data_dir: str | None = typer.Option(None, "--data-dir")) -> None:
    """Print summary of the latest graph build."""
    from star_crawl.db.connection import connect

    conn = connect(_data_dir(data_dir), read_only=True)
    try:
        row = conn.execute(
            """SELECT n_keywords, n_edges, n_clusters, built_at
                 FROM graph_meta ORDER BY built_at DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            console.print("[yellow]no graph built yet[/yellow]")
            return
        console.print(
            f"latest build [dim]{row['built_at'][:16]}[/dim]: "
            f"{row['n_keywords']} keywords · {row['n_edges']} edges · "
            f"{row['n_clusters']} clusters"
        )
        clusters = conn.execute(
            "SELECT id, label, n_keywords FROM clusters ORDER BY n_keywords DESC LIMIT 20"
        ).fetchall()
        for c in clusters:
            console.print(
                f"  cluster {c['id']:>3} — [cyan]{c['label']}[/cyan] ({c['n_keywords']})"
            )
    finally:
        conn.close()


@graph_app.command("top")
def graph_top_cmd(
    by: str = typer.Option("doc_freq", "--by", help="doc_freq | degree"),
    limit: int = typer.Option(30, "--limit"),
    cluster: int | None = typer.Option(None, "--cluster"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """List top keywords by frequency or degree."""
    from star_crawl.db.connection import connect

    if by not in ("doc_freq", "degree"):
        err_console.print("[red]error:[/red] --by must be doc_freq or degree")
        raise typer.Exit(code=3)

    conn = connect(_data_dir(data_dir), read_only=True)
    try:
        params: list[object] = []
        where = ""
        if cluster is not None:
            where = "WHERE cluster_id = ?"
            params.append(cluster)
        rows = conn.execute(
            f"""SELECT id, display, doc_freq, degree, cluster_id
                  FROM v_keyword_full {where}
                 ORDER BY {by} DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
        table = Table(title=f"Top by {by}")
        table.add_column("ID", justify="right")
        table.add_column("Display")
        table.add_column("Cluster", justify="right")
        table.add_column("Docs", justify="right")
        table.add_column("Degree", justify="right")
        for r in rows:
            table.add_row(
                str(r["id"]), r["display"],
                str(r["cluster_id"] or "—"),
                str(r["doc_freq"]), str(r["degree"]),
            )
        console.print(table)
    finally:
        conn.close()


@graph_app.command("relabel")
def graph_relabel_cmd(
    cluster_id: int = typer.Argument(...),
    label: str = typer.Argument(...),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Override an auto-cluster label (preserved across rebuilds)."""
    from star_crawl.db.connection import connect

    conn = connect(_data_dir(data_dir))
    try:
        cur = conn.execute(
            "UPDATE clusters SET label = ?, is_user_labeled = 1 WHERE id = ?",
            (label, cluster_id),
        )
        if cur.rowcount == 0:
            err_console.print(f"[red]error:[/red] cluster {cluster_id} not found")
            raise typer.Exit(code=3)
        conn.commit()
    finally:
        conn.close()
    console.print(f"cluster {cluster_id} → [cyan]{label}[/cyan]")


@graph_app.command("export")
def graph_export_cmd(
    fmt: str = typer.Argument(..., help="graphml | json | png"),
    out: str = typer.Option(..., "--out"),
    source: list[str] | None = typer.Option(None, "--source"),
    since: str | None = typer.Option(None, "--since"),
    until: str | None = typer.Option(None, "--until"),
    min_freq: int = typer.Option(3, "--min-freq"),
    min_npmi: float = typer.Option(0.15, "--min-npmi"),
    cluster: int | None = typer.Option(None, "--cluster"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
    server_url: str = typer.Option(
        "http://127.0.0.1:8000", "--server-url",
        help="(png only) URL of a running star-crawl serve",
    ),
) -> None:
    """Export the current graph view to GraphML / JSON / PNG."""
    from star_crawl.db.connection import connect
    from star_crawl.graph import export as gexport
    from star_crawl.graph.repository import GraphFilters, read_graph

    if fmt not in ("graphml", "json", "png"):
        err_console.print(f"[red]error:[/red] unknown format '{fmt}'")
        raise typer.Exit(code=3)

    out_path = Path(out)
    path = _data_dir(data_dir)

    if fmt in ("graphml", "json"):
        conn = connect(path, read_only=True)
        try:
            filters = GraphFilters(
                sources=source, since=since, until=until,
                min_freq=min_freq, min_npmi=min_npmi, cluster=cluster,
            )
            payload = read_graph(conn, filters)
        finally:
            conn.close()
        if fmt == "json":
            size = gexport.to_cytoscape_json(payload, out_path)
        else:
            size = gexport.to_graphml(payload, out_path)
        console.print(
            f"wrote [green]{len(payload['nodes'])}[/green] nodes / "
            f"[green]{len(payload['edges'])}[/green] edges "
            f"→ {out_path} ({size:,} bytes)"
        )
        return

    # png
    query_parts: list[str] = [f"min_freq={min_freq}", f"min_npmi={min_npmi}"]
    if source:
        for s in source:
            query_parts.append(f"source={s}")
    if since:
        query_parts.append(f"since={since}")
    if until:
        query_parts.append(f"until={until}")
    if cluster is not None:
        query_parts.append(f"cluster={cluster}")
    query_string = "&".join(query_parts)
    try:
        size = gexport.to_png(server_url, query_string, out_path)
    except RuntimeError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=3) from None
    console.print(f"wrote screenshot → {out_path} ({size:,} bytes)")


@app.command()
def stats(
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Print corpus stats."""
    from star_crawl.db.connection import connect

    path = _data_dir(data_dir)
    conn = connect(path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        by_source = conn.execute(
            "SELECT source_name, COUNT(*) AS n FROM articles GROUP BY source_name "
            "ORDER BY n DESC"
        ).fetchall()
    finally:
        conn.close()

    console.print(f"Total articles: [bold]{total}[/bold]")
    if by_source:
        table = Table(title="By source")
        table.add_column("Source")
        table.add_column("Articles", justify="right")
        for row in by_source:
            table.add_row(row["source_name"], str(row["n"]))
        console.print(table)


@app.command()
def refresh(
    source_name: str = typer.Argument(...),
    data_dir: str | None = typer.Option(None, "--data-dir"),
    config_dir: str = typer.Option("configs/sources", "--config-dir"),
) -> None:
    """Re-fetch articles for a source (e.g., after extractor improvement)."""
    import asyncio as _asyncio

    from star_crawl.core import pipeline

    try:
        cfg = load_one_by_name(source_name, Path(config_dir))
    except SourceLoadError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=3) from None

    path = _data_dir(data_dir)
    db_migrate.migrate(path)
    res = _asyncio.run(pipeline.refresh_articles(cfg, data_dir=path))
    console.print(
        f"refresh {source_name}: {res.status} +{res.extracted_new} new, "
        f"{res.extracted_dup} dup, {res.error_count} err"
    )


@app.command()
def export(
    fmt: str = typer.Argument(..., help="jsonl | parquet"),
    out: str = typer.Option(..., "--out"),
    source: str | None = typer.Option(None, "--source"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Export articles to JSONL or Parquet."""
    from star_crawl.db.connection import connect

    if fmt not in ("jsonl", "parquet"):
        err_console.print(f"[red]error:[/red] unknown format '{fmt}'")
        raise typer.Exit(code=3)

    path = _data_dir(data_dir)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(path)
    try:
        params: list[object] = []
        where = ""
        if source:
            where = "WHERE source_name = ?"
            params.append(source)
        rows = conn.execute(
            f"SELECT * FROM articles {where} ORDER BY id", params
        ).fetchall()
    finally:
        conn.close()

    if fmt == "jsonl":
        import json

        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                d = dict(r)
                f.write(json.dumps(d, default=str, ensure_ascii=False) + "\n")
        console.print(f"wrote [green]{len(rows)}[/green] articles → {out_path}")
        return

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        err_console.print(
            "[red]error:[/red] parquet export requires the [parquet] extra: "
            "pip install -e '.[parquet]'"
        )
        raise typer.Exit(code=3) from None

    if not rows:
        console.print("[dim]no articles to export[/dim]")
        return

    cols = list(rows[0].keys())
    data = {c: [r[c] for r in rows] for c in cols}
    table = pa.table(data)
    pq.write_table(table, out_path)
    console.print(f"wrote [green]{len(rows)}[/green] articles → {out_path}")


@db_app.command("inspect")
def db_inspect(
    target: str = typer.Argument(..., help="run-history | errors"),
    source: str | None = typer.Option(None, "--source"),
    run: int | None = typer.Option(None, "--run"),
    limit: int = typer.Option(20, "--limit"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Read-only DB queries for ops."""
    from star_crawl.db.connection import connect

    path = _data_dir(data_dir)
    conn = connect(path, read_only=True)
    try:
        if target == "run-history":
            params: list[object] = []
            where = ""
            if source:
                where = "WHERE source_name = ?"
                params.append(source)
            rows = conn.execute(
                f"""SELECT id, source_name, started_at, status, discovered,
                           extracted_new, error_count
                      FROM crawl_runs {where}
                     ORDER BY started_at DESC LIMIT ?""",
                [*params, limit],
            ).fetchall()
            table = Table(title="Run history")
            table.add_column("ID", justify="right")
            table.add_column("Source")
            table.add_column("Started")
            table.add_column("Status")
            table.add_column("Disc", justify="right")
            table.add_column("New", justify="right")
            table.add_column("Err", justify="right")
            for r in rows:
                table.add_row(
                    str(r["id"]), r["source_name"], r["started_at"][:16],
                    r["status"], str(r["discovered"]),
                    str(r["extracted_new"]), str(r["error_count"]),
                )
            console.print(table)
        elif target == "errors":
            if run is None:
                err_console.print("[red]error:[/red] --run is required for errors")
                raise typer.Exit(code=3)
            rows = conn.execute(
                """SELECT url, kind, message, occurred_at FROM errors
                    WHERE run_id = ? ORDER BY occurred_at LIMIT ?""",
                (run, limit),
            ).fetchall()
            table = Table(title=f"Errors for run #{run}")
            table.add_column("Time")
            table.add_column("Kind")
            table.add_column("URL", style="dim")
            table.add_column("Message")
            for r in rows:
                table.add_row(r["occurred_at"][:16], r["kind"], r["url"], r["message"])
            console.print(table)
        else:
            err_console.print(f"[red]error:[/red] unknown target '{target}'")
            raise typer.Exit(code=3)
    finally:
        conn.close()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Start the read-only web UI."""
    import os

    from star_crawl.web.auth import auth_enabled

    if host not in ("127.0.0.1", "localhost", "::1") and not auth_enabled():
        err_console.print(
            "[red]error:[/red] exposed mode requires STAR_CRAWL_AUTH=user:pass to be set in env."
        )
        err_console.print("Either bind to 127.0.0.1 or set credentials and try again.")
        raise typer.Exit(code=3)

    if data_dir:
        os.environ["STAR_CRAWL_DATA_DIR"] = data_dir

    if auth_enabled():
        console.print("[green]auth enabled[/green] (basic auth from STAR_CRAWL_AUTH)")
    console.print(f"Listening on http://{host}:{port}")

    import uvicorn

    uvicorn.run("star_crawl.web.app:app", host=host, port=port, log_level="info")


@app.command()
def version() -> None:
    """Print version."""
    from star_crawl import __version__

    typer.echo(f"star-crawl {__version__}")


if __name__ == "__main__":
    app()
