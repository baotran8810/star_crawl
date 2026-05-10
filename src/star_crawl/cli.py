"""star-crawl CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from star_crawl.db import migrate as db_migrate
from star_crawl.sources.loader import SourceLoadError, load_all

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
def version() -> None:
    """Print version."""
    from star_crawl import __version__

    typer.echo(f"star-crawl {__version__}")


if __name__ == "__main__":
    app()
