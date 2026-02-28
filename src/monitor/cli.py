"""CLI entry point: uv run monitor [--input <dir>] [--thresholds <dir>] [--output <dir>]"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from monitor import DataError, carino, parquet_output, reports
from monitor import breach as breach_mod
from monitor import data as data_mod
from monitor import portfolios as portfolios_mod
from monitor import thresholds as thresholds_mod
from monitor.windows import WINDOWS, slice_window

logger = logging.getLogger("monitor")


class _DefaultGroup(click.Group):
    """Click group that falls back to 'run' when no known subcommand is given."""

    default_cmd_name = "run"

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Only prepend 'run' when args look like options (start with '-'),
        # not when they look like a subcommand name (which may be a typo).
        if not args or args[0].startswith("-"):
            args = [self.default_cmd_name] + list(args)
        return super().parse_args(ctx, args)


@click.group(cls=_DefaultGroup)
def main():
    """Monitor portfolio factor exposures against configurable thresholds."""


@main.command()
@click.option(
    "--input", "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="./input",
    help="Root input directory containing portfolios/ and factor_returns.csv",
)
@click.option(
    "--thresholds", "thresholds_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Thresholds directory (default: {input}/thresholds)",
)
@click.option(
    "--output", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="./output",
    help="Output directory for reports",
)
@click.option(
    "--parquet/--no-parquet",
    default=True,
    help="Write per-window parquet attribution and breach files.",
)
def run(input_dir: Path, thresholds_dir: Path | None, output_dir: Path, parquet: bool) -> None:
    """Run the monitoring pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    if thresholds_dir is None:
        thresholds_dir = input_dir / "thresholds"

    try:
        factor_returns = data_mod.load_factor_returns(input_dir)
        n_dates, n_factors = len(factor_returns), len(factor_returns.columns)
        logger.info("Loaded factor returns: %d dates, %d factors", n_dates, n_factors)

        portfolio_list = portfolios_mod.discover(input_dir, thresholds_dir)
        logger.info("Discovered %d portfolios", len(portfolio_list))
    except DataError as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)

    results: dict[str, list[breach_mod.Breach]] = {}
    errors: dict[str, Exception] = {}

    for portfolio in portfolio_list:
        try:
            logger.info("Processing %s...", portfolio.name)

            config = thresholds_mod.load(portfolio.thresholds_path)
            exp_data = data_mod.load_exposures(
                portfolio.exposures_path, factor_returns, config.layers
            )

            n_dates = len(exp_data.dates)
            logger.info("  %d dates, %d exposure pairs", n_dates, len(exp_data.exposures))

            breaches: list[breach_mod.Breach] = []
            attribution_rows: dict[str, list[dict[str, object]]] = {w.name: [] for w in WINDOWS}
            breach_rows: dict[str, list[dict[str, object]]] = {w.name: [] for w in WINDOWS}

            for end_date in exp_data.dates:
                for window_def in WINDOWS:
                    ws = slice_window(exp_data.dates, end_date, window_def, exp_data.dates[0])
                    if ws is None:
                        continue

                    # Extract window slice arrays
                    mask = ws.mask
                    r_p = exp_data.portfolio_returns[mask].values
                    exposures_slice = {
                        key: series[mask].values
                        for key, series in exp_data.exposures.items()
                    }
                    factor_rets_slice = {
                        col: factor_returns[col][mask].values
                        for col in factor_returns.columns
                    }

                    contributions = carino.compute(r_p, exposures_slice, factor_rets_slice)
                    breaches.extend(
                        breach_mod.detect(contributions, config, ws.end_date, window_def.name)
                    )

                    if parquet:
                        attribution_rows[window_def.name].append(
                            parquet_output.build_attribution_row(
                                ws.end_date, contributions, exposures_slice
                            )
                        )
                        breach_rows[window_def.name].append(
                            parquet_output.build_breach_row(
                                ws.end_date, contributions, config, window_def.name
                            )
                        )

            results[portfolio.name] = breaches
            logger.info("  %d breaches found", len(breaches))

            if parquet:
                layer_factor_pairs = sorted(exp_data.exposures.keys())
                parquet_output.write(
                    attribution_rows,
                    breach_rows,
                    output_dir / portfolio.name / "attributions",
                    layer_factor_pairs,
                )

        except DataError as e:
            logger.error("  Error processing %s: %s", portfolio.name, e)
            errors[portfolio.name] = e

    reports.generate(results, errors, output_dir)
    logger.info("Reports written to %s", output_dir)

    total_breaches = sum(len(b) for b in results.values())
    logger.info(
        "Done: %d portfolios processed, %d errors, %d total breaches",
        len(results),
        len(errors),
        total_breaches,
    )

    if errors:
        sys.exit(1)


@main.command()
@click.option(
    "--output", "output_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="./output",
    help="Output directory containing breach data",
)
@click.option(
    "--port",
    type=int,
    default=8050,
    help="Port to serve the dashboard on",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Run in debug mode with hot-reloading",
)
def dashboard(output_dir: Path, port: int, debug: bool) -> None:
    """Launch the Breach Explorer Dashboard."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    try:
        from monitor.dashboard import create_app
    except ImportError:
        click.echo(
            "Dashboard dependencies not installed. Run: pip install monitoring[dashboard]",
            err=True,
        )
        sys.exit(1)

    app = create_app(output_dir)
    if debug:
        logger.warning("DEBUG MODE ENABLED — do not expose to untrusted networks")
    logger.info("Starting Breach Explorer Dashboard on http://localhost:%d", port)
    app.run(host="127.0.0.1", port=port, debug=debug)


@main.command()
@click.option(
    "--output", "output_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="./output",
    help="Output directory containing breach data",
)
@click.option("--portfolio", multiple=True, help="Filter by portfolio(s)")
@click.option("--layer", multiple=True, help="Filter by layer(s)")
@click.option("--factor", multiple=True, help="Filter by factor(s)")
@click.option("--window", multiple=True, help="Filter by window(s)")
@click.option("--direction", multiple=True, help="Filter by direction(s)")
@click.option("--start-date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option(
    "--format", "output_format",
    type=click.Choice(["csv", "json"]),
    default="csv",
    help="Output format",
)
@click.option("--limit", type=int, default=None, help="Max rows to return")
def query(
    output_dir: Path,
    portfolio: tuple[str, ...],
    layer: tuple[str, ...],
    factor: tuple[str, ...],
    window: tuple[str, ...],
    direction: tuple[str, ...],
    start_date: str | None,
    end_date: str | None,
    output_format: str,
    limit: int | None,
) -> None:
    """Query filtered breach data."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    try:
        from monitor.dashboard.data import load_breaches
        from monitor.dashboard.query_builder import build_where_clause
    except ImportError:
        click.echo(
            "Dashboard dependencies not installed. Run: pip install monitoring[dashboard]",
            err=True,
        )
        sys.exit(1)

    conn = load_breaches(output_dir)

    where_sql, params = build_where_clause(
        list(portfolio) or None,
        list(layer) or None,
        list(factor) or None,
        list(window) or None,
        list(direction) or None,
        start_date,
        end_date,
        None,  # abs_value_range
        None,  # distance_range
    )

    sql = f"SELECT * FROM breaches {where_sql} ORDER BY end_date DESC, portfolio, layer, factor"
    if limit is not None:
        sql += f" LIMIT {limit}"

    result = conn.execute(sql, params)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()

    if output_format == "csv":
        import csv as csv_mod
        import io

        buf = io.StringIO()
        writer = csv_mod.writer(buf)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
        click.echo(buf.getvalue(), nl=False)
    else:
        import json

        records = [dict(zip(columns, row)) for row in rows]
        # Convert non-serializable types to strings
        for record in records:
            for key, value in record.items():
                if not isinstance(value, (str, int, float, bool, type(None))):
                    record[key] = str(value)
        click.echo(json.dumps(records, indent=2))


@main.command("filter-options")
@click.option(
    "--output", "output_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="./output",
    help="Output directory containing breach data",
)
def filter_options(output_dir: Path) -> None:
    """Show available filter values as JSON."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    try:
        from monitor.dashboard.data import get_filter_options, load_breaches
    except ImportError:
        click.echo(
            "Dashboard dependencies not installed. Run: pip install monitoring[dashboard]",
            err=True,
        )
        sys.exit(1)

    import json

    conn = load_breaches(output_dir)
    options = get_filter_options(conn)
    click.echo(json.dumps(options, indent=2))
