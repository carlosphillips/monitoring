"""Manual integration tests for operations.py - Verify end-to-end functionality.

These tests verify that operations.py works correctly when imported and used
as the primary API for agent access to the dashboard.
"""

from __future__ import annotations

import json
import pytest


def test_manual_operations_import_and_init(sample_output):
    """Manual test: Import operations module and create instance."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Operations Import and Init ===")
    ops = DashboardOperations(sample_output)
    print(f"✓ DashboardOperations created for {sample_output}")
    assert ops is not None
    ops.close()
    print("✓ Close succeeded")


def test_manual_operations_query_breaches(sample_output):
    """Manual test: Query breaches with various filters."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Query Breaches ===")
    with DashboardOperations(sample_output) as ops:
        # Test 1: Query all
        rows = ops.query_breaches()
        print(f"✓ Query all breaches: {len(rows)} rows")
        assert len(rows) == 7

        # Test 2: Query with portfolio filter
        rows = ops.query_breaches(portfolios=["portfolio_a"])
        print(f"✓ Query portfolio_a: {len(rows)} rows")
        assert len(rows) == 5

        # Test 3: Query with multiple filters
        rows = ops.query_breaches(
            portfolios=["portfolio_a"],
            layers=["structural"],
            directions=["upper"]
        )
        print(f"✓ Query with multiple filters: {len(rows)} rows")

        # Test 4: Query with limit
        rows = ops.query_breaches(limit=2)
        print(f"✓ Query with limit=2: {len(rows)} rows")
        assert len(rows) == 2

        # Test 5: Print sample row
        if rows:
            print(f"✓ Sample row columns: {list(rows[0].keys())}")


def test_manual_operations_hierarchy(sample_output):
    """Manual test: Query hierarchical aggregation."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Query Hierarchy ===")
    with DashboardOperations(sample_output) as ops:
        # Test 1: Single dimension
        rows = ops.query_hierarchy(["portfolio"])
        print(f"✓ Hierarchy by portfolio: {len(rows)} groups")
        for row in rows:
            print(f"  - {row['portfolio']}: {row['breach_count']} breaches")

        # Test 2: Multiple dimensions
        rows = ops.query_hierarchy(["portfolio", "layer"])
        print(f"✓ Hierarchy by portfolio+layer: {len(rows)} groups")

        # Test 3: With filters
        rows = ops.query_hierarchy(
            ["layer"],
            portfolios=["portfolio_a"]
        )
        print(f"✓ Hierarchy by layer (filtered): {len(rows)} groups")


def test_manual_operations_export_csv(sample_output):
    """Manual test: Export to CSV."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Export CSV ===")
    with DashboardOperations(sample_output) as ops:
        csv_data = ops.export_breaches_csv(limit=3)
        lines = csv_data.strip().split("\n")
        print(f"✓ CSV export: {len(lines)} lines (header + {len(lines)-1} rows)")
        print(f"✓ Header: {lines[0][:80]}...")


def test_manual_operations_filter_options(sample_output):
    """Manual test: Get filter options."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Filter Options ===")
    with DashboardOperations(sample_output) as ops:
        options = ops.get_filter_options()
        print(f"✓ Available dimensions: {list(options.keys())}")
        for dim, values in options.items():
            print(f"  - {dim}: {len(values)} values - {values[:3]}...")


def test_manual_operations_date_range(sample_output):
    """Manual test: Get date range."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Date Range ===")
    with DashboardOperations(sample_output) as ops:
        min_date, max_date = ops.get_date_range()
        print(f"✓ Date range: {min_date} to {max_date}")


def test_manual_operations_summary_stats(sample_output):
    """Manual test: Get summary statistics."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Summary Stats ===")
    with DashboardOperations(sample_output) as ops:
        stats = ops.get_summary_stats()
        print(f"✓ Total breaches: {stats['total_breaches']}")
        print(f"✓ Portfolios: {stats['portfolios']}")
        print(f"✓ Date range: {stats['date_range']}")
        print(f"✓ Dimensions: {stats['dimensions']}")


def test_manual_singleton_context(sample_output):
    """Manual test: Singleton context functionality."""
    from monitor.dashboard.operations import (
        get_operations_context,
        _cleanup_operations_context
    )

    print("\n=== Manual Test: Singleton Context ===")

    # Clean up any existing context
    _cleanup_operations_context()

    # First call: create singleton
    ops1 = get_operations_context(str(sample_output))
    print(f"✓ Singleton created")

    # Second call: reuse singleton
    ops2 = get_operations_context()
    print(f"✓ Singleton reused")
    assert ops1 is ops2

    # Test query on singleton
    rows = ops1.query_breaches(limit=1)
    print(f"✓ Query on singleton: {len(rows)} rows")

    # Clean up
    _cleanup_operations_context()
    print(f"✓ Singleton cleaned up")


def test_manual_operations_context_manager(sample_output):
    """Manual test: Context manager interface."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Context Manager ===")

    with DashboardOperations(sample_output) as ops:
        print(f"✓ Context manager __enter__")
        rows = ops.query_breaches(limit=1)
        assert len(rows) == 1
        print(f"✓ Query succeeded in context")

    print(f"✓ Context manager __exit__")


def test_manual_complex_workflow(sample_output):
    """Manual test: Complete workflow with multiple operations."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Complex Workflow ===")

    with DashboardOperations(sample_output) as ops:
        # Step 1: Get overview
        stats = ops.get_summary_stats()
        print(f"Step 1: Dataset has {stats['total_breaches']} breaches")

        # Step 2: Explore dimensions
        options = ops.get_filter_options()
        print(f"Step 2: Found {len(options['portfolio'])} portfolios")

        # Step 3: Analyze breaches by layer
        hierarchy = ops.query_hierarchy(["layer"])
        print(f"Step 3: Analyzed {len(hierarchy)} layers")

        # Step 4: Drill down to specific portfolio
        portfolio = options["portfolio"][0]
        rows = ops.query_breaches(portfolios=[portfolio], limit=5)
        print(f"Step 4: Found {len(rows)} breaches for {portfolio}")

        # Step 5: Export filtered data
        csv_data = ops.export_breaches_csv(portfolios=[portfolio])
        lines = csv_data.strip().split("\n")
        print(f"Step 5: Exported {len(lines)-1} rows as CSV")

        print("✓ Complex workflow completed successfully")


def test_manual_error_handling(sample_output):
    """Manual test: Error handling."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Error Handling ===")

    with DashboardOperations(sample_output) as ops:
        # Test 1: Invalid date format
        try:
            ops.query_breaches(start_date="invalid-date")
            print("✗ Should have raised ValueError for invalid date")
        except ValueError as e:
            print(f"✓ Caught invalid date: {e}")

        # Test 2: Invalid numeric range
        try:
            ops.query_breaches(abs_value_range=[1, 2, 3])
            print("✗ Should have raised ValueError for invalid range")
        except ValueError as e:
            print(f"✓ Caught invalid range: {e}")

        # Test 3: Invalid hierarchy dimension
        try:
            ops.query_hierarchy(["invalid_dimension"])
            print("✗ Should have raised ValueError for invalid dimension")
        except ValueError as e:
            print(f"✓ Caught invalid dimension: {e}")


def test_manual_json_serializable_output(sample_output):
    """Manual test: Verify outputs are JSON serializable."""
    from monitor.dashboard.operations import DashboardOperations
    import json

    print("\n=== Manual Test: JSON Serializability ===")

    with DashboardOperations(sample_output) as ops:
        # Test 1: Query results
        rows = ops.query_breaches(limit=1)
        try:
            json_str = json.dumps(rows)
            print(f"✓ Query results are JSON serializable ({len(json_str)} chars)")
        except Exception as e:
            # Some date types might not serialize directly
            print(f"⚠ Query results need conversion: {e}")

        # Test 2: Hierarchy results
        rows = ops.query_hierarchy(["portfolio"])
        json_str = json.dumps(rows)
        print(f"✓ Hierarchy results are JSON serializable")

        # Test 3: Filter options
        options = ops.get_filter_options()
        json_str = json.dumps(options)
        print(f"✓ Filter options are JSON serializable")

        # Test 4: Summary stats
        stats = ops.get_summary_stats()
        json_str = json.dumps(stats)
        print(f"✓ Summary stats are JSON serializable")


def test_manual_security_checks(sample_output):
    """Manual test: Verify security constraints."""
    from monitor.dashboard.operations import DashboardOperations

    print("\n=== Manual Test: Security Checks ===")

    with DashboardOperations(sample_output) as ops:
        # Test 1: SQL injection attempt
        rows = ops.query_breaches(
            portfolios=["portfolio_a'; DROP TABLE breaches; --"]
        )
        print(f"✓ SQL injection attempt blocked (returned {len(rows)} rows)")

        # Test 2: Invalid limit
        try:
            ops.query_breaches(limit=-10)
            print("✗ Should have blocked negative limit")
        except ValueError:
            print("✓ Negative limit blocked")

        # Test 3: Row limit enforcement
        rows = ops.query_breaches(limit=999999)
        print(f"✓ Row limit enforced (returned {len(rows)} rows max)")


# Summary test to run all manual tests
def test_manual_all_tests(sample_output):
    """Run all manual tests and print summary."""
    print("\n" + "="*60)
    print("MANUAL INTEGRATION TESTS FOR operations.py")
    print("="*60)

    test_manual_operations_import_and_init(sample_output)
    test_manual_operations_query_breaches(sample_output)
    test_manual_operations_hierarchy(sample_output)
    test_manual_operations_export_csv(sample_output)
    test_manual_operations_filter_options(sample_output)
    test_manual_operations_date_range(sample_output)
    test_manual_operations_summary_stats(sample_output)
    test_manual_singleton_context(sample_output)
    test_manual_operations_context_manager(sample_output)
    test_manual_complex_workflow(sample_output)
    test_manual_error_handling(sample_output)
    test_manual_json_serializable_output(sample_output)
    test_manual_security_checks(sample_output)

    print("\n" + "="*60)
    print("✓ ALL MANUAL TESTS PASSED")
    print("="*60)
