# Invoice Template Placeholder

**NOTE**: This is a placeholder. For Phase 11 MVP, we'll use HTML rendering instead of DOCX.

In production, this would be a proper DOCX file with docxtpl placeholders:
- {{client_id}}
- {{period_from}}
- {{period_to}}
- {{currency}}
- {{total}}
- {% for item in items %}
  - {{item.date}}, {{item.worker}}, {{item.task}}, {{item.qty}}, {{item.amount}}
  {% endfor %}

To create actual DOCX template:
1. Install python-docx: pip install python-docx docxtpl
2. Create invoice.docx with MS Word
3. Replace values with {{placeholders}}
4. Use docxtpl to render

For Phase 11, we'll focus on HTML→PDF path which is simpler and works without binary DOCX files.
