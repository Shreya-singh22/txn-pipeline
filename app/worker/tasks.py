import logging, os, uuid
from datetime import datetime, timezone
import pandas as pd
from app.worker.celery_app import celery_app
from app.database import SessionLocal
from app.models import Job, Transaction, JobSummary
from app.worker.cleaning import clean_dataframe
from app.worker.anomaly import detect_anomalies
from app.worker.llm import classify_categories, generate_narrative_summary

logger = logging.getLogger(__name__)

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@celery_app.task(bind=True, max_retries=0)
def process_csv(self, job_id, file_path):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        job.status = "processing"
        db.commit()
        df = pd.read_csv(file_path, dtype=str)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        for col in ["txn_id","date","merchant","amount","currency","status","category","account_id","notes"]:
            if col not in df.columns:
                df[col] = ""
        job.row_count_raw = len(df)
        db.commit()
        df_clean = clean_dataframe(df)
        df_clean = detect_anomalies(df_clean)
        df_clean = classify_categories(df_clean)
        summary_data = generate_narrative_summary(df_clean)
        for _, row in df_clean.iterrows():
            amt = row.get("amount")
            txn = Transaction(id=str(uuid.uuid4()), job_id=job_id,
                txn_id=row.get("txn_id"), date=row.get("date"), merchant=row.get("merchant"),
                amount=float(amt) if amt is not None and pd.notna(amt) else None,
                currency=row.get("currency"), status=row.get("status"), category=row.get("category"),
                account_id=row.get("account_id"), notes=row.get("notes"),
                is_anomaly=bool(row.get("is_anomaly", False)),
                anomaly_reason=row.get("anomaly_reason") or None,
                llm_category=row.get("llm_category") or None,
                llm_raw_response=str(row.get("llm_raw_response","") or "")[:2000] or None,
                llm_failed=bool(row.get("llm_failed", False)))
            db.add(txn)
        summary = JobSummary(id=str(uuid.uuid4()), job_id=job_id,
            total_spend_inr=float(summary_data.get("total_spend_inr") or 0),
            total_spend_usd=float(summary_data.get("total_spend_usd") or 0),
            top_merchants=[{"merchant": m["merchant"], "total": float(m["total"])} for m in (summary_data.get("top_merchants") or [])],
            anomaly_count=int(summary_data.get("anomaly_count") or 0),
            narrative=summary_data.get("narrative"),
            risk_level=summary_data.get("risk_level"),
            raw_llm_json={"total_spend_inr": float(summary_data.get("total_spend_inr") or 0),
                          "total_spend_usd": float(summary_data.get("total_spend_usd") or 0),
                          "anomaly_count": int(summary_data.get("anomaly_count") or 0),
                          "narrative": summary_data.get("narrative"),
                          "risk_level": summary_data.get("risk_level")})
        db.add(summary)
        job.status = "completed"
        job.row_count_clean = len(df_clean)
        job.completed_at = utcnow()
        db.commit()
        logger.info(f"[{job_id}] Completed")
    except Exception as e:
        logger.exception(f"[{job_id}] Failed: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = utcnow()
                db.commit()
        except Exception as rollback_err:
            logger.error(f"[{job_id}] Failed to update job status to failed: {rollback_err}")
    finally:
        db.close()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
