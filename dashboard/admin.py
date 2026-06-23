from django.contrib import admin
from .models import UploadedDataset, Alert

@admin.register(UploadedDataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'file_type', 'row_count', 'col_count', 'uploaded_at']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['alert_type', 'column', 'message', 'created_at', 'is_read']
    list_filter = ['alert_type', 'is_read']
