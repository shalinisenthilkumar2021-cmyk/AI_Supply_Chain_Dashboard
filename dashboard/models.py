from django.db import models
import json

class UploadedDataset(models.Model):
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=10)  # csv, excel, pdf
    uploaded_at = models.DateTimeField(auto_now_add=True)
    row_count = models.IntegerField(default=0)
    col_count = models.IntegerField(default=0)
    columns = models.TextField(default='[]')  # JSON list of column names

    def get_columns(self):
        return json.loads(self.columns)

    def __str__(self):
        return f"{self.name} ({self.uploaded_at.strftime('%Y-%m-%d')})"

class Alert(models.Model):
    ALERT_TYPES = [('anomaly', 'Anomaly'), ('forecast', 'Forecast'), ('threshold', 'Threshold')]
    dataset = models.ForeignKey(UploadedDataset, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    column = models.CharField(max_length=100, blank=True)
    value = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.alert_type}] {self.message[:60]}"
