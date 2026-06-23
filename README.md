# AI-Powered Supply Chain Intelligence Dashboard

Django 5 + Plotly + Prophet

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py makemigrations
python manage.py migrate

# 4. Create admin user (optional)
python manage.py createsuperuser

# 5. Start server
python manage.py runserver
```

Open http://127.0.0.1:8000

## Features
- **Upload**: CSV / Excel / PDF with auto-cleaning
- **KPI Dashboard**: Revenue, Profit, Quantity, Margin
- **Charts**: Line, Bar, Column, Pie, Donut (4 themes)
- **Forecasting**: Prophet-based with confidence bands
- **Anomaly Detection**: Z-Score and IQR
- **Alerts**: In-app + Email notifications
- **Export**: CSV, Excel (formatted), PDF Report

## Themes
Dark · Light · AI · Corporate — switch in the navbar

## Email Alerts
Edit `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` in `settings.py`.
