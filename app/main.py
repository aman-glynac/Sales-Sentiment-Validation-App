from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

from .models import *
from .auth import get_current_user, create_access_token, verify_token
from .database import db_manager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Deal Validation App", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

TARGET_ANNOTATIONS_PER_DEAL = 15

def parse_json_field(data, field_name, default=None):
    """Parse JSON field from database"""
    field_data = data.get(field_name, default)
    if isinstance(field_data, str):
        try:
            return json.loads(field_data)
        except:
            return default
    return field_data if field_data is not None else default

def get_deal_annotation_counts(annotations: Dict) -> Dict[str, int]:
    """Get count of unique annotators for each deal"""
    deal_counts = {}
    for deal_id, deal_annotations in annotations.items():
        deal_counts[deal_id] = len(deal_annotations.keys())
    return deal_counts

async def get_next_deal_for_user(email: str) -> Optional[str]:
    """Get next deal ID for user to annotate with intelligent distribution"""
    # Get deals this user has already completed
    user_completed_deals = set(await db_manager.get_user_annotations(email))
    
    # Get all deals
    deals = await db_manager.get_deals()
    
    # Get annotation counts for all deals
    annotation_counts = await db_manager.get_annotation_counts_by_deal()
    
    # Create list of available deals for this user with their current annotation counts
    available_deals = []
    for deal_id in deals.keys():
        deal_id = str(deal_id)
        if deal_id not in user_completed_deals:
            current_count = annotation_counts.get(deal_id, 0)
            if current_count < TARGET_ANNOTATIONS_PER_DEAL:
                available_deals.append((deal_id, current_count))
    
    if not available_deals:
        return None
    
    # Sort by annotation count (ascending) to prioritize deals with fewer annotations
    # Then by deal_id for consistent ordering when counts are equal
    available_deals.sort(key=lambda x: (x[1], x[0]))
    
    # Return the deal with the lowest annotation count
    return available_deals[0][0]

def sort_activities_chronologically(activities: List[Dict]) -> List[Dict]:
    """Sort activities by timestamp"""
    def get_timestamp(activity):
        timestamp_fields = [
            'sent_at', 'createdate', 'meeting_start_time', 'lastmodifieddate'
        ]
        
        for field in timestamp_fields:
            if field in activity and activity[field]:
                try:
                    timestamp_str = activity[field]
                    if isinstance(timestamp_str, str):
                        # Handle various timestamp formats
                        timestamp_str = timestamp_str.replace('Z', '+00:00')
                        return datetime.fromisoformat(timestamp_str)
                except:
                    continue
        
        return datetime.min.replace(tzinfo=timezone.utc)
    
    return sorted(activities, key=get_timestamp)

async def get_admin_dashboard_context(request: Request, authenticated: bool = True):
    """Get admin dashboard context data"""
    if not authenticated:
        return {
            "request": request,
            "authenticated": False
        }
    
    # Get users with their progress
    users = await db_manager.get_users()
    user_progress = []
    
    for user in users:
        progress = await db_manager.get_user_progress(user["email"])
        user_progress.append({
            "email": user["email"],
            "name": user["name"],
            "completed_count": progress["completed_count"],
            "total_deals": progress["total_deals"],
            "is_admin": user.get("is_admin", False)
        })
    
    # Get admin stats
    admin_stats = await db_manager.get_admin_stats()
    
    return {
        "request": request,
        "users": user_progress,
        "total_deals": admin_stats['total_deals'],
        "total_annotations": admin_stats['total_annotations'],
        "completed_deals": admin_stats['completed_deals'],
        "target_annotations_per_deal": TARGET_ANNOTATIONS_PER_DEAL,
        "authenticated": True
    }

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    try:
        await db_manager.initialize()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await db_manager.close()

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...)):
    """Handle user login"""
    # Check if user exists
    user = await db_manager.get_user_by_email(email.lower())
    
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email not authorized. Please contact your administrator."
        })
    
    # Create JWT token
    token = create_access_token(data={"sub": user["email"]})
    
    # Set cookie and redirect
    response = RedirectResponse(url="/instructions", status_code=302)
    response.set_cookie(
        key="access_token", 
        value=token, 
        httponly=True,
        max_age=24*60*60,  # 24 hours
        samesite="lax"
    )
    return response

@app.get("/instructions", response_class=HTMLResponse)
async def instructions(request: Request, current_user: str = Depends(get_current_user)):
    """Instructions page"""
    progress = await db_manager.get_user_progress(current_user)
    
    return templates.TemplateResponse("instructions.html", {
        "request": request,
        "user_email": current_user,
        "progress": progress
    })

@app.get("/start-annotation")
async def start_annotation(current_user: str = Depends(get_current_user)):
    """Start annotation process"""
    next_deal = await get_next_deal_for_user(current_user)
    
    if not next_deal:
        return RedirectResponse(url="/instructions?completed=true", status_code=302)
    
    return RedirectResponse(url=f"/activities/{next_deal}", status_code=302)

@app.get("/api/admin/deal-distribution")
async def get_deal_distribution(admin_token: Optional[str] = Cookie(None)):
    """Get deal annotation distribution for admin monitoring"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    deals = await db_manager.get_deals()
    annotation_counts = await db_manager.get_annotation_counts_by_deal()
    
    distribution_stats = {
        "target_per_deal": TARGET_ANNOTATIONS_PER_DEAL,
        "total_deals": len(deals),
        "completed_deals": 0,
        "in_progress_deals": 0,
        "not_started_deals": 0,
        "deal_details": []
    }
    
    for deal_id in deals.keys():
        deal_id = str(deal_id)
        current_count = annotation_counts.get(deal_id, 0)
        
        status = "not_started"
        if current_count >= TARGET_ANNOTATIONS_PER_DEAL:
            status = "completed"
            distribution_stats["completed_deals"] += 1
        elif current_count > 0:
            status = "in_progress"
            distribution_stats["in_progress_deals"] += 1
        else:
            distribution_stats["not_started_deals"] += 1
        
        distribution_stats["deal_details"].append({
            "deal_id": deal_id,
            "current_annotations": current_count,
            "target_annotations": TARGET_ANNOTATIONS_PER_DEAL,
            "status": status,
            "progress_percentage": (current_count / TARGET_ANNOTATIONS_PER_DEAL * 100) if TARGET_ANNOTATIONS_PER_DEAL > 0 else 0
        })
    
    # Sort by progress (lowest first to show which deals need attention)
    distribution_stats["deal_details"].sort(key=lambda x: x["current_annotations"])
    
    return distribution_stats

@app.get("/activities/{deal_id}", response_class=HTMLResponse)
async def view_activities(request: Request, deal_id: str, current_user: str = Depends(get_current_user)):
    """View deal activities"""
    # Ensure deal_id is string
    deal_id = str(deal_id)
    
    deal = await db_manager.get_deal_by_id(deal_id)
    if not deal:
        return templates.TemplateResponse("activities.html", {
            "request": request,
            "error": f"Deal {deal_id} not found",
            "user_email": current_user,
            "progress": await db_manager.get_user_progress(current_user)
        })
    
    # Check if user already completed this deal
    user_completed_deals = await db_manager.get_user_annotations(current_user)
    if deal_id in user_completed_deals:
        return templates.TemplateResponse("activities.html", {
            "request": request,
            "error": "You have already completed this deal. Please continue with the next one.",
            "user_email": current_user,
            "progress": await db_manager.get_user_progress(current_user)
        })
    
    # Parse activities from JSON string to Python objects
    activities = parse_json_field(deal, "activities", [])
    
    # Sort activities chronologically
    activities = sort_activities_chronologically(activities)
    
    return templates.TemplateResponse("activities.html", {
        "request": request,
        "deal": deal,
        "activities": activities,
        "deal_id": deal_id,
        "user_email": current_user,
        "progress": await db_manager.get_user_progress(current_user)
    })

@app.get("/rating/{deal_id}", response_class=HTMLResponse)
async def rating_interface(request: Request, deal_id: str, current_user: str = Depends(get_current_user)):
    """Rating interface for LLM outputs"""
    # Ensure deal_id is string
    deal_id = str(deal_id)
    
    deal = await db_manager.get_deal_by_id(deal_id)
    if not deal:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": f"Deal {deal_id} not found",
            "user_email": current_user,
            "progress": await db_manager.get_user_progress(current_user)
        })
    
    llm_output_raw = await db_manager.get_llm_output_by_deal_id(deal_id)
    if not llm_output_raw:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": f"AI analysis not found for deal {deal_id}",
            "user_email": current_user,
            "progress": await db_manager.get_user_progress(current_user)
        })
    
    # Parse JSON fields in LLM output
    llm_output = {
        "overall_sentiment": llm_output_raw.get("overall_sentiment"),
        "sentiment_score": llm_output_raw.get("sentiment_score"),
        "confidence": llm_output_raw.get("confidence"),
        "activity_breakdown": parse_json_field(llm_output_raw, "activity_breakdown", {}),
        "deal_momentum_indicators": parse_json_field(llm_output_raw, "deal_momentum_indicators", {}),
        "reasoning": llm_output_raw.get("reasoning"),
        "professional_gaps": parse_json_field(llm_output_raw, "professional_gaps", []),
        "excellence_indicators": parse_json_field(llm_output_raw, "excellence_indicators", []),
        "risk_indicators": parse_json_field(llm_output_raw, "risk_indicators", []),
        "opportunity_indicators": parse_json_field(llm_output_raw, "opportunity_indicators", []),
        "temporal_trend": llm_output_raw.get("temporal_trend"),
        "recommended_actions": parse_json_field(llm_output_raw, "recommended_actions", []),
        "context_analysis_notes": parse_json_field(llm_output_raw, "context_analysis_notes", [])
    }
    
    # Check if user already completed this deal
    user_completed_deals = await db_manager.get_user_annotations(current_user)
    if deal_id in user_completed_deals:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": "You have already completed this deal. Please continue with the next one.",
            "user_email": current_user,
            "progress": await db_manager.get_user_progress(current_user)
        })
    
    return templates.TemplateResponse("rating.html", {
        "request": request,
        "deal": deal,
        "llm_output": llm_output,
        "deal_id": deal_id,
        "user_email": current_user,
        "progress": await db_manager.get_user_progress(current_user)
    })

@app.post("/submit-rating")
async def submit_rating(request: Request, current_user: str = Depends(get_current_user)):
    """Submit annotation rating"""
    form_data = await request.form()
    
    deal_id = str(form_data.get("deal_id"))
    if not deal_id:
        raise HTTPException(status_code=400, detail="Deal ID required")
    
    # Check if user already completed this deal
    user_completed_deals = await db_manager.get_user_annotations(current_user)
    if deal_id in user_completed_deals:
        raise HTTPException(status_code=400, detail="Deal already completed")
    
    # Extract ratings
    ratings = {}
    rating_fields = [
        "overall_sentiment", "activity_breakdown", "deal_momentum_indicators",
        "reasoning", "professional_gaps", "excellence_indicators",
        "risk_indicators", "opportunity_indicators", "temporal_trend",
        "recommended_actions"
    ]
    
    # Validate all required fields
    missing_fields = []
    for field in rating_fields:
        score = form_data.get(f"{field}_score")
        confidence = form_data.get(f"{field}_confidence")
        
        if not score or not confidence:
            missing_fields.append(field)
        else:
            ratings[field] = {
                "score": int(score),
                "confidence": int(confidence),
                "notes": form_data.get(f"{field}_notes", "")
            }
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing ratings for: {', '.join(missing_fields)}"
        )
    
    # Save annotation to database
    time_spent = int(form_data.get("time_spent", 0))
    success = await db_manager.create_annotation(deal_id, current_user, ratings, time_spent)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save annotation")
    
    # Get next deal
    next_deal = await get_next_deal_for_user(current_user)
    
    # Update user progress
    progress = await db_manager.get_user_progress(current_user)
    
    return JSONResponse({
        "message": "Rating submitted successfully", 
        "next_deal": next_deal,
        "completed_count": progress["completed_count"]
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin_token: Optional[str] = Cookie(None)):
    """Admin dashboard with persistent session"""
    # Check if already authenticated via cookie
    if admin_token and admin_token == os.getenv("ADMIN_PASSWORD"):
        context = await get_admin_dashboard_context(request, authenticated=True)
        return templates.TemplateResponse("admin.html", context)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "authenticated": False
    })

@app.post("/admin", response_class=HTMLResponse)
async def admin_login(request: Request, admin_password: str = Form(...)):
    """Admin login"""
    if admin_password != os.getenv("ADMIN_PASSWORD"):
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "error": "Invalid admin password",
            "authenticated": False
        })
    
    # Get dashboard data
    context = await get_admin_dashboard_context(request, authenticated=True)
    
    # Create response with cookie
    response = templates.TemplateResponse("admin.html", context)
    response.set_cookie(
        key="admin_token",
        value=admin_password,
        httponly=True,
        max_age=3600,  # 1 hour
        samesite="lax"
    )
    return response

@app.post("/admin/add-user")
async def add_user(
    request: Request,
    email: str = Form(...), 
    name: str = Form(...),
    admin_token: Optional[str] = Cookie(None)
):
    """Add new user"""
    # Check admin authentication from cookie
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin authentication required")
    
    # Check if user already exists
    existing_user = await db_manager.get_user_by_email(email.lower())
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create new user
    success = await db_manager.create_user(email.lower(), name, False)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    return JSONResponse({"message": "User added successfully"})

@app.delete("/admin/remove-user")
async def remove_user(
    request: Request,
    email: str = Form(...), 
    keep_progress: bool = Form(False),
    admin_token: Optional[str] = Cookie(None)
):
    """Remove user"""
    # Check admin authentication from cookie
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin authentication required")
    
    # Check if user exists
    user = await db_manager.get_user_by_email(email.lower())
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove user's annotations if not keeping progress
    if not keep_progress:
        await db_manager.delete_user_annotations(email.lower())
    
    # Remove user
    success = await db_manager.delete_user(email.lower())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove user")
    
    return JSONResponse({"message": "User removed successfully"})

@app.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("admin_token")
    return response

@app.get("/api/progress")
async def get_progress_api(current_user: str = Depends(get_current_user)):
    """Get user progress API"""
    progress = await db_manager.get_user_progress(current_user)
    return progress

@app.get("/api/admin/stats")
async def get_admin_stats(request: Request, admin_token: Optional[str] = Cookie(None)):
    """Get admin statistics"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin_stats = await db_manager.get_admin_stats()
    
    # Calculate target total annotations
    target_total_annotations = admin_stats['total_deals'] * TARGET_ANNOTATIONS_PER_DEAL
    
    # Get user completion stats
    users = await db_manager.get_users()
    completion_stats = []
    
    for user in users:
        progress = await db_manager.get_user_progress(user["email"])
        completion_stats.append({
            "email": user["email"],
            "completed": progress["completed_count"],
            "percentage": (progress["completed_count"] / progress["total_deals"] * 100) if progress["total_deals"] > 0 else 0
        })
    
    return {
        "total_users": admin_stats['total_users'],
        "total_deals": admin_stats['total_deals'],
        "total_annotations": admin_stats['total_annotations'],
        "target_total_annotations": target_total_annotations,
        "overall_progress": (admin_stats['total_annotations'] / target_total_annotations * 100) if target_total_annotations > 0 else 0,
        "user_stats": completion_stats
    }

@app.get("/api/download/{data_type}")
async def download_data(data_type: str, admin_token: Optional[str] = Cookie(None)):
    """Download data as JSON"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if data_type == "users":
        users = await db_manager.get_users()
        data = {"users": users}
    elif data_type == "annotations":
        data = await db_manager.get_annotations()
    elif data_type == "deals":
        deals_raw = await db_manager.get_deals()
        # Parse JSON fields for export
        deals = {}
        for deal_id, deal_data in deals_raw.items():
            deals[deal_id] = dict(deal_data)
            deals[deal_id]["activities"] = parse_json_field(deal_data, "activities", [])
        data = deals
    elif data_type == "llm_outputs":
        llm_outputs_raw = await db_manager.get_llm_outputs()
        # Parse JSON fields for export
        llm_outputs = {}
        for deal_id, output_data in llm_outputs_raw.items():
            llm_outputs[deal_id] = {
                "overall_sentiment": output_data.get("overall_sentiment"),
                "sentiment_score": output_data.get("sentiment_score"),
                "confidence": output_data.get("confidence"),
                "activity_breakdown": parse_json_field(output_data, "activity_breakdown", {}),
                "deal_momentum_indicators": parse_json_field(output_data, "deal_momentum_indicators", {}),
                "reasoning": output_data.get("reasoning"),
                "professional_gaps": parse_json_field(output_data, "professional_gaps", []),
                "excellence_indicators": parse_json_field(output_data, "excellence_indicators", []),
                "risk_indicators": parse_json_field(output_data, "risk_indicators", []),
                "opportunity_indicators": parse_json_field(output_data, "opportunity_indicators", []),
                "temporal_trend": output_data.get("temporal_trend"),
                "recommended_actions": parse_json_field(output_data, "recommended_actions", []),
                "context_analysis_notes": parse_json_field(output_data, "context_analysis_notes", [])
            }
        data = llm_outputs
    else:
        raise HTTPException(status_code=404, detail="Invalid data type")
    
    # Return as downloadable JSON
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f"attachment; filename={data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connectivity
        db_healthy = await db_manager.health_check()
        
        if not db_healthy:
            return JSONResponse({
                "status": "unhealthy",
                "reason": "Database connection failed",
                "timestamp": datetime.utcnow().isoformat()
            }, status_code=503)
        
        # Get basic stats to verify data availability
        admin_stats = await db_manager.get_admin_stats()
        
        return JSONResponse({
            "status": "healthy",
            "version": "2.0.0",
            "database_status": "connected",
            "data_stats": {
                "users": admin_stats['total_users'],
                "deals": admin_stats['total_deals'],
                "annotations": admin_stats['total_annotations']
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "reason": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, status_code=503)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)