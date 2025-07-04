// Deal Validation App - Frontend JavaScript

class DealValidationApp {
    constructor() {
        this.startTime = Date.now();
        this.currentDealId = null;
        this.ratings = {};
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadProgress();
        this.startTimeTracking();
    }

    bindEvents() {
        // Rating form submission
        const ratingForm = document.getElementById('rating-form');
        if (ratingForm) {
            ratingForm.addEventListener('submit', (e) => this.handleRatingSubmit(e));
        }

        // Navigation buttons
        const backToActivitiesBtn = document.getElementById('back-to-activities');
        if (backToActivitiesBtn) {
            backToActivitiesBtn.addEventListener('click', () => this.goBackToActivities());
        }

        // Rating star interactions
        this.initRatingStars();
        
        // Auto-save functionality
        this.initAutoSave();
    }

    initRatingStars() {
        const ratingGroups = document.querySelectorAll('.rating-group');
        ratingGroups.forEach(group => {
            const stars = group.querySelectorAll('.rating-stars input[type="radio"]');
            stars.forEach(star => {
                star.addEventListener('change', (e) => {
                    this.updateRating(e.target.name, e.target.value);
                });
            });
        });
    }

    initAutoSave() {
        const textareas = document.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                this.saveToLocalStorage();
            });
        });

        // Load saved data on page load
        this.loadFromLocalStorage();
    }

    updateRating(fieldName, value) {
        if (!this.ratings[fieldName]) {
            this.ratings[fieldName] = {};
        }
        this.ratings[fieldName].score = parseInt(value);
        
        // Update visual feedback
        this.updateRatingDisplay(fieldName, value);
        
        // Save to local storage
        this.saveToLocalStorage();
    }

    updateRatingDisplay(fieldName, value) {
        const ratingGroup = document.querySelector(`[data-field="${fieldName}"]`);
        if (ratingGroup) {
            const stars = ratingGroup.querySelectorAll('.rating-stars label');
            stars.forEach((star, index) => {
                if (index < value) {
                    star.style.color = '#ffc107';
                } else {
                    star.style.color = '#ddd';
                }
            });
        }
    }

    saveToLocalStorage() {
        const dealId = this.getCurrentDealId();
        if (dealId) {
            const formData = this.collectFormData();
            localStorage.setItem(`deal_${dealId}_draft`, JSON.stringify(formData));
        }
    }

    loadFromLocalStorage() {
        const dealId = this.getCurrentDealId();
        if (dealId) {
            const savedData = localStorage.getItem(`deal_${dealId}_draft`);
            if (savedData) {
                const formData = JSON.parse(savedData);
                this.populateForm(formData);
            }
        }
    }

    populateForm(formData) {
        // Populate ratings
        Object.keys(formData.ratings || {}).forEach(fieldName => {
            const rating = formData.ratings[fieldName];
            
            // Set score
            if (rating.score) {
                const scoreInput = document.querySelector(`input[name="${fieldName}_score"][value="${rating.score}"]`);
                if (scoreInput) {
                    scoreInput.checked = true;
                    this.updateRatingDisplay(fieldName, rating.score);
                }
            }
            
            // Set confidence
            if (rating.confidence) {
                const confidenceInput = document.querySelector(`input[name="${fieldName}_confidence"][value="${rating.confidence}"]`);
                if (confidenceInput) {
                    confidenceInput.checked = true;
                }
            }
            
            // Set notes
            if (rating.notes) {
                const notesTextarea = document.querySelector(`textarea[name="${fieldName}_notes"]`);
                if (notesTextarea) {
                    notesTextarea.value = rating.notes;
                }
            }
        });
    }

    collectFormData() {
        const formData = new FormData(document.getElementById('rating-form'));
        const data = { ratings: {} };
        
        const ratingFields = [
            'overall_sentiment', 'activity_breakdown', 'deal_momentum_indicators',
            'reasoning', 'professional_gaps', 'excellence_indicators',
            'risk_indicators', 'opportunity_indicators', 'temporal_trend',
            'recommended_actions'
        ];
        
        ratingFields.forEach(field => {
            data.ratings[field] = {
                score: formData.get(`${field}_score`),
                confidence: formData.get(`${field}_confidence`),
                notes: formData.get(`${field}_notes`) || ''
            };
        });
        
        return data;
    }

    getCurrentDealId() {
        const urlParts = window.location.pathname.split('/');
        return urlParts[urlParts.length - 1];
    }

    startTimeTracking() {
        this.startTime = Date.now();
    }

    getTimeSpent() {
        return Math.floor((Date.now() - this.startTime) / 1000);
    }

    async handleRatingSubmit(e) {
        e.preventDefault();
        
        if (!this.validateForm()) {
            this.showAlert('Please complete all required ratings before submitting.', 'danger');
            return;
        }

        const confirmSubmit = confirm('Are you sure you want to submit this rating? You cannot change it later.');
        if (!confirmSubmit) {
            return;
        }

        const submitBtn = document.getElementById('submit-rating');
        const originalText = submitBtn.textContent;
        
        try {
            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitting...';
            
            // Prepare form data
            const formData = new FormData(e.target);
            formData.append('time_spent', this.getTimeSpent());
            
            // Submit to server
            const response = await fetch('/submit-rating', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showAlert('Rating submitted successfully!', 'success');
                
                // Clear local storage
                const dealId = this.getCurrentDealId();
                if (dealId) {
                    localStorage.removeItem(`deal_${dealId}_draft`);
                }
                
                // Redirect to next deal or completion page
                setTimeout(() => {
                    if (result.next_deal) {
                        window.location.href = `/activities/${result.next_deal}`;
                    } else {
                        window.location.href = '/instructions?completed=true';
                    }
                }, 2000);
                
            } else {
                throw new Error(result.detail || 'Submission failed');
            }
            
        } catch (error) {
            console.error('Submission error:', error);
            this.showAlert(`Error: ${error.message}`, 'danger');
        } finally {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }

    validateForm() {
        const ratingFields = [
            'overall_sentiment', 'activity_breakdown', 'deal_momentum_indicators',
            'reasoning', 'professional_gaps', 'excellence_indicators',
            'risk_indicators', 'opportunity_indicators', 'temporal_trend',
            'recommended_actions'
        ];
        
        for (const field of ratingFields) {
            const scoreInput = document.querySelector(`input[name="${field}_score"]:checked`);
            const confidenceInput = document.querySelector(`input[name="${field}_confidence"]:checked`);
            
            if (!scoreInput || !confidenceInput) {
                return false;
            }
        }
        
        return true;
    }

    goBackToActivities() {
        const dealId = this.getCurrentDealId();
        if (dealId) {
            window.location.href = `/activities/${dealId}`;
        }
    }

    async handleAddUser(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        
        try {
            const response = await fetch('/admin/add-user', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showAlert('User added successfully!', 'success');
                e.target.reset();
                setTimeout(() => location.reload(), 1000);
            } else {
                throw new Error(result.detail || 'Failed to add user');
            }
            
        } catch (error) {
            console.error('Add user error:', error);
            this.showAlert(`Error: ${error.message}`, 'danger');
        }
    }

    async loadProgress() {
        try {
            const response = await fetch('/api/progress');
            const progress = await response.json();
            
            // Update progress display
            const progressElement = document.getElementById('progress-info');
            if (progressElement) {
                progressElement.textContent = `${progress.completed_count} of ${progress.total_deals} deals completed`;
            }
            
            // Update progress bar
            const progressBar = document.getElementById('progress-bar');
            if (progressBar) {
                const percentage = (progress.completed_count / progress.total_deals) * 100;
                progressBar.style.width = `${percentage}%`;
            }
            
        } catch (error) {
            console.error('Failed to load progress:', error);
        }
    }

    showAlert(message, type = 'info') {
        // Remove existing alerts
        const existingAlerts = document.querySelectorAll('.alert');
        existingAlerts.forEach(alert => alert.remove());
        
        // Create new alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        // Insert at top of main content
        const mainContent = document.querySelector('.container');
        if (mainContent) {
            mainContent.insertBefore(alertDiv, mainContent.firstChild);
        }
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    // Utility function to format timestamps
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    // Utility function to truncate text
    truncateText(text, maxLength = 100) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
}

// Activity display enhancements
class ActivityDisplay {
    constructor() {
        this.init();
    }

    init() {
        this.addActivityIcons();
        this.addExpandableContent();
        this.addTimelineConnectors();
    }

    addActivityIcons() {
        const activities = document.querySelectorAll('.activity-item');
        activities.forEach(activity => {
            const typeElement = activity.querySelector('.activity-type');
            if (typeElement) {
                const type = typeElement.textContent.toLowerCase();
                const icon = this.getActivityIcon(type);
                typeElement.innerHTML = `${icon} ${typeElement.textContent}`;
            }
        });
    }

    getActivityIcon(type) {
        const icons = {
            'email': '📧',
            'call': '📞',
            'meeting': '🤝',
            'note': '📝',
            'task': '✅'
        };
        return icons[type] || '📋';
    }

    addExpandableContent() {
        const activities = document.querySelectorAll('.activity-item');
        activities.forEach(activity => {
            const content = activity.querySelector('.activity-content');
            if (content && content.textContent.length > 300) {
                const fullText = content.innerHTML;
                const truncatedText = this.truncateHTML(fullText, 300);
                
                content.innerHTML = truncatedText;
                
                const expandBtn = document.createElement('button');
                expandBtn.className = 'btn btn-sm btn-secondary expand-btn';
                expandBtn.textContent = 'Show More';
                expandBtn.onclick = () => this.toggleExpand(content, fullText, truncatedText, expandBtn);
                
                activity.appendChild(expandBtn);
            }
        });
    }

    truncateHTML(html, maxLength) {
        const div = document.createElement('div');
        div.innerHTML = html;
        const text = div.textContent || div.innerText;
        
        if (text.length <= maxLength) return html;
        
        const truncated = text.substring(0, maxLength);
        return truncated + '...';
    }

    toggleExpand(content, fullText, truncatedText, btn) {
        if (btn.textContent === 'Show More') {
            content.innerHTML = fullText;
            btn.textContent = 'Show Less';
        } else {
            content.innerHTML = truncatedText;
            btn.textContent = 'Show More';
        }
    }

    addTimelineConnectors() {
        const activities = document.querySelectorAll('.activity-item');
        activities.forEach((activity, index) => {
            if (index < activities.length - 1) {
                activity.classList.add('timeline-item');
            }
        });
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dealValidationApp = new DealValidationApp();
    window.activityDisplay = new ActivityDisplay();
});

// Global functions for template usage
window.formatTimestamp = (timestamp) => {
    return window.dealValidationApp.formatTimestamp(timestamp);
};

// Service worker registration for offline support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}