# backend/src/handlers/google_export.py
from fastapi import APIRouter
from pydantic import BaseModel
from src.utils.g_sheet import append_rows_to_sheet
import os

router = APIRouter()

class ExportRows(BaseModel):
    rows: list[list]

@router.post("/export/sheets")
def export_to_sheets(payload: ExportRows):
    SHEET_ID = os.getenv("LEADS_SHEET_ID")
    append_rows_to_sheet(SHEET_ID, payload.rows)
    return {"ok": True, "rows": len(payload.rows)}