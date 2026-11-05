"""
Excel (.xlsx) export of report rows (list of dicts with identical keys).
"""
import io
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def rows_to_xlsx_bytes(rows: List[Dict[str, Any]], sheet_title: str = "Report") -> bytes:
    if not rows:
        rows = [{"info": "No data available"}]
    headers = list(rows[0].keys())
    wb = Workbook()
    ws = wb.active
    ws.title = (sheet_title or "Report")[:31]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    for idx, header in enumerate(headers, 1):
        longest = max(len(str(header)), *(len(str(r.get(header, "") or "")) for r in rows))
        ws.column_dimensions[get_column_letter(idx)].width = min(60, max(10, longest + 2))
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
