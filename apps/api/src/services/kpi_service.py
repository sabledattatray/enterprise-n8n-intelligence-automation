import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from apps.api.src.models.entities import IngestionRun, KPISnapshot
from apps.api.src.schemas.kpi import (
    CategoryBreakdown,
    DailyTrend,
    GeographyBreakdown,
    KPIBreakdowns,
    KPIComputeRequest,
    KPISnapshotData,
)

logger = logging.getLogger("eiap.kpi")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KPIService:
    def __init__(self, db: Session):
        self.db = db

    def compute_kpis(self, req: KPIComputeRequest, materialize: bool = True) -> KPISnapshotData:
        """
        Executes safe, null-safe, zero-division-protected SQL aggregations over fact_orders
        and associated dimension tables. Aggregates only single-currency records.
        Materializes snapshot into kpi_snapshots.
        """
        currency = req.currency_code or "USD"

        # Build dynamic WHERE clause to ensure unambiguous parameter types in psycopg3
        where_clauses = ["f.currency_code = :currency"]
        params: Dict[str, Any] = {"currency": currency}

        if req.period_start:
            where_clauses.append("d.full_date >= :period_start")
            params["period_start"] = req.period_start.date()

        if req.period_end:
            where_clauses.append("d.full_date <= :period_end")
            params["period_end"] = req.period_end.date()

        where_sql = " AND ".join(where_clauses)

        # 1. Main KPI aggregation query
        sql_summary = text(f"""
            SELECT
                COALESCE(SUM(f.revenue), 0) AS total_revenue,
                COALESCE(SUM(f.cost), 0) AS total_cost,
                COALESCE(SUM(f.profit), 0) AS gross_profit,
                ROUND(
                    COALESCE(SUM(f.profit), 0) / NULLIF(COALESCE(SUM(f.revenue), 0), 0) * 100,
                    4
                ) AS margin_pct,
                COUNT(DISTINCT f.external_order_id) AS total_orders,
                ROUND(
                    COALESCE(SUM(f.revenue), 0) / NULLIF(COUNT(DISTINCT f.external_order_id), 0),
                    4
                ) AS average_order_value,
                ROUND(
                    COUNT(CASE WHEN f.order_status = 'CANCELLED' THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100,
                    4
                ) AS cancellation_rate_pct,
                MIN(d.full_date) AS min_date,
                MAX(d.full_date) AS max_date
            FROM fact_orders f
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE {where_sql}
        """)

        row = self.db.execute(sql_summary, params).mappings().first()
        if not row or row["total_orders"] == 0:
            logger.warning(f"No fact records found for currency '{currency}'. Returning empty KPI snapshot.")
            total_revenue = 0.0
            total_cost = 0.0
            gross_profit = 0.0
            margin_pct = 0.0
            total_orders = 0
            aov = 0.0
            cancellation_rate = 0.0
            period_start = req.period_start or utc_now()
            period_end = req.period_end or utc_now()
        else:
            total_revenue = float(row["total_revenue"])
            total_cost = float(row["total_cost"])
            gross_profit = float(row["gross_profit"])
            margin_pct = float(row["margin_pct"] or 0.0)
            total_orders = int(row["total_orders"])
            aov = float(row["average_order_value"] or 0.0)
            cancellation_rate = float(row["cancellation_rate_pct"] or 0.0)
            period_start = req.period_start or (
                datetime.combine(row["min_date"], datetime.min.time(), tzinfo=timezone.utc)
                if row["min_date"]
                else utc_now()
            )
            period_end = req.period_end or (
                datetime.combine(row["max_date"], datetime.max.time(), tzinfo=timezone.utc)
                if row["max_date"]
                else utc_now()
            )

        # 2. Product Category breakdown
        sql_cat = text(f"""
            SELECT
                p.category,
                COALESCE(SUM(f.revenue), 0) AS revenue,
                COALESCE(SUM(f.cost), 0) AS cost,
                COALESCE(SUM(f.profit), 0) AS profit,
                ROUND(
                    COALESCE(SUM(f.profit), 0) / NULLIF(COALESCE(SUM(f.revenue), 0), 0) * 100,
                    2
                ) AS margin_pct,
                COUNT(DISTINCT f.external_order_id) AS order_count
            FROM fact_orders f
            JOIN dim_product p ON f.product_key = p.product_key
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE {where_sql}
            GROUP BY p.category
            ORDER BY revenue DESC
        """)
        cat_rows = self.db.execute(sql_cat, params).mappings().all()
        by_category = [
            CategoryBreakdown(
                category=r["category"],
                revenue=float(r["revenue"]),
                cost=float(r["cost"]),
                profit=float(r["profit"]),
                margin_pct=float(r["margin_pct"] or 0.0),
                order_count=int(r["order_count"]),
            )
            for r in cat_rows
        ]

        # 3. Geography breakdown
        sql_geo = text(f"""
            SELECT
                g.country_code,
                g.region,
                COALESCE(SUM(f.revenue), 0) AS revenue,
                COALESCE(SUM(f.profit), 0) AS profit,
                COUNT(DISTINCT f.external_order_id) AS order_count
            FROM fact_orders f
            JOIN dim_geography g ON f.geography_key = g.geography_key
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE {where_sql}
            GROUP BY g.country_code, g.region
            ORDER BY revenue DESC
        """)
        geo_rows = self.db.execute(sql_geo, params).mappings().all()
        by_geography = [
            GeographyBreakdown(
                country_code=r["country_code"],
                region=r["region"],
                revenue=float(r["revenue"]),
                profit=float(r["profit"]),
                order_count=int(r["order_count"]),
            )
            for r in geo_rows
        ]

        # 4. Daily trends
        sql_trend = text(f"""
            SELECT
                d.full_date,
                COALESCE(SUM(f.revenue), 0) AS revenue,
                COUNT(DISTINCT f.external_order_id) AS orders,
                COALESCE(SUM(f.profit), 0) AS profit
            FROM fact_orders f
            JOIN dim_date d ON f.order_date_key = d.date_key
            WHERE {where_sql}
            GROUP BY d.full_date
            ORDER BY d.full_date ASC
        """)
        trend_rows = self.db.execute(sql_trend, params).mappings().all()
        daily_trends = [
            DailyTrend(
                date=r["full_date"].isoformat(),
                revenue=float(r["revenue"]),
                orders=int(r["orders"]),
                profit=float(r["profit"]),
            )
            for r in trend_rows
        ]

        # 5. Calculate data quality score
        quality_score = 100.0
        if req.source_run_id:
            run = self.db.query(IngestionRun).filter(IngestionRun.run_id == req.source_run_id).first()
            if run and run.total_rows > 0:
                quality_score = round((run.accepted_rows / run.total_rows) * 100.0, 2)

        # 6. Materialize snapshot into kpi_snapshots table if requested
        snapshot_id = uuid.uuid4()
        now = utc_now()
        if materialize:
            snapshot = KPISnapshot(
                snapshot_id=snapshot_id,
                period_start=period_start,
                period_end=period_end,
                currency_code=currency,
                revenue=Decimal(str(round(total_revenue, 4))),
                cost=Decimal(str(round(total_cost, 4))),
                profit=Decimal(str(round(gross_profit, 4))),
                orders=total_orders,
                margin_pct=Decimal(str(round(margin_pct, 4))),
                quality_score=Decimal(str(quality_score)),
                computed_at=now,
                source_run_id=req.source_run_id if req.source_run_id else None,
            )
            self.db.add(snapshot)
            self.db.commit()

            logger.info(
                f"Materialized KPI snapshot {snapshot_id}: Orders={total_orders}, Revenue=${total_revenue:,.2f}, Profit=${gross_profit:,.2f}, Margin={margin_pct:.2f}%"
            )

        return KPISnapshotData(
            snapshot_id=snapshot_id,
            period_start=period_start,
            period_end=period_end,
            currency_code=currency,
            revenue=round(total_revenue, 2),
            cost=round(total_cost, 2),
            profit=round(gross_profit, 2),
            margin_pct=round(margin_pct, 2),
            orders=total_orders,
            average_order_value=round(aov, 2),
            cancellation_rate_pct=round(cancellation_rate, 2),
            quality_score=quality_score,
            computed_at=now,
            source_run_id=req.source_run_id,
            breakdowns=KPIBreakdowns(
                by_category=by_category,
                by_geography=by_geography,
                daily_trends=daily_trends,
            ),
        )
