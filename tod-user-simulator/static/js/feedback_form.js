/**
 * TOD Feedback Form JavaScript - Interactive Feedback Collection
 * Handles dynamic feedback form interactions and validation
 */

class TODFeedbackForm {
    constructor() {
        this.sessionId = null;
        this.formData = {};
        this.requiredRatings = [
            'task_success_rate',
            'user_satisfaction', 
            'appropriateness',
            'naturalness',
            'coherence',
            'efficiency',
            'conciseness'
        ];
        this.isSubmitting = false;
        this.autoSaveInterval = null;

        this.init();
    }

    init() {
        this.loadSessionData();
        this.bindEvents();
        this.setupFormValidation();
        this.setupAutoSave();
        this.loadSavedData();
        this.setupAccessibility();
    }

    loadSessionData() {
        // Get session ID from form or URL
        const sessionIdInput = document.querySelector('input[name="session_id"]');
        if (sessionIdInput) {
            this.sessionId = sessionIdInput.value;
        } else {
            // Try to get from URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            this.sessionId = urlParams.get('session_id');
        }

        if (!this.sessionId) {
            this.showError('Session ID not found. Please start a new conversation.');
        }
    }

    bindEvents() {
        // Form submission
        const feedbackForm = document.getElementById('feedback-form');
        if (feedbackForm) {
            feedbackForm.addEventListener('submit', this.handleFormSubmit.bind(this));
        }

        // Rating input changes
        const ratingInputs = document.querySelectorAll('input[type="radio"]');
        ratingInputs.forEach(input => {
            input.addEventListener('change', this.handleRatingChange.bind(this));
            input.addEventListener('focus', this.handleRatingFocus.bind(this));
        });

        // Comments textarea
        const commentsTextarea = document.getElementById('comments');
        if (commentsTextarea) {
            commentsTextarea.addEventListener('input', this.handleCommentsChange.bind(this));
            commentsTextarea.addEventListener('blur', this.validateComments.bind(this));
        }

        // Prevent accidental navigation
        window.addEventListener('beforeunload', this.handleBeforeUnload.bind(this));

        // Keyboard navigation
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }

    handleFormSubmit(event) {
        event.preventDefault();
        
        if (this.isSubmitting) {
            return;
        }

        if (!this.validateForm()) {
            return;
        }

        this.submitFeedback();
    }

    async submitFeedback() {
        const submitButton = document.getElementById('submit-feedback');
        const form = document.getElementById('feedback-form');

        try {
            // Set submitting state
            this.isSubmitting = true;
            this.setSubmitButtonState(true);

            // Collect form data
            const formData = new FormData(form);
            
            // Add additional metadata
            formData.append('submission_timestamp', new Date().toISOString());
            formData.append('user_agent', navigator.userAgent);
            formData.append('screen_resolution', `${screen.width}x${screen.height}`);

            // Submit to server
            const response = await this.makeRequest('/submit_feedback', formData);

            if (response.status === 'success') {
                this.handleSubmissionSuccess(response);
            } else {
                throw new Error(response.error || 'Submission failed');
            }

        } catch (error) {
            console.error('Error submitting feedback:', error);
            this.handleSubmissionError(error);
        } finally {
            this.isSubmitting = false;
            this.setSubmitButtonState(false);
        }
    }

    async makeRequest(url, formData) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timed out. Please try again.');
            }
            
            throw error;
        }
    }

    handleSubmissionSuccess(response) {
        // Clear auto-save data
        this.clearSavedData();

        // Show success message
        this.showSuccessMessage('Thank you for your feedback! Your responses have been saved.');

        // Disable form to prevent resubmission
        this.disableForm();

        // Redirect after delay
        setTimeout(() => {
            window.location.href = response.redirect || '/tod_simulator';
        }, 2000);
    }

    handleSubmissionError(error) {
        this.showError(`Error submitting feedback: ${error.message}`);
        
        // Re-enable form
        this.setSubmitButtonState(false);
    }

    handleRatingChange(event) {
        const input = event.target;
        const groupName = input.name;
        const value = input.value;

        // Update form data
        this.formData[groupName] = value;

        // Visual feedback
        this.updateRatingVisuals(groupName, input);

        // Validate this rating group
        this.validateRatingGroup(groupName);

        // Auto-save
        this.saveFormData();

        // Update progress
        this.updateProgress();
    }

    handleRatingFocus(event) {
        const input = event.target;
        const ratingGroup = input.closest('.rating-group');
        
        if (ratingGroup) {
            ratingGroup.classList.add('focused');
            
            // Remove focus class when focus leaves the group
            const removeFocus = () => {
                setTimeout(() => {
                    if (!ratingGroup.contains(document.activeElement)) {
                        ratingGroup.classList.remove('focused');
                    }
                }, 100);
            };
            
            input.addEventListener('blur', removeFunction, { once: true });
        }
    }

    handleCommentsChange(event) {
        const textarea = event.target;
        const value = textarea.value;

        // Update form data
        this.formData.comments = value;

        // Update character count
        this.updateCharacterCount(textarea);

        // Auto-save
        this.saveFormData();
    }

    handleBeforeUnload(event) {
        if (this.hasUnsavedChanges() && !this.isSubmitting) {
            event.preventDefault();
            event.returnValue = 'You have unsaved feedback. Are you sure you want to leave?';
            return event.returnValue;
        }
    }

    handleKeyDown(event) {
        // Navigate between rating groups with arrow keys
        if (event.target.type === 'radio') {
            if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                event.preventDefault();
                this.navigateRatingGroups(event.target, event.key === 'ArrowUp' ? -1 : 1);
            }
        }

        // Submit with Ctrl/Cmd + Enter
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            const form = document.getElementById('feedback-form');
            if (form) {
                form.dispatchEvent(new Event('submit'));
            }
        }
    }

    // Validation methods
    validateForm() {
        let isValid = true;
        const errors = [];

        // Clear previous errors
        this.clearErrors();

        // Validate required ratings
        this.requiredRatings.forEach(ratingName => {
            const selected = document.querySelector(`input[name="${ratingName}"]:checked`);
            if (!selected) {
                isValid = false;
                errors.push(this.getRatingDisplayName(ratingName));
                this.highlightMissingRating(ratingName);
            }
        });

        // Validate comments length
        const comments = document.getElementById('comments').value;
        if (comments.length > 2000) {
            isValid = false;
            errors.push('Comments are too long (maximum 2000 characters)');
            this.highlightError(document.getElementById('comments'));
        }

        if (!isValid) {
            this.showValidationErrors(errors);
            this.scrollToFirstError();
        }

        return isValid;
    }

    validateRatingGroup(groupName) {
        const selected = document.querySelector(`input[name="${groupName}"]:checked`);
        const ratingGroup = document.querySelector(`input[name="${groupName}"]`).closest('.form-group');
        
        if (selected) {
            ratingGroup.classList.remove('error');
            ratingGroup.classList.add('completed');
        }
    }

    validateComments() {
        const textarea = document.getElementById('comments');
        const value = textarea.value;
        
        if (value.length > 2000) {
            this.highlightError(textarea);
            this.showError('Comments are too long. Please keep them under 2000 characters.');
        } else {
            this.removeError(textarea);
        }
    }

    // Visual feedback methods
    updateRatingVisuals(groupName, selectedInput) {
        // Remove selected class from all options in this group
        const groupOptions = document.querySelectorAll(`input[name="${groupName}"]`);
        groupOptions.forEach(option => {
            option.parentElement.classList.remove('selected');
        });

        // Add selected class to chosen option
        selectedInput.parentElement.classList.add('selected');

        // Add completion indicator to the group
        const formGroup = selectedInput.closest('.form-group');
        if (formGroup) {
            formGroup.classList.add('completed');
            
            // Add checkmark if not already present
            if (!formGroup.querySelector('.completion-indicator')) {
                const indicator = document.createElement('span');
                indicator.className = 'completion-indicator';
                indicator.innerHTML = '✓';
                indicator.style.color = '#28a745';
                indicator.style.marginLeft = '0.5rem';
                
                const label = formGroup.querySelector('label');
                if (label) {
                    label.appendChild(indicator);
                }
            }
        }
    }

    updateCharacterCount(textarea) {
        const maxLength = 2000;
        const currentLength = textarea.value.length;
        
        let counter = textarea.parentNode.querySelector('.char-counter');
        if (!counter) {
            counter = document.createElement('div');
            counter.className = 'char-counter';
            counter.style.fontSize = '0.8rem';
            counter.style.color = '#666';
            counter.style.textAlign = 'right';
            counter.style.marginTop = '0.25rem';
            textarea.parentNode.appendChild(counter);
        }

        counter.textContent = `${currentLength}/${maxLength}`;
        
        if (currentLength > maxLength * 0.9) {
            counter.style.color = currentLength > maxLength ? '#dc3545' : '#ffc107';
        } else {
            counter.style.color = '#666';
        }
    }

    updateProgress() {
        const completedRatings = this.requiredRatings.filter(rating => {
            return document.querySelector(`input[name="${rating}"]:checked`);
        }).length;

        const totalRatings = this.requiredRatings.length;
        const progressPercentage = (completedRatings / totalRatings) * 100;

        // Update or create progress bar
        let progressBar = document.querySelector('.feedback-progress');
        if (!progressBar) {
            progressBar = this.createProgressBar();
        }

        const progressFill = progressBar.querySelector('.progress-fill');
        const progressText = progressBar.querySelector('.progress-text');

        if (progressFill) {
            progressFill.style.width = `${progressPercentage}%`;
        }

        if (progressText) {
            progressText.textContent = `${completedRatings}/${totalRatings} sections completed`;
        }

        // Show completion message when all ratings are done
        if (completedRatings === totalRatings) {
            this.showSuccessMessage('All required ratings completed! You can now submit your feedback.', 3000);
        }
    }

    createProgressBar() {
        const progressContainer = document.createElement('div');
        progressContainer.className = 'feedback-progress';
        progressContainer.innerHTML = `
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            <div class="progress-text">0/${this.requiredRatings.length} sections completed</div>
        `;

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .feedback-progress {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: white;
                padding: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                z-index: 100;
                text-align: center;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #f0f0f0;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 0.5rem;
            }
            .progress-fill {
                height: 100%;
                background: var(--primary-color);
                transition: width 0.3s ease;
                width: 0%;
            }
            .progress-text {
                font-size: 0.9rem;
                color: #666;
            }
        `;
        document.head.appendChild(style);

        // Insert at top of page
        document.body.insertBefore(progressContainer, document.body.firstChild);

        // Adjust body padding to account for fixed progress bar
        document.body.style.paddingTop = '80px';

        return progressContainer;
    }

    // Error handling methods
    showValidationErrors(errors) {
        const errorContainer = this.getOrCreateErrorContainer();
        errorContainer.innerHTML = `
            <strong>Please complete the following required sections:</strong>
            <ul>
                ${errors.map(error => `<li>${error}</li>`).join('')}
            </ul>
        `;
        errorContainer.style.display = 'block';
    }

    highlightMissingRating(ratingName) {
        const ratingGroup = document.querySelector(`input[name="${ratingName}"]`).closest('.form-group');
        if (ratingGroup) {
            ratingGroup.classList.add('error');
            
            // Add error indicator
            if (!ratingGroup.querySelector('.error-indicator')) {
                const indicator = document.createElement('span');
                indicator.className = 'error-indicator';
                indicator.textContent = ' (Required)';
                indicator.style.color = '#dc3545';
                indicator.style.fontWeight = 'bold';
                
                const label = ratingGroup.querySelector('label');
                if (label) {
                    label.appendChild(indicator);
                }
            }
        }
    }

    highlightError(element) {
        if (element) {
            element.classList.add('error');
            element.style.borderColor = '#dc3545';
            element.style.boxShadow = '0 0 0 2px rgba(220, 53, 69, 0.2)';
        }
    }

    removeError(element) {
        if (element) {
            element.classList.remove('error');
            element.style.borderColor = '';
            element.style.boxShadow = '';
        }
    }

    clearErrors() {
        // Remove error classes
        const errorElements = document.querySelectorAll('.error');
        errorElements.forEach(element => this.removeError(element));

        // Remove error indicators
        const errorIndicators = document.querySelectorAll('.error-indicator');
        errorIndicators.forEach(indicator => indicator.remove());

        // Hide error container
        const errorContainer = document.querySelector('.feedback-error-container');
        if (errorContainer) {
            errorContainer.style.display = 'none';
        }
    }

    scrollToFirstError() {
        const firstError = document.querySelector('.form-group.error');
        if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Focus first input in the error group
            const firstInput = firstError.querySelector('input');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 500);
            }
        }
    }

    // Utility methods
    getRatingDisplayName(ratingName) {
        const displayNames = {
            'task_success_rate': 'Task Success Rate',
            'user_satisfaction': 'User Satisfaction',
            'appropriateness': 'Appropriateness',
            'naturalness': 'Naturalness',
            'coherence': 'Coherence',
            'efficiency': 'Efficiency',
            'conciseness': 'Conciseness'
        };
        return displayNames[ratingName] || ratingName;
    }

    getOrCreateErrorContainer() {
        let container = document.querySelector('.feedback-error-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'feedback-error-container tod-error-message';
            container.style.display = 'none';
            
            const form = document.getElementById('feedback-form');
            if (form) {
                form.insertBefore(container, form.firstChild);
            }
        }
        return container;
    }

    setSubmitButtonState(isSubmitting) {
        const submitButton = document.getElementById('submit-feedback');
        if (!submitButton) return;

        if (isSubmitting) {
            submitButton.disabled = true;
            submitButton.dataset.originalText = submitButton.textContent;
            submitButton.innerHTML = '<span class="tod-loading"></span> Submitting...';
        } else {
            submitButton.disabled = false;
            submitButton.textContent = submitButton.dataset.originalText || 'Submit Feedback';
        }
    }

    disableForm() {
        const form = document.getElementById('feedback-form');
        if (form) {
            const inputs = form.querySelectorAll('input, textarea, button');
            inputs.forEach(input => {
                input.disabled = true;
            });
        }
    }

    navigateRatingGroups(currentInput, direction) {
        const allRatingGroups = Array.from(document.querySelectorAll('.rating-group'));
        const currentGroup = currentInput.closest('.rating-group');
        const currentIndex = allRatingGroups.indexOf(currentGroup);
        
        const nextIndex = currentIndex + direction;
        if (nextIndex >= 0 && nextIndex < allRatingGroups.length) {
            const nextGroup = allRatingGroups[nextIndex];
            const firstInput = nextGroup.querySelector('input[type="radio"]');
            if (firstInput) {
                firstInput.focus();
            }
        }
    }

    // Auto-save functionality
    setupAutoSave() {
        this.autoSaveInterval = setInterval(() => {
            this.saveFormData();
        }, 30000); // Save every 30 seconds
    }

    saveFormData() {
        if (!this.sessionId) return;

        try {
            const data = {
                ...this.formData,
                timestamp: new Date().toISOString()
            };
            localStorage.setItem(`tod_feedback_${this.sessionId}`, JSON.stringify(data));
        } catch (e) {
            console.warn('Could not save form data:', e);
        }
    }

    loadSavedData() {
        if (!this.sessionId) return;

        try {
            const savedData = localStorage.getItem(`tod_feedback_${this.sessionId}`);
            if (savedData) {
                const data = JSON.parse(savedData);
                
                // Restore ratings
                Object.keys(data).forEach(key => {
                    if (key !== 'timestamp' && key !== 'comments') {
                        const input = document.querySelector(`input[name="${key}"][value="${data[key]}"]`);
                        if (input) {
                            input.checked = true;
                            this.handleRatingChange({ target: input });
                        }
                    }
                });

                // Restore comments
                if (data.comments) {
                    const commentsTextarea = document.getElementById('comments');
                    if (commentsTextarea) {
                        commentsTextarea.value = data.comments;
                        this.handleCommentsChange({ target: commentsTextarea });
                    }
                }

                this.showSuccessMessage('Previous feedback data restored', 3000);
            }
        } catch (e) {
            console.warn('Could not load saved data:', e);
        }
    }

    clearSavedData() {
        if (!this.sessionId) return;

        try {
            localStorage.removeItem(`tod_feedback_${this.sessionId}`);
        } catch (e) {
            console.warn('Could not clear saved data:', e);
        }
    }

    hasUnsavedChanges() {
        return Object.keys(this.formData).length > 0;
    }

    setupAccessibility() {
        // Add ARIA labels and descriptions
        const ratingGroups = document.querySelectorAll('.rating-group');
        ratingGroups.forEach((group, index) => {
            const inputs = group.querySelectorAll('input[type="radio"]');
            const groupId = `rating-group-${index}`;
            
            inputs.forEach((input, inputIndex) => {
                input.setAttribute('aria-describedby', `${groupId}-description`);
            });

            // Add description for screen readers
            const description = group.querySelector('.rating-description');
            if (description) {
                description.id = `${groupId}-description`;
            }
        });
    }

    // Message display methods
    showError(message, duration = 5000) {
        this.showMessage(message, 'error', duration);
    }

    showSuccessMessage(message, duration = 3000) {
        this.showMessage(message, 'success', duration);
    }

    showMessage(message, type = 'info', duration = 3000) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `tod-${type}-message feedback-toast`;
        messageDiv.textContent = message;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '20px';
        messageDiv.style.right = '20px';
        messageDiv.style.zIndex = '1001';
        messageDiv.style.padding = '1rem';
        messageDiv.style.borderRadius = '4px';
        messageDiv.style.maxWidth = '300px';
        messageDiv.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';

        document.body.appendChild(messageDiv);

        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, duration);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new TODFeedbackForm();
});