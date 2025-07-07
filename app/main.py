from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

from models import *
from auth import *
from github_utils import GitHubManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Deal Validation App", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize GitHub manager
github_manager = GitHubManager()

# File paths
USERS_FILE = os.getenv("USERS_FILE", "./data/users.json")
DEALS_FILE = os.getenv("DEALS_FILE", "./data/deals.json")
LLM_OUTPUTS_FILE = os.getenv("LLM_OUTPUTS_FILE", "./data/llm_outputs.json")
ANNOTATIONS_FILE = os.getenv("ANNOTATIONS_FILE", "./data/annotations.json")

TARGET_ANNOTATIONS_PER_DEAL = 3

def load_json_file(file_path: str) -> Dict:
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Normalize data structures
        if file_path.endswith('deals.json'):
            # Always work with dict structure
            if isinstance(data, list):
                normalized = {}
                for deal in data:
                    if 'deal_id' in deal:
                        normalized[str(deal['deal_id'])] = deal
                data = normalized
            # Ensure all deal_ids are strings
            else:
                normalized = {}
                for key, value in data.items():
                    normalized[str(key)] = value
                data = normalized
        
        elif file_path.endswith('llm_outputs.json'):
            # Normalize to dict if array
            if isinstance(data, list):
                normalized = {k: v for d in data for k, v in d.items()}
                data = normalized
            # Ensure all keys are strings
            else:
                normalized = {}
                for key, value in data.items():
                    normalized[str(key)] = value
                data = normalized
        
        elif file_path.endswith('users.json'):
            # Ensure proper structure
            if not isinstance(data, dict) or 'users' not in data:
                data = {"users": data if isinstance(data, list) else []}
        
        return data
        
    except FileNotFoundError:
        if file_path.endswith('users.json'):
            return {"users": []}
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {file_path}: {e}")
        if file_path.endswith('users.json'):
            return {"users": []}
        return {}
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}

def save_json_file(file_path: str, data: Dict):
    """Save JSON file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_deal_annotation_counts(annotations: Dict) -> Dict[str, int]:
    """Get count of unique annotators for each deal"""
    deal_counts = {}
    for deal_id, deal_annotations in annotations.items():
        deal_counts[deal_id] = len(deal_annotations.keys())
    return deal_counts

def get_next_deal_for_user(email: str) -> Optional[str]:
    """Get next deal ID for user to annotate with intelligent distribution"""
    deals = load_json_file(DEALS_FILE)
    annotations = load_json_file(ANNOTATIONS_FILE)
    
    # Get deals this user has already completed
    user_completed_deals = set()
    for deal_id, deal_annotations in annotations.items():
        if email in deal_annotations:
            user_completed_deals.add(str(deal_id))
    
    # Get annotation counts for all deals
    deal_counts = get_deal_annotation_counts(annotations)
    
    # Create list of available deals for this user with their current annotation counts
    available_deals = []
    for deal_id in deals.keys():
        deal_id = str(deal_id)
        if deal_id not in user_completed_deals:
            current_count = deal_counts.get(deal_id, 0)
            if current_count < TARGET_ANNOTATIONS_PER_DEAL:
                available_deals.append((deal_id, current_count))
    
    if not available_deals:
        return None
    
    # Sort by annotation count (ascending) to prioritize deals with fewer annotations
    # Then by deal_id for consistent ordering when counts are equal
    available_deals.sort(key=lambda x: (x[1], x[0]))
    
    # Return the deal with the lowest annotation count
    return available_deals[0][0]

def get_user_progress(email: str) -> Dict:
    """Get user's annotation progress with updated logic"""
    annotations = load_json_file(ANNOTATIONS_FILE)
    deals = load_json_file(DEALS_FILE)
    
    # Get deals this user has completed
    completed_deals = []
    for deal_id, deal_annotations in annotations.items():
        if email in deal_annotations:
            completed_deals.append(deal_id)
    
    # Calculate total possible deals for this user
    # This is the number of deals that still need annotations
    deal_counts = get_deal_annotation_counts(annotations)
    available_deals_for_user = 0
    
    for deal_id in deals.keys():
        deal_id = str(deal_id)
        current_count = deal_counts.get(deal_id, 0)
        if current_count < TARGET_ANNOTATIONS_PER_DEAL and deal_id not in completed_deals:
            available_deals_for_user += 1
    
    total_possible_for_user = len(completed_deals) + available_deals_for_user
    
    return {
        "completed_count": len(completed_deals),
        "total_deals": total_possible_for_user,
        "completed_deals": completed_deals
    }

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

def get_admin_dashboard_context(request: Request, authenticated: bool = True):
    """Get admin dashboard context data"""
    if not authenticated:
        return {
            "request": request,
            "authenticated": False
        }
    
    users_data = load_json_file(USERS_FILE)
    annotations = load_json_file(ANNOTATIONS_FILE)
    deals = load_json_file(DEALS_FILE)
    
    # Calculate detailed progress for each user
    user_progress = []
    total_annotations = 0
    
    for user in users_data.get("users", []):
        progress = get_user_progress(user["email"])
        user_progress.append({
            "email": user["email"],
            "name": user["name"],
            "completed_count": progress["completed_count"],
            "total_deals": progress["total_deals"],  # This is now user-specific
            "is_admin": user.get("is_admin", False)
        })
        total_annotations += progress["completed_count"]
    
    # Calculate deal distribution stats
    deal_counts = get_deal_annotation_counts(annotations)
    completed_deals = sum(1 for count in deal_counts.values() if count >= TARGET_ANNOTATIONS_PER_DEAL)
    
    return {
        "request": request,
        "users": user_progress,
        "total_deals": len(deals),
        "total_annotations": total_annotations,
        "completed_deals": completed_deals,
        "target_annotations_per_deal": TARGET_ANNOTATIONS_PER_DEAL,
        "authenticated": True
    }

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...)):
    """Handle user login"""
    users_data = load_json_file(USERS_FILE)
    
    # Check if user exists
    user_exists = False
    for user in users_data.get("users", []):
        if user["email"].lower() == email.lower():
            user_exists = True
            email = user["email"]  # Use the exact case from the database
            break
    
    if not user_exists:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email not authorized. Please contact your administrator."
        })
    
    # Create JWT token
    token = create_access_token(data={"sub": email})
    
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
    progress = get_user_progress(current_user)
    
    return templates.TemplateResponse("instructions.html", {
        "request": request,
        "user_email": current_user,
        "progress": progress
    })

@app.get("/start-annotation")
async def start_annotation(current_user: str = Depends(get_current_user)):
    """Start annotation process"""
    next_deal = get_next_deal_for_user(current_user)
    
    if not next_deal:
        return RedirectResponse(url="/instructions?completed=true", status_code=302)
    
    return RedirectResponse(url=f"/activities/{next_deal}", status_code=302)

@app.get("/api/admin/deal-distribution")
async def get_deal_distribution(admin_token: Optional[str] = Cookie(None)):
    """Get deal annotation distribution for admin monitoring"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    deals = load_json_file(DEALS_FILE)
    annotations = load_json_file(ANNOTATIONS_FILE)
    deal_counts = get_deal_annotation_counts(annotations)
    
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
        current_count = deal_counts.get(deal_id, 0)
        
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
    deals = load_json_file(DEALS_FILE)
    
    # Ensure deal_id is string
    deal_id = str(deal_id)
    
    if deal_id not in deals:
        return templates.TemplateResponse("activities.html", {
            "request": request,
            "error": f"Deal {deal_id} not found",
            "user_email": current_user,
            "progress": get_user_progress(current_user)
        })
    
    # Check if user already completed this deal
    progress = get_user_progress(current_user)
    if deal_id in progress["completed_deals"]:
        return templates.TemplateResponse("activities.html", {
            "request": request,
            "error": "You have already completed this deal. Please continue with the next one.",
            "user_email": current_user,
            "progress": progress
        })
    
    deal = deals[deal_id]
    
    # Sort activities chronologically
    activities = sort_activities_chronologically(deal.get("activities", []))
    
    return templates.TemplateResponse("activities.html", {
        "request": request,
        "deal": deal,
        "activities": activities,
        "deal_id": deal_id,
        "user_email": current_user,
        "progress": progress
    })

@app.get("/rating/{deal_id}", response_class=HTMLResponse)
async def rating_interface(request: Request, deal_id: str, current_user: str = Depends(get_current_user)):
    """Rating interface for LLM outputs"""
    deals = load_json_file(DEALS_FILE)
    llm_outputs = load_json_file(LLM_OUTPUTS_FILE)

    # Ensure deal_id is string
    deal_id = str(deal_id)
    
    if deal_id not in deals:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": f"Deal {deal_id} not found",
            "user_email": current_user,
            "progress": get_user_progress(current_user)
        })
    
    # if deal_id not in llm_outputs:
    #     return templates.TemplateResponse("rating.html", {
    #         "request": request,
    #         "error": f"AI analysis not found for deal {deal_id}",
    #         "user_email": current_user,
    #         "progress": get_user_progress(current_user)
    #     })
    
    # Check if user already completed this deal
    progress = get_user_progress(current_user)
    if deal_id in progress["completed_deals"]:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": "You have already completed this deal. Please continue with the next one.",
            "user_email": current_user,
            "progress": progress
        })
    
    deal = deals[deal_id]
    llm_output = llm_outputs[deal_id]
    
    return templates.TemplateResponse("rating.html", {
        "request": request,
        "deal": deal,
        "llm_output": llm_output,
        "deal_id": deal_id,
        "user_email": current_user,
        "progress": progress
    })

@app.post("/submit-rating")
async def submit_rating(request: Request, current_user: str = Depends(get_current_user)):
    """Submit annotation rating"""
    form_data = await request.form()
    
    deal_id = str(form_data.get("deal_id"))
    if not deal_id:
        raise HTTPException(status_code=400, detail="Deal ID required")
    
    # Check if user already completed this deal
    progress = get_user_progress(current_user)
    if deal_id in progress["completed_deals"]:
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
    
    # Create annotation entry
    annotation = {
        "user_email": current_user,
        "timestamp": datetime.utcnow().isoformat(),
        "ratings": ratings,
        "time_spent_seconds": int(form_data.get("time_spent", 0))
    }
    
    # Load and update annotations
    annotations = load_json_file(ANNOTATIONS_FILE)
    
    if deal_id not in annotations:
        annotations[deal_id] = {}
    
    annotations[deal_id][current_user] = annotation
    
    # Save to local file
    save_json_file(ANNOTATIONS_FILE, annotations)
    
    # Save to GitHub
    try:
        github_manager.update_annotations(annotations)
    except Exception as e:
        print(f"GitHub update failed: {e}")
    
    # Get next deal
    next_deal = get_next_deal_for_user(current_user)
    
    return JSONResponse({
        "message": "Rating submitted successfully", 
        "next_deal": next_deal,
        "completed_count": len(progress["completed_deals"]) + 1
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin_token: Optional[str] = Cookie(None)):
    """Admin dashboard with persistent session"""
    # Check if already authenticated via cookie
    if admin_token and admin_token == os.getenv("ADMIN_PASSWORD"):
        context = get_admin_dashboard_context(request, authenticated=True)
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
    context = get_admin_dashboard_context(request, authenticated=True)
    
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
    
    users_data = load_json_file(USERS_FILE)
    
    # Check if user already exists (case-insensitive)
    for user in users_data.get("users", []):
        if user["email"].lower() == email.lower():
            raise HTTPException(status_code=400, detail="User already exists")
    
    # Add new user
    new_user = {
        "email": email,
        "name": name,
        "is_admin": False,
        "created_at": datetime.utcnow().isoformat()
    }
    
    if "users" not in users_data:
        users_data["users"] = []
    
    users_data["users"].append(new_user)
    save_json_file(USERS_FILE, users_data)
    
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
    
    users_data = load_json_file(USERS_FILE)
    
    # Remove user from users list
    original_count = len(users_data.get("users", []))
    users_data["users"] = [
        user for user in users_data.get("users", []) 
        if user["email"].lower() != email.lower()
    ]
    
    if len(users_data["users"]) == original_count:
        raise HTTPException(status_code=404, detail="User not found")
    
    save_json_file(USERS_FILE, users_data)
    
    # Remove user's annotations if not keeping progress
    if not keep_progress:
        annotations = load_json_file(ANNOTATIONS_FILE)
        modified = False
        
        for deal_id in list(annotations.keys()):
            if email in annotations[deal_id]:
                del annotations[deal_id][email]
                modified = True
                # Remove empty deal entries
                if not annotations[deal_id]:
                    del annotations[deal_id]
        
        if modified:
            save_json_file(ANNOTATIONS_FILE, annotations)
    
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
    progress = get_user_progress(current_user)
    return progress

@app.get("/api/admin/stats")
async def get_admin_stats(request: Request, admin_token: Optional[str] = Cookie(None)):
    """Get admin statistics"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users_data = load_json_file(USERS_FILE)
    annotations = load_json_file(ANNOTATIONS_FILE)
    deals = load_json_file(DEALS_FILE)
    
    # Calculate statistics with new logic
    total_users = len(users_data.get("users", []))
    total_deals = len(deals)
    total_annotations = sum(len(deal_annots) for deal_annots in annotations.values())
    
    # Calculate target total annotations (deals * target per deal)
    target_total_annotations = total_deals * TARGET_ANNOTATIONS_PER_DEAL
    
    # User completion stats
    completion_stats = []
    for user in users_data.get("users", []):
        progress = get_user_progress(user["email"])
        completion_stats.append({
            "email": user["email"],
            "completed": progress["completed_count"],
            "percentage": (progress["completed_count"] / progress["total_deals"] * 100) if progress["total_deals"] > 0 else 0
        })
    
    return {
        "total_users": total_users,
        "total_deals": total_deals,
        "total_annotations": total_annotations,
        "target_total_annotations": target_total_annotations,
        "overall_progress": (total_annotations / target_total_annotations * 100) if target_total_annotations > 0 else 0,
        "user_stats": completion_stats
    }

@app.get("/api/download/{data_type}")
async def download_data(data_type: str, admin_token: Optional[str] = Cookie(None)):
    """Download data as JSON"""
    if not admin_token or admin_token != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if data_type == "users":
        data = load_json_file(USERS_FILE)
    elif data_type == "annotations":
        data = load_json_file(ANNOTATIONS_FILE)
    elif data_type == "deals":
        data = load_json_file(DEALS_FILE)
    elif data_type == "llm_outputs":
        data = load_json_file(LLM_OUTPUTS_FILE)
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
        # Check essential files
        essential_files = [USERS_FILE, DEALS_FILE, LLM_OUTPUTS_FILE, ANNOTATIONS_FILE]
        missing_files = []
        
        for file_path in essential_files:
            if not os.path.exists(file_path):
                missing_files.append(os.path.basename(file_path))
        
        if missing_files:
            return {
                "status": "unhealthy",
                "reason": f"Missing files: {', '.join(missing_files)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test file readability
        for file_path in essential_files:
            try:
                load_json_file(file_path)
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "reason": f"Cannot read {os.path.basename(file_path)}: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "reason": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)