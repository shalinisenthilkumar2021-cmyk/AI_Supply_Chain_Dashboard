import pandas as pd
import numpy as np
import pdfplumber
import io
import json
from scipy import stats


# ─────────────────────────────────────────────
# FILE LOADING
# ─────────────────────────────────────────────

def load_file(file_obj, file_type):
    """Load CSV, Excel, or PDF into a DataFrame."""
    if file_type == 'csv':
        df = pd.read_csv(file_obj)
    elif file_type == 'excel':
        df = pd.read_excel(file_obj, engine='openpyxl')
    elif file_type == 'pdf':
        df = extract_pdf_tables(file_obj)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
    return df


def extract_pdf_tables(file_obj):
    """Extract tables from a PDF using pdfplumber, return as DataFrame."""
    all_tables = []
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table and len(table) > 1:
                    headers = table[0]
                    rows = table[1:]
                    df = pd.DataFrame(rows, columns=headers)
                    all_tables.append(df)
    if all_tables:
        return pd.concat(all_tables, ignore_index=True)
    raise ValueError("No tables found in PDF. Please upload a PDF that contains tabular data.")


# ─────────────────────────────────────────────
# DATA CLEANING
# ─────────────────────────────────────────────

def clean_dataframe(df):
    """
    Perform full data cleaning:
    - Remove duplicates
    - Fill/drop missing values
    - Convert numeric columns
    - Strip whitespace from strings
    Returns (cleaned_df, cleaning_report dict)
    """
    report = {}

    original_rows = len(df)
    df = df.drop_duplicates()
    report['duplicates_removed'] = original_rows - len(df)

    report['missing_before'] = int(df.isnull().sum().sum())

    # Strip string whitespace
    str_cols = df.select_dtypes(include='object').columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({'nan': np.nan, 'None': np.nan, '': np.nan})

    # Try to coerce object columns to numeric
    for col in str_cols:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass

    # Fill numeric NaN with column median
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        median = df[col].median()
        df[col] = df[col].fillna(median)

    # Fill remaining string NaN with 'Unknown'
    df = df.fillna('Unknown')

    report['missing_after'] = int(df.isnull().sum().sum())
    report['final_rows'] = len(df)
    report['final_cols'] = len(df.columns)

    return df, report


# ─────────────────────────────────────────────
# DATASET SUMMARY
# ─────────────────────────────────────────────

def get_dataset_summary(df):
    """Return a dict summary of the dataset."""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include='object').columns.tolist()

    summary = {
        'rows': len(df),
        'columns': len(df.columns),
        'numeric_columns': num_cols,
        'categorical_columns': cat_cols,
        'missing_values': int(df.isnull().sum().sum()),
        'dtypes': df.dtypes.astype(str).to_dict(),
    }

    if num_cols:
        desc = df[num_cols].describe().round(2)
        summary['stats'] = desc.to_dict()

    return summary


# ─────────────────────────────────────────────
# KPI CALCULATIONS
# ─────────────────────────────────────────────

def calculate_kpis(df):
    """Auto-detect revenue/profit/quantity columns and compute KPIs."""
    kpis = {}
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    def find_col(keywords):
        for col in df.columns:
            if any(k in col.lower() for k in keywords):
                return col
        return num_cols[0] if num_cols else None

    rev_col = find_col(['revenue', 'sales', 'income', 'amount', 'total'])
    profit_col = find_col(['profit', 'margin', 'net', 'earning'])
    qty_col = find_col(['quantity', 'qty', 'units', 'count', 'volume'])

    if rev_col:
        kpis['total_revenue'] = round(float(df[rev_col].sum()), 2)
        kpis['avg_revenue'] = round(float(df[rev_col].mean()), 2)
        kpis['revenue_column'] = rev_col

    if profit_col and profit_col != rev_col:
        kpis['total_profit'] = round(float(df[profit_col].sum()), 2)
        kpis['avg_profit'] = round(float(df[profit_col].mean()), 2)
        kpis['profit_column'] = profit_col
        if rev_col and kpis.get('total_revenue', 0) != 0:
            kpis['profit_margin_pct'] = round(
                (kpis['total_profit'] / kpis['total_revenue']) * 100, 2)

    if qty_col:
        kpis['total_quantity'] = round(float(df[qty_col].sum()), 2)
        kpis['quantity_column'] = qty_col

    # Growth (month-over-month if date col exists)
    date_col = None
    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col], errors='ignore')
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_col = col
                break
        except Exception:
            pass

    if date_col and rev_col:
        df_sorted = df.sort_values(date_col)
        df_sorted['month'] = df_sorted[date_col].dt.to_period('M')
        monthly = df_sorted.groupby('month')[rev_col].sum()
        if len(monthly) >= 2:
            last = monthly.iloc[-1]
            prev = monthly.iloc[-2]
            if prev != 0:
                kpis['mom_growth_pct'] = round(((last - prev) / prev) * 100, 2)

    kpis['total_records'] = len(df)
    return kpis


# ─────────────────────────────────────────────
# ANOMALY DETECTION
# ─────────────────────────────────────────────

def detect_anomalies_zscore(df, threshold=3.0):
    """Z-Score anomaly detection on numeric columns."""
    anomalies = []
    num_cols = df.select_dtypes(include=[np.number]).columns

    for col in num_cols:
        z_scores = np.abs(stats.zscore(df[col].dropna()))
        outlier_indices = df[col].dropna().index[z_scores > threshold].tolist()
        for idx in outlier_indices:
            anomalies.append({
                'method': 'Z-Score',
                'column': col,
                'row_index': int(idx),
                'value': float(df.loc[idx, col]),
                'z_score': round(float(z_scores[df[col].dropna().index.get_loc(idx)]), 3),
            })

    return anomalies


def detect_anomalies_iqr(df):
    """IQR anomaly detection on numeric columns."""
    anomalies = []
    num_cols = df.select_dtypes(include=[np.number]).columns

    for col in num_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        outliers = df[(df[col] < lower) | (df[col] > upper)]
        for idx, row in outliers.iterrows():
            anomalies.append({
                'method': 'IQR',
                'column': col,
                'row_index': int(idx),
                'value': float(row[col]),
                'lower_bound': round(float(lower), 3),
                'upper_bound': round(float(upper), 3),
            })

    return anomalies


# ─────────────────────────────────────────────
# FORECASTING
# ─────────────────────────────────────────────

def run_forecast(df, periods=30):
    """
    Run Prophet forecast on the first numeric + date column combo found.
    Returns forecast dict or error string.
    """
    try:
        from prophet import Prophet

        date_col = None
        for col in df.columns:
            try:
                converted = pd.to_datetime(df[col], errors='coerce')
                if converted.notna().sum() > len(df) * 0.5:
                    date_col = col
                    df[col] = converted
                    break
            except Exception:
                pass

        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if not date_col or not num_cols:
            return {'error': 'No suitable date + numeric column pair found for forecasting.'}

        target_col = num_cols[0]
        prophet_df = df[[date_col, target_col]].dropna()
        prophet_df.columns = ['ds', 'y']
        prophet_df = prophet_df.sort_values('ds')

        model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)

        result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)
        return {
            'dates': result['ds'].dt.strftime('%Y-%m-%d').tolist(),
            'forecast': result['yhat'].round(2).tolist(),
            'lower': result['yhat_lower'].round(2).tolist(),
            'upper': result['yhat_upper'].round(2).tolist(),
            'target_column': target_col,
        }

    except ImportError:
        return {'error': 'Prophet not installed. Run: pip install prophet'}
    except Exception as e:
        return {'error': str(e)}


# ─────────────────────────────────────────────
# CHART DATA HELPERS
# ─────────────────────────────────────────────

def get_chart_data(df, chart_type='line', x_col=None, y_col=None):
    """Return chart-ready data dict for Plotly."""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include='object').columns.tolist()

    if not x_col:
        x_col = cat_cols[0] if cat_cols else (df.columns[0] if len(df.columns) > 0 else None)
    if not y_col:
        y_col = num_cols[0] if num_cols else None

    if not x_col or not y_col:
        return {}

    grouped = df.groupby(x_col)[y_col].sum().reset_index()

    return {
        'x': grouped[x_col].astype(str).tolist(),
        'y': grouped[y_col].round(2).tolist(),
        'x_col': x_col,
        'y_col': y_col,
        'chart_type': chart_type,
    }
