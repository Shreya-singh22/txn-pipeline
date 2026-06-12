import pandas as pd
from app.worker.anomaly import detect_anomalies

def test_detect_anomalies_median_outlier():
    # Setup data where one txn exceeds 3x the account's median
    data = {
        "account_id": ["ACC001", "ACC001", "ACC001", "ACC001", "ACC001"],
        "amount": [10.0, 12.0, 11.0, 13.0, 100.0],  # median = 12.0, 3x median = 36.0, 100.0 is outlier
        "currency": ["INR", "INR", "INR", "INR", "INR"],
        "merchant": ["A", "B", "C", "D", "E"],
        "notes": ["", "", "", "", ""]
    }
    df = pd.DataFrame(data)
    df_anomaly = detect_anomalies(df)

    assert df_anomaly.iloc[4]["is_anomaly"] == True
    assert "Amount exceeds 3x account median" in df_anomaly.iloc[4]["anomaly_reason"]
    assert df_anomaly.iloc[0]["is_anomaly"] == False

def test_detect_anomalies_domestic_usd():
    # Setup USD txn at domestic merchant Swiggy
    data = {
        "account_id": ["ACC001", "ACC001"],
        "amount": [50.0, 50.0],
        "currency": ["USD", "INR"],
        "merchant": ["Swiggy", "Swiggy"],
        "notes": ["", ""]
    }
    df = pd.DataFrame(data)
    df_anomaly = detect_anomalies(df)

    assert df_anomaly.iloc[0]["is_anomaly"] == True
    assert "USD at domestic-only merchant" in df_anomaly.iloc[0]["anomaly_reason"]
    assert df_anomaly.iloc[1]["is_anomaly"] == False

def test_detect_anomalies_suspicious_notes():
    data = {
        "account_id": ["ACC001", "ACC001"],
        "amount": [10.0, 10.0],
        "currency": ["INR", "INR"],
        "merchant": ["A", "B"],
        "notes": ["This is SUSPICIOUS", "Normal notes"]
    }
    df = pd.DataFrame(data)
    df_anomaly = detect_anomalies(df)

    assert df_anomaly.iloc[0]["is_anomaly"] == True
    assert "Note flagged as SUSPICIOUS" in df_anomaly.iloc[0]["anomaly_reason"]
    assert df_anomaly.iloc[1]["is_anomaly"] == False
