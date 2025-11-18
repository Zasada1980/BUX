# api/admin_ui.py — E1 HTMX Inbox (модерация pending changes)
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Any, List
from sqlalchemy import text
from db import SessionLocal
from utils.audit import record_metric

router = APIRouter(tags=["admin-ui"])

# ════════════════════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════════════════════
class PendingItem(BaseModel):
    id: int
    invoice_id: int | None = None
    kind: str
    payload: dict[str, Any]
    created_at: str
    status: str

class PendingListOut(BaseModel):
    items: List[PendingItem]
    total: int
    page: int
    limit: int
    has_next: bool

# ════════════════════════════════════════════════════════════════════════════
# SQL helpers
# ════════════════════════════════════════════════════════════════════════════
def _select_pending_sql(status: str):
    return text("""
        SELECT id, kind, payload_json, created_at, status, correlation_id
        FROM pending_changes
        WHERE status = :status
        ORDER BY datetime(created_at) DESC
        LIMIT :limit OFFSET :offset
    """)

def _count_pending_sql(status: str):
    return text("""
        SELECT COUNT(1) as c
        FROM pending_changes
        WHERE status = :status
    """)

# ════════════════════════════════════════════════════════════════════════════
# E1-T1: JSON список /admin/pending (S34)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/admin/pending", response_model=PendingListOut)
def pending_list(request: Request,
                 page: int = 1,
                 limit: int = 20,
                 status: str = "pending"):
    """
    GET /admin/pending?page=1&limit=20&status=pending
    
    DoD (S34):
    - Возвращает JSON с полями: items[], total, page, limit, has_next
    - Content negotiation: если HX-Request header → HTML таблица
    """
    page = max(page, 1)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit

    with SessionLocal() as session:
        total = session.execute(_count_pending_sql(status), {"status": status}).scalar() or 0
        rows = session.execute(_select_pending_sql(status), {
            "status": status, "limit": limit, "offset": offset
        }).mappings().all()

        items = [PendingItem(**{
            "id": r["id"], 
            "invoice_id": r.get("correlation_id"),
            "kind": r["kind"], 
            "payload": _parse_json(r["payload_json"]),  # parse JSON string to dict
            "created_at": str(r["created_at"]), 
            "status": r["status"]
        }) for r in rows]

    out = PendingListOut(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_next=(offset + limit) < total
    )

    # Content negotiation: HTMX хочет HTML
    accept = request.headers.get("accept", "")
    is_htmx = request.headers.get("HX-Request") == "true"
    
    if is_htmx or "text/html" in accept:
        html = _render_table_html(out)
        return Response(html, media_type="text/html; charset=utf-8")
    
    return out

def _render_table_html(data: PendingListOut) -> str:
    """Рендер HTML таблицы для HTMX"""
    header = f"<div class='muted'>Всего: {data.total} · стр. {data.page} · лимит {data.limit}</div>"
    
    rows = []
    for it in data.items:
        rows.append(f"""
<tr id="row-{it.id}">
  <td>#{it.id}</td>
  <td>{it.invoice_id or ''}</td>
  <td>{it.kind}</td>
  <td><pre class="payload">{_safe_json(it.payload)}</pre></td>
  <td>{it.created_at}</td>
  <td>
    <button hx-post="/admin/pending/{it.id}/approve" hx-target="#row-{it.id}" hx-swap="outerHTML">✅</button>
    <button hx-post="/admin/pending/{it.id}/reject"  hx-target="#row-{it.id}" hx-swap="outerHTML">❌</button>
  </td>
</tr>""")
    
    table = f"""
<table class="grid">
  <thead><tr><th>ID</th><th>Invoice</th><th>Kind</th><th>Payload</th><th>Created</th><th>Actions</th></tr></thead>
  <tbody>{''.join(rows) or '<tr><td colspan="6">Пусто</td></tr>'}</tbody>
</table>"""
    
    pager = ""
    if data.page > 1:
        pager += f"""<button hx-get="/admin/pending?page={data.page-1}&limit={data.limit}" hx-target="#inbox" hx-swap="outerHTML">◀ Пред</button>"""
    if data.has_next:
        pager += f"""<button hx-get="/admin/pending?page={data.page+1}&limit={data.limit}" hx-target="#inbox" hx-swap="outerHTML">След ▶</button>"""
    
    return f"""<div id="inbox">{header}{table}<div class="pager">{pager}</div></div>"""

def _safe_json(obj: Any) -> str:
    """Безопасный JSON для HTML"""
    import json, html
    return html.escape(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

def _parse_json(s: str) -> Any:
    """Parse JSON string to Python object"""
    import json
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}

# ════════════════════════════════════════════════════════════════════════════
# E1-T2: HTMX страница /admin/inbox (S35)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/admin/inbox")
def inbox_page():
    """
    Главная страница inbox с HTMX (offline, без CDN)
    
    DoD (S35):
    - HTML с hx-get="/admin/pending"
    - Кнопки approve/reject с hx-post
    - Toast уведомления через custom JS (без Alpine)
    """
    return Response("""
<!doctype html><meta charset="utf-8">
<title>Admin Inbox</title>
<style>
 body{font:14px system-ui,Segoe UI,Arial,sans-serif;margin:16px;background:#f5f5f5}
 .grid{border-collapse:collapse;width:100%;background:#fff}
 .grid th,.grid td{border:1px solid #ddd;padding:8px;vertical-align:top}
 .grid th{background:#f0f0f0;font-weight:600}
 .muted{color:#666;margin:6px 0;font-size:13px}
 .pager{margin-top:12px;display:flex;gap:8px}
 .pager button{padding:6px 12px;cursor:pointer}
 pre.payload{max-width:480px;white-space:pre-wrap;word-break:break-word;margin:0;font-size:12px;background:#fafafa;padding:4px}
 button{background:#007bff;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:13px}
 button:hover{background:#0056b3}
 #toast{position:fixed;right:12px;bottom:12px;background:#222;color:#fff;padding:10px 14px;border-radius:8px;opacity:0;transition:.2s;z-index:9999}
 #toast.show{opacity:1}
</style>
<script>
 function toast(msg){
   const t=document.getElementById('toast');
   t.textContent=msg;
   t.classList.add('show');
   setTimeout(()=>t.classList.remove('show'),1500);
 }
 document.addEventListener('htmx:afterOnLoad', (e)=>{ 
   if(e.detail.xhr && e.detail.xhr.getResponseHeader('X-Toast')) {
     toast(e.detail.xhr.getResponseHeader('X-Toast'));
   }
 });
</script>
<body hx-boost="true">
<h2>🗂 Inbox — Moderation</h2>
<div hx-get="/admin/pending" hx-trigger="load" hx-target="#inbox" hx-swap="outerHTML">
  <p class="muted">Загрузка...</p>
</div>
<div id="toast"></div>
<script src="/static/htmx.min.js"></script>
</body>""", media_type="text/html; charset=utf-8")

# ════════════════════════════════════════════════════════════════════════════
# E1-T3: approve/reject с метриками (S35)
# ════════════════════════════════════════════════════════════════════════════
@router.post("/admin/pending/{pid}/approve")
def approve_pending(pid: int, request: Request):
    """
    POST /admin/pending/{pid}/approve
    
    DoD (S35):
    - Обновляет pending_changes.status = 'approved'
    - Записывает метрику mod.approve в api.jsonl
    - Возвращает HTML строку таблицы с hx-swap
    """
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM pending_changes WHERE id=:id"), 
            {"id": pid}
        ).mappings().first()
        
        if not row:
            raise HTTPException(404, "pending not found")
        
        if row["status"] != "pending":
            return Response(
                f"<tr id='row-{pid}'><td colspan='6'>#{pid} уже {row['status']}</td></tr>", 
                headers={"X-Toast": "уже обработано"}
            )
        
        session.execute(text("""
            UPDATE pending_changes
            SET status='approved', 
                reviewed_by='admin', 
                reviewed_at=CURRENT_TIMESTAMP, 
                review_reason='manual approve'
            WHERE id=:id
        """), {"id": pid})
        session.commit()
        
        # Метрика mod.approve
        record_metric("mod.approve", fields={
            "item_id": pid, 
            "user_id": "admin", 
            "kind": row["kind"]
        }, outcome="accepted")
        
        # Обновлённая строка
        html = f"""<tr id='row-{pid}' style='opacity:.6'>
<td>#{pid}</td>
<td>{row.get('correlation_id') or ''}</td>
<td>{row['kind']}</td>
<td><pre class='payload'>{_safe_json(row['payload_json'])}</pre></td>
<td>{row['created_at']}</td>
<td>✔️ approved</td>
</tr>"""
        
        return Response(
            html, 
            media_type="text/html; charset=utf-8", 
            headers={"X-Toast": f"OK Approved #{pid}"}
        )

@router.post("/admin/pending/{pid}/reject")
def reject_pending(pid: int, request: Request):
    """
    POST /admin/pending/{pid}/reject
    
    DoD (S35):
    - Обновляет pending_changes.status = 'rejected'
    - Записывает метрику mod.reject в api.jsonl
    - Возвращает HTML строку таблицы с hx-swap
    """
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM pending_changes WHERE id=:id"), 
            {"id": pid}
        ).mappings().first()
        
        if not row:
            raise HTTPException(404, "pending not found")
        
        if row["status"] != "pending":
            return Response(
                f"<tr id='row-{pid}'><td colspan='6'>#{pid} уже {row['status']}</td></tr>", 
                headers={"X-Toast": "уже обработано"}
            )
        
        session.execute(text("""
            UPDATE pending_changes
            SET status='rejected', 
                reviewed_by='admin', 
                reviewed_at=CURRENT_TIMESTAMP, 
                review_reason='manual reject'
            WHERE id=:id
        """), {"id": pid})
        session.commit()
        
        # Метрика mod.reject
        record_metric("mod.reject", fields={
            "item_id": pid, 
            "user_id": "admin", 
            "kind": row["kind"]
        }, outcome="rejected")
        
        # Обновлённая строка
        html = f"""<tr id='row-{pid}' style='opacity:.6'>
<td>#{pid}</td>
<td>{row.get('correlation_id') or ''}</td>
<td>{row['kind']}</td>
<td><pre class='payload'>{_safe_json(row['payload_json'])}</pre></td>
<td>{row['created_at']}</td>
<td>✖️ rejected</td>
</tr>"""
        
        return Response(
            html, 
            media_type="text/html; charset=utf-8", 
            headers={"X-Toast": f"REJECT #{pid}"}
        )
