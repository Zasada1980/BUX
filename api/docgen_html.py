"""HTML rendering and PDF conversion for invoices."""
import os
import pathlib
from jinja2 import Template  # type: ignore[import-untyped]
from utils.money import fmt_money


# Minimal HTML template for invoice
HTML_TPL = """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {{ client_id }}</title>
    <style>
        @font-face {
            font-family: 'DejaVu Sans';
            src: local('DejaVu Sans'), local('Arial');
        }
        body { font-family: 'DejaVu Sans', Arial, sans-serif; margin: 40px; }
        h2 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .total { font-weight: bold; font-size: 1.2em; margin-top: 20px; }
        .money { font-family: 'DejaVu Sans', 'Noto Sans', sans-serif; }
    </style>
</head>
<body>
    <h2>Invoice: {{ client_id }}</h2>
    <p><strong>Period:</strong> {{ period_from }} — {{ period_to }}</p>
    <p><strong>Currency:</strong> {{ currency }}</p>
    
    <table>
        <tr>
            <th>Date</th>
            <th>Site</th>
            <th>Worker</th>
            <th>Task</th>
            <th>Qty</th>
            <th>Unit</th>
            <th>Amount ({{ currency }})</th>
        </tr>
        {% for i in items -%}
        <tr>
            <td>{{ i.date }}</td>
            <td>{{ i.site }}</td>
            <td>{{ i.worker }}</td>
            <td>{{ i.task }}</td>
            <td>{{ i.qty }}</td>
            <td>{{ i.unit }}</td>
            <td class="money" style="direction:ltr; unicode-bidi:isolate;">{{ i.fmt_amount }}</td>
        </tr>
        {% endfor %}
    </table>
    
    <div class="total money" style="direction:ltr; unicode-bidi:isolate;">Total: {{ fmt_total }}</div>
</body>
</html>"""


def render_html(context: dict, out_dir: str = "exports") -> str:
    """
    Render invoice as HTML from template.
    
    Args:
        context: Invoice data dictionary
        out_dir: Output directory for generated files
        
    Returns:
        Path to generated HTML file
    """
    os.makedirs(out_dir, exist_ok=True)
    
    # Add formatted amounts
    for item in context.get('items', []):
        item['fmt_amount'] = fmt_money(item['amount'])
    
    context['fmt_total'] = fmt_money(context['total'])
    
    html = Template(HTML_TPL).render(**context)
    filename = f"invoice_{context['client_id']}_{context['period_from']}_{context['period_to']}.html"
    path = os.path.join(out_dir, filename)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return path


def html_to_pdf(html_path: str) -> str | None:
    """
    Convert HTML to PDF using weasyprint if available.
    
    Args:
        html_path: Path to HTML file
        
    Returns:
        Path to generated PDF file, or None if weasyprint not available
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
        pdf_path = pathlib.Path(html_path).with_suffix(".pdf")
        HTML(filename=html_path).write_pdf(str(pdf_path))
        return str(pdf_path)
    except ImportError:
        # weasyprint not installed - skip PDF generation
        return None
    except Exception as e:
        # Other errors (e.g., missing dependencies like cairo)
        print(f"PDF generation failed: {e}")
        return None
