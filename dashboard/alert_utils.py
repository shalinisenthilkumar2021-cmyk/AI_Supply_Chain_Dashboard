"""
Real-time alert creation and email notifications.
"""
from django.core.mail import send_mail
from django.conf import settings
from .models import Alert


def create_alert(dataset, alert_type, message, column='', value=None):
    alert = Alert.objects.create(
        dataset=dataset,
        alert_type=alert_type,
        message=message,
        column=column,
        value=value
    )
    return alert


def send_email_alert(subject: str, message: str, recipient_list: list):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email alert failed: {e}")
        return False


def process_anomaly_alerts(dataset, anomalies: dict, send_email=False, email_to=None):
    created = []
    for col, info in anomalies.items():
        msg = f"Anomaly detected in '{col}': {info['count']} outlier(s) found."
        alert = create_alert(dataset, 'anomaly', msg, column=col)
        created.append(alert)
        if send_email and email_to:
            send_email_alert(
                subject=f'[Supply Chain Alert] Anomaly in {col}',
                message=msg,
                recipient_list=[email_to],
            )
    return created
