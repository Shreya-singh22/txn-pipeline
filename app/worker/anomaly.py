import pandas as pd

DOMESTIC_ONLY = {"swiggy","ola","irctc","zomato","flipkart","bigbasket","meesho","jiomart","dunzo","blinkit","zepto","nykaa","myntra"}

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_anomaly"] = False
    df["anomaly_reason"] = ""

    def flag_outliers(group):
        amounts = group["amount"].dropna()
        if len(amounts) < 2:
            return group
        median = amounts.median()
        threshold = 3 * median
        mask = group["amount"] > threshold
        group.loc[mask, "is_anomaly"] = True
        group.loc[mask, "anomaly_reason"] = group.loc[mask, "anomaly_reason"].apply(
            lambda r: (r + "; " if r else "") + f"Amount exceeds 3x account median (median={median:.2f}, threshold={threshold:.2f})")
        return group

    if "account_id" in df.columns and df["account_id"].str.strip().ne("").any():
        df = df.groupby("account_id", group_keys=False).apply(flag_outliers)
    
    def is_domestic_usd(row):
        if str(row.get("currency","")).upper() != "USD":
            return False
        return any(d in str(row.get("merchant","")).lower() for d in DOMESTIC_ONLY)

    mask = df.apply(is_domestic_usd, axis=1)
    df.loc[mask, "is_anomaly"] = True
    df.loc[mask, "anomaly_reason"] = df.loc[mask, "anomaly_reason"].apply(lambda r: (r+"; " if r else "") + "USD at domestic-only merchant")

    mask2 = df["notes"].str.upper().str.contains("SUSPICIOUS", na=False)
    df.loc[mask2, "is_anomaly"] = True
    df.loc[mask2, "anomaly_reason"] = df.loc[mask2, "anomaly_reason"].apply(lambda r: (r+"; " if r else "") + "Note flagged as SUSPICIOUS")
    return df
