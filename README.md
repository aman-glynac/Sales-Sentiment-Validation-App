# Deal Validation App

A web application for interns to validate AI-generated sentiment analysis of sales deals.

## Folder Structure

```
deal-validation-app/
├── app/
│   ├── main.py              # FastAPI main application
│   ├── models.py            # Pydantic models
│   ├── auth.py              # Authentication utilities
│   ├── github_utils.py      # GitHub integration
│   └── static/
│       ├── css/
│       │   └── style.css    # Main stylesheet
│       └── js/
│           └── app.js       # Frontend JavaScript
├── templates/
│   ├── login.html           # Login page
│   ├── instructions.html    # Instructions for interns
│   ├── activities.html      # Deal activities view
│   ├── rating.html          # LLM output rating interface
│   └── admin.html           # Admin dashboard
├── data/
│   ├── users.json           # Authorized users
│   ├── deals.json           # Deal data
│   ├── llm_outputs.json     # Pre-generated LLM outputs
│   └── annotations.json     # Intern annotations
├── .env                     # Environment variables
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Setup Instructions

### Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd deal-validation-app
   pip install -r requirements.txt
   python setup.py
   ```

2. **Configure Environment**
   - Update `.env` file with your credentials
   - Update `data/users.json` with intern email addresses
   - Replace `data/deals.json` with your actual deal data
   - Replace `data/llm_outputs.json` with your LLM outputs

3. **Run Application**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Detailed Setup

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Environment Setup

Create a `.env` file with your configuration:
- `ADMIN_PASSWORD`: Password for admin access (required)
- `SECRET_KEY`: JWT secret key (required)
- `GITHUB_TOKEN`: GitHub personal access token (optional)
- `GITHUB_REPO`: Repository for storing annotations (optional)

#### 3. Initialize Data Files

Run the setup script to create sample data files:
```bash
python setup.py
```

Or manually create the data files:

**users.json**
```json
{
  "users": [
    {
      "email": "intern1@company.com",
      "name": "John Doe",
      "is_admin": false,
      "created_at": "2024-07-04T10:00:00Z"
    }
  ]
}
```

**deals.json** - Replace with your actual deal data (Array structure)
```json
[
  {
    "deal_id": "12691023255",
    "activities": [
      {
        "sent_at": "2023-05-22T14:07:15.247Z",
        "from": "salesperson@company.com",
        "to": ["client@company.com"],
        "subject": "Follow up on proposal",
        "body": "Email content here...",
        "state": "email",
        "direction": "outgoing",
        "activity_type": "email"
      },
      {
        "id": "34955940502",
        "createdate": "2023-05-18T15:52:56.590Z",
        "call_title": "Client call",
        "call_body": "Call notes here...",
        "call_direction": "OUTBOUND",
        "call_duration": 30,
        "call_status": "COMPLETED",
        "activity_type": "call"
      }
    ],
    "amount": "12000",
    "closedate": "2023-05-22T14:19:33.980Z",
    "createdate": "2022-12-20T06:00:00Z",
    "dealstage": "Closed won",
    "deal_stage_probability": "100.0",
    "dealtype": "newbusiness"
  }
]
```

**llm_outputs.json** - Replace with your pre-generated LLM outputs (Object structure)
```json
{
  "12691023255": {
    "overall_sentiment": "positive",
    "sentiment_score": 0.65,
    "confidence": 0.85,
    "activity_breakdown": {
      "email": {
        "sentiment": "positive",
        "sentiment_score": 0.7,
        "key_indicators": ["Proactive follow-up"],
        "count": 1
      }
    },
    "deal_momentum_indicators": {
      "stage_progression": "advancing",
      "client_engagement_trend": "increasing",
      "competitive_position": "strengthening"
    },
    "reasoning": "Detailed analysis...",
    "professional_gaps": [],
    "excellence_indicators": ["Proactive communication"],
    "risk_indicators": [],
    "opportunity_indicators": ["Client interest"],
    "temporal_trend": "improving",
    "recommended_actions": ["Continue communication"],
    "context_analysis_notes": ["Pattern observations"]
  }
}
```

#### 4. Run the Application

**Development Mode:**
```bash
python run.py --reload --debug
```

**Production Mode:**
```bash
python run.py --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

### Docker Deployment

#### Development with Docker
```bash
docker build -t deal-validation-app .
docker run -p 8000:8000 -v $(pwd)/data:/app/data --env-file .env deal-validation-app
```

#### Production with Docker Compose
```bash
docker-compose up -d
```

#### Production with Nginx
```bash
docker-compose --profile production up -d
```

## Usage

### For Interns
1. **Login**: Go to the application URL and login with your email address
2. **Read Instructions**: Carefully read the instructions page
3. **Review Activities**: Read through deal activities chronologically
4. **Rate Analysis**: Rate each aspect of the AI's analysis (1-5 scale)
5. **Submit**: Submit your ratings and move to the next deal

### For Admins
1. **Access Dashboard**: Go to `/admin` and enter admin password
2. **Add Users**: Add intern email addresses and names
3. **Monitor Progress**: Track completion rates and progress
4. **Manage Data**: Export annotations and manage user access

### Data Flow
1. **Pre-generate LLM outputs** for all deals in your dataset
2. **Store in JSON format** (`data/llm_outputs.json`)
3. **Interns rate outputs** through the web interface
4. **Annotations stored** in `data/annotations.json` and GitHub (optional)
5. **Export data** for analysis and model improvement

## File Structure Details

```
deal-validation-app/
├── app/
│   ├── main.py              # FastAPI main application
│   ├── models.py            # Pydantic models
│   ├── auth.py              # Authentication utilities
│   ├── github_utils.py      # GitHub integration
│   └── static/
│       ├── css/
│       │   └── style.css    # Main stylesheet
│       └── js/
│           ├── app.js       # Frontend JavaScript
│           └── sw.js        # Service worker
├── templates/
│   ├── login.html           # Login page
│   ├── instructions.html    # Instructions for interns
│   ├── activities.html      # Deal activities view
│   ├── rating.html          # LLM output rating interface
│   └── admin.html           # Admin dashboard
├── data/
│   ├── users.json           # Authorized users
│   ├── deals.json           # Deal data
│   ├── llm_outputs.json     # Pre-generated LLM outputs
│   └── annotations.json     # Intern annotations
├── .env                     # Environment variables
├── requirements.txt         # Python dependencies
├── setup.py                 # Initialization script
├── run.py                   # Application runner
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose configuration
├── nginx.conf              # Nginx configuration
└── README.md               # This file
```

## API Endpoints

### Public Endpoints
- `GET /`: Login page
- `POST /login`: User authentication
- `GET /health`: Health check

### Authenticated Endpoints
- `GET /instructions`: Instructions page
- `GET /activities/{deal_id}`: Deal activities view
- `GET /rating/{deal_id}`: Rating interface
- `POST /submit-rating`: Submit annotation
- `GET /api/progress`: Get user progress
- `GET /logout`: Logout user

### Admin Endpoints
- `GET /admin`: Admin dashboard
- `POST /admin/add-user`: Add new user
- `DELETE /admin/remove-user`: Remove user

## Configuration

### Environment Variables
- `ADMIN_PASSWORD`: Admin dashboard password (required)
- `SECRET_KEY`: JWT signing key (required)
- `GITHUB_TOKEN`: GitHub API token (optional)
- `GITHUB_REPO`: GitHub repository (optional)
- `GITHUB_BRANCH`: Git branch (default: main)
- `DEBUG`: Enable debug mode (default: false)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)

### GitHub Integration
When configured, the app automatically:
- Backs up annotations to GitHub repository
- Provides version control for annotation data
- Enables collaboration and data persistence

## Security Features

- **JWT Authentication**: Secure session management
- **Email Verification**: Users must be pre-authorized
- **Admin Controls**: Separate admin interface with password protection
- **Rate Limiting**: Protection against abuse (when using nginx)
- **HTTPS Support**: SSL/TLS encryption in production
- **Input Validation**: Comprehensive data validation
- **CORS Protection**: Secure cross-origin requests

## Monitoring and Analytics

### Built-in Metrics
- User completion rates
- Time spent per annotation
- Inter-annotator agreement tracking
- Progress monitoring
- System health checks

### Data Export
- JSON format for easy analysis
- GitHub backup for version control
- Admin dashboard for quick insights
- RESTful API for programmatic access

## Troubleshooting

### Common Issues

**"Email not authorized"**
- Check if user email is in `data/users.json`
- Verify email address spelling

**"Deal not found"**
- Ensure deal exists in `data/deals.json`
- Check deal_id format consistency

**"LLM output not found"**  
- Verify LLM output exists in `data/llm_outputs.json`
- Check deal_id matching between files

**GitHub integration not working**
- Verify `GITHUB_TOKEN` has repository access
- Check `GITHUB_REPO` format: `username/repo-name`
- Ensure repository exists and is accessible

**Application won't start**
- Run `python setup.py` to initialize
- Check `.env` file configuration
- Verify all dependencies are installed

### Logs and Debugging
- Enable debug mode: `python run.py --debug`
- Check console output for errors
- Review browser network tab for API issues
- Use health check endpoint: `/health`

## Development

### Adding New Features
1. Update models in `app/models.py`
2. Add API endpoints in `app/main.py`
3. Update frontend in `templates/` and `static/`
4. Test with sample data

### Database Migration
Currently uses JSON files. To migrate to database:
1. Choose database (PostgreSQL, MySQL, SQLite)
2. Update models to use SQLAlchemy
3. Create migration scripts
4. Update data access patterns

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
1. Check this README first
2. Review application logs
3. Test with sample data
4. Contact your administrator