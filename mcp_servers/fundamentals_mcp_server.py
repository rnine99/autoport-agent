#!/usr/bin/env python3
"""Fundamentals MCP Server.

Provides raw fundamental data for programmatic analysis via MCP.
Designed for multi-year trend analysis, cross-company comparison, and chart creation.

Tools:
- get_financial_statements: Raw income/balance/cash flow (multi-year)
- get_financial_ratios: Raw ratios and key metrics (multi-year)
- get_growth_metrics: Raw growth rates (multi-year)
- get_historical_valuation: Raw DCF and enterprise value (multi-year)
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("FundamentalsMCP")


def _load_fmp_client():
    """Lazily load FMP client so server can start without FMP_API_KEY."""
    from src.data_client.fmp import FMPClient

    return FMPClient()


@mcp.tool()
async def get_financial_statements(
    symbol: str,
    statement_type: Literal["income", "balance", "cash", "all"] = "all",
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 10,
) -> dict:
    """Fetch raw historical financial statements for multi-year trend analysis.

    Use cases:
    - Plot revenue/earnings growth over 10 years
    - Compare profit margins across competitors
    - Build financial models with historical data

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT)
        statement_type: "income", "balance", "cash", or "all" (default: "all")
        period: "annual" or "quarter" (default: "annual")
        limit: Number of periods to fetch (default: 10)

    Returns:
        Raw JSON with full statement data (all fields, not summarized)
    """
    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}", "symbol": symbol}

    result = {
        "symbol": symbol,
        "data_type": "financial_statements",
        "statement_type": statement_type,
        "period": period,
        "source": "fmp",
    }

    try:
        async with client:
            if statement_type == "income":
                data = await client.get_income_statement(
                    symbol, period=period, limit=limit
                )
                result["data"] = data
                result["count"] = len(data) if data else 0

            elif statement_type == "balance":
                data = await client.get_balance_sheet(
                    symbol, period=period, limit=limit
                )
                result["data"] = data
                result["count"] = len(data) if data else 0

            elif statement_type == "cash":
                data = await client.get_cash_flow(symbol, period=period, limit=limit)
                result["data"] = data
                result["count"] = len(data) if data else 0

            else:  # "all"
                income = await client.get_income_statement(
                    symbol, period=period, limit=limit
                )
                balance = await client.get_balance_sheet(
                    symbol, period=period, limit=limit
                )
                cash_flow = await client.get_cash_flow(
                    symbol, period=period, limit=limit
                )

                result["data"] = {
                    "income_statement": income or [],
                    "balance_sheet": balance or [],
                    "cash_flow": cash_flow or [],
                }
                result["count"] = {
                    "income_statement": len(income) if income else 0,
                    "balance_sheet": len(balance) if balance else 0,
                    "cash_flow": len(cash_flow) if cash_flow else 0,
                }

        return result

    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "symbol": symbol}


@mcp.tool()
async def get_financial_ratios(
    symbol: str,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 10,
) -> dict:
    """Fetch raw historical financial ratios and key metrics for quantitative analysis.

    Use cases:
    - Track P/E, P/B, ROE trends over time
    - Screen stocks by ratio thresholds
    - Compare valuation metrics across companies

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT)
        period: "annual" or "quarter" (default: "annual")
        limit: Number of periods to fetch (default: 10)

    Returns:
        Raw JSON with key metrics and financial ratios per period
    """
    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}", "symbol": symbol}

    try:
        async with client:
            key_metrics = await client.get_key_metrics(
                symbol, period=period, limit=limit
            )
            ratios = await client.get_financial_ratios(
                symbol, period=period, limit=limit
            )

        return {
            "symbol": symbol,
            "data_type": "financial_ratios",
            "period": period,
            "count": {
                "key_metrics": len(key_metrics) if key_metrics else 0,
                "ratios": len(ratios) if ratios else 0,
            },
            "data": {
                "key_metrics": key_metrics or [],
                "ratios": ratios or [],
            },
            "source": "fmp",
        }

    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "symbol": symbol}


@mcp.tool()
async def get_growth_metrics(
    symbol: str,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 10,
) -> dict:
    """Fetch raw historical growth rates for trend analysis.

    Use cases:
    - Chart revenue/EPS growth trajectory
    - Identify growth acceleration/deceleration
    - Compare growth rates across competitors

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT)
        period: "annual" or "quarter" (default: "annual")
        limit: Number of periods to fetch (default: 10)

    Returns:
        Raw JSON with growth rates per period
    """
    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}", "symbol": symbol}

    try:
        async with client:
            financial_growth = await client.get_financial_growth(
                symbol, period=period, limit=limit
            )
            income_growth = await client.get_income_statement_growth(
                symbol, period=period, limit=limit
            )

        return {
            "symbol": symbol,
            "data_type": "growth_metrics",
            "period": period,
            "count": {
                "financial_growth": len(financial_growth) if financial_growth else 0,
                "income_statement_growth": len(income_growth) if income_growth else 0,
            },
            "data": {
                "financial_growth": financial_growth or [],
                "income_statement_growth": income_growth or [],
            },
            "source": "fmp",
        }

    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "symbol": symbol}


@mcp.tool()
async def get_historical_valuation(
    symbol: str,
    period: Literal["annual", "quarter"] = "annual",
    limit: int = 10,
) -> dict:
    """Fetch historical DCF and enterprise value data for valuation analysis.

    Use cases:
    - Track fair value estimates over time
    - Compare current price vs historical DCF
    - Build valuation trend charts

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT)
        period: "annual" or "quarter" (default: "annual")
        limit: Number of periods to fetch (default: 10)

    Returns:
        Raw JSON with current DCF, historical DCF, and enterprise value per period
    """
    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}", "symbol": symbol}

    try:
        async with client:
            current_dcf = await client.get_dcf(symbol)
            historical_dcf = await client.get_historical_dcf(
                symbol, period=period, limit=limit
            )
            enterprise_value = await client.get_enterprise_value(
                symbol, period=period, limit=limit
            )

        return {
            "symbol": symbol,
            "data_type": "historical_valuation",
            "period": period,
            "count": {
                "current_dcf": len(current_dcf) if current_dcf else 0,
                "historical_dcf": len(historical_dcf) if historical_dcf else 0,
                "enterprise_value": len(enterprise_value) if enterprise_value else 0,
            },
            "data": {
                "current_dcf": current_dcf or [],
                "historical_dcf": historical_dcf or [],
                "enterprise_value": enterprise_value or [],
            },
            "source": "fmp",
        }

    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "symbol": symbol}


if __name__ == "__main__":
    mcp.run()
