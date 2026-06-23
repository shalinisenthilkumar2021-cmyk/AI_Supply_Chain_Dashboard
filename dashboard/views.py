import os
import json
import pandas as pd
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, JsonResponse
from django.contrib import messages
from django.conf import settings

from .models import UploadedDataset, Alert
from .data_processor import (load_dataset, clean_dataset, dataset_summary, compute_kpis,
                               detect_anomalies, data_quality_score,
                               detect_low_stock, ai_recommendations)
from .chart_builder import line_chart, bar_chart, column_chart, pie_chart, donut_chart, anomaly_chart, stacked_bar_chart, supplier_chart
from .export_utils import export_csv, export_excel, export_pdf_report
from .alert_utils import process_anomaly_alerts
from .low_stock import detect_low_stock, compute_reorder_point
from .ai_recommendations import generate_recommendations, data_quality_score


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_theme(request):
    theme = request.GET.get('theme') or request.session.get('sc_theme', 'dark')
    request.session['sc_theme'] = theme
    return theme

def _get_df(request):
    file_path = request.session.get('current_file')
    if not file_path or not Path(file_path).exists():
        return None
    return load_dataset(file_path)

def _get_dataset(request):
    ds_id = request.session.get('current_dataset_id')
    if ds_id:
        try:
            return UploadedDataset.objects.get(pk=ds_id)
        except UploadedDataset.DoesNotExist:
            pass
    return None

def _base_ctx(request):
    return {
        'current_theme': _get_theme(request),
        'unread_alerts': Alert.objects.filter(is_read=False).count(),
    }


# ── Index ─────────────────────────────────────────────────────────────────────

def index(request):
    ctx = _base_ctx(request)
    ctx['datasets'] = UploadedDataset.objects.order_by('-uploaded_at')[:10]
    return render(request, 'dashboard/index.html', ctx)


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_dataset(request):
    if request.method != 'POST':
        return redirect('index')

    uploaded = request.FILES.get('file')
    if not uploaded:
        messages.error(request, 'No file selected.')
        return redirect('index')

    name = request.POST.get('name') or uploaded.name
    ext = Path(uploaded.name).suffix.lower()
    save_path = Path(settings.UPLOAD_DIR) / uploaded.name

    with open(save_path, 'wb+') as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    try:
        df = load_dataset(str(save_path))
        df, clean_report = clean_dataset(df)
        ds = UploadedDataset.objects.create(
            name=name,
            file_path=str(save_path),
            file_type=ext.lstrip('.'),
            row_count=len(df),
            col_count=len(df.columns),
            columns=json.dumps(df.columns.tolist())
        )
        clean_path = str(save_path).replace(ext, '_clean.csv')
        df.to_csv(clean_path, index=False)
        request.session['current_file'] = clean_path
        request.session['current_dataset_id'] = ds.pk
        removed = clean_report.get('duplicates_removed', 0)
        messages.success(request, f"✅ Uploaded '{name}' — {len(df)} rows, {len(df.columns)} cols. Removed {removed} duplicates.")
    except Exception as e:
        messages.error(request, f'Error processing file: {e}')
        return redirect('index')

    return redirect('dashboard')


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(request):
    df = _get_df(request)
    if df is None:
        messages.warning(request, 'Please upload a dataset first.')
        return redirect('index')

    ctx = _base_ctx(request)
    dataset = _get_dataset(request)
    summary = dataset_summary(df)
    kpis = compute_kpis(df)
    columns = df.columns.tolist()
    numeric_cols = df.select_dtypes(include='number').columns.tolist()

    # Data Quality Score
    dq = data_quality_score(df)

    # Low Stock
    low_stock = detect_low_stock(df)

    # AI Recommendations (quick pass — no anomaly/forecast at page load)
    recs = generate_recommendations(df, kpis, {}, low_stock)

    ctx.update({
        'summary': summary,
        'kpis': kpis,
        'columns': columns,
        'numeric_cols': numeric_cols,
        'dataset': dataset,
        'data_quality': dq,
        'low_stock': low_stock,
        'recommendations': recs,
        'data_preview': df.head(10).to_html(
            classes='table table-sm table-hover text-nowrap',
            border=0, index=False
        ),
    })
    return render(request, 'dashboard/dashboard.html', ctx)


# ── Chart AJAX ────────────────────────────────────────────────────────────────

def build_chart(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    df = _get_df(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)

    chart_type = request.POST.get('chart_type', 'bar')
    x_col = request.POST.get('x_column', '')
    y_cols = request.POST.getlist('y_columns')
    theme = request.POST.get('theme', 'dark')

    if not x_col:
        return JsonResponse({'error': 'X column is required.'}, status=400)
    if not y_cols:
        return JsonResponse({'error': 'Select at least one Y column.'}, status=400)
    if x_col not in df.columns:
        return JsonResponse({'error': f"Column '{x_col}' not found."}, status=400)

    try:
        if chart_type == 'line':
            valid_y = [c for c in y_cols if c in df.columns]
            fig = line_chart(df, x_col, valid_y, title=f'Line: {", ".join(valid_y)} by {x_col}', theme=theme)
        elif chart_type == 'bar':
            fig = bar_chart(df, x_col, y_cols[0], title=f'Bar: {y_cols[0]} by {x_col}', theme=theme)
        elif chart_type == 'column':
            valid_y = [c for c in y_cols if c in df.columns]
            fig = column_chart(df, x_col, valid_y, title=f'Column: {", ".join(valid_y)}', theme=theme)
        elif chart_type == 'pie':
            fig = pie_chart(df, x_col, y_cols[0], title=f'Pie: {y_cols[0]}', theme=theme)
        elif chart_type == 'donut':
            fig = donut_chart(df, x_col, y_cols[0], title=f'Donut: {y_cols[0]}', theme=theme)
        elif chart_type == 'stacked_bar':
            valid_y = [c for c in y_cols if c in df.columns]
            fig = stacked_bar_chart(df, x_col, valid_y, title=f'Stacked Bar: {", ".join(valid_y)}', theme=theme)
        elif chart_type == 'stacked_bar':
            valid_y = [c for c in y_cols if c in df.columns]
            fig = stacked_bar_chart(df, x_col, valid_y, title=f'Stacked Bar: {", ".join(valid_y)}', theme=theme)
        else:
            return JsonResponse({'error': f'Unknown chart type: {chart_type}'}, status=400)
        return JsonResponse({'chart': fig})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# ── Anomaly Detection ─────────────────────────────────────────────────────────

def detect_anomalies_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    df = _get_df(request)
    dataset = _get_dataset(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)

    method = request.POST.get('method', 'zscore')
    theme = request.POST.get('theme', 'dark')
    send_email = request.POST.get('send_email') == 'on'
    email_to = request.POST.get('email_to', '')

    try:
        anomalies = detect_anomalies(df, method)
        charts = {}
        for col, info in anomalies.items():
            charts[col] = anomaly_chart(df, col, info['indices'], theme=theme)
        if dataset and anomalies:
            process_anomaly_alerts(dataset, anomalies, send_email=send_email, email_to=email_to)
        return JsonResponse({'anomalies': anomalies, 'charts': charts})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Export ────────────────────────────────────────────────────────────────────

def export_report(request, format):
    df = _get_df(request)
    if df is None:
        messages.error(request, 'No dataset loaded.')
        return redirect('dashboard')
    summary = dataset_summary(df)
    kpis = compute_kpis(df)
    try:
        if format == 'csv':
            path = export_csv(df, 'report.csv')
            mime = 'text/csv'
        elif format == 'excel':
            path = export_excel(df, 'report.xlsx', summary)
            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif format == 'pdf':
            path = export_pdf_report(df, summary, kpis, 'report.pdf')
            mime = 'application/pdf'
        else:
            messages.error(request, 'Unknown export format.')
            return redirect('dashboard')
        return FileResponse(open(path, 'rb'), as_attachment=True,
                            filename=Path(path).name, content_type=mime)
    except Exception as e:
        messages.error(request, f'Export failed: {e}')
        return redirect('dashboard')


# ── Alerts ────────────────────────────────────────────────────────────────────

def alerts_view(request):
    ctx = _base_ctx(request)
    ctx['alerts'] = Alert.objects.order_by('-created_at')[:50]
    Alert.objects.filter(is_read=False).update(is_read=True)
    return render(request, 'dashboard/alerts.html', ctx)


def load_dataset_session(request, pk):
    ds = get_object_or_404(UploadedDataset, pk=pk)
    ext = Path(ds.file_path).suffix.lower()
    base = Path(ds.file_path).stem
    clean_path = Path(settings.UPLOAD_DIR) / f'{base}_clean.csv'
    if not clean_path.exists():
        clean_path = Path(ds.file_path)
    request.session['current_file'] = str(clean_path)
    request.session['current_dataset_id'] = ds.pk
    messages.success(request, f"Loaded dataset: {ds.name}")
    return redirect('dashboard')


# ── Low Stock Alerts ──────────────────────────────────────────────────────────

def low_stock_view(request):
    df = _get_df(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)
    from .data_processor import detect_low_stock
    try:
        threshold = float(request.GET.get('threshold', 0.15))
    except ValueError:
        threshold = 0.15
    items = detect_low_stock(df, threshold)
    return JsonResponse({'items': items, 'count': len(items), 'threshold_pct': threshold * 100})


# ── Reorder Points ────────────────────────────────────────────────────────────

def reorder_points_view(request):
    df = _get_df(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)
    from .data_processor import compute_reorder_points
    points = compute_reorder_points(df)
    return JsonResponse({'points': points, 'count': len(points)})


# ── Supplier Performance ──────────────────────────────────────────────────────

def supplier_performance_view(request):
    try:
        df = _get_df(request)
        if df is None:
            return JsonResponse({'error': 'No dataset loaded. Please upload a file first.'}, status=400)
        from .data_processor import supplier_performance
        from .chart_builder import supplier_chart
        theme = request.GET.get('theme', _get_theme(request))
        data = supplier_performance(df)
        chart = None
        if data:
            try:
                chart = supplier_chart(data, theme=theme)
            except Exception:
                chart = None
        return JsonResponse({'suppliers': data, 'count': len(data), 'chart': chart})
    except Exception as e:
        import traceback
        return JsonResponse({'error': f'Supplier analysis failed: {str(e)}'}, status=500)


# ── Data Quality Score ────────────────────────────────────────────────────────

def data_quality_view(request):
    df = _get_df(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)
    from .data_processor import data_quality_score
    result = data_quality_score(df)
    return JsonResponse(result)


# ── AI Recommendations ────────────────────────────────────────────────────────

def ai_recommendations_view(request):
    df = _get_df(request)
    if df is None:
        return JsonResponse({'error': 'No dataset loaded.'}, status=400)
    from .data_processor import (ai_recommendations, compute_kpis,
                                  detect_anomalies, detect_low_stock,
                                  data_quality_score)
    kpis     = compute_kpis(df)
    anomalies= detect_anomalies(df, 'zscore')
    low_stock= detect_low_stock(df)
    quality  = data_quality_score(df)
    recs     = ai_recommendations(df, kpis, anomalies, low_stock, quality)
    return JsonResponse({'recommendations': recs, 'count': len(recs)})
