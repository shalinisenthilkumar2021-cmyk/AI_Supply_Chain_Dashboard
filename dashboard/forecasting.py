"""
Extended Forecasting: Demand, Inventory, and Supplier Performance.
"""
import pandas as pd
import numpy as np


def forecast_demand(df: pd.DataFrame, target_col: str, date_col: str = None, periods: int = 30) -> dict:
    """Demand forecasting via Prophet — same as core but named explicitly."""
    from .data_processor import run_forecast
    return run_forecast(df, target_col, date_col, periods)


def forecast_inventory(df: pd.DataFrame, stock_col: str, demand_col: str = None, periods: int = 30) -> dict:
    """
    Inventory forecast: projects future stock level by subtracting forecast demand.
    Falls back to Prophet on stock column if demand col is unavailable.
    """
    from .data_processor import run_forecast

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not demand_col:
        demand_keywords = ['demand', 'sales', 'sold', 'orders', 'usage']
        demand_col = next(
            (c for c in numeric_cols if any(k in c.lower() for k in demand_keywords)),
            None
        )

    if demand_col:
        # Simulate inventory: running balance = stock - cumulative demand forecast
        demand_forecast = run_forecast(df, demand_col, None, periods)
        if 'error' in demand_forecast:
            return demand_forecast

        # Coerce stock column — handles mixed int/str types
        raw_stock = df[stock_col].copy()
        if raw_stock.dtype == object:
            raw_stock = raw_stock.astype(str).str.replace('[^0-9.-]', '', regex=True)
        stock_series = pd.to_numeric(raw_stock, errors='coerce').dropna()
        if len(stock_series) == 0:
            return {'error': f"Column '{stock_col}' has no numeric values."}
        current_stock = float(stock_series.iloc[-1])
        future_demand = demand_forecast['yhat'][demand_forecast['historical_len']:]
        future_dates  = demand_forecast['dates'][demand_forecast['historical_len']:]

        projected = []
        balance = current_stock
        stockout_day = None
        for i, (d, dem) in enumerate(zip(future_dates, future_demand)):
            balance = max(0, balance - max(0, dem))
            projected.append({'date': d, 'projected_stock': round(balance, 2)})
            if balance == 0 and stockout_day is None:
                stockout_day = d

        return {
            'type': 'inventory',
            'stock_col': stock_col,
            'demand_col': demand_col,
            'current_stock': current_stock,
            'projected': projected,
            'stockout_date': stockout_day,
            'demand_forecast': demand_forecast,
        }
    else:
        # Fallback: Prophet on stock column
        result = run_forecast(df, stock_col, None, periods)
        result['type'] = 'inventory_prophet_fallback'
        return result


def supplier_performance(df: pd.DataFrame) -> dict:
    """
    Compute supplier KPIs from the dataset.
    Detects supplier, lead time, on-time delivery, and defect rate columns.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    all_cols = df.columns.tolist()

    supplier_col = next(
        (c for c in all_cols if any(k in c.lower() for k in ['supplier', 'vendor', 'partner'])),
        None
    )
    lead_col = next(
        (c for c in numeric_cols if any(k in c.lower() for k in ['lead', 'delivery_time', 'lead_time'])),
        None
    )
    ontime_col = next(
        (c for c in all_cols if any(k in c.lower() for k in ['on_time', 'ontime', 'delivery_status', 'on time'])),
        None
    )
    defect_col = next(
        (c for c in numeric_cols if any(k in c.lower() for k in ['defect', 'return', 'reject', 'quality'])),
        None
    )

    if not supplier_col:
        return {'error': 'No supplier/vendor column detected in dataset.'}

    result = {'supplier_col': supplier_col, 'suppliers': []}

    for supplier, group in df.groupby(supplier_col):
        entry = {'name': str(supplier), 'order_count': len(group)}
        if lead_col:
            entry['avg_lead_time'] = round(float(group[lead_col].mean()), 1)
        if ontime_col:
            ontime_vals = group[ontime_col].astype(str).str.lower()
            ontime_rate = ontime_vals.isin(['yes', '1', 'true', 'on time', 'delivered']).mean()
            entry['ontime_rate_pct'] = round(ontime_rate * 100, 1)
        if defect_col:
            entry['avg_defect_rate'] = round(float(group[defect_col].mean()), 2)

        # Score 0–100
        score = 50
        if 'ontime_rate_pct' in entry:
            score = entry['ontime_rate_pct']
        if 'avg_defect_rate' in entry and entry['avg_defect_rate'] > 0:
            score = max(0, score - entry['avg_defect_rate'] * 2)
        entry['performance_score'] = round(score, 1)
        result['suppliers'].append(entry)

    result['suppliers'].sort(key=lambda x: x['performance_score'], reverse=True)
    return result
