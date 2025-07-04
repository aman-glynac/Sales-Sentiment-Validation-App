from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class User(BaseModel):
    email: EmailStr
    name: str
    is_admin: bool = False
    created_at: datetime

class Activity(BaseModel):
    activity_type: str
    # Common fields
    id: Optional[str] = None
    createdate: Optional[datetime] = None
    lastmodifieddate: Optional[datetime] = None
    
    # Email specific fields
    sent_at: Optional[datetime] = None
    from_: Optional[str] = Field(None, alias='from')
    to: Optional[List[str]] = []
    subject: Optional[str] = None
    body: Optional[str] = None
    state: Optional[str] = None
    direction: Optional[str] = None
    
    # Call specific fields
    call_title: Optional[str] = None
    call_body: Optional[str] = None
    call_direction: Optional[str] = None
    call_duration: Optional[int] = None
    call_status: Optional[str] = None
    
    # Meeting specific fields
    meeting_title: Optional[str] = None
    meeting_location: Optional[str] = None
    meeting_location_type: Optional[str] = None
    meeting_outcome: Optional[str] = None
    meeting_start_time: Optional[datetime] = None
    meeting_end_time: Optional[datetime] = None
    internal_meeting_notes: Optional[str] = None
    
    # Note specific fields
    note_body: Optional[str] = None
    
    # Task specific fields
    task_subject: Optional[str] = None
    task_body: Optional[str] = None
    task_status: Optional[str] = None
    task_priority: Optional[str] = None
    task_type: Optional[str] = None

class Deal(BaseModel):
    deal_id: str
    amount: Union[str, float]  # Can be string or number
    dealstage: str
    dealtype: str
    deal_stage_probability: Union[str, float]  # Can be string or number
    createdate: Union[datetime, str]
    closedate: Optional[Union[datetime, str]] = None
    activities: List[Dict[str, Any]]  # Keep as dict for flexibility

class ActivityBreakdown(BaseModel):
    sentiment: str
    sentiment_score: float
    key_indicators: List[str]
    count: int

class DealMomentumIndicators(BaseModel):
    stage_progression: str
    client_engagement_trend: str
    competitive_position: str

class LLMOutput(BaseModel):
    overall_sentiment: str
    sentiment_score: float
    confidence: float
    activity_breakdown: Dict[str, ActivityBreakdown]
    deal_momentum_indicators: DealMomentumIndicators
    reasoning: str
    professional_gaps: List[str]
    excellence_indicators: List[str]
    risk_indicators: List[str]
    opportunity_indicators: List[str]
    temporal_trend: str
    recommended_actions: List[str]
    context_analysis_notes: List[str]

class Rating(BaseModel):
    score: int  # 1-5 scale
    confidence: int  # 1-5 scale
    notes: str = ""

class Annotation(BaseModel):
    user_email: EmailStr
    timestamp: datetime
    ratings: Dict[str, Rating]
    time_spent_seconds: int

class UserProgress(BaseModel):
    completed_count: int
    total_deals: int
    completed_deals: List[str]
    next_deal: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr

class AddUserRequest(BaseModel):
    email: EmailStr
    name: str
    admin_password: str

class RemoveUserRequest(BaseModel):
    email: EmailStr
    keep_progress: bool = False
    admin_password: str

class DealData(BaseModel):
    """Model for deal data with flexible structure"""
    deal_id: str
    amount: Union[str, float]
    dealstage: str
    dealtype: str
    deal_stage_probability: Union[str, float]
    createdate: Union[datetime, str]
    closedate: Optional[Union[datetime, str]] = None
    activities: List[Dict[str, Any]]
    
    class Config:
        # Allow extra fields for flexibility
        extra = "allow"