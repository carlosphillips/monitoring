"""CLI entry point: uv run monitor [--input <dir>] [--thresholds <dir>] [--output <dir>]"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from monitor import DataError, carino, reports
from monitor import breach as breach_mod
from monitor import data as data_mod
from monitor import portfolios as portfolios_mod
from monitor import thresholds as thresholds_mod
from monitor.windows import WINDOWS, slice_window

logger = logging.getLogger("monitor")


@click.command()
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
def main(input_dir: Path, thresholds_dir: Path | None, output_dir: Path) -> None:
    """Monitor portfolio factor exposures against configurable thresholds."""
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

            results[portfolio.name] = breaches
            logger.info("  %d breaches found", len(breaches))

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
