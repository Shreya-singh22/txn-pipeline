from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: Optional[dict] = None
    class Config:
        from_attributes = True

class JobListItem(BaseModel):
    job_id: str
    status: str
    filename: str
    row_count_raw: Optional[int] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class JobUploadResponse(BaseModel):
    job_id: str
    message: str
    status: str

class TransactionOut(BaseModel):
    id: str
    txn_id: Optional[str] = None
    date: Optional[str] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[str] = None
    notes: Optional[str] = None
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_failed: bool = False
    class Config:
        from_attributes = True

class SummaryOut(BaseModel):
    total_spend_inr: Optional[float] = None
    total_spend_usd: Optional[float] = None
    top_merchants: Optional[List[Any]] = None
    anomaly_count: Optional[int] = None
    narrative: Optional[str] = None
    risk_level: Optional[str] = None

class JobResultsResponse(BaseModel):
    job_id: str
    status: str
    transactions: List[TransactionOut]
    anomalies: List[TransactionOut]
    category_breakdown: dict
    summary: Optional[SummaryOut] = None
