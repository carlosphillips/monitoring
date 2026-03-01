"""HTML report generation (parquet files handle data output)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader

from monitor.breach import Breach
from monitor.windows import WINDOW_NAMES

env = Environment(loader=PackageLoader("monitor", "templates"), autoescape=True)

# Ordered window names for consistent output
WINDOW_ORDER = WINDOW_NAMES


def generate(
    results: dict[str, list[Breach]],
    errors: dict[str, Exception],
    output_dir: Path,
) -> None:
    """Generate all reports (HTML only; data output via parquet files).

    Args:
        results: {portfolio_name: [Breach, ...]} for successful portfolios
        errors: {portfolio_name: exception} for failed portfolios
        output_dir: Directory to write reports to (created if missing)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build summary data: portfolio x window -> breach_count
    summary_rows = _build_summary(results)

    # Write summary HTML
    _write_summary_html(summary_rows, errors, output_dir / "summary.html")

    # Write per-portfolio reports
    for portfolio_name, breaches in results.items():
        portfolio_dir = output_dir / portfolio_name
        portfolio_dir.mkdir(parents=True, exist_ok=True)

        sorted_breaches = sorted(
            breaches,
            key=lambda b: (b.end_date, b.layer, b.factor or "", b.window),
        )

        _write_report_html(portfolio_name, sorted_breaches, portfolio_dir / "report.html")


def _build_summary(results: dict[str, list[Breach]]) -> list[dict]:
    """Build summary rows: one per portfolio x window."""
    rows = []
    for portfolio_name in sorted(results.keys()):
        breaches = results[portfolio_name]
        # Count breaches per window
        window_counts: dict[str, int] = {w: 0 for w in WINDOW_ORDER}
        for b in breaches:
            if b.window in window_counts:
                window_counts[b.window] += 1

        for window in WINDOW_ORDER:
            rows.append({
                "portfolio": portfolio_name,
                "window": window,
                "breach_count": window_counts[window],
            })
    return rows


def _write_summary_html(
    rows: list[dict], errors: dict[str, Exception], path: Path
) -> None:
    template = env.get_template("summary.html.j2")
    html = template.render(rows=rows, errors=errors)
    path.write_text(html)


def _write_report_html(
    portfolio_name: str, breaches: list[Breach], path: Path
) -> None:
    template = env.get_template("report.html.j2")
    html = template.render(portfolio_name=portfolio_name, breaches=breaches)
    path.write_text(html)
