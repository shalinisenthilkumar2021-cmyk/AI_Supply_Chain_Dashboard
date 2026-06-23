from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_dataset, name='upload_dataset'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/chart/', views.build_chart, name='build_chart'),
    path('dashboard/anomalies/', views.detect_anomalies_view, name='detect_anomalies'),
    path('dashboard/export/<str:format>/', views.export_report, name='export_report'),
    path('alerts/', views.alerts_view, name='alerts'),
    path('load/<int:pk>/', views.load_dataset_session, name='load_dataset'),
    # ── New endpoints ──
    path('dashboard/low-stock/', views.low_stock_view, name='low_stock'),
    path('dashboard/reorder-points/', views.reorder_points_view, name='reorder_points'),
    path('dashboard/supplier-performance/', views.supplier_performance_view, name='supplier_performance'),
    path('dashboard/data-quality/', views.data_quality_view, name='data_quality'),
    path('dashboard/ai-recommendations/', views.ai_recommendations_view, name='ai_recommendations'),
]
