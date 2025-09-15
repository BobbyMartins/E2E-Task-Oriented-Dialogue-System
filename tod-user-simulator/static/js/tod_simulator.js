/**
 * TOD Simulator JavaScript - Domain and Model Selection
 * Handles dynamic UI interactions for the TOD simulator main page
 */

class TODSimulator {
    constructor() {
        this.domainDescriptions = {
            'hotel': {
                title: 'Hotel Booking Domain',
                description: 'Test hotel booking conversations including room reservations, cancellations, and general inquiries.',
                intents: ['book_room', 'cancel_booking', 'general_enquiries', 'chit_chat'],
                slots: ['dateFrom', 'dateTo', 'bookingID'],
                examples: [
                    'I want to book a room for next weekend',
                    'Can you help me cancel my booking?',
                    'What amenities do you have?'
                ]
            },
            'restaurant': {
                title: 'Restaurant Reservation Domain',
                description: 'Test restaurant reservation conversations including making reservations, cancellations, and menu inquiries.',
                intents: ['make_reservation', 'cancel_reservation', 'menu_inquiry', 'chit_chat'],
                slots: ['date', 'time', 'party_size', 'reservationID'],
                examples: [
                    'I need a table for 4 people tonight',
                    'Do you have vegetarian options?',
                    'I want to cancel my reservation'
                ]
            },
            'flight': {
                title: 'Flight Booking Domain',
                description: 'Test flight booking conversations including flight searches, bookings, cancellations, and status checks.',
                intents: ['book_flight', 'cancel_booking', 'flight_status', 'chit_chat'],
                slots: ['departure_city', 'arrival_city', 'departure_date', 'return_date', 'bookingID'],
                examples: [
                    'I need a flight from New York to London',
                    'What\'s the status of flight AA123?',
                    'I want to cancel my booking'
                ]
            }
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormValidation();
        this.loadSavedPreferences();
    }

    bindEvents() {
        // Assignment type change handler
        const assignmentRadios = document.querySelectorAll('input[name="assignment_type"]');
        assignmentRadios.forEach(radio => {
            radio.addEventListener('change', this.handleAssignmentTypeChange.bind(this));
        });

        // Domain selection change handler
        const domainSelect = document.getElementById('domain');
        if (domainSelect) {
            domainSelect.addEventListener('change', this.handleDomainChange.bind(this));
        }

        // Form submission handler
        const todForm = document.getElementById('tod-simulator-form');
        if (todForm) {
            todForm.addEventListener('submit', this.handleFormSubmit.bind(this));
        }

        // Model type change handler for additional validation
        const modelTypeSelect = document.getElementById('model_type');
        if (modelTypeSelect) {
            modelTypeSelect.addEventListener('change', this.handleModelTypeChange.bind(this));
        }
    }

    handleAssignmentTypeChange(event) {
        const manualModelSelection = document.getElementById('manual-model-selection');
        const modelTypeSelect = document.getElementById('model_type');
        
        if (event.target.value === 'manual') {
            this.showElement(manualModelSelection);
            modelTypeSelect.required = true;
            this.addRequiredIndicator(modelTypeSelect);
        } else {
            this.hideElement(manualModelSelection);
            modelTypeSelect.required = false;
            modelTypeSelect.value = '';
            this.removeRequiredIndicator(modelTypeSelect);
        }

        // Save preference
        this.savePreference('assignment_type', event.target.value);
    }

    handleDomainChange(event) {
        const selectedDomain = event.target.value;
        const domainInfo = document.getElementById('domain-info');
        
        if (selectedDomain && this.domainDescriptions[selectedDomain]) {
            const info = this.domainDescriptions[selectedDomain];
            domainInfo.innerHTML = this.generateDomainInfoHTML(info);
            this.animateElementIn(domainInfo);
        } else {
            domainInfo.innerHTML = '<p>Select a domain above to see its description and capabilities.</p>';
        }

        // Save preference
        this.savePreference('domain', selectedDomain);
    }

    handleModelTypeChange(event) {
        // Save preference
        this.savePreference('model_type', event.target.value);
        
        // Provide visual feedback
        const selectedOption = event.target.selectedOptions[0];
        if (selectedOption && selectedOption.value) {
            this.showSuccessMessage(`Selected: ${selectedOption.textContent}`, 2000);
        }
    }

    handleFormSubmit(event) {
        if (!this.validateForm()) {
            event.preventDefault();
            return false;
        }

        // Show loading state
        const submitButton = document.getElementById('start-tod-btn');
        this.setLoadingState(submitButton, true);

        // Clear saved preferences on successful submission
        this.clearPreferences();

        return true;
    }

    validateForm() {
        const domain = document.getElementById('domain').value;
        const assignmentType = document.querySelector('input[name="assignment_type"]:checked')?.value;
        const modelType = document.getElementById('model_type').value;

        // Clear previous error messages
        this.clearErrorMessages();

        let isValid = true;
        const errors = [];

        if (!domain) {
            errors.push('Please select a domain');
            this.highlightError(document.getElementById('domain'));
            isValid = false;
        }

        if (!assignmentType) {
            errors.push('Please select an assignment type');
            isValid = false;
        }

        if (assignmentType === 'manual' && !modelType) {
            errors.push('Please select a model for manual assignment');
            this.highlightError(document.getElementById('model_type'));
            isValid = false;
        }

        if (!isValid) {
            this.showErrorMessages(errors);
        }

        return isValid;
    }

    setupFormValidation() {
        // Real-time validation
        const domainSelect = document.getElementById('domain');
        const modelTypeSelect = document.getElementById('model_type');

        if (domainSelect) {
            domainSelect.addEventListener('blur', () => {
                if (domainSelect.value) {
                    this.removeError(domainSelect);
                }
            });
        }

        if (modelTypeSelect) {
            modelTypeSelect.addEventListener('blur', () => {
                const assignmentType = document.querySelector('input[name="assignment_type"]:checked')?.value;
                if (assignmentType === 'manual' && modelTypeSelect.value) {
                    this.removeError(modelTypeSelect);
                }
            });
        }
    }

    generateDomainInfoHTML(info) {
        return `
            <div class="domain-info-card">
                <h4>${info.title}</h4>
                <p>${info.description}</p>
                <div class="domain-details">
                    <div class="detail-section">
                        <strong>Available Intents:</strong>
                        <ul>
                            ${info.intents.map(intent => `<li>${intent}</li>`).join('')}
                        </ul>
                    </div>
                    <div class="detail-section">
                        <strong>Key Slots:</strong>
                        <ul>
                            ${info.slots.map(slot => `<li>${slot}</li>`).join('')}
                        </ul>
                    </div>
                </div>
                <div class="domain-examples">
                    <strong>Example Conversations:</strong>
                    <ul class="example-list">
                        ${info.examples.map(example => `<li>"${example}"</li>`).join('')}
                    </ul>
                </div>
            </div>
        `;
    }

    // Utility methods
    showElement(element) {
        if (element) {
            element.style.display = 'block';
            element.style.opacity = '0';
            element.style.transform = 'translateY(-10px)';
            
            // Trigger animation
            requestAnimationFrame(() => {
                element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            });
        }
    }

    hideElement(element) {
        if (element) {
            element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            element.style.opacity = '0';
            element.style.transform = 'translateY(-10px)';
            
            setTimeout(() => {
                element.style.display = 'none';
            }, 300);
        }
    }

    animateElementIn(element) {
        if (element) {
            element.style.opacity = '0';
            element.style.transform = 'translateY(10px)';
            
            requestAnimationFrame(() => {
                element.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            });
        }
    }

    addRequiredIndicator(element) {
        const label = document.querySelector(`label[for="${element.id}"]`);
        if (label && !label.querySelector('.required-indicator')) {
            const indicator = document.createElement('span');
            indicator.className = 'required-indicator';
            indicator.textContent = ' *';
            indicator.style.color = '#dc3545';
            label.appendChild(indicator);
        }
    }

    removeRequiredIndicator(element) {
        const label = document.querySelector(`label[for="${element.id}"]`);
        if (label) {
            const indicator = label.querySelector('.required-indicator');
            if (indicator) {
                indicator.remove();
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

    showErrorMessages(errors) {
        // Remove existing error container
        const existingError = document.querySelector('.tod-error-container');
        if (existingError) {
            existingError.remove();
        }

        // Create new error container
        const errorContainer = document.createElement('div');
        errorContainer.className = 'tod-error-container tod-error-message';
        errorContainer.innerHTML = `
            <strong>Please fix the following errors:</strong>
            <ul>
                ${errors.map(error => `<li>${error}</li>`).join('')}
            </ul>
        `;

        // Insert at the top of the form
        const form = document.getElementById('tod-simulator-form');
        if (form) {
            form.insertBefore(errorContainer, form.firstChild);
            errorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    clearErrorMessages() {
        const errorContainer = document.querySelector('.tod-error-container');
        if (errorContainer) {
            errorContainer.remove();
        }

        // Clear field-level errors
        const errorFields = document.querySelectorAll('.error');
        errorFields.forEach(field => this.removeError(field));
    }

    showSuccessMessage(message, duration = 3000) {
        // Remove existing success message
        const existingSuccess = document.querySelector('.tod-success-container');
        if (existingSuccess) {
            existingSuccess.remove();
        }

        // Create success message
        const successContainer = document.createElement('div');
        successContainer.className = 'tod-success-container tod-success-message';
        successContainer.textContent = message;

        // Insert at the top of the form
        const form = document.getElementById('tod-simulator-form');
        if (form) {
            form.insertBefore(successContainer, form.firstChild);
            
            // Auto-remove after duration
            setTimeout(() => {
                if (successContainer.parentNode) {
                    successContainer.remove();
                }
            }, duration);
        }
    }

    setLoadingState(button, isLoading) {
        if (!button) return;

        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.innerHTML = '<span class="tod-loading"></span> Starting Session...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || 'Start TOD Session';
        }
    }

    // Preference management
    savePreference(key, value) {
        try {
            localStorage.setItem(`tod_simulator_${key}`, value);
        } catch (e) {
            console.warn('Could not save preference:', e);
        }
    }

    loadSavedPreferences() {
        try {
            // Load domain preference
            const savedDomain = localStorage.getItem('tod_simulator_domain');
            if (savedDomain) {
                const domainSelect = document.getElementById('domain');
                if (domainSelect && domainSelect.querySelector(`option[value="${savedDomain}"]`)) {
                    domainSelect.value = savedDomain;
                    this.handleDomainChange({ target: domainSelect });
                }
            }

            // Load assignment type preference
            const savedAssignmentType = localStorage.getItem('tod_simulator_assignment_type');
            if (savedAssignmentType) {
                const assignmentRadio = document.querySelector(`input[name="assignment_type"][value="${savedAssignmentType}"]`);
                if (assignmentRadio) {
                    assignmentRadio.checked = true;
                    this.handleAssignmentTypeChange({ target: assignmentRadio });
                }
            }

            // Load model type preference
            const savedModelType = localStorage.getItem('tod_simulator_model_type');
            if (savedModelType) {
                const modelTypeSelect = document.getElementById('model_type');
                if (modelTypeSelect && modelTypeSelect.querySelector(`option[value="${savedModelType}"]`)) {
                    modelTypeSelect.value = savedModelType;
                }
            }
        } catch (e) {
            console.warn('Could not load preferences:', e);
        }
    }

    clearPreferences() {
        try {
            localStorage.removeItem('tod_simulator_domain');
            localStorage.removeItem('tod_simulator_assignment_type');
            localStorage.removeItem('tod_simulator_model_type');
        } catch (e) {
            console.warn('Could not clear preferences:', e);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new TODSimulator();
});