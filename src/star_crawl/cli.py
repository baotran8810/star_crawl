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
