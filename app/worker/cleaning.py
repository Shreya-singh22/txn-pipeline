import uuid
import pandas as pd
from datetime import datetime

DATE_FORMATS = ["%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]

def _parse_date(val):
    if not isinstance(val, str) or not val.strip():
        return ""
    val = val.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return pd.to_datetime(val, dayfirst=True).date().isoformat()
    except:
        return val

def _clean_amount(val):
    if pd.isna(val):
        return None
    s = str(val).strip().replace("$", "").replace(",", "").replace(" ", "")
    try:
        return float(s)
    except:
        return None

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["txn_id"] = df["txn_id"].apply(lambda v: f"GEN-{uuid.uuid4().hex[:8].upper()}" if pd.isna(v) or str(v).strip() == "" else str(v).strip())
    df["date"] = df["date"].apply(_parse_date)
    df["amount"] = df["amount"].apply(_clean_amount)
    df["currency"] = df["currency"].apply(lambda v: str(v).strip().upper() if pd.notna(v) and str(v).strip() else "UNKNOWN")
    df["status"] = df["status"].apply(lambda v: str(v).strip().upper() if pd.notna(v) and str(v).strip() else "UNKNOWN")
    df["category"] = df["category"].apply(lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else "Uncategorised")
    df["merchant"] = df["merchant"].apply(lambda v: str(v).strip() if pd.notna(v) else "")
    df["notes"] = df["notes"].fillna("").apply(str)
    df["account_id"] = df["account_id"].fillna("").apply(str).str.strip()
    df = df.drop_duplicates()
    return df.reset_index(drop=True)
