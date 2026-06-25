from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

log = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
    )
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.layout import Layout
    from rich.live import Live
    from rich.columns import Columns
    from rich.tree import Tree
    from rich import box
    from rich.align import Align
    from rich.prompt import Confirm

    _RICH = True
except ImportError:

    class _Dummy:
        def __getattr__(self, name):
            return self

        def __call__(self, *args, **kwargs):
            return ""

    _RICH = False
    Console = _Dummy
    Table = _Dummy
    Panel = _Dummy
    Progress = _Dummy
    Syntax = _Dummy
    Text = _Dummy
    Layout = _Dummy
    Live = _Dummy
    Columns = _Dummy
    Tree = _Dummy

    class _DummyCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __call__(self, *args, **kwargs):
            return self

    Confirm = _DummyCtx


def _console() -> Console:
    return Console() if _RICH else Console()  # type: ignore


def _noop(*args, **kwargs):
    pass


BANNER = """
████████╗██╗  ██╗███████╗     █████╗ ██╗    ██╗ █████╗ ██╗██████╗ ██╗████████╗
╚══██╔══╝██║  ██║██╔════╝    ██╔══██╗██║    ██║██╔══██╗██║██╔══██╗██║╚══██╔══╝
   ██║   ███████║█████╗      ███████║██║ █╗ ██║███████║██║██████╔╝██║   ██║
   ██║   ██╔══██║██╔══╝      ██╔══██║██║███╗██║██╔══██║██║██╔══██╗██║   ██║
   ██║   ██║  ██║███████╗    ██║  ██║╚███╔███╔╝██║  ██║██║██║  ██║██║   ██║
   ╚═╝   ╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝   ╚═╝
"""


def print_banner() -> None:
    con = _console()
    if _RICH:
        con.print(BANNER, style="bold cyan", highlight=False)
        con.print("  Community AI Security Audit Platform", style="bold white")
        con.print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        con.rule(style="cyan")
    else:
        print(BANNER)
        print("Community AI Security Audit Platform")
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 60)


def install_traceback_handler() -> None:
    if _RICH:
        from rich.traceback import install as rich_tb_install

        rich_tb_install(show_locals=False, width=120)


def score_color(value: float) -> str:
    if value >= 90:
        return "green"
    if value >= 80:
        return "cyan"
    if value >= 60:
        return "yellow"
    if value >= 40:
        return "orange3"
    return "red"


def score_emoji(value: float) -> str:
    if value >= 90:
        return "🟢"
    if value >= 80:
        return "🟦"
    if value >= 60:
        return "🟡"
    if value >= 40:
        return "🟠"
    return "🔴"


def rating_label(value: float) -> str:
    if value >= 90:
        return "Excellent"
    if value >= 80:
        return "Good"
    if value >= 70:
        return "Fair"
    if value >= 60:
        return "Poor"
    return "Critical"


def styled_print(*args, **kwargs):
    con = _console()
    sep = kwargs.pop("sep", " ")
    text = sep.join(str(a) for a in args)
    if _RICH:
        con.print(text, **kwargs)
    else:
        print(text, **kwargs)


def header(title: str, subtitle: str = "") -> None:
    con = _console()
    if _RICH:
        con.print()
        con.rule(f"[bold cyan]{title}[/]", style="cyan")
        if subtitle:
            con.print(f"  [dim]{subtitle}[/]")
        con.print()
    else:
        width = 60
        print(f"\n{'=' * width}")
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        print(f"{'=' * width}\n")


def panel(title: str, content: str, style: str = "cyan") -> None:
    con = _console()
    if _RICH:
        con.print(Panel(content, title=title, border_style=style))
    else:
        print(f"\n--- {title} ---")
        print(content)
        print("---")


def error(message: str) -> None:
    if _RICH:
        _console().print(f"[bold red]✖[/] {message}")
    else:
        print(f"ERROR: {message}")


def success(message: str) -> None:
    if _RICH:
        _console().print(f"[bold green]✔[/] {message}")
    else:
        print(f"OK: {message}")


def warning(message: str) -> None:
    if _RICH:
        _console().print(f"[bold yellow]⚠[/] {message}")
    else:
        print(f"WARNING: {message}")


def info(message: str) -> None:
    if _RICH:
        _console().print(f"[dim]ℹ[/] {message}")
    else:
        print(f"  {message}")


def note(message: str) -> None:
    if _RICH:
        _console().print(f"[dim]  {message}[/]")
    else:
        print(f"  ({message})")


def divider() -> None:
    con = _console()
    if _RICH:
        con.rule(style="dim")
    else:
        print(f"{'─' * 60}")


def make_score_table(
    title: str,
    rows: List[tuple],
    columns: Optional[List[str]] = None,
) -> Table:
    tbl = Table(title=title, box=box.ROUNDED, title_justify="left")
    if columns:
        for col in columns:
            tbl.add_column(col, style="bold")
    else:
        tbl.add_column("Dimension", style="bold")
        tbl.add_column("Score")

    for row in rows:
        styled_row = []
        for cell in row:
            if isinstance(cell, (int, float)):
                val = float(cell)
                color = score_color(val)
                styled_row.append(f"[{color}]{val:.1f}[/]")
            else:
                styled_row.append(str(cell))
        tbl.add_row(*styled_row)

    return tbl


def print_score_table(
    title: str,
    rows: List[tuple],
    columns: Optional[List[str]] = None,
) -> None:
    con = _console()
    tbl = make_score_table(title, rows, columns)
    if _RICH:
        con.print(tbl)
    else:
        con.print(f"\n{title}")
        if columns:
            con.print("  ".join(columns))
            con.print("  " + "-" * 40)
        for row in rows:
            con.print("  ".join(str(c) for c in row))


def make_results_table(
    results: List[Dict[str, Any]],
    name_key: str = "scanner_name",
    score_keys: Optional[List[str]] = None,
    extra_keys: Optional[List[str]] = None,
) -> Table:
    if score_keys is None:
        score_keys = ["score"]
    if extra_keys is None:
        extra_keys = []

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    tbl.add_column("Scanner", style="bold")
    for k in score_keys:
        tbl.add_column(k.replace("_", " ").title(), justify="right")
    for k in extra_keys:
        tbl.add_column(k.replace("_", " ").title(), justify="right")

    for r in results:
        name = r.get(name_key, "?")
        row = [name]
        for k in score_keys:
            val = r.get(k, 0)
            if isinstance(val, (int, float)):
                color = score_color(float(val))
                row.append(f"[{color}]{val:.1f}[/]")
            else:
                row.append(str(val))
        for k in extra_keys:
            val = r.get(k, "")
            if isinstance(val, float):
                row.append(f"{val:.2%}")
            else:
                row.append(str(val))
        tbl.add_row(*row)

    return tbl


def print_results_table(
    results: List[Dict[str, Any]],
    title: str = "",
    name_key: str = "scanner_name",
    score_keys: Optional[List[str]] = None,
    extra_keys: Optional[List[str]] = None,
) -> None:
    con = _console()
    tbl = make_results_table(results, name_key, score_keys, extra_keys)
    if _RICH:
        if title:
            con.print(Panel(tbl, title=title, border_style="cyan"))
        else:
            con.print(tbl)
    else:
        con.print(f"\n{title}")
        for r in results:
            name = r.get(name_key, "?")
            scores = " ".join(f"{k}={r.get(k, 0):.1f}" for k in (score_keys or []))
            extras = " ".join(f"{k}={r.get(k, '')}" for k in (extra_keys or []))
            con.print(f"  {name}: {scores} {extras}")


def make_finding_table(findings: List[Dict[str, Any]]) -> Table:
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    tbl.add_column("Severity", style="bold")
    tbl.add_column("Description")
    tbl.add_column("Category")
    for f in findings:
        sev = str(f.get("severity", "unknown")).lower()
        sev_color = {"critical": "red", "high": "orange3", "medium": "yellow", "low": "cyan"}.get(
            sev, "white"
        )
        tbl.add_row(
            f"[{sev_color}]{sev.upper()}[/]",
            str(f.get("description", "")),
            str(f.get("category", "")),
        )
    return tbl


def print_findings(findings: List[Dict[str, Any]], title: str = "Findings") -> None:
    if not findings:
        info("No findings.")
        return
    con = _console()
    tbl = make_finding_table(findings)
    if _RICH:
        con.print(Panel(tbl, title=title, border_style="yellow"))
    else:
        con.print(f"\n{title}")
        for f in findings:
            con.print(f"  [{f.get('severity','?')}] {f.get('description','')}")


@contextmanager
def progress_context(description: str = "Working...") -> Iterator[Progress]:
    if _RICH:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=_console(),
        )
    else:
        progress = Progress()  # type: ignore

    with progress:
        progress.add_task(description, total=None)
        yield progress


def task_progress(
    items: List[str],
    description: str = "Processing",
) -> Iterator[Tuple[str, int, int]]:
    total = len(items)
    if _RICH:
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=_console(),
        )
        with progress:
            task_id = progress.add_task(description, total=total)
            for i, item in enumerate(items):
                progress.update(task_id, description=f"{description}: {item}", completed=i)
                yield item, i, total
                progress.advance(task_id)
    else:
        for i, item in enumerate(items):
            print(f"  [{i + 1}/{total}] {item}...")
            yield item, i, total


def print_json(data: Any) -> None:
    if _RICH:
        json_str = json.dumps(data, indent=2, default=str)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        _console().print(syntax)
    else:
        print(json.dumps(data, indent=2, default=str))


def print_overall_score(overall: float, *sub_scores: Tuple[str, float]) -> None:
    con = _console()
    color = score_color(overall)
    emoji = score_emoji(overall)
    rating = rating_label(overall)

    if _RICH:
        score_display = Text.assemble(
            (f"{emoji}  ", ""),
            (f"{overall:.1f}", f"bold {color}"),
            ("\n", ""),
            (f"  {rating}", color),
        )
        con.print(
            Panel(
                Align.center(score_display),
                title="Overall Audit Score",
                border_style=color,
                padding=(1, 4),
            )
        )

        if sub_scores:
            tbl = Table(box=box.SIMPLE, show_header=False)
            tbl.add_column("Dimension", style="bold")
            tbl.add_column("Score", justify="right")
            for label, val in sub_scores:
                tbl.add_row(label, f"[{score_color(val)}]{val:.1f}[/]")
            con.print(tbl)
    else:
        print(f"\n{'=' * 60}")
        print(f"  Overall Audit Score: {overall:.1f} ({rating})")
        print(f"{'=' * 60}")
        for label, val in sub_scores:
            print(f"  {label:20s} {val:.1f}")


def make_discover_table(caps: Dict[str, List[str]]) -> Table:
    main_tbl = Table(box=box.ROUNDED, show_header=False)
    main_tbl.add_column("Category", style="bold cyan", no_wrap=True)
    main_tbl.add_column("Items")
    for category, items in caps.items():
        label = category.replace("_", " ").title()
        item_str = ", ".join(f"[green]{i}[/]" for i in items) if items else "[dim](none)[/]"
        main_tbl.add_row(label, item_str)
    return main_tbl


def make_discover_tree(caps: Dict[str, List[str]]) -> Tree:
    tree = Tree("🔍 [bold cyan]Community AI Audit[/]", guide_style="dim")
    for category, items in caps.items():
        label = category.replace("_", " ").title()
        branch = tree.add(f"[bold]{label}[/]")
        if items:
            for item in items:
                branch.add(f"[green]{item}[/]")
        else:
            branch.add("[dim](none)[/]")
    return tree


def print_discover(caps: Dict[str, List[str]], format: str = "tree") -> None:
    con = _console()
    if not _RICH:
        for category, items in caps.items():
            print(f"\n  {category.replace('_', ' ').title()}:")
            for item in items:
                print(f"    • {item}")
        return

    if format == "tree":
        con.print(make_discover_tree(caps))
    else:
        con.print(Panel(make_discover_table(caps), title="Discovered Capabilities"))


def confirm_action(message: str, default: bool = False) -> bool:
    if _RICH:
        return Confirm.ask(message, default=default)
    try:
        response = input(f"{message} (y/N): ").strip().lower()
        return response in ("y", "yes", "true")
    except (EOFError, KeyboardInterrupt):
        return default
