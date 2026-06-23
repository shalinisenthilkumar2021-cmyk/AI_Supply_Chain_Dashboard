"""
Plotly chart builder — all chart types + forecast + anomaly.
"""
import plotly.graph_objects as go
import json

THEMES = {
    'dark':      {'bg':'#1a1a2e','paper':'#16213e','font':'#e0e0e0','grid':'#2d2d2d',
                  'colors':['#00d4ff','#ff6b6b','#ffd93d','#6bcb77','#c77dff','#ff9f43']},
    'light':     {'bg':'#f8f9fa','paper':'#ffffff','font':'#212529','grid':'#dee2e6',
                  'colors':['#0d6efd','#dc3545','#ffc107','#198754','#6f42c1','#fd7e14']},
    'ai':        {'bg':'#0a0a1a','paper':'#111133','font':'#00ffcc','grid':'#1a1a44',
                  'colors':['#00ffcc','#ff00aa','#ffcc00','#00aaff','#ff5500','#aa00ff']},
    'corporate': {'bg':'#f0f4f8','paper':'#ffffff','font':'#1a2332','grid':'#ccd6e0',
                  'colors':['#003087','#c8102e','#00843d','#ff6900','#5b2d8e','#00b4d8']},
    # Neo Enterprise Glass
    'neo_glass': {'bg':'#0d1117','paper':'#161b22','font':'#e6edf3','grid':'#21262d',
                  'colors':['#58a6ff','#3fb950','#f78166','#d2a8ff','#ffa657','#79c0ff']},
    # Bloomberg Hybrid
    'bloomberg': {'bg':'#000000','paper':'#0a0a0a','font':'#f5c518','grid':'#1a1a1a',
                  'colors':['#f5c518','#00d4aa','#ff4444','#4fc3f7','#ff9800','#ce93d8']},
    # Midnight Blue
    'midnight':  {'bg':'#0a0e27','paper':'#0f1535','font':'#a9b4d0','grid':'#1e2a4a',
                  'colors':['#4d9fff','#ff6b9d','#43e97b','#fa8231','#a29bfe','#fd79a8']},
    # Emerald Pro
    'emerald':   {'bg':'#0a1628','paper':'#0d1f38','font':'#e8f5e9','grid':'#1a3048',
                  'colors':['#00e676','#40c4ff','#ff6e40','#ffd740','#ea80fc','#64ffda']},
}

def _t(theme):
    return THEMES.get(theme, THEMES['dark'])

def _layout(title, theme):
    t = _t(theme)
    return dict(
        title=dict(text=title, font=dict(color=t['font'], size=15)),
        paper_bgcolor=t['paper'],
        plot_bgcolor=t['bg'],
        font=dict(color=t['font'], size=12),
        xaxis=dict(gridcolor=t['grid'], zerolinecolor=t['grid'], color=t['font']),
        yaxis=dict(gridcolor=t['grid'], zerolinecolor=t['grid'], color=t['font']),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=t['font'])),
        margin=dict(l=50, r=30, t=55, b=50),
        hovermode='x unified',
    )

def _json(fig):
    return json.loads(fig.to_json())

# ── Chart types ───────────────────────────────────────────────────────────────

def line_chart(df, x_col, y_cols, title='Line Chart', theme='dark'):
    t = _t(theme)
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[col], name=col,
            line=dict(color=t['colors'][i % len(t['colors'])], width=2.5),
            mode='lines+markers', marker=dict(size=4)
        ))
    fig.update_layout(**_layout(title, theme))
    return _json(fig)

def bar_chart(df, x_col, y_col, title='Bar Chart', theme='dark'):
    t = _t(theme)
    fig = go.Figure(go.Bar(
        x=df[x_col], y=df[y_col],
        marker_color=t['colors'][0],
        marker_line_color=t['colors'][1],
        marker_line_width=1,
        text=df[y_col].round(1),
        textposition='outside',
    ))
    fig.update_layout(**_layout(title, theme))
    return _json(fig)

def column_chart(df, x_col, y_cols, title='Column Chart', theme='dark'):
    t = _t(theme)
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Bar(
            name=col, x=df[x_col], y=df[col],
            marker_color=t['colors'][i % len(t['colors'])]
        ))
    fig.update_layout(barmode='group', **_layout(title, theme))
    return _json(fig)

def pie_chart(df, labels_col, values_col, title='Pie Chart', theme='dark'):
    t = _t(theme)
    fig = go.Figure(go.Pie(
        labels=df[labels_col], values=df[values_col],
        marker=dict(colors=t['colors']),
        textinfo='label+percent',
        hole=0,
    ))
    fig.update_layout(**_layout(title, theme))
    return _json(fig)

def donut_chart(df, labels_col, values_col, title='Donut Chart', theme='dark'):
    t = _t(theme)
    fig = go.Figure(go.Pie(
        labels=df[labels_col], values=df[values_col],
        marker=dict(colors=t['colors']),
        textinfo='label+percent',
        hole=0.45,
    ))
    fig.update_layout(**_layout(title, theme))
    return _json(fig)

def forecast_chart(forecast_data: dict, target_col: str, theme='dark'):
    t = _t(theme)
    hist_len = forecast_data['historical_len']
    dates    = forecast_data['dates']
    yhat     = forecast_data['yhat']
    lower    = forecast_data['yhat_lower']
    upper    = forecast_data['yhat_upper']

    fig = go.Figure()

    # Confidence band (future only)
    fig.add_trace(go.Scatter(
        x=dates[hist_len:] + dates[hist_len:][::-1],
        y=upper[hist_len:] + lower[hist_len:][::-1],
        fill='toself',
        fillcolor='rgba(255,107,107,0.15)',
        line=dict(color='rgba(0,0,0,0)'),
        name='80% Confidence',
        hoverinfo='skip',
    ))

    # Historical line
    fig.add_trace(go.Scatter(
        x=dates[:hist_len], y=yhat[:hist_len],
        name='Historical', mode='lines',
        line=dict(color=t['colors'][0], width=2.5),
    ))

    # Forecast line
    fig.add_trace(go.Scatter(
        x=dates[hist_len:], y=yhat[hist_len:],
        name='Forecast', mode='lines',
        line=dict(color=t['colors'][1], width=2.5, dash='dash'),
    ))

    # Divider line
    if hist_len < len(dates):
        fig.add_vline(
            x=dates[hist_len - 1],
            line_dash='dot',
            line_color=t['colors'][2],
            annotation_text='Forecast Start',
            annotation_font_color=t['font'],
        )

    fig.update_layout(**_layout(f'📈 {target_col} — Forecast ({len(dates) - hist_len} periods)', theme))
    return _json(fig)

def anomaly_chart(df, col: str, anomaly_indices: list, theme='dark'):
    t = _t(theme)
    normal_mask = ~df.index.isin(anomaly_indices)

    fig = go.Figure()

    # Normal points
    fig.add_trace(go.Scatter(
        x=df[normal_mask].index.tolist(),
        y=df[normal_mask][col].tolist(),
        mode='markers',
        name='Normal',
        marker=dict(color=t['colors'][0], size=6, opacity=0.8),
    ))

    # Anomaly points
    if anomaly_indices:
        fig.add_trace(go.Scatter(
            x=anomaly_indices,
            y=df.loc[anomaly_indices, col].tolist(),
            mode='markers',
            name='⚠ Anomaly',
            marker=dict(color=t['colors'][1], size=12, symbol='x', line=dict(width=2)),
        ))

    # Mean line
    mean_val = df[col].mean()
    fig.add_hline(
        y=mean_val,
        line_dash='dash',
        line_color=t['colors'][2],
        annotation_text=f'Mean: {mean_val:.2f}',
        annotation_font_color=t['font'],
    )

    fig.update_layout(**_layout(f'⚠ Anomaly Detection — {col} ({len(anomaly_indices)} outliers)', theme))
    return _json(fig)


def supplier_chart(suppliers: list, theme='dark'):
    """Horizontal bar chart of supplier scores."""
    t = _t(theme)
    if not suppliers:
        return None
    names  = [s['supplier'] for s in suppliers]
    scores = [s['score']    for s in suppliers]
    colors = [t['colors'][0] if sc >= 75 else t['colors'][1] if sc >= 50 else t['colors'][3]
              for sc in scores]
    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation='h',
        marker_color=colors,
        text=[f"{sc}" for sc in scores],
        textposition='outside',
    ))
    fig.update_layout(
        **_layout('🏭 Supplier Performance Score (0-100)', theme),
        xaxis=dict(range=[0, 110], gridcolor=t['grid'], color=t['font']),
        height=max(250, len(names) * 40),
    )
    return _json(fig)


def stacked_bar_chart(df, x_col, y_cols, title='Stacked Bar', theme='dark'):
    t = _t(theme)
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        if col in df.columns:
            fig.add_trace(go.Bar(
                name=col, x=df[x_col], y=df[col],
                marker_color=t['colors'][i % len(t['colors'])]
            ))
    fig.update_layout(barmode='stack', **_layout(title, theme))
    return _json(fig)
