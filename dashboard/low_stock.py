"""
Low Stock Alert System
Detects products/items with inventory below reorder point.
"""
import pandas as pd
import numpy as np


def detect_low_stock(df: pd.DataFrame, stock_col: str = None, threshold: float = None) -> dict:
    """
    Auto-detect stock/inventory column and flag low-stock items.
    Returns dict with flagged rows, threshold used, and summary.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # Auto-detect stock column
    if not stock_col:
        stock_keywords = ['stock', 'inventory', 'qty', 'quantity', 'units', 'on_hand', 'available', 'balance']
        stock_col = next(
            (c for c in numeric_cols if any(k in c.lower() for k in stock_keywords)),
            numeric_cols[0] if numeric_cols else None
        )

    if not stock_col or stock_col not in df.columns:
        return {'error': 'No stock/inventory column found. Please check your dataset.'}

    series = pd.to_numeric(df[stock_col], errors='coerce').dropna()
    if len(series) == 0:
        return {'error': f"Column '{stock_col}' has no numeric values."}

    # Auto-threshold: 20th percentile if not specified
    if threshold is None:
        threshold = float(series.quantile(0.20))

    low_mask = series <= threshold
    low_indices = series[low_mask].index.tolist()

    # Build result rows
    result_rows = []
    name_col = next((c for c in df.columns if any(k in c.lower() for k in ['name','product','item','sku','description'])), None)
    for idx in low_indices[:50]:
        row = {'index': int(idx), 'stock_value': round(float(df.loc[idx, stock_col]), 2)}
        if name_col:
            row['item_name'] = str(df.loc[idx, name_col])
        result_rows.append(row)

    return {
        'stock_col':    stock_col,
        'threshold':    round(threshold, 2),
        'total_items':  len(series),
        'low_stock_count': len(low_indices),
        'low_stock_pct': round(len(low_indices) / len(series) * 100, 1),
        'items':        result_rows,
        'mean_stock':   round(float(series.mean()), 2),
        'min_stock':    round(float(series.min()), 2),
        'max_stock':    round(float(series.max()), 2),
    }


def compute_reorder_point(df: pd.DataFrame, stock_col: str, demand_col: str = None, lead_time_days: int = 7) -> dict:
    """
    Reorder Point = Average Daily Demand × Lead Time + Safety Stock
    Safety Stock = Z(1.65 for 95%) × std(demand) × sqrt(lead_time)
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not demand_col:
        demand_keywords = ['demand','sales','sold','orders','usage','consumption']
        demand_col = next(
            (c for c in numeric_cols if any(k in c.lower() for k in demand_keywords)),
            None
        )

    if not demand_col:
        return {'error': 'No demand/sales column found for reorder point calculation.'}

    demand_series = pd.to_numeric(df[demand_col], errors='coerce').dropna()
    avg_demand = float(demand_series.mean())
    std_demand = float(demand_series.std())
    safety_stock = round(1.65 * std_demand * (lead_time_days ** 0.5), 2)
    reorder_point = round(avg_demand * lead_time_days + safety_stock, 2)

    return {
        'demand_col':    demand_col,
        'stock_col':     stock_col,
        'lead_time_days': lead_time_days,
        'avg_demand':    round(avg_demand, 2),
        'std_demand':    round(std_demand, 2),
        'safety_stock':  safety_stock,
        'reorder_point': reorder_point,
        'formula':       f'ROP = {avg_demand:.2f} × {lead_time_days} + {safety_stock:.2f} = {reorder_point}',
    }
