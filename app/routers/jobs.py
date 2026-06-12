import os, uuid, shutil, logging
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job, Transaction, JobSummary
from app.schemas import JobUploadResponse, JobStatusResponse, JobListItem, JobResultsResponse, TransactionOut, SummaryOut
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/upload", response_model=JobUploadResponse, status_code=202)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if os.path.getsize(dest) == 0:
        os.remove(dest)
        raise HTTPException(status_code=400, detail="File is empty.")
    
    # Validate CSV headers
    import pandas as pd
    try:
        df_headers = pd.read_csv(dest, nrows=1)
        cols = set([c.strip().lower().replace(" ", "_") for c in df_headers.columns])
        required_cols = {"txn_id", "date", "merchant", "amount", "currency", "status", "category", "account_id"}
        # If it doesn't match at least 3 expected columns, reject it
        if len(cols.intersection(required_cols)) < 3:
            os.remove(dest)
            raise HTTPException(status_code=400, detail="Invalid CSV structure. Make sure headers contain transaction columns (txn_id, date, merchant, amount, etc.).")
    except Exception as parse_err:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=400, detail=f"Malformed CSV file: {str(parse_err)}")
    job = Job(id=str(uuid.uuid4()), filename=file.filename, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    from app.worker.tasks import process_csv
    process_csv.delay(job.id, dest)
    return JobUploadResponse(job_id=job.id, message="Job enqueued", status="pending")

@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    response = JobStatusResponse(job_id=job.id, status=job.status, filename=job.filename,
        row_count_raw=job.row_count_raw, row_count_clean=job.row_count_clean,
        created_at=job.created_at, completed_at=job.completed_at, error_message=job.error_message)
    if job.status == "completed" and job.summary:
        s = job.summary
        response.summary = {"total_spend_inr": s.total_spend_inr, "total_spend_usd": s.total_spend_usd,
            "anomaly_count": s.anomaly_count, "risk_level": s.risk_level, "narrative": s.narrative}
    return response

@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status not in ("completed", "failed"):
        raise HTTPException(status_code=202, detail=f"Job is still {job.status}.")
    txns = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    txn_out = [TransactionOut.model_validate(t) for t in txns]
    anomalies = [t for t in txn_out if t.is_anomaly]
    breakdown: dict = {}
    for t in txns:
        cat = t.llm_category or t.category or "Uncategorised"
        breakdown[cat] = round(breakdown.get(cat, 0) + (t.amount or 0), 2)
    summary_out = None
    if job.summary:
        s = job.summary
        summary_out = SummaryOut(total_spend_inr=s.total_spend_inr, total_spend_usd=s.total_spend_usd,
            top_merchants=s.top_merchants, anomaly_count=s.anomaly_count, narrative=s.narrative, risk_level=s.risk_level)
    return JobResultsResponse(job_id=job_id, status=job.status, transactions=txn_out,
        anomalies=anomalies, category_breakdown=breakdown, summary=summary_out)

@router.get("", response_model=list[JobListItem])
def list_jobs(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        if status not in {"pending","processing","completed","failed"}:
            raise HTTPException(status_code=400, detail="Invalid status.")
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return [JobListItem(job_id=j.id, status=j.status, filename=j.filename,
        row_count_raw=j.row_count_raw, created_at=j.created_at) for j in jobs]
