"""
Export helpers: CSV, Excel (XlsxWriter), PDF (ReportLab).
"""
import io
import csv
import pandas as pd
from pathlib import Path
from django.conf import settings
import json


def export_csv(df: pd.DataFrame, filename: str) -> str:
    path = Path(settings.REPORTS_DIR) / filename
    df.to_csv(path, index=False)
    return str(path)


def export_excel(df: pd.DataFrame, filename: str, summary: dict = None) -> str:
    path = Path(settings.REPORTS_DIR) / filename
    with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Data']

        # Format header
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#003087', 'font_color': '#ffffff',
            'border': 1, 'align': 'center'
        })
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_fmt)
            worksheet.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

        # Summary sheet
        if summary:
            ws2 = workbook.add_worksheet('Summary')
            bold = workbook.add_format({'bold': True})
            ws2.write(0, 0, 'Metric', bold)
            ws2.write(0, 1, 'Value', bold)
            row = 1
            for k, v in summary.items():
                ws2.write(row, 0, str(k))
                ws2.write(row, 1, str(v))
                row += 1
    return str(path)


def export_pdf_report(df: pd.DataFrame, summary: dict, kpis: dict, filename: str) -> str:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import cm

    path = Path(settings.REPORTS_DIR) / filename
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  textColor=colors.HexColor('#003087'), fontSize=18)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
                               textColor=colors.HexColor('#003087'))

    story = [
        Paragraph('AI Supply Chain Intelligence — Report', title_style),
        Spacer(1, 0.5*cm),
        Paragraph('Dataset Summary', h2_style),
    ]

    # Summary table
    sum_data = [['Metric', 'Value']] + [[str(k), str(v)] for k, v in list(summary.items())[:12]]
    sum_table = Table(sum_data, colWidths=[8*cm, 8*cm])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003087')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f4f8'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story += [sum_table, Spacer(1, 0.5*cm)]

    # KPI table
    if kpis:
        story.append(Paragraph('Key Performance Indicators', h2_style))
        kpi_data = [['KPI', 'Value']] + [[str(k), str(v)] for k, v in list(kpis.items())[:12]]
        kpi_table = Table(kpi_data, colWidths=[8*cm, 8*cm])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c8102e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fff5f5'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story += [kpi_table, Spacer(1, 0.5*cm)]

    # Data preview (first 20 rows)
    story.append(Paragraph('Data Preview (first 20 rows)', h2_style))
    preview = df.head(20)
    col_count = len(preview.columns)
    col_width = max(2.5*cm, 24*cm / col_count)
    data_rows = [list(preview.columns)] + preview.astype(str).values.tolist()
    data_table = Table(data_rows, colWidths=[col_width]*col_count, repeatRows=1)
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00843d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0fff4'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(data_table)

    doc.build(story)
    return str(path)
