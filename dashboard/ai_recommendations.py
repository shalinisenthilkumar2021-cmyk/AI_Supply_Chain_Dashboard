"""
AI Recommendations Panel
Generates intelligent supply chain recommendations based on KPIs, anomalies,
low stock, and forecast data. Uses pattern rules + optional Claude API.
"""
import numpy as np
import pandas as pd


# ── Rule-based recommendations ────────────────────────────────────────────────

def generate_recommendations(df: pd.DataFrame, kpis: dict, anomalies: dict,
                              low_stock: dict = None, forecast: dict = None) -> list:
    recs = []

    # 1. Low stock warnings
    if low_stock and not low_stock.get('error'):
        pct = low_stock.get('low_stock_pct', 0)
        count = low_stock.get('low_stock_count', 0)
        if pct > 30:
            recs.append({
                'priority': 'HIGH',
                'icon': '🚨',
                'category': 'Inventory',
                'title': f'Critical Low Stock — {pct}% items below threshold',
                'detail': f'{count} items at or below reorder threshold ({low_stock["threshold"]} units). Immediate restocking recommended.',
                'action': 'Raise purchase orders immediately for flagged SKUs.',
            })
        elif pct > 10:
            recs.append({
                'priority': 'MEDIUM',
                'icon': '⚠️',
                'category': 'Inventory',
                'title': f'Low Stock Warning — {pct}% items below threshold',
                'detail': f'{count} items approaching depletion. Plan restocking within 7 days.',
                'action': 'Review and trigger reorder for affected items.',
            })

    # 2. Anomaly warnings
    if anomalies:
        col_list = list(anomalies.keys())[:3]
        total_anomalies = sum(v['count'] for v in anomalies.values())
        recs.append({
            'priority': 'HIGH' if total_anomalies > 10 else 'MEDIUM',
            'icon': '🔍',
            'category': 'Data Quality',
            'title': f'Anomalies Detected — {total_anomalies} outliers in {len(anomalies)} column(s)',
            'detail': f'Columns affected: {", ".join(col_list)}. These may indicate data entry errors, supply disruptions, or demand spikes.',
            'action': 'Investigate flagged records before making procurement decisions.',
        })

    # 3. Profit margin
    margin = kpis.get('profit_margin_pct')
    if margin is not None:
        if margin < 5:
            recs.append({
                'priority': 'HIGH',
                'icon': '📉',
                'category': 'Financials',
                'title': f'Low Profit Margin — {margin}%',
                'detail': 'Margin below 5% signals cost pressure or pricing issues.',
                'action': 'Review procurement costs, supplier contracts, and pricing strategy.',
            })
        elif margin > 25:
            recs.append({
                'priority': 'LOW',
                'icon': '📈',
                'category': 'Financials',
                'title': f'Strong Margin — {margin}%',
                'detail': 'Above-average margin. Consider reinvesting in capacity or buffer stock.',
                'action': 'Explore volume discounts with top-performing suppliers.',
            })

    # 4. Missing values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    missing_pct = df[numeric_cols].isnull().mean().mean() * 100
    if missing_pct > 5:
        recs.append({
            'priority': 'MEDIUM',
            'icon': '🧹',
            'category': 'Data Quality',
            'title': f'Data Quality Score Alert — {100 - missing_pct:.0f}/100',
            'detail': f'{missing_pct:.1f}% of numeric values are missing. This reduces forecast accuracy.',
            'action': 'Audit data sources and fill gaps before running forecasts.',
        })

    # 5. Forecast stockout
    if forecast and forecast.get('stockout_date'):
        recs.append({
            'priority': 'HIGH',
            'icon': '📦',
            'category': 'Inventory',
            'title': f'Stockout Predicted — {forecast["stockout_date"]}',
            'detail': 'Inventory forecast shows stock reaching zero. Supply chain disruption risk.',
            'action': f'Place replenishment order before {forecast["stockout_date"]} to avoid stockout.',
        })

    # 6. Data size warning
    if len(df) < 30:
        recs.append({
            'priority': 'LOW',
            'icon': '📊',
            'category': 'Data Quality',
            'title': 'Small Dataset — Forecast Confidence Low',
            'detail': f'Only {len(df)} rows. Forecasts and anomaly detection work best with 100+ rows.',
            'action': 'Upload a larger historical dataset for more reliable insights.',
        })

    if not recs:
        recs.append({
            'priority': 'LOW',
            'icon': '✅',
            'category': 'General',
            'title': 'No Critical Issues Detected',
            'detail': 'Your supply chain metrics look healthy based on current data.',
            'action': 'Continue monitoring. Run anomaly detection regularly.',
        })

    # Sort: HIGH → MEDIUM → LOW
    order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    recs.sort(key=lambda r: order.get(r['priority'], 9))
    return recs


def data_quality_score(df: pd.DataFrame) -> dict:
    """
    Composite data quality score 0–100.
    Factors: completeness, uniqueness, numeric parsability.
    """
    total_cells = df.size
    missing_cells = df.isnull().sum().sum()
    completeness = 1 - (missing_cells / total_cells) if total_cells else 1

    dup_rows = df.duplicated().sum()
    uniqueness = 1 - (dup_rows / len(df)) if len(df) else 1

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_ratio = len(numeric_cols) / len(df.columns) if len(df.columns) else 0
    parsability = min(1.0, 0.5 + numeric_ratio * 0.5)

    score = round((completeness * 0.5 + uniqueness * 0.3 + parsability * 0.2) * 100, 1)

    return {
        'score': score,
        'grade': 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D',
        'completeness_pct': round(completeness * 100, 1),
        'uniqueness_pct':   round(uniqueness * 100, 1),
        'parsability_pct':  round(parsability * 100, 1),
        'missing_cells':    int(missing_cells),
        'duplicate_rows':   int(dup_rows),
    }
