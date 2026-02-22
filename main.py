#!/usr/bin/env python3
"""CLI + API entry point for the Website Ingestion & Structuring Pipeline.

CLI Usage::

    python main.py --url https://example.com
    python main.py --url https://example.com --depth 2 --limit 50 --format csv

API Usage::

    python main.py serve
    python main.py serve --port 9000
"""

from __future__ import annotations

import sys

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from app.logger import setup_logging
from app.job_manager import JobManager

cli = typer.Typer(
    name="website-pipeline",
    help="🌐 Website Ingestion & Structuring Pipeline — crawl, extract, and export website data.",
    add_completion=False,
)
console = Console()


@cli.callback(invoke_without_command=True)
def crawl(
    ctx: typer.Context,
    url: str = typer.Option(None, "--url", "-u", help="Starting URL to crawl."),
    depth: int = typer.Option(3, "--depth", "-d", help="Maximum crawl depth (BFS)."),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of pages to crawl."),
    rate_limit: float = typer.Option(1.0, "--rate-limit", "-r", help="Seconds between requests."),
    output_dir: str = typer.Option("site_dataset", "--output-dir", "-o", help="Output directory."),
    fmt: str = typer.Option("parquet", "--format", "-f", help="Output format: parquet, csv, jsonl."),
    no_raw_html: bool = typer.Option(False, "--no-raw-html", help="Skip saving raw HTML files."),
    no_images: bool = typer.Option(False, "--no-images", help="Skip downloading images."),
    no_dynamic: bool = typer.Option(False, "--no-dynamic", help="Disable headless browser fallback."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
    json_logs: bool = typer.Option(False, "--json-logs", help="Output logs as JSON lines."),
) -> None:
    """🕷️  Crawl a website and produce structured datasets."""
    # If a subcommand is being invoked (e.g. 'serve'), skip crawl
    if ctx.invoked_subcommand is not None:
        return

    if url is None:
        rprint("[bold cyan]Website Ingestion Pipeline[/bold cyan]")
        rprint("Use [bold]--url[/bold] to crawl, or [bold]serve[/bold] to start the API.\n")
        rprint("Examples:")
        rprint("  python main.py --url https://example.com")
        rprint("  python main.py serve")
        rprint("  python main.py --help")
        raise typer.Exit()

    setup_logging(level=log_level, json_output=json_logs)

    # Header
    rprint(Panel.fit(
        f"[bold cyan]Website Ingestion Pipeline[/bold cyan]\n"
        f"[dim]URL:[/dim]  {url}\n"
        f"[dim]Depth:[/dim] {depth}  •  [dim]Limit:[/dim] {limit}  •  [dim]Rate:[/dim] {rate_limit}s\n"
        f"[dim]Output:[/dim] {output_dir}/  •  [dim]Format:[/dim] {fmt}",
        border_style="blue",
    ))

    try:
        manager = JobManager(
            start_url=url,
            max_depth=depth,
            page_limit=limit,
            rate_limit=rate_limit,
            output_dir=output_dir,
            output_format=fmt,
            save_raw_html=not no_raw_html,
            dynamic_fallback=not no_dynamic,
            download_images=not no_images,
        )
    except Exception as exc:
        rprint(f"[bold red]Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # Run the crawl
    try:
        report = manager.run()
    except KeyboardInterrupt:
        rprint("\n[yellow]Crawl interrupted by user.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as exc:
        rprint(f"[bold red]Crawl failed:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # ── Summary ───────────────────────────────────────────────────────
    _print_report(report, output_dir)


@cli.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="API server host."),
    port: int = typer.Option(8000, "--port", "-p", help="API server port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level."),
) -> None:
    """🚀 Start the FastAPI server for web/GUI access."""
    import uvicorn

    rprint(Panel.fit(
        f"[bold cyan]Website Ingestion Pipeline — API Server[/bold cyan]\n"
        f"[dim]Host:[/dim] {host}:{port}\n"
        f"[dim]Docs:[/dim] http://localhost:{port}/docs\n"
        f"[dim]Swagger:[/dim] http://localhost:{port}/redoc",
        border_style="green",
    ))

    uvicorn.run(
        "app.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )


def _print_report(report: dict, output_dir: str) -> None:
    """Pretty-print the crawl report summary."""
    rprint()
    table = Table(title="📊 Crawl Report", border_style="bright_blue")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white")

    table.add_row("Total Pages", str(report.get("total_pages", 0)))
    table.add_row("Failed Pages", str(report.get("failed_pages", 0)))
    table.add_row("Total Images", str(report.get("total_images", 0)))
    table.add_row("External Links", str(report.get("external_links", 0)))
    table.add_row("Time Taken", f"{report.get('time_taken_seconds', 0):.1f}s")

    console.print(table)

    if report.get("errors"):
        rprint(f"\n[yellow]⚠️  {len(report['errors'])} error(s) encountered. See crawl_report.json for details.[/yellow]")

    rprint(f"\n[green]✅ Dataset saved to:[/green] [bold]{output_dir}/[/bold]")
    rprint("[dim]Files: pages.parquet, images.parquet, crawl_report.json, manifest.json[/dim]")


if __name__ == "__main__":
    cli()
