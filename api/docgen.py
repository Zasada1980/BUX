"""Document generation module for invoices."""
import os
from decimal import Decimal
from sqlalchemy import text
from db import SessionLocal


def collect_invoice_data(client_id: str, d_from: str, d_to: str, currency: str) -> dict:
    """
    Collect invoice data from database for given period.
    
    Args:
        client_id: Client identifier (currently maps to user_id)
        d_from: Start date (ISO8601 format)
        d_to: End date (ISO8601 format)
        currency: Currency code
        
    Returns:
        Dictionary with invoice context: client_id, period_from, period_to, items, total
    """
    with SessionLocal() as s:
        # Aggregate tasks for the period
        # Temporary: using shifts.user_id as surrogate for client_id
        rows = s.execute(text("""
            SELECT t.rowid as id, date(s.created_at) as date, s.user_id as worker,
                   t.rate_code as task, t.qty as qty, t.unit as unit, t.amount as amount
            FROM tasks t
            JOIN shifts s ON s.id = t.shift_id
            WHERE date(s.created_at) BETWEEN :f AND :t
            ORDER BY s.created_at ASC
        """), {"f": d_from, "t": d_to}).mappings().all()

        items = []
        total = Decimal("0")  # D1: use Decimal instead of float
        
        for r in rows:
            amt = Decimal(str(r["amount"]))  # D1: convert to Decimal
            items.append({
                "date": r["date"],
                "site": "-",  # Placeholder until sites table is added
                "worker": r["worker"],
                "task": r["task"],
                "qty": r["qty"],
                "unit": r["unit"],
                "amount": amt  # D1: Keep as Decimal for money operations
            })
            total += amt

        return {
            "client_id": client_id,
            "period_from": d_from,
            "period_to": d_to,
            "currency": currency,
            "items": items,
            "total": total,  # D1: return Decimal
        }


def render_docx(context: dict, template_path: str = "templates/invoice.docx", out_dir: str = "exports") -> str:
    """
    Render invoice DOCX from template.
    
    NOTE: This is a stub for Phase 11 MVP. Full implementation requires python-docx + docxtpl.
    For now, we'll focus on HTML→PDF path.
    
    Args:
        context: Invoice data dictionary
        template_path: Path to DOCX template
        out_dir: Output directory for generated files
        
    Returns:
        Path to generated DOCX file (or None if skipped)
    """
    # Stub implementation - not creating actual DOCX
    # Full implementation would be:
    # from docxtpl import DocxTemplate
    # os.makedirs(out_dir, exist_ok=True)
    # doc = DocxTemplate(template_path)
    # doc.render(context)
    # out_docx = os.path.join(out_dir, f"invoice_{context['client_id']}_{context['period_from']}_{context['period_to']}.docx")
    # doc.save(out_docx)
    # return out_docx
    
    return None  # Skipped for Phase 11 MVP
