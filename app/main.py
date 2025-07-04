from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import json
import os
from typing import Optional, Dict, List
from dotenv import load_dotenv

from models import *
from auth import *
from github_utils import GitHubManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Sales Sentiment Validation App", version="1.0.0")

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

def load_json_file(file_path: str) -> Dict:
    """Load JSON file with error handling and structure normalization"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Handle different data structures
        if file_path.endswith('deals.json'):
            # Convert array structure to dict for easier access
            if isinstance(data, list):
                deals_dict = {}
                for deal in data:
                    deal_id = deal.get('deal_id')
                    if deal_id:
                        deals_dict[deal_id] = deal
                return deals_dict
            return data
        elif file_path.endswith('llm_outputs.json'):
            # Convert array structure to dict if needed
            if isinstance(data, list):
                outputs_dict = {}
                for output in data:
                    deal_id = output.get('deal_id')
                    if deal_id:
                        outputs_dict[deal_id] = output
                return outputs_dict
            return data
        else:
            return data
    except FileNotFoundError:
        return {} if not file_path.endswith('users.json') else {"users": []}
    except json.JSONDecodeError:
        return {} if not file_path.endswith('users.json') else {"users": []}

def save_json_file(file_path: str, data: Dict):
    """Save JSON file with error handling"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def get_user_progress(email: str) -> Dict:
    """Get user's annotation progress"""
    annotations = load_json_file(ANNOTATIONS_FILE)
    completed_deals = []
    
    for deal_id, deal_annotations in annotations.items():
        if email in deal_annotations:
            completed_deals.append(deal_id)
    
    return {
        "completed_count": len(completed_deals),
        "completed_deals": completed_deals
    }

def get_next_deal_for_user(email: str) -> Optional[str]:
    """Get next deal ID for user to annotate"""
    deals = load_json_file(DEALS_FILE)
    progress = get_user_progress(email)
    
    for deal_id in deals.keys():
        if deal_id not in progress["completed_deals"]:
            return deal_id
    
    return None

def sort_activities_chronologically(activities: List[Dict]) -> List[Dict]:
    """Sort activities by timestamp - handles multiple timestamp fields"""
    def get_timestamp(activity):
        # Try different timestamp fields based on activity type
        timestamp_fields = [
            'sent_at',           # Email
            'createdate',        # Call, Note, Task
            'meeting_start_time', # Meeting
            'lastmodifieddate'   # Note (fallback)
        ]
        
        for field in timestamp_fields:
            if field in activity and activity[field]:
                try:
                    # Handle both Z and +00:00 timezone formats
                    timestamp_str = activity[field].replace('Z', '+00:00')
                    return datetime.fromisoformat(timestamp_str)
                except (ValueError, TypeError):
                    continue
        
        # If no valid timestamp found, return minimum date
        return datetime.min.replace(tzinfo=None)
    
    return sorted(activities, key=get_timestamp)

def format_deal_amount(amount_str: str) -> str:
    """Format deal amount string as currency"""
    try:
        amount = float(amount_str)
        return f"${amount:,.2f}"
    except (ValueError, TypeError):
        return f"${amount_str}"

def format_deal_probability(prob_str: str) -> str:
    """Format deal probability string as percentage"""
    try:
        prob = float(prob_str)
        return f"{prob:.1f}%"
    except (ValueError, TypeError):
        return f"{prob_str}%"

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
        if user["email"] == email:
            user_exists = True
            break
    
    if not user_exists:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email not authorized. Please contact admin."
        })
    
    # Create JWT token
    token = create_access_token(data={"sub": email})
    
    # Set cookie and redirect
    response = RedirectResponse(url="/instructions", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

@app.get("/instructions", response_class=HTMLResponse)
async def instructions(request: Request, current_user: str = Depends(get_current_user)):
    """Instructions page"""
    return templates.TemplateResponse("instructions.html", {
        "request": request,
        "user_email": current_user
    })

@app.get("/start-annotation")
async def start_annotation(current_user: str = Depends(get_current_user)):
    """Start annotation process"""
    next_deal = get_next_deal_for_user(current_user)
    
    if not next_deal:
        return JSONResponse({"message": "No more deals to annotate"}, status_code=200)
    
    return RedirectResponse(url=f"/activities/{next_deal}", status_code=302)

@app.get("/activities/{deal_id}", response_class=HTMLResponse)
async def view_activities(request: Request, deal_id: str, current_user: str = Depends(get_current_user)):
    """View deal activities"""
    deals = load_json_file(DEALS_FILE)
    
    if deal_id not in deals:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Check if user already completed this deal
    progress = get_user_progress(current_user)
    if deal_id in progress["completed_deals"]:
        return templates.TemplateResponse("activities.html", {
            "request": request,
            "error": "You have already completed this deal",
            "user_email": current_user
        })
    
    deal = deals[deal_id]
    
    # Sort activities chronologically
    activities = sort_activities_chronologically(deal.get("activities", []))
    
    return templates.TemplateResponse("activities.html", {
        "request": request,
        "deal": deal,
        "activities": activities,
        "deal_id": deal_id,
        "user_email": current_user
    })

@app.get("/rating/{deal_id}", response_class=HTMLResponse)
async def rating_interface(request: Request, deal_id: str, current_user: str = Depends(get_current_user)):
    """Rating interface for LLM outputs"""
    deals = load_json_file(DEALS_FILE)
    llm_outputs = load_json_file(LLM_OUTPUTS_FILE)
    
    if deal_id not in deals:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    if deal_id not in llm_outputs:
        raise HTTPException(status_code=404, detail="LLM output not found")
    
    # Check if user already completed this deal
    progress = get_user_progress(current_user)
    if deal_id in progress["completed_deals"]:
        return templates.TemplateResponse("rating.html", {
            "request": request,
            "error": "You have already completed this deal",
            "user_email": current_user
        })
    
    deal = deals[deal_id]
    llm_output = llm_outputs[deal_id]
    
    return templates.TemplateResponse("rating.html", {
        "request": request,
        "deal": deal,
        "llm_output": llm_output,
        "deal_id": deal_id,
        "user_email": current_user
    })

@app.post("/submit-rating")
async def submit_rating(request: Request, current_user: str = Depends(get_current_user)):
    """Submit annotation rating"""
    form_data = await request.form()
    
    deal_id = form_data.get("deal_id")
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
    
    for field in rating_fields:
        score = form_data.get(f"{field}_score")
        confidence = form_data.get(f"{field}_confidence")
        notes = form_data.get(f"{field}_notes")
        
        ratings[field] = {
            "score": int(score) if score else None,
            "confidence": int(confidence) if confidence else None,
            "notes": notes or ""
        }
    
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
        # Continue anyway - we have local backup
    
    return JSONResponse({"message": "Rating submitted successfully", "next_deal": get_next_deal_for_user(current_user)})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_get(request: Request):
    """Admin dashboard GET - show login form"""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "authenticated": False
    })

@app.post("/admin", response_class=HTMLResponse)
async def admin_dashboard_post(request: Request, admin_password: str = Form(...)):
    """Admin dashboard POST - handle login"""
    if admin_password != os.getenv("ADMIN_PASSWORD"):
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "error": "Invalid admin password",
            "authenticated": False
        })
    
    users_data = load_json_file(USERS_FILE)
    annotations = load_json_file(ANNOTATIONS_FILE)
    deals = load_json_file(DEALS_FILE)
    
    # Calculate progress for each user
    user_progress = []
    for user in users_data.get("users", []):
        progress = get_user_progress(user["email"])
        user_progress.append({
            "email": user["email"],
            "name": user["name"],
            "completed_count": progress["completed_count"],
            "total_deals": len(deals)
        })
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "users": user_progress,
        "total_deals": len(deals),
        "total_annotations": len(annotations),
        "authenticated": True
    })

@app.post("/admin/add-user")
async def add_user(request: Request, admin_password: str = Form(...), email: str = Form(...), name: str = Form(...)):
    """Add new user"""
    if admin_password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Invalid admin password")
    
    users_data = load_json_file(USERS_FILE)
    
    # Check if user already exists
    for user in users_data.get("users", []):
        if user["email"] == email:
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
async def remove_user(request: Request, admin_password: str = Form(...), email: str = Form(...), keep_progress: bool = Form(False)):
    """Remove user"""
    if admin_password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=403, detail="Invalid admin password")
    
    users_data = load_json_file(USERS_FILE)
    
    # Remove user from users list
    users_data["users"] = [user for user in users_data.get("users", []) if user["email"] != email]
    save_json_file(USERS_FILE, users_data)
    
    # Remove user's annotations if not keeping progress
    if not keep_progress:
        annotations = load_json_file(ANNOTATIONS_FILE)
        for deal_id in annotations:
            if email in annotations[deal_id]:
                del annotations[deal_id][email]
        save_json_file(ANNOTATIONS_FILE, annotations)
    
    return JSONResponse({"message": "User removed successfully"})

@app.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/api/progress")
async def get_progress(current_user: str = Depends(get_current_user)):
    """Get user progress"""
    progress = get_user_progress(current_user)
    deals = load_json_file(DEALS_FILE)
    
    return {
        "completed_count": progress["completed_count"],
        "total_deals": len(deals),
        "next_deal": get_next_deal_for_user(current_user)
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check if essential files exist
        essential_files = [USERS_FILE, DEALS_FILE, LLM_OUTPUTS_FILE, ANNOTATIONS_FILE]
        for file_path in essential_files:
            if not os.path.exists(file_path):
                return {"status": "unhealthy", "reason": f"Missing file: {file_path}"}
        
        # Check if files are readable
        for file_path in essential_files:
            try:
                load_json_file(file_path)
            except Exception as e:
                return {"status": "unhealthy", "reason": f"Cannot read file {file_path}: {str(e)}"}
        
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)