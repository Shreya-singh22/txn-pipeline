import json, logging, re
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)
VALID_CATEGORIES = ["Food","Shopping","Travel","Transport","Utilities","Cash Withdrawal","Entertainment","Other"]
genai.configure(api_key=settings.GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-2.0-flash")

def _extract_json(text):
    cleaned = re.sub(r"```(?:json)?", "", text).replace("```","").strip()
    return json.loads(cleaned)

@retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def _call_gemini(prompt):
    return _model.generate_content(prompt).text

def classify_categories(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["llm_category"] = None
    df["llm_failed"] = False
    df["llm_raw_response"] = None
    mask = df["category"] == "Uncategorised"
    unc = df[mask].copy()
    if unc.empty:
        return df
    
    # Process in batches of 100 rows to prevent token limit issues and make it robust at scale
    batch_size = 100
    for start_idx in range(0, len(unc), batch_size):
        batch = unc.iloc[start_idx:start_idx + batch_size]
        rows_text = "\n".join(f'{i+1}. txn_id={r["txn_id"]}, merchant="{r["merchant"]}", amount={r["amount"]}, currency={r["currency"]}, notes="{r["notes"]}"' for i, (_, r) in enumerate(batch.iterrows()))
        prompt = f"""Classify each transaction into EXACTLY one of: {", ".join(VALID_CATEGORIES)}
Return ONLY a JSON array like: [{{"txn_id":"TXN001","category":"Food"}}]
Transactions:
{rows_text}"""
        try:
            raw = _call_gemini(prompt)
            results = _extract_json(raw)
            cat_map = {item["txn_id"]: item["category"] for item in results if "txn_id" in item}
            for idx, row in batch.iterrows():
                cat = cat_map.get(row["txn_id"])
                df.at[idx, "llm_category"] = cat if cat in VALID_CATEGORIES else "Other"
                df.at[idx, "llm_raw_response"] = raw
        except Exception as e:
            logger.error(f"LLM classification failed for batch {start_idx}-{start_idx+len(batch)}: {e}")
            for idx in batch.index:
                df.at[idx, "llm_failed"] = True
    return df

def generate_narrative_summary(df: pd.DataFrame) -> dict:
    inr = df[df["currency"]=="INR"]["amount"].sum()
    usd = df[df["currency"]=="USD"]["amount"].sum()
    anomaly_count = int(df["is_anomaly"].sum())
    top_merchants = df.groupby("merchant")["amount"].sum().sort_values(ascending=False).head(3).reset_index().rename(columns={"amount":"total"}).to_dict(orient="records")
    prompt = f"""Analyze this transaction data and return ONLY a JSON object (no markdown):
{{
  "total_spend_inr": {round(inr,2)},
  "total_spend_usd": {round(usd,2)},
  "top_merchants": {top_merchants},
  "anomaly_count": {anomaly_count},
  "narrative": "<2-3 sentence spending summary>",
  "risk_level": "<low|medium|high>"
}}
risk: high if anomaly_count>5, medium if 2-5, low if <=1"""
    try:
        raw = _call_gemini(prompt)
        result = _extract_json(raw)
        result.setdefault("total_spend_inr", round(inr,2))
        result.setdefault("total_spend_usd", round(usd,2))
        result.setdefault("top_merchants", top_merchants)
        result.setdefault("anomaly_count", anomaly_count)
        result.setdefault("narrative", "Narrative unavailable.")
        result.setdefault("risk_level", "medium")
        return result
    except Exception as e:
        logger.error(f"LLM narrative failed: {e}")
        risk = "high" if anomaly_count > 5 else ("medium" if anomaly_count >= 2 else "low")
        top_name = top_merchants[0]["merchant"] if top_merchants else "various merchants"
        narrative = (
            f"Analyzed {len(df)} transactions totaling ₹{inr:,.2f} (INR) and "
            f"${usd:,.2f} (USD). The top merchant by spend was {top_name}. "
            f"{anomaly_count} anomalies were detected, indicating a {risk} risk level "
            f"(LLM-generated narrative unavailable; this summary was computed from data statistics)."
        )
        return {"total_spend_inr": round(inr,2), "total_spend_usd": round(usd,2),
                "top_merchants": top_merchants, "anomaly_count": anomaly_count,
                "narrative": narrative, "risk_level": risk}
