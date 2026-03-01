"""Breach Pivot Dashboard - Interactive multi-portfolio breach analysis.

This package provides the data layer for the Dash-based dashboard:
- State management with Pydantic validation
- DuckDB querying on consolidated parquet files
- Parameterized SQL with dimension validators to prevent injection
- Multi-gate data validation (load, query, visualization)
- Extensible dimension registry
"""
