import pandas as pd
from app.worker.cleaning import clean_dataframe, _clean_amount, _parse_date

def test_parse_date():
    assert _parse_date("25-06-2024") == "2024-06-25"
    assert _parse_date("2024/02/05") == "2024-02-05"
    assert _parse_date("2024-02-05") == "2024-02-05"
    assert _parse_date("25/05/2024") == "2024-05-25"  # non-ambiguous d/m/y format
    assert _parse_date("   ") == ""
    assert _parse_date(None) == ""

def test_clean_amount():
    assert _clean_amount("$1,234.56") == 1234.56
    assert _clean_amount(" 500 ") == 500.0
    assert _clean_amount("invalid") is None
    assert _clean_amount(None) is None

def test_clean_dataframe():
    raw_data = {
        "txn_id": ["TXN001", "  ", "TXN001"],
        "date": ["25-06-2024", "2024/02/05", "25-06-2024"],
        "merchant": ["Swiggy", "Ola", "Swiggy"],
        "amount": ["$120.50", "300", "$120.50"],
        "currency": ["inr", "usd", "inr"],
        "status": ["success", "failed", "success"],
        "category": ["", "Transport", ""],
        "account_id": ["ACC1", "ACC2", "ACC1"],
        "notes": ["Verified", "", "Verified"]
    }
    df = pd.DataFrame(raw_data)
    cleaned_df = clean_dataframe(df)

    # Check that duplicates are removed
    assert len(cleaned_df) == 2

    # Check cased currency and status
    assert cleaned_df.iloc[0]["currency"] == "INR"
    assert cleaned_df.iloc[1]["status"] == "FAILED"

    # Check empty category is set to 'Uncategorised'
    assert cleaned_df.iloc[0]["category"] == "Uncategorised"

    # Check blank txn_id is generated
    assert cleaned_df.iloc[1]["txn_id"].startswith("GEN-")
