"""
Core data processing module: cleaning, summary, anomaly detection, forecasting.
"""
import pandas as pd
import numpy as np
import pdfplumber
import json
from pathlib import Path


# ── File Loading ──────────────────────────────────────────────────────────────

def load_dataset(file_path: str) -> pd.DataFrame:
    ext = Path(file_path).suffix.lower()
    if ext == '.csv':
        return pd.read_csv(file_path)
    elif ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    elif ext == '.pdf':
        return extract_pdf_tables(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_pdf_tables(file_path: str) -> pd.DataFrame:
    tables = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            for t in page_tables:
                if t and len(t) > 1:
                    df = pd.DataFrame(t[1:], columns=t[0])
                    tables.append(df)
    if tables:
        return pd.concat(tables, ignore_index=True)
    text_rows = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.splitlines():
                    if line.strip():
                        text_rows.append({'text': line.strip()})
    return pd.DataFrame(text_rows)


# ── Cleaning ──────────────────────────────────────────────────────────────────

def clean_dataset(df: pd.DataFrame) -> tuple:
    report = {}
    original_shape = df.shape

    before = len(df)
    df = df.drop_duplicates()
    report['duplicates_removed'] = before - len(df)

    missing = df.isnull().sum()
    report['missing_before'] = missing[missing > 0].to_dict()

    for col in df.columns:
        if df[col].dtype in [np.float64, np.int64]:
            df[col].fillna(df[col].median(), inplace=True)
        else:
            if df[col].isnull().any():
                mode_val = df[col].mode()
                df[col].fillna(mode_val[0] if len(mode_val) else 'Unknown', inplace=True)

    for col in df.select_dtypes(include='object').columns:
        try:
            df[col] = pd.to_numeric(df[col].str.replace(',', '').str.strip())
        except Exception:
            pass

    report['original_shape'] = original_shape
    report['clean_shape'] = df.shape
    return df, report


# ── Summary ───────────────────────────────────────────────────────────────────

def dataset_summary(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    return {
        'rows': len(df),
        'cols': len(df.columns),
        'numeric_cols': numeric_cols,
        'categorical_cols': cat_cols,
        'missing_values': int(df.isnull().sum().sum()),
        'dtypes': df.dtypes.astype(str).to_dict(),
    }


# ── KPIs ──────────────────────────────────────────────────────────────────────

def compute_kpis(df: pd.DataFrame) -> dict:
    kpis = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    revenue_col = next((c for c in numeric_cols if any(k in c.lower() for k in ['revenue','sales','amount'])), None)
    profit_col  = next((c for c in numeric_cols if 'profit' in c.lower()), None)
    qty_col     = next((c for c in numeric_cols if any(k in c.lower() for k in ['qty','quantity','units'])), None)

    if revenue_col:
        kpis['total_revenue'] = round(float(df[revenue_col].sum()), 2)
        kpis['avg_revenue']   = round(float(df[revenue_col].mean()), 2)
        kpis['revenue_col']   = revenue_col
    if profit_col:
        kpis['total_profit'] = round(float(df[profit_col].sum()), 2)
        kpis['profit_col']   = profit_col
        if revenue_col and kpis.get('total_revenue', 0) != 0:
            kpis['profit_margin_pct'] = round(kpis['total_profit'] / kpis['total_revenue'] * 100, 2)
    if qty_col:
        kpis['total_quantity'] = int(df[qty_col].sum())

    kpis['total_rows']      = len(df)
    kpis['numeric_columns'] = numeric_cols
    return kpis


# ── Anomaly Detection ─────────────────────────────────────────────────────────

def detect_anomalies(df: pd.DataFrame, method: str = 'zscore') -> dict:
    """
    Detects anomalies in all numeric columns.
    For small datasets or low-variance data, uses a relaxed threshold
    so results are still meaningful.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    results = {}

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 3:
            continue

        if method == 'zscore':
            std = series.std()
            if std == 0:
                # All same value — no anomalies possible
                continue
            z = np.abs((series - series.mean()) / std)
            # Use threshold=2.0 for small datasets (< 50 rows), 3.0 for large
            threshold = 2.0 if len(series) < 50 else 3.0
            anomaly_idx = series[z > threshold].index.tolist()

        else:  # IQR
            Q1  = series.quantile(0.25)
            Q3  = series.quantile(0.75)
            IQR = Q3 - Q1
            if IQR == 0:
                # Try using std-based range instead
                mean, std = series.mean(), series.std()
                if std == 0:
                    continue
                anomaly_idx = series[np.abs(series - mean) > 2 * std].index.tolist()
            else:
                # Use 1.0× for small datasets, 1.5× for large
                multiplier = 1.0 if len(series) < 50 else 1.5
                lower = Q1 - multiplier * IQR
                upper = Q3 + multiplier * IQR
                anomaly_idx = series[(series < lower) | (series > upper)].index.tolist()

        if anomaly_idx:
            results[col] = {
                'count':   len(anomaly_idx),
                'indices': anomaly_idx[:20],
                'values':  df.loc[anomaly_idx[:20], col].tolist(),
                'mean':    round(float(series.mean()), 2),
                'std':     round(float(series.std()), 2),
                'min':     round(float(series.min()), 2),
                'max':     round(float(series.max()), 2),
            }

    return results


# ── Forecasting ───────────────────────────────────────────────────────────────

def run_forecast(df: pd.DataFrame, target_col: str, date_col: str = None, periods: int = 30) -> dict:
    """
    Forecast using statsmodels ExponentialSmoothing (Holt-Winters).
    No compiler needed — works on all Windows/Python versions.
    Falls back to simple moving average if statsmodels fails.
    """
    if target_col not in df.columns:
        return {"error": f"Column '{target_col}' not found in dataset."}

    # ── Clean target column ───────────────────────────────────────────────────
    raw = df[target_col].copy()
    if raw.dtype == object:
        raw = raw.astype(str).str.replace("[^0-9.-]", "", regex=True)
    y_series = pd.to_numeric(raw, errors="coerce").dropna().astype(float).reset_index(drop=True)

    if len(y_series) < 4:
        return {"error": f"Column '{target_col}' needs at least 4 numeric rows for forecasting."}

    # ── Build date index ──────────────────────────────────────────────────────
    if date_col and date_col in df.columns and date_col != "":
        dates_raw = pd.to_datetime(df[date_col], errors="coerce")
        valid = dates_raw.notna() & pd.to_numeric(raw, errors="coerce").notna()
        if valid.sum() >= 4:
            hist_dates = dates_raw[valid].reset_index(drop=True)
        else:
            hist_dates = pd.date_range(start="2023-01-01", periods=len(y_series), freq="D")
    else:
        hist_dates = pd.date_range(start="2023-01-01", periods=len(y_series), freq="D")

    # ── Forecast future dates ─────────────────────────────────────────────────
    last_date = pd.to_datetime(hist_dates.iloc[-1] if hasattr(hist_dates, "iloc") else hist_dates[-1])
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=int(periods), freq="D")
    all_dates = list(hist_dates) + list(future_dates)

    # ── Fit model ────────────────────────────────────────────────────────────
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        n = len(y_series)
        # Choose seasonal period safely
        seasonal_periods = 7 if n >= 14 else None
        trend = "add" if n >= 6 else None
        seasonal = "add" if seasonal_periods and n >= seasonal_periods * 2 else None

        model = ExponentialSmoothing(
            y_series,
            trend=trend,
            seasonal=seasonal,
            seasonal_periods=seasonal_periods,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True, use_brute=False)
        yhat_future = fit.forecast(int(periods))

        # Confidence interval (±1.5 std of residuals)
        resid_std = float(np.std(fit.resid)) if hasattr(fit, "resid") else float(y_series.std())
        yhat_all = list(fit.fittedvalues.round(2)) + list(yhat_future.round(2))
        lower_all = [round(v - 1.5 * resid_std, 2) for v in yhat_all]
        upper_all = [round(v + 1.5 * resid_std, 2) for v in yhat_all]

    except Exception:
        # Simple fallback: rolling mean
        window = min(7, len(y_series))
        last_mean = float(y_series.rolling(window).mean().iloc[-1])
        slope = float((y_series.iloc[-1] - y_series.iloc[0]) / max(len(y_series) - 1, 1))
        yhat_hist = y_series.rolling(window, min_periods=1).mean().round(2).tolist()
        yhat_future_vals = [round(last_mean + slope * (i + 1), 2) for i in range(int(periods))]
        yhat_all = yhat_hist + yhat_future_vals
        std = float(y_series.std())
        lower_all = [round(v - std, 2) for v in yhat_all]
        upper_all = [round(v + std, 2) for v in yhat_all]

    return {
        "dates":          [pd.Timestamp(d).strftime("%Y-%m-%d") for d in all_dates],
        "yhat":           yhat_all,
        "yhat_lower":     lower_all,
        "yhat_upper":     upper_all,
        "historical_len": len(y_series),
        "target_col":     target_col,
    }


# ── Low Stock Alert ───────────────────────────────────────────────────────────

def detect_low_stock(df: pd.DataFrame, threshold_pct: float = 0.15) -> list:
    """
    Finds rows where stock/inventory/qty columns are below threshold_pct of max.
    Returns list of dicts with item, column, value, threshold.
    """
    results = []
    stock_keywords = ['stock', 'inventory', 'qty', 'quantity', 'units', 'on_hand', 'available']
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    stock_cols = [c for c in numeric_cols if any(k in c.lower() for k in stock_keywords)]

    if not stock_cols:
        stock_cols = numeric_cols[:3]  # fallback: first 3 numeric cols

    name_col = next((c for c in df.columns if any(k in c.lower() for k in ['product','item','name','sku','id'])), None)

    for col in stock_cols:
        col_max = df[col].max()
        if col_max == 0:
            continue
        thresh = col_max * threshold_pct
        low_rows = df[df[col] <= thresh]
        for idx, row in low_rows.iterrows():
            item_name = str(row[name_col]) if name_col else f"Row {idx}"
            results.append({
                'item':      item_name,
                'column':    col,
                'value':     round(float(row[col]), 2),
                'threshold': round(float(thresh), 2),
                'max':       round(float(col_max), 2),
                'pct':       round(float(row[col]) / col_max * 100, 1),
            })

    results.sort(key=lambda x: x['pct'])
    return results[:50]


# ── Reorder Point Prediction ──────────────────────────────────────────────────

def compute_reorder_points(df: pd.DataFrame) -> list:
    """
    Calculates reorder point: ROP = (avg_daily_demand × lead_time) + safety_stock.
    Uses numeric columns to infer demand, lead time, safety stock.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    demand_col   = next((c for c in numeric_cols if any(k in c.lower() for k in ['demand','sales','sold','usage'])), None)
    lead_col     = next((c for c in numeric_cols if any(k in c.lower() for k in ['lead','leadtime','lead_time'])), None)
    safety_col   = next((c for c in numeric_cols if any(k in c.lower() for k in ['safety','buffer','reserve'])), None)
    name_col     = next((c for c in df.columns if any(k in c.lower() for k in ['product','item','name','sku'])), None)

    results = []
    if demand_col is None:
        return results

    for idx, row in df.iterrows():
        try:
            avg_demand  = float(row[demand_col])
            lead_time   = float(row[lead_col])   if lead_col   else 7.0
            safety_stock= float(row[safety_col]) if safety_col else avg_demand * 0.5
            rop = (avg_demand * lead_time) + safety_stock
            results.append({
                'item':          str(row[name_col]) if name_col else f"Row {idx}",
                'avg_demand':    round(avg_demand, 2),
                'lead_time':     round(lead_time, 2),
                'safety_stock':  round(safety_stock, 2),
                'reorder_point': round(rop, 2),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x['reorder_point'], reverse=True)
    return results[:30]


# ── Supplier Performance ──────────────────────────────────────────────────────

def supplier_performance(df: pd.DataFrame) -> list:
    """
    Aggregates performance metrics per supplier: avg delivery, defect rate,
    fill rate, total orders, performance score (0-100).
    """
    supplier_col = next((c for c in df.columns if any(k in c.lower() for k in
                         ['supplier','vendor','provider','source'])), None)
    if supplier_col is None:
        return []

    delivery_col = next((c for c in df.select_dtypes(include='number').columns if
                         any(k in c.lower() for k in ['delivery','lead','days','time'])), None)
    defect_col   = next((c for c in df.select_dtypes(include='number').columns if
                         any(k in c.lower() for k in ['defect','return','reject','quality'])), None)
    fill_col     = next((c for c in df.select_dtypes(include='number').columns if
                         any(k in c.lower() for k in ['fill','fulfill','complete'])), None)
    cost_col     = next((c for c in df.select_dtypes(include='number').columns if
                         any(k in c.lower() for k in ['cost','price','amount'])), None)

    results = []
    for supplier, grp in df.groupby(supplier_col):
        rec = {'supplier': str(supplier), 'orders': len(grp)}
        score_components = []

        if delivery_col:
            avg_del = grp[delivery_col].mean()
            rec['avg_delivery_days'] = round(float(avg_del), 1)
            # Lower delivery = better; normalize: assume 1-30 day range
            score_components.append(max(0, 100 - (avg_del / 30 * 100)))

        if defect_col:
            avg_def = grp[defect_col].mean()
            rec['avg_defect_rate'] = round(float(avg_def), 2)
            score_components.append(max(0, 100 - avg_def))

        if fill_col:
            avg_fill = grp[fill_col].mean()
            rec['avg_fill_rate'] = round(float(avg_fill), 2)
            score_components.append(min(100, float(avg_fill)))

        if cost_col:
            rec['total_cost'] = round(float(grp[cost_col].sum()), 2)

        rec['score'] = round(float(np.mean(score_components)) if score_components else 50.0, 1)
        results.append(rec)

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


# ── Data Quality Score ────────────────────────────────────────────────────────

def data_quality_score(df: pd.DataFrame) -> dict:
    """
    Returns a composite data quality score (0-100) with breakdown.
    """
    total_cells = df.shape[0] * df.shape[1]
    if total_cells == 0:
        return {'score': 0}

    # Completeness: non-null cells
    completeness = (1 - df.isnull().sum().sum() / total_cells) * 100

    # Uniqueness: no exact duplicate rows
    dup_count = df.duplicated().sum()
    uniqueness = (1 - dup_count / max(len(df), 1)) * 100

    # Consistency: numeric cols with no infinite values
    num_df = df.select_dtypes(include=[np.number])
    inf_count = np.isinf(num_df.values).sum() if len(num_df.columns) else 0
    consistency = (1 - inf_count / max(total_cells, 1)) * 100

    # Validity: numeric cols with valid (non-NaN, non-Inf) ratio
    validity = completeness  # simplified

    score = round((completeness * 0.4 + uniqueness * 0.3 + consistency * 0.2 + validity * 0.1), 1)

    return {
        'score':        min(score, 100.0),
        'completeness': round(completeness, 1),
        'uniqueness':   round(uniqueness, 1),
        'consistency':  round(consistency, 1),
        'validity':     round(validity, 1),
        'total_cells':  total_cells,
        'missing_cells':int(df.isnull().sum().sum()),
        'duplicate_rows':int(dup_count),
        'grade': 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D',
    }


# ── AI Recommendations ────────────────────────────────────────────────────────

def ai_recommendations(df: pd.DataFrame, kpis: dict, anomalies: dict,
                        low_stock: list, quality: dict) -> list:
    """
    Rule-based AI recommendations derived from data analysis.
    Returns list of {priority, category, title, detail} dicts.
    """
    recs = []

    # Data quality
    if quality.get('score', 100) < 75:
        recs.append({
            'priority': 'HIGH', 'category': 'Data Quality',
            'title': f"Data quality score is {quality['score']}% (Grade {quality['grade']})",
            'detail': f"Fix {quality['missing_cells']} missing cells and {quality['duplicate_rows']} duplicate rows to improve accuracy."
        })

    # Low stock
    critical = [s for s in low_stock if s['pct'] < 10]
    if critical:
        items = ', '.join(s['item'] for s in critical[:3])
        recs.append({
            'priority': 'HIGH', 'category': 'Inventory',
            'title': f"{len(critical)} item(s) critically low on stock",
            'detail': f"Immediate reorder needed: {items}"
        })
    elif low_stock:
        recs.append({
            'priority': 'MEDIUM', 'category': 'Inventory',
            'title': f"{len(low_stock)} item(s) approaching reorder threshold",
            'detail': 'Review reorder points and initiate procurement planning.'
        })

    # Anomalies
    if anomalies:
        cols = ', '.join(list(anomalies.keys())[:3])
        total = sum(v['count'] for v in anomalies.values())
        recs.append({
            'priority': 'MEDIUM', 'category': 'Anomaly',
            'title': f"{total} anomalies detected across {len(anomalies)} column(s)",
            'detail': f"Investigate outliers in: {cols}. Possible data errors or supply disruptions."
        })

    # Profit margin
    margin = kpis.get('profit_margin_pct')
    if margin is not None:
        if margin < 10:
            recs.append({
                'priority': 'HIGH', 'category': 'Financial',
                'title': f"Low profit margin: {margin}%",
                'detail': 'Review pricing strategy and cost reduction opportunities.'
            })
        elif margin > 40:
            recs.append({
                'priority': 'LOW', 'category': 'Financial',
                'title': f"Strong profit margin: {margin}%",
                'detail': 'Consider reinvesting in capacity or market expansion.'
            })

    # Dataset size
    if df.shape[0] < 30:
        recs.append({
            'priority': 'LOW', 'category': 'Forecasting',
            'title': 'Small dataset may reduce forecast accuracy',
            'detail': f'Only {df.shape[0]} rows detected. Collect more historical data for reliable Prophet forecasts.'
        })

    if not recs:
        recs.append({
            'priority': 'LOW', 'category': 'General',
            'title': 'No critical issues detected',
            'detail': 'Supply chain data looks healthy. Continue monitoring KPIs and anomalies regularly.'
        })

    # Sort: HIGH first
    order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    recs.sort(key=lambda x: order.get(x['priority'], 9))
    return recs
