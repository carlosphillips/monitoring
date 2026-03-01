"""Tests for report generation (HTML only; data output via parquet)."""

from datetime import date

from monitor.breach import Breach
from monitor.reports import generate


class TestGenerate:
    def test_creates_output_directory(self, tmp_path):
        output_dir = tmp_path / "output"
        generate({}, {}, output_dir)
        assert output_dir.exists()

    def test_no_csv_files_generated(self, tmp_path):
        """Verify CSV files are not generated (parquet is now the output format)."""
        results = {
            "portfolio_a": [
                Breach(date(2024, 1, 15), "tactical", "market", "daily", 0.006, -0.005, 0.005),
            ],
        }
        generate(results, {}, tmp_path)

        # No summary.csv should be generated
        assert not (tmp_path / "summary.csv").exists()
        # No portfolio breaches.csv should be generated
        assert not (tmp_path / "portfolio_a" / "breaches.csv").exists()

    def test_empty_breaches_creates_html_only(self, tmp_path):
        generate({"portfolio_a": []}, {}, tmp_path)

        # HTML should be created
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

    def test_portfolio_report_html_sorted(self, tmp_path):
        breaches = [
            Breach(date(2024, 3, 16), "tactical", "HML", "annual", 0.07, -0.05, 0.05),
            Breach(date(2024, 3, 15), "tactical", "HML", "annual", 0.06, -0.05, 0.05),
        ]
        generate({"test": breaches}, {}, tmp_path)

        html = (tmp_path / "test" / "report.html").read_text()
        assert "2024-03-15" in html
        assert "2024-03-16" in html
