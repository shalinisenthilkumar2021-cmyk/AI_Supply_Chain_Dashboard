from django import forms


class UploadFileForm(forms.Form):
    FILE_TYPES = [('csv', 'CSV'), ('excel', 'Excel'), ('pdf', 'PDF')]
    file = forms.FileField(
        label='Upload Dataset',
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,.xlsx,.xls,.pdf', 'class': 'form-control'})
    )
    name = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dataset name (optional)'})
    )


class ChartConfigForm(forms.Form):
    CHART_TYPES = [
        ('line', 'Line'), ('bar', 'Bar'), ('column', 'Column'),
        ('pie', 'Pie'), ('donut', 'Donut'),
    ]
    THEMES = [('dark', 'Dark'), ('light', 'Light'), ('ai', 'AI'), ('corporate', 'Corporate')]
    ANOMALY_METHODS = [('zscore', 'Z-Score'), ('iqr', 'IQR')]

    chart_type = forms.ChoiceField(choices=CHART_TYPES,
                                    widget=forms.Select(attrs={'class': 'form-select'}))
    x_column = forms.ChoiceField(choices=[],
                                  widget=forms.Select(attrs={'class': 'form-select'}))
    y_columns = forms.MultipleChoiceField(choices=[],
                                           widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}))
    theme = forms.ChoiceField(choices=THEMES,
                               widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, columns=None, **kwargs):
        super().__init__(*args, **kwargs)
        if columns:
            col_choices = [(c, c) for c in columns]
            self.fields['x_column'].choices = col_choices
            self.fields['y_columns'].choices = col_choices


class ForecastForm(forms.Form):
    target_col = forms.ChoiceField(choices=[],
                                    widget=forms.Select(attrs={'class': 'form-select'}))
    date_col = forms.ChoiceField(choices=[('', '-- None (use index) --')],
                                  required=False,
                                  widget=forms.Select(attrs={'class': 'form-select'}))
    periods = forms.IntegerField(min_value=7, max_value=365, initial=30,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))
    theme = forms.ChoiceField(
        choices=[('dark', 'Dark'), ('light', 'Light'), ('ai', 'AI'), ('corporate', 'Corporate')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, numeric_cols=None, all_cols=None, **kwargs):
        super().__init__(*args, **kwargs)
        if numeric_cols:
            self.fields['target_col'].choices = [(c, c) for c in numeric_cols]
        if all_cols:
            self.fields['date_col'].choices = [('', '-- None --')] + [(c, c) for c in all_cols]


class AnomalyForm(forms.Form):
    METHODS = [('zscore', 'Z-Score (3σ)'), ('iqr', 'IQR (1.5×)')]
    method = forms.ChoiceField(choices=METHODS,
                                widget=forms.Select(attrs={'class': 'form-select'}))
    theme = forms.ChoiceField(
        choices=[('dark', 'Dark'), ('light', 'Light'), ('ai', 'AI'), ('corporate', 'Corporate')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    send_email = forms.BooleanField(required=False, label='Send email alert on anomaly')
    email_to = forms.EmailField(required=False,
                                 widget=forms.EmailInput(attrs={'class': 'form-control',
                                                                 'placeholder': 'alert@example.com'}))
