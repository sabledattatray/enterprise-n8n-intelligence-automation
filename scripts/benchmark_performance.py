#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Performance & Concurrency Benchmarking Suite

Executes rigorous performance, latency percentile, and concurrency benchmarking
against the live FastAPI service and PostgreSQL analytics warehouse.
Records genuine, reproducible metrics without fabrication.
"""

import concurrent.futures
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import httpx
from sqlalchemy import create_engine, text

# Load environment configuration
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "")
DB_URL = os.getenv("LOCAL_DATABASE_URL", "postgresql+psycopg://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/business_analytics")

HEADERS = {
    "X-API-Key": API_KEY,
    "X-Correlation-ID": "benchmark_perf_suite",
    "Content-Type": "application/json",
}


def benchmark_endpoint(client: httpx.Client, method: str, path: str, payload=None, n_requests=30) -> dict:
    """Measures latency distribution (p50, p95, p99, mean, rps) for an endpoint."""
    latencies_ms = []
    status_codes = []

    for _ in range(n_requests):
        t0 = time.perf_counter()
        if method == "GET":
            resp = client.get(f"{API_BASE}{path}", headers=HEADERS)
        else:
            resp = client.post(f"{API_BASE}{path}", headers=HEADERS, json=payload)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)
        status_codes.append(resp.status_code)

    latencies_ms.sort()
    p50 = statistics.median(latencies_ms)
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
    p99 = latencies_ms[int(len(latencies_ms) * 0.99)]
    mean_lat = statistics.mean(latencies_ms)
    min_lat = min(latencies_ms)
    max_lat = max(latencies_ms)
    success_rate = (sum(1 for s in status_codes if 200 <= s < 300) / len(status_codes)) * 100.0

    return {
        "endpoint": f"{method} {path}",
        "total_requests": n_requests,
        "success_rate_pct": success_rate,
        "min_ms": round(min_lat, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max_lat, 2),
        "mean_ms": round(mean_lat, 2),
    }


def benchmark_concurrent_load(concurrency_levels=[1, 5, 10], requests_per_level=50) -> list:
    """Measures system throughput under concurrent load."""
    results = []

    def make_req():
        with httpx.Client(timeout=10.0) as c:
            t0 = time.perf_counter()
            r = c.get(f"{API_BASE}/v1/kpis/latest", headers=HEADERS)
            t1 = time.perf_counter()
            return (t1 - t0) * 1000.0, r.status_code

    for c_level in concurrency_levels:
        t_start = time.perf_counter()
        latencies = []
        codes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=c_level) as executor:
            futures = [executor.submit(make_req) for _ in range(requests_per_level)]
            for fut in concurrent.futures.as_completed(futures):
                lat, code = fut.result()
                latencies.append(lat)
                codes.append(code)
        t_total = time.perf_counter() - t_start
        rps = round(requests_per_level / t_total, 2)
        latencies.sort()

        results.append({
            "concurrency": c_level,
            "requests": requests_per_level,
            "elapsed_seconds": round(t_total, 3),
            "throughput_rps": rps,
            "p50_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
            "success_rate_pct": round((sum(1 for s in codes if s == 200) / len(codes)) * 100.0, 1),
        })

    return results


def benchmark_database_queries() -> list:
    """Measures PostgreSQL query execution speed on 8,564 fact records."""
    engine = create_engine(DB_URL)
    queries = [
        ("Full Fact Table Aggregation", "SELECT COUNT(*), SUM(revenue), SUM(profit) FROM fact_orders"),
        ("Multi-Dimension Join (30-day)", """
            SELECT d.full_date, p.category, SUM(f.revenue) AS daily_rev
            FROM fact_orders f
            JOIN dim_date d ON f.order_date_key = d.date_key
            JOIN dim_product p ON f.product_key = p.product_key
            GROUP BY d.full_date, p.category
            ORDER BY d.full_date DESC, daily_rev DESC
            LIMIT 50
        """),
        ("Geography Breakdown with Margin", """
            SELECT g.country_code, g.region, COUNT(f.order_key) AS orders,
                   SUM(f.revenue) AS rev, SUM(f.profit) AS profit,
                   ROUND((SUM(f.profit) / NULLIF(SUM(f.revenue), 0) * 100)::numeric, 2) AS margin_pct
            FROM fact_orders f
            JOIN dim_geography g ON f.geography_key = g.geography_key
            GROUP BY g.country_code, g.region
            ORDER BY rev DESC
        """),
    ]

    db_results = []
    with engine.connect() as conn:
        for name, sql in queries:
            times = []
            for _ in range(20):
                t0 = time.perf_counter()
                conn.execute(text(sql)).fetchall()
                t1 = time.perf_counter()
                times.append((t1 - t0) * 1000.0)
            times.sort()
            db_results.append({
                "query_name": name,
                "p50_ms": round(statistics.median(times), 2),
                "p95_ms": round(times[int(len(times) * 0.95)], 2),
                "mean_ms": round(statistics.mean(times), 2),
            })
    engine.dispose()
    return db_results


def main():
    print("=" * 80)
    print("EIAP PERFORMANCE & CONCURRENCY BENCHMARKING SUITE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Endpoint Latency Benchmarks
    print("\n[Step 1] Measuring Core Endpoint Latencies (30 iterations each)...")
    endpoints_to_test = [
        ("GET", "/health/live", None),
        ("GET", "/health/ready", None),
        ("GET", "/v1/kpis/latest", None),
        ("GET", "/v1/operations/health", None),
        ("GET", "/v1/reports/history", None),
        ("GET", "/v1/anomalies/open", None),
        ("POST", "/v1/ai/generate", {
            "period_start": "2026-07-01T00:00:00Z",
            "period_end": "2026-09-30T23:59:59Z",
            "currency_code": "USD",
            "materialize": False,
        }),
    ]

    endpoint_results = []
    with httpx.Client(timeout=15.0) as client:
        for method, path, payload in endpoints_to_test:
            res = benchmark_endpoint(client, method, path, payload=payload, n_requests=30)
            endpoint_results.append(res)
            print(f"  {res['endpoint']:<45} | p50: {res['p50_ms']:>6.2f}ms | p95: {res['p95_ms']:>6.2f}ms | Success: {res['success_rate_pct']}%")

    # 2. Concurrency Load Test
    print("\n[Step 2] Executing Concurrency Load Test (50 requests at C=1, 5, 10)...")
    concurrency_results = benchmark_concurrent_load(concurrency_levels=[1, 5, 10], requests_per_level=50)
    for cr in concurrency_results:
        print(f"  Concurrency: {cr['concurrency']:>2} workers | Throughput: {cr['throughput_rps']:>6.2f} req/s | p50: {cr['p50_ms']:>6.2f}ms | p95: {cr['p95_ms']:>6.2f}ms | Success: {cr['success_rate_pct']}%")

    # 3. Database Execution Benchmarks
    print("\n[Step 3] Measuring PostgreSQL Analytic Query Latencies (20 iterations each)...")
    db_results = benchmark_database_queries()
    for dbr in db_results:
        print(f"  {dbr['query_name']:<40} | p50: {dbr['p50_ms']:>6.2f}ms | p95: {dbr['p95_ms']:>6.2f}ms | Mean: {dbr['mean_ms']:>6.2f}ms")

    # 4. Save structured results
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    benchmark_data = {
        "benchmark_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": "Docker Local Dev (127.0.0.1)",
        "endpoint_latencies": endpoint_results,
        "concurrency_benchmarks": concurrency_results,
        "database_benchmarks": db_results,
    }
    with open(out_dir / "latest_benchmark_results.json", "w") as f:
        json.dump(benchmark_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"BENCHMARK COMPLETED. Results written to: docs/performance/latest_benchmark_results.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
