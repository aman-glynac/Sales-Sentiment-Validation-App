import os
import json
import requests
import base64
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class GitHubManager:
    """Manage GitHub repository operations for storing annotations"""
    
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo = os.getenv("GITHUB_REPO")
        self.branch = os.getenv("GITHUB_BRANCH", "main")
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        
        if not self.token or not self.repo:
            print("Warning: GitHub configuration not found. Annotations will only be stored locally.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get GitHub API headers"""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    
    def _get_file_content(self, file_path: str) -> tuple[str, str]:
        """Get file content and SHA from GitHub"""
        url = f"{self.base_url}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content, data["sha"]
            elif response.status_code == 404:
                return "", ""  # File doesn't exist
            else:
                raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Error fetching file from GitHub: {e}")
            return "", ""
    
    def _update_file(self, file_path: str, content: str, sha: str = "", message: str = "") -> bool:
        """Update file on GitHub"""
        url = f"{self.base_url}/contents/{file_path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message or f"Update {file_path}",
            "content": encoded_content,
            "branch": self.branch
        }
        
        if sha:
            data["sha"] = sha
        
        try:
            response = requests.put(url, json=data, headers=self._get_headers())
            
            if response.status_code in [200, 201]:
                return True
            else:
                print(f"GitHub API error: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            print(f"Error updating file on GitHub: {e}")
            return False
    
    def update_annotations(self, annotations: Dict[str, Any]) -> bool:
        """Update annotations file on GitHub"""
        if not self.token or not self.repo:
            print("GitHub not configured - skipping upload")
            return False
        
        file_path = "data/annotations.json"
        
        # Get current file SHA
        current_content, sha = self._get_file_content(file_path)
        
        # Convert annotations to JSON string
        new_content = json.dumps(annotations, indent=2)
        
        # Create commit message
        timestamp = datetime.utcnow().isoformat()
        message = f"Update annotations - {timestamp}"
        
        # Update file
        return self._update_file(file_path, new_content, sha, message)
    
    def backup_data(self, data: Dict[str, Any], file_name: str) -> bool:
        """Backup data to GitHub"""
        if not self.token or not self.repo:
            print("GitHub not configured - skipping backup")
            return False
        
        file_path = f"backups/{file_name}"
        
        # Get current file SHA (if exists)
        current_content, sha = self._get_file_content(file_path)
        
        # Convert data to JSON string
        content = json.dumps(data, indent=2)
        
        # Create commit message
        timestamp = datetime.utcnow().isoformat()
        message = f"Backup {file_name} - {timestamp}"
        
        # Update file
        return self._update_file(file_path, content, sha, message)
    
    def get_annotations(self) -> Dict[str, Any]:
        """Get annotations from GitHub"""
        if not self.token or not self.repo:
            return {}
        
        file_path = "data/annotations.json"
        content, _ = self._get_file_content(file_path)
        
        try:
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {}
    
    def create_repository_structure(self) -> bool:
        """Create initial repository structure"""
        if not self.token or not self.repo:
            return False
        
        files_to_create = [
            ("data/annotations.json", "{}"),
            ("data/users.json", '{"users": []}'),
            ("README.md", "# Deal Validation Annotations\n\nThis repository stores annotations from the deal validation app.")
        ]
        
        success = True
        for file_path, content in files_to_create:
            if not self._update_file(file_path, content, "", f"Initialize {file_path}"):
                success = False
        
        return success