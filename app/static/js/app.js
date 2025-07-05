// Deal Validation App - Frontend JavaScript

class DealValidationApp {
    constructor() {
        this.startTime = Date.now();
        this.currentDealId = null;
        this.ratings = {};
        this.autoSaveInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        // Only load progress if not on admin page
        if (!window.location.pathname.includes('/admin')) {
            this.loadProgress();
        }
        this.startTimeTracking();
        this.initializeUI();
    }

    initializeUI() {
        // Add smooth scrolling to all internal links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        // Add loading state to buttons
        document.querySelectorAll('.btn').forEach(button => {
            button.addEventListener('click', function() {
                if (this.type === 'submit' || this.classList.contains('btn-primary')) {
                    this.classList.add('loading');
                }
            });
        });
    }

    bindEvents() {
        // Rating form submission
        const ratingForm = document.getElementById('rating-form');
        if (ratingForm) {
            ratingForm.addEventListener('submit', (e) => this.handleRatingSubmit(e));
        }

        // Rating star interactions
        this.initRatingStars();
        
        // Auto-save functionality
        this.initAutoSave();

        // Activity content expansion
        // this.initActivityExpansion();

        // Keyboard shortcuts
        this.initKeyboardShortcuts();
    }

    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + S to save draft
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveToLocalStorage();
                this.showNotification('Draft saved', 'success');
            }
            
            // Ctrl/Cmd + Enter to submit
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const submitBtn = document.getElementById('submit-rating');
                if (submitBtn && !submitBtn.disabled) {
                    submitBtn.click();
                }
            }
        });
    }

    // initActivityExpansion() {
    //     const activities = document.querySelectorAll('.activity-content .body');
    //     activities.forEach(activity => {
    //         const content = activity.textContent || '';
    //         if (content.length > 500) {
    //             const truncated = content.substring(0, 500) + '...';
    //             const fullContent = content;
                
    //             activity.innerHTML = `
    //                 <span class="truncated-content">${this.escapeHtml(truncated)}</span>
    //                 <span class="full-content" style="display: none;">${this.escapeHtml(fullContent)}</span>
    //                 <button class="btn btn-sm btn-secondary expand-btn" style="margin-top: 0.5rem;">
    //                     Show More
    //                 </button>
    //             `;
                
    //             const expandBtn = activity.querySelector('.expand-btn');
    //             expandBtn.addEventListener('click', () => this.toggleContent(activity));
    //         }
    //     });
    // }

    // toggleContent(container) {
    //     const truncated = container.querySelector('.truncated-content');
    //     const full = container.querySelector('.full-content');
    //     const btn = container.querySelector('.expand-btn');
        
    //     if (truncated.style.display === 'none') {
    //         truncated.style.display = 'inline';
    //         full.style.display = 'none';
    //         btn.textContent = 'Show More';
    //     } else {
    //         truncated.style.display = 'none';
    //         full.style.display = 'inline';
    //         btn.textContent = 'Show Less';
    //     }
    // }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    initRatingStars() {
        const ratingGroups = document.querySelectorAll('.rating-stars');
        
        ratingGroups.forEach(group => {
            const inputs = group.querySelectorAll('input[type="radio"]');
            const labels = group.querySelectorAll('label');
            
            // Create array of labels sorted by their star value for easier manipulation
            const sortedLabels = Array.from(labels).sort((a, b) => {
                const aValue = parseInt(a.getAttribute('for').split('_').pop());
                const bValue = parseInt(b.getAttribute('for').split('_').pop());
                return aValue - bValue;
            });
            
            // Function to update star display
            const updateStarDisplay = (rating = 0, isHover = false) => {
                sortedLabels.forEach((label, index) => {
                    const starValue = index + 1;
                    label.classList.remove('active', 'hover', 'selected');
                    
                    if (starValue <= rating) {
                        if (isHover) {
                            label.classList.add('hover');
                        } else {
                            label.classList.add('active');
                        }
                    }
                });
            };
            
            // Add hover effects
            sortedLabels.forEach((label, index) => {
                const starValue = index + 1;
                
                label.addEventListener('mouseenter', () => {
                    updateStarDisplay(starValue, true);
                });
            });
            
            // Reset on mouse leave to show current selection
            group.addEventListener('mouseleave', () => {
                const checked = group.querySelector('input:checked');
                const currentRating = checked ? parseInt(checked.value) : 0;
                updateStarDisplay(currentRating, false);
            });
            
            // Handle radio button changes
            inputs.forEach(input => {
                input.addEventListener('change', (e) => {
                    const value = parseInt(e.target.value);
                    updateStarDisplay(value, false);
                    
                    // Add selection animation
                    const selectedLabel = sortedLabels[value - 1];
                    if (selectedLabel) {
                        selectedLabel.classList.add('selected');
                        setTimeout(() => {
                            selectedLabel.classList.remove('selected');
                        }, 300);
                    }
                    
                    this.updateRating(e.target.name, e.target.value);
                    // Call the global function instead of this method
                    if (typeof updateSectionProgress === 'function') {
                        updateSectionProgress();
                    }
                });
            });
            
            // Initialize display - ensure all stars start as grey unless there's a pre-selected value
            const checked = group.querySelector('input:checked');
            if (checked) {
                updateStarDisplay(parseInt(checked.value), false);
            } else {
                // Ensure all stars start as grey (no rating)
                updateStarDisplay(0, false);
            }
        });
    }

    initAutoSave() {
        // Auto-save every 30 seconds
        this.autoSaveInterval = setInterval(() => {
            this.saveToLocalStorage();
        }, 30000);

        // Save on text input
        const textareas = document.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                // Debounce auto-save
                clearTimeout(this.saveTimeout);
                this.saveTimeout = setTimeout(() => {
                    this.saveToLocalStorage();
                }, 2000);
            });
        });

        // Load saved data on page load
        this.loadFromLocalStorage();

        // Save before unload
        window.addEventListener('beforeunload', () => {
            this.saveToLocalStorage();
        });
    }

    updateRating(fieldName, value) {
        if (!this.ratings[fieldName]) {
            this.ratings[fieldName] = {};
        }
        this.ratings[fieldName] = parseInt(value);
        
        // Visual feedback
        this.showNotification('Rating updated', 'info', 1000);
    }

    saveToLocalStorage() {
        const dealId = this.getCurrentDealId();
        if (!dealId) return;
        
        const formData = this.collectFormData();
        const savedData = {
            ...formData,
            savedAt: new Date().toISOString()
        };
        
        try {
            localStorage.setItem(`deal_${dealId}_draft`, JSON.stringify(savedData));
            console.log('Draft saved successfully');
        } catch (e) {
            console.error('Failed to save draft:', e);
        }
    }

    loadFromLocalStorage() {
        const dealId = this.getCurrentDealId();
        if (!dealId) return;
        
        try {
            const savedData = localStorage.getItem(`deal_${dealId}_draft`);
            if (savedData) {
                const data = JSON.parse(savedData);
                this.populateForm(data);
                
                // Show when draft was saved
                if (data.savedAt) {
                    const savedDate = new Date(data.savedAt);
                    const timeAgo = this.getTimeAgo(savedDate);
                    this.showNotification(`Draft loaded (saved ${timeAgo})`, 'info');
                }
            }
        } catch (e) {
            console.error('Failed to load draft:', e);
        }
    }

    getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };
        
        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return `${interval} ${unit}${interval === 1 ? '' : 's'} ago`;
            }
        }
        
        return 'just now';
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
                    // Update star display
                    const labels = scoreInput.closest('.rating-stars').querySelectorAll('label');
                    labels.forEach((label, index) => {
                        label.style.color = index < rating.score ? '#f59e0b' : '#e2e8f0';
                    });
                }
            }
            
            // Set confidence
            if (rating.confidence) {
                const confidenceInput = document.querySelector(`input[name="${fieldName}_confidence"][value="${rating.confidence}"]`);
                if (confidenceInput) {
                    confidenceInput.checked = true;
                    // Update star display
                    const labels = confidenceInput.closest('.rating-stars').querySelectorAll('label');
                    labels.forEach((label, index) => {
                        label.style.color = index < rating.confidence ? '#f59e0b' : '#e2e8f0';
                    });
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
        
        // Update progress after loading
        if (typeof updateSectionProgress === 'function') {
            updateSectionProgress();
        }
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
            const score = formData.get(`${field}_score`);
            const confidence = formData.get(`${field}_confidence`);
            const notes = formData.get(`${field}_notes`);
            
            if (score || confidence || notes) {
                data.ratings[field] = {
                    score: score ? parseInt(score) : null,
                    confidence: confidence ? parseInt(confidence) : null,
                    notes: notes || ''
                };
            }
        });
        
        return data;
    }

    getCurrentDealId() {
        const urlParts = window.location.pathname.split('/');
        return urlParts[urlParts.length - 1];
    }

    startTimeTracking() {
        this.startTime = Date.now();
        
        // Update time display every minute
        setInterval(() => {
            const timeSpent = this.getTimeSpent();
            const minutes = Math.floor(timeSpent / 60);
            const timeDisplay = document.getElementById('time-spent');
            if (timeDisplay) {
                timeDisplay.textContent = `Time spent: ${minutes} minute${minutes === 1 ? '' : 's'}`;
            }
        }, 60000);
    }

    getTimeSpent() {
        return Math.floor((Date.now() - this.startTime) / 1000);
    }

    async handleRatingSubmit(e) {
        e.preventDefault();
        
        if (!this.validateForm()) {
            this.showAlert('Please complete all required ratings before submitting.', 'danger');
            // Scroll to first incomplete section
            const firstIncomplete = document.querySelector('.rating-section:not(.completed)');
            if (firstIncomplete) {
                firstIncomplete.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        const confirmSubmit = confirm('Are you sure you want to submit this rating? You cannot change it later.');
        if (!confirmSubmit) {
            return;
        }

        const submitBtn = document.getElementById('submit-rating');
        const originalText = submitBtn.innerHTML;
        
        try {
            // Disable submit button and show loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span> Submitting...';
            
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
                this.showAlert('✅ Rating submitted successfully!', 'success');
                
                // Clear local storage
                const dealId = this.getCurrentDealId();
                if (dealId) {
                    localStorage.removeItem(`deal_${dealId}_draft`);
                }
                
                // Clear auto-save interval
                if (this.autoSaveInterval) {
                    clearInterval(this.autoSaveInterval);
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
            this.showAlert(`❌ Error: ${error.message}`, 'danger');
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    }

    validateForm() {
        const ratingFields = [
            'overall_sentiment', 'activity_breakdown', 'deal_momentum_indicators',
            'reasoning', 'professional_gaps', 'excellence_indicators',
            'risk_indicators', 'opportunity_indicators', 'temporal_trend',
            'recommended_actions'
        ];
        
        let allValid = true;
        
        for (const field of ratingFields) {
            const scoreInput = document.querySelector(`input[name="${field}_score"]:checked`);
            const confidenceInput = document.querySelector(`input[name="${field}_confidence"]:checked`);
            
            const section = document.querySelector(`[data-section="${field}"]`);
            
            if (!scoreInput || !confidenceInput) {
                allValid = false;
                section?.classList.add('error');
            } else {
                section?.classList.remove('error');
            }
        }
        
        return allValid;
    }

    async loadProgress() {
        try {
            const response = await fetch('/api/progress');
            if (!response.ok) throw new Error('Failed to load progress');
            
            const progress = await response.json();
            
            // Update all progress displays
            const progressElements = document.querySelectorAll('#progress-info, .progress-info');
            progressElements.forEach(element => {
                if (element) {
                    element.innerHTML = `
                        <span class="progress-badge">
                            ${progress.completed_count} Completed
                        </span>
                    `;
                }
            });
            
            // Update progress bar if exists
            const progressBar = document.getElementById('progress-bar');
            if (progressBar) {
                const percentage = (progress.completed_count / progress.total_deals) * 100;
                progressBar.style.width = `${percentage}%`;
                progressBar.setAttribute('aria-valuenow', percentage);
            }
            
        } catch (error) {
            console.error('Failed to load progress:', error);
        }
    }

    showAlert(message, type = 'info', duration = 5000) {
        // Remove existing alerts
        document.querySelectorAll('.alert-notification').forEach(alert => alert.remove());
        
        // Create new alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-notification slide-in`;
        alertDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            max-width: 400px;
            box-shadow: var(--shadow-lg);
        `;
        alertDiv.innerHTML = message;
        
        document.body.appendChild(alertDiv);
        
        // Auto-hide after duration
        if (duration > 0) {
            setTimeout(() => {
                alertDiv.classList.add('fade-out');
                setTimeout(() => alertDiv.remove(), 300);
            }, duration);
        }
    }

    showNotification(message, type = 'info', duration = 2000) {
        // Create a small notification toast
        const toast = document.createElement('div');
        toast.className = 'notification-toast';
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--text-primary);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: slideInUp 0.3s ease;
        `;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutDown 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// Activity display enhancements
class ActivityDisplay {
    constructor() {
        this.init();
    }

    init() {
        this.addActivityNumbers();
        this.highlightKeywords();
    }

    addActivityNumbers() {
        const activities = document.querySelectorAll('.activity-item');
        activities.forEach((activity, index) => {
            const numberBadge = document.createElement('div');
            numberBadge.className = 'activity-number';
            numberBadge.style.cssText = `
                position: absolute;
                left: -3rem;
                top: 1.5rem;
                width: 2rem;
                height: 2rem;
                background: var(--primary-color);
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                font-size: 0.875rem;
            `;
            numberBadge.textContent = index + 1;
            activity.appendChild(numberBadge);
        });
    }

    highlightKeywords() {
        const keywords = ['follow up', 'follow-up', 'next steps', 'concerns', 'questions', 
                         'proposal', 'contract', 'deadline', 'urgent', 'asap'];
        
        const bodies = document.querySelectorAll('.activity-content .body');
        bodies.forEach(body => {
            let html = body.innerHTML;
            keywords.forEach(keyword => {
                const regex = new RegExp(`\\b(${keyword})\\b`, 'gi');
                html = html.replace(regex, '<mark>$1</mark>');
            });
            body.innerHTML = html;
        });
    }
}

// Admin functionality
class AdminDashboard {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadStats();
    }

    bindEvents() {
        const addUserForm = document.getElementById('add-user-form');
        if (addUserForm) {
            addUserForm.addEventListener('submit', (e) => this.handleAddUser(e));
        }
    }

    async handleAddUser(e) {
        e.preventDefault();
        
        const email = document.getElementById('user_email').value;
        const name = document.getElementById('user_name').value;
        
        if (!email || !name) {
            this.showAlert('Please fill in all fields', 'danger');
            return;
        }
        
        const formData = new FormData();
        formData.append('email', email);
        formData.append('name', name);
        
        try {
            const response = await fetch('/admin/add-user', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert('✅ User added successfully!', 'success');
                e.target.reset();
                setTimeout(() => location.reload(), 1500);
            } else {
                throw new Error(data.detail || 'Failed to add user');
            }
        } catch (error) {
            this.showAlert(`❌ Error: ${error.message}`, 'danger');
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/admin/stats');
            if (!response.ok) return;
            
            const stats = await response.json();
            
            // Update UI with stats
            if (stats.overall_progress !== undefined) {
                const progressElement = document.getElementById('overall-progress-stat');
                if (progressElement) {
                    progressElement.textContent = `${stats.overall_progress.toFixed(1)}%`;
                }
            }
        } catch (error) {
            console.error('Failed to load admin stats:', error);
        }
    }

    showAlert(message, type) {
        const app = window.dealValidationApp || new DealValidationApp();
        app.showAlert(message, type);
    }

    async loadDealDistribution() {
        try {
            const response = await fetch('/api/admin/deal-distribution');
            if (!response.ok) return;
            
            const data = await response.json();
            this.displayDealDistribution(data);
        } catch (error) {
            console.error('Failed to load deal distribution:', error);
        }
    }

    displayDealDistribution(data) {
        const container = document.getElementById('deal-distribution-details');
        if (!container) return;
        
        let html = `
            <div style="background: var(--bg-secondary); padding: 1.5rem; border-radius: 8px;">
                <h4>Deal-by-Deal Progress (First 20 deals shown)</h4>
                <div style="max-height: 400px; overflow-y: auto; margin-top: 1rem;">
        `;
        
        // Show first 20 deals for performance
        const dealsToShow = data.deal_details.slice(0, 20);
        
        dealsToShow.forEach(deal => {
            const statusColor = deal.status === 'completed' ? 'var(--success-color)' : 
                            deal.status === 'in_progress' ? 'var(--warning-color)' : 'var(--text-muted)';
            
            html += `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.75rem; border-bottom: 1px solid var(--border-color);">
                    <div>
                        <strong>Deal #${deal.deal_id}</strong>
                        <span style="margin-left: 1rem; color: ${statusColor};">
                            ${deal.current_annotations}/${deal.target_annotations} annotations
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div class="progress-bar" style="width: 120px;">
                            <div class="progress-fill" style="width: ${deal.progress_percentage}%;"></div>
                        </div>
                        <span style="font-weight: 600;">${deal.progress_percentage.toFixed(1)}%</span>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
                <div style="margin-top: 1rem; text-align: center; color: var(--text-muted);">
                    Showing ${dealsToShow.length} of ${data.total_deals} deals
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        container.style.display = 'block';
    }
}

// Move this outside the class and after the class definition
window.loadDealDistribution = function() {
    const adminDashboard = window.adminDashboard;
    if (adminDashboard) {
        adminDashboard.loadDealDistribution();
    }
};

// Initialize appropriate class based on page
document.addEventListener('DOMContentLoaded', () => {
    // Always initialize base app
    window.dealValidationApp = new DealValidationApp();
    
    // Initialize activity display on activities page
    if (document.querySelector('.activities-container')) {
        window.activityDisplay = new ActivityDisplay();
    }
    
    // Initialize admin dashboard on admin page
    if (document.querySelector('.admin-section')) {
        window.adminDashboard = new AdminDashboard();
    }
    
    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInUp {
            from { transform: translateY(100%); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        @keyframes slideOutDown {
            from { transform: translateY(0); opacity: 1; }
            to { transform: translateY(100%); opacity: 0; }
        }
        
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        .rating-section.error {
            border-color: var(--danger-color);
            box-shadow: 0 0 0 3px rgba(245, 101, 101, 0.1);
        }
        
        mark {
            background-color: #fef3c7;
            padding: 0.125rem 0.25rem;
            border-radius: 0.25rem;
        }
        
        .fade-out {
            animation: fadeOut 0.3s ease;
        }
        
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
    `;
    document.head.appendChild(style);
});

// Global utility functions
window.removeUser = async function(email, keepProgress = false) {
    const confirmDelete = confirm(`Are you sure you want to remove ${email}?${keepProgress ? ' (Progress will be kept)' : ''}`);
    if (!confirmDelete) return;
    
    const formData = new FormData();
    formData.append('email', email);
    formData.append('keep_progress', keepProgress);
    
    try {
        const response = await fetch('/admin/remove-user', {
            method: 'DELETE',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const app = window.dealValidationApp || new DealValidationApp();
            app.showAlert('✅ User removed successfully!', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            throw new Error(data.detail || 'Failed to remove user');
        }
    } catch (error) {
        const app = window.dealValidationApp || new DealValidationApp();
        app.showAlert(`❌ Error: ${error.message}`, 'danger');
    }
};

window.downloadData = function(type) {
    const app = window.dealValidationApp || new DealValidationApp();
    app.showNotification(`Preparing ${type} download...`, 'info');
    
    // Download the file
    window.location.href = `/api/download/${type}`;
};

window.generateReport = function() {
    const app = window.dealValidationApp || new DealValidationApp();
    app.showNotification('Generating comprehensive report...', 'info');
    
    // Implement report generation
    setTimeout(() => {
        app.showAlert('📊 Report generation feature coming soon!', 'info');
    }, 1000);
};

// Section toggle function for rating page
window.toggleSection = function(sectionName) {
    const section = document.querySelector(`[data-section="${sectionName}"]`);
    if (section) {
        section.classList.toggle('collapsed');
    }
};

// Update section progress for rating page
window.updateSectionProgress = function() {
    const sections = [
        'overall_sentiment', 'activity_breakdown', 'deal_momentum_indicators',
        'reasoning', 'professional_gaps', 'excellence_indicators',
        'risk_indicators', 'opportunity_indicators', 'temporal_trend',
        'recommended_actions'
    ];
    
    let completed = 0;
    
    sections.forEach(section => {
        const scoreChecked = document.querySelector(`input[name="${section}_score"]:checked`);
        const confidenceChecked = document.querySelector(`input[name="${section}_confidence"]:checked`);
        
        const progressItem = document.querySelector(`[data-progress-section="${section}"] .status-indicator`);
        
        if (progressItem) {
            if (scoreChecked && confidenceChecked) {
                progressItem.className = 'status-indicator completed';
                completed++;
            } else if (scoreChecked || confidenceChecked) {
                progressItem.className = 'status-indicator in-progress';
            } else {
                progressItem.className = 'status-indicator pending';
            }
        }
    });
    
    // Update overall progress
    const sectionsCompleted = document.getElementById('sections-completed');
    if (sectionsCompleted) {
        sectionsCompleted.textContent = `${completed}/10`;
    }
    
    const overallProgress = document.getElementById('overall-progress');
    if (overallProgress) {
        overallProgress.style.width = `${(completed / 10) * 100}%`;
    }
    
    // Update completion status
    const statusElement = document.getElementById('completion-status');
    if (statusElement) {
        if (completed === 10) {
            statusElement.textContent = '✅ All sections completed - ready to submit!';
            statusElement.style.color = 'var(--success-color)';
        } else {
            statusElement.textContent = `⏳ ${10 - completed} sections remaining`;
            statusElement.style.color = 'var(--text-muted)';
        }
    }
};

// Service worker registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('Service Worker registered:', registration);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    });
}

