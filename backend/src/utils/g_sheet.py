import os
from google.oauth2.service_account import Credentials
import gspread

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_gspread_client_from_service_account_json(path=None):
    path = path or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)

def append_rows_to_sheet(sheet_id, rows, sheet_name=None):
    gc = get_gspread_client_from_service_account_json()
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.sheet1
    # append_rows accepts a list of rows (each row is a list)
    # value_input_option typing from gspread stubs may conflict with string literals; ignore the type error here
    ws.append_rows(rows, value_input_option="USER_ENTERED")  # type: ignore[arg-type]