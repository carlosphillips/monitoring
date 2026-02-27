"""Tests for report generation."""

import csv
from datetime import date

from monitor.breach import Breach
from monitor.reports import generate


class TestGenerate:
    def test_creates_output_directory(self, tmp_path):
        output_dir = tmp_path / "output"
        generate({}, {}, output_dir)
        assert output_dir.exists()

    def test_summary_csv_structure(self, tmp_path):
        results = {
            "portfolio_a": [
                Breach(date(2024, 1, 15), "tactical", "market", "daily", 0.006, -0.005, 0.005),
                Breach(date(2024, 1, 15), "tactical", "market", "annual", 0.05, -0.04, 0.04),
            ],
        }
        generate(results, {}, tmp_path)

        with open(tmp_path / "summary.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5  # 5 windows
        daily = next(r for r in rows if r["window"] == "daily")
        assert daily["portfolio"] == "portfolio_a"
        assert daily["breach_count"] == "1"
        annual = next(r for r in rows if r["window"] == "annual")
        assert annual["breach_count"] == "1"

    def test_breaches_csv_structure(self, tmp_path):
        breaches = [
            Breach(date(2024, 3, 15), "tactical", "HML", "annual", 0.067, -0.05, 0.05),
            Breach(date(2024, 3, 15), "residual", None, "annual", -0.0012, -0.001, 0.001),
        ]
        generate({"test": breaches}, {}, tmp_path)

        with open(tmp_path / "test" / "breaches.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        # Sorted by layer: residual < tactical
        assert rows[0]["layer"] == "residual"
        assert rows[0]["factor"] == ""  # None -> empty
        assert rows[1]["layer"] == "tactical"

    def test_empty_breaches_creates_header_only_files(self, tmp_path):
        generate({"portfolio_a": []}, {}, tmp_path)

        with open(tmp_path / "portfolio_a" / "breaches.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0

        # HTML should still exist
        assert (tmp_path / "portfolio_a" / "report.html").exists()
        html = (tmp_path / "portfolio_a" / "report.html").read_text()
        assert "No breaches detected" in html

    def test_summary_html_exists(self, tmp_path):
        generate({"p": []}, {}, tmp_path)
        html = (tmp_path / "summary.html").read_text()
        assert "Portfolio Monitoring Summary" in html

    def test_errors_shown_in_summary_html(self, tmp_path):
        generate({}, {"bad_portfolio": ValueError("missing data")}, tmp_path)
        html = (tmp_path / "summary.html").read_text()
        assert "bad_portfolio" in html
        assert "missing data" in html

    def test_breaches_sorted(self, tmp_path):
        breaches = [
            Breach(date(2024, 3, 16), "tactical", "HML", "annual", 0.07, -0.05, 0.05),
            Breach(date(2024, 3, 15), "tactical", "HML", "annual", 0.06, -0.05, 0.05),
        ]
        generate({"test": breaches}, {}, tmp_path)

        with open(tmp_path / "test" / "breaches.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["end_date"] == "2024-03-15"
        assert rows[1]["end_date"] == "2024-03-16"

    def test_asymmetric_bounds_in_csv(self, tmp_path):
        breaches = [
            Breach(date(2024, 1, 1), "tactical", "market", "daily", 0.01, None, 0.005),
        ]
        generate({"test": breaches}, {}, tmp_path)

        with open(tmp_path / "test" / "breaches.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["threshold_min"] == ""
        assert rows[0]["threshold_max"] == "0.005"
