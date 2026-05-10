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
    source: str | None = typer.Option(None, "--source"),
    rebuild: bool = typer.Option(False, "--rebuild"),
    top_n: int = typer.Option(15, "--top-n"),
    min_score: float = typer.Option(0.35, "--min-score"),
    no_glossary: bool = typer.Option(False, "--no-glossary"),
    config_dir: str = typer.Option("configs/graph", "--config-dir"),
    data_dir: str | None = typer.Option(None, "--data-dir"),
) -> None:
    """Run keyword extraction over the corpus (KeyBERT + glossary boost)."""
    from star_crawl.graph.extract import KeyBertExtractor
    from star_crawl.graph.glossary import Glossary, load as load_glossary
    from star_crawl.graph.runner import extract_corpus

    path = _data_dir(data_dir)
    db_migrate.migrate(path)

    glossary = load_glossary(Path(config_dir)) if not no_glossary else Glossary()
    extractor = KeyBertExtractor(top_n=top_n, min_score=min_score)

    console.print("[dim]Loading model (first run downloads ~80MB)…[/dim]")
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
        f"({stats.keywords_glossary} glossary, {stats.keywords_keybert} keybert) · "
        f"skipped {stats.articles_skipped} (lang filter)"
    )


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
