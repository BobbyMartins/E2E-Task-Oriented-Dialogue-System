/**
 * TOD Chat JavaScript - Real-time Chat Functionality
 * Handles dynamic chat interactions for the TOD chat interface
 */

class TODChat {
    constructor() {
        this.sessionId = null;
        this.domain = null;
        this.modelType = null;
        this.currentTurn = 1;
        this.conversationActive = true;
        this.messageQueue = [];
        this.isProcessing = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.typingTimeout = null;

        this.init();
    }

    init() {
        this.loadSessionData();
        this.bindEvents();
        this.setupAutoSave();
        this.setupKeyboardShortcuts();
        this.focusMessageInput();
    }

    loadSessionData() {
        // Get session data from hidden inputs
        const sessionIdInput = document.getElementById('session-id');
        const domainInput = document.getElementById('domain');
        const modelTypeInput = document.getElementById('model-type');

        if (sessionIdInput) this.sessionId = sessionIdInput.value;
        if (domainInput) this.domain = domainInput.value;
        if (modelTypeInput) this.modelType = modelTypeInput.value;

        // Validate required data
        if (!this.sessionId || !this.domain || !this.modelType) {
            this.showError('Session data is incomplete. Please start a new session.');
            this.conversationActive = false;
        }
    }

    bindEvents() {
        // Message form submission
        const messageForm = document.getElementById('message-form');
        if (messageForm) {
            messageForm.addEventListener('submit', this.handleMessageSubmit.bind(this));
        }

        // End conversation button
        const endConversationBtn = document.getElementById('end-conversation');
        if (endConversationBtn) {
            endConversationBtn.addEventListener('click', this.handleEndConversation.bind(this));
        }

        // Provide feedback button
        const provideFeedbackBtn = document.getElementById('provide-feedback');
        if (provideFeedbackBtn) {
            provideFeedbackBtn.addEventListener('click', this.handleProvideFeedback.bind(this));
        }

        // Message input events
        const userMessageInput = document.getElementById('user-message');
        if (userMessageInput) {
            userMessageInput.addEventListener('input', this.handleInputChange.bind(this));
            userMessageInput.addEventListener('keydown', this.handleKeyDown.bind(this));
        }

        // Window events
        window.addEventListener('beforeunload', this.handleBeforeUnload.bind(this));
        window.addEventListener('online', this.handleOnline.bind(this));
        window.addEventListener('offline', this.handleOffline.bind(this));
    }

    handleMessageSubmit(event) {
        event.preventDefault();
        
        if (!this.conversationActive || this.isProcessing) {
            return;
        }

        const userMessageInput = document.getElementById('user-message');
        const userMessage = userMessageInput.value.trim();

        if (!userMessage) {
            this.showError('Please enter a message');
            return;
        }

        if (userMessage.length > 1000) {
            this.showError('Message is too long. Please keep it under 1000 characters.');
            return;
        }

        this.sendMessage(userMessage);
    }

    async sendMessage(userMessage) {
        const userMessageInput = document.getElementById('user-message');
        const messageForm = document.getElementById('message-form');
        const submitButton = messageForm.querySelector('button[type="submit"]');

        // Set processing state
        this.isProcessing = true;
        this.setInputState(false);

        // Add user message to chat
        this.addMessage('user', userMessage);

        // Clear input
        userMessageInput.value = '';

        // Show bot typing indicator
        const typingIndicator = this.addTypingIndicator('bot');

        try {
            // Send message to server
            const response = await this.makeRequest('/tod_chat_message', {
                message: userMessage,
                session_id: this.sessionId
            });

            // Remove typing indicator
            this.removeTypingIndicator(typingIndicator);

            if (response.status === 'success') {
                // Add bot response
                this.addMessage('bot', response.message);
                
                // Update turn counter
                this.updateTurnCounter();
                
                // Check if conversation should end
                if (response.conversation_ended) {
                    this.handleConversationEnd();
                }

                // Reset retry count on success
                this.retryCount = 0;
            } else {
                throw new Error(response.error || 'Failed to get response');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            
            // Remove typing indicator
            this.removeTypingIndicator(typingIndicator);
            
            // Handle retry logic
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                this.showRetryOption(userMessage);
            } else {
                this.showError('Failed to send message after multiple attempts. Please try again or start a new session.');
            }
        } finally {
            // Reset processing state
            this.isProcessing = false;
            this.setInputState(true);
        }
    }

    async makeRequest(url, data) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
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

    handleEndConversation() {
        if (!this.conversationActive) return;

        const confirmMessage = 'Are you sure you want to end this conversation? You will be asked to provide feedback.';
        
        if (confirm(confirmMessage)) {
            this.endConversation();
        }
    }

    handleConversationEnd() {
        // Automatic conversation end (triggered by system)
        this.conversationActive = false;
        
        // Add system message about automatic end
        this.addSystemMessage('The conversation has ended automatically. Thank you for your participation!');
        
        // Show transition message
        this.showTransitionToFeedback();
        
        // Auto-transition to feedback after a delay
        setTimeout(() => {
            this.transitionToFeedback();
        }, 3000);
    }

    showTransitionToFeedback() {
        const chatInputContainer = document.getElementById('chat-input-container');
        const conversationEnded = document.getElementById('conversation-ended');
        const endConversationBtn = document.getElementById('end-conversation');

        if (chatInputContainer) chatInputContainer.style.display = 'none';
        if (endConversationBtn) endConversationBtn.disabled = true;

        // Create transition message
        const transitionDiv = document.createElement('div');
        transitionDiv.className = 'transition-message';
        transitionDiv.innerHTML = `
            <div class="transition-content">
                <h3>Conversation Complete!</h3>
                <p>The system has detected that your task has been completed.</p>
                <p>You will be automatically redirected to provide feedback in <span id="countdown">3</span> seconds.</p>
                <div class="transition-actions">
                    <button id="feedback-now" class="btn primary-btn">Provide Feedback Now</button>
                    <button id="skip-feedback" class="btn secondary-btn">Skip Feedback</button>
                </div>
            </div>
        `;

        // Add styles
        transitionDiv.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 1000;
            text-align: center;
            max-width: 400px;
            width: 90%;
        `;

        document.body.appendChild(transitionDiv);

        // Countdown timer
        let countdown = 3;
        const countdownElement = document.getElementById('countdown');
        const countdownInterval = setInterval(() => {
            countdown--;
            if (countdownElement) {
                countdownElement.textContent = countdown;
            }
            if (countdown <= 0) {
                clearInterval(countdownInterval);
            }
        }, 1000);

        // Bind buttons
        document.getElementById('feedback-now').addEventListener('click', () => {
            clearInterval(countdownInterval);
            transitionDiv.remove();
            this.transitionToFeedback();
        });

        document.getElementById('skip-feedback').addEventListener('click', () => {
            clearInterval(countdownInterval);
            transitionDiv.remove();
            this.skipFeedback();
        });
    }

    transitionToFeedback() {
        // Save current state before navigating
        this.saveConversationState();
        
        // Navigate to feedback form
        window.location.href = `/feedback_form?session_id=${this.sessionId}`;
    }

    skipFeedback() {
        // Show confirmation
        if (confirm('Are you sure you want to skip providing feedback? Your input helps improve the system.')) {
            // Navigate back to simulator
            window.location.href = '/tod_simulator';
        } else {
            // Show transition again
            this.showTransitionToFeedback();
        }
    }

    async endConversation() {
        this.conversationActive = false;
        
        // Update UI
        const chatInputContainer = document.getElementById('chat-input-container');
        const conversationEnded = document.getElementById('conversation-ended');
        const endConversationBtn = document.getElementById('end-conversation');

        if (chatInputContainer) chatInputContainer.style.display = 'none';
        if (conversationEnded) conversationEnded.style.display = 'block';
        if (endConversationBtn) endConversationBtn.disabled = true;

        // Add system message
        this.addSystemMessage('Conversation ended. Thank you for your participation!');

        // Notify server
        try {
            await this.makeRequest('/end_tod_conversation', {
                session_id: this.sessionId
            });
        } catch (error) {
            console.error('Error ending conversation:', error);
            // Don't show error to user as conversation is already ended
        }

        // Auto-scroll to feedback button
        setTimeout(() => {
            const provideFeedbackBtn = document.getElementById('provide-feedback');
            if (provideFeedbackBtn) {
                provideFeedbackBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                provideFeedbackBtn.focus();
            }
        }, 500);
    }

    handleProvideFeedback() {
        // Save current state before navigating
        this.saveConversationState();
        
        // Navigate to feedback form
        window.location.href = `/feedback_form?session_id=${this.sessionId}`;
    }

    handleInputChange(event) {
        const input = event.target;
        const charCount = input.value.length;
        const maxLength = 1000;

        // Update character counter if it exists
        let charCounter = document.getElementById('char-counter');
        if (!charCounter) {
            charCounter = document.createElement('div');
            charCounter.id = 'char-counter';
            charCounter.className = 'char-counter';
            input.parentNode.appendChild(charCounter);
        }

        charCounter.textContent = `${charCount}/${maxLength}`;
        charCounter.style.color = charCount > maxLength * 0.9 ? '#dc3545' : '#666';

        // Clear typing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }

        // Set new timeout for typing indicator (if implemented on server)
        this.typingTimeout = setTimeout(() => {
            // Could send typing stopped indicator to server
        }, 1000);
    }

    handleKeyDown(event) {
        // Handle Enter key (submit) and Shift+Enter (new line)
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            const form = document.getElementById('message-form');
            if (form) {
                form.dispatchEvent(new Event('submit'));
            }
        }
    }

    handleBeforeUnload(event) {
        if (this.conversationActive && this.currentTurn > 1) {
            event.preventDefault();
            event.returnValue = 'You have an active conversation. Are you sure you want to leave?';
            return event.returnValue;
        }
    }

    handleOnline() {
        this.showSuccessMessage('Connection restored', 3000);
        this.setInputState(true);
    }

    handleOffline() {
        this.showError('Connection lost. Please check your internet connection.');
        this.setInputState(false);
    }

    // Message handling methods
    addMessage(sender, content, timestamp = null) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        messageDiv.setAttribute('data-turn', this.currentTurn);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = timestamp || this.formatTime(new Date());

        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);

        chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        // Animate message in
        this.animateMessageIn(messageDiv);

        // Save to local storage for recovery
        this.saveMessageToLocal(sender, content, timestamp);
    }

    addSystemMessage(content) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        this.animateMessageIn(messageDiv);
    }

    addTypingIndicator(sender) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return null;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message typing-indicator-container`;
        messageDiv.id = 'typing-indicator';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = '<div class="typing-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';

        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        return messageDiv;
    }

    removeTypingIndicator(indicator) {
        if (indicator && indicator.parentNode) {
            indicator.parentNode.removeChild(indicator);
        }
    }

    updateTurnCounter() {
        this.currentTurn++;
        const turnCounter = document.getElementById('turn-counter');
        if (turnCounter) {
            turnCounter.textContent = this.currentTurn;
            
            // Animate counter update
            turnCounter.style.transform = 'scale(1.2)';
            turnCounter.style.color = 'var(--primary-color)';
            
            setTimeout(() => {
                turnCounter.style.transform = 'scale(1)';
                turnCounter.style.color = '';
            }, 200);
        }
    }

    // UI utility methods
    setInputState(enabled) {
        const userMessageInput = document.getElementById('user-message');
        const submitButton = document.querySelector('#message-form button[type="submit"]');

        if (userMessageInput) {
            userMessageInput.disabled = !enabled;
            if (enabled) {
                userMessageInput.focus();
            }
        }

        if (submitButton) {
            submitButton.disabled = !enabled;
            submitButton.textContent = enabled ? 'Send' : 'Processing...';
        }
    }

    focusMessageInput() {
        const userMessageInput = document.getElementById('user-message');
        if (userMessageInput && this.conversationActive) {
            userMessageInput.focus();
        }
    }

    scrollToBottom() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    animateMessageIn(messageElement) {
        messageElement.style.opacity = '0';
        messageElement.style.transform = 'translateY(20px)';
        
        requestAnimationFrame(() => {
            messageElement.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            messageElement.style.opacity = '1';
            messageElement.style.transform = 'translateY(0)';
        });
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Error handling and user feedback
    showError(message, duration = 5000) {
        this.showMessage(message, 'error', duration);
    }

    showSuccessMessage(message, duration = 3000) {
        this.showMessage(message, 'success', duration);
    }

    showMessage(message, type = 'info', duration = 3000) {
        // Remove existing messages of the same type
        const existingMessage = document.querySelector(`.tod-${type}-message`);
        if (existingMessage) {
            existingMessage.remove();
        }

        // Create message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `tod-${type}-message`;
        messageDiv.textContent = message;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '20px';
        messageDiv.style.right = '20px';
        messageDiv.style.zIndex = '1000';
        messageDiv.style.padding = '1rem';
        messageDiv.style.borderRadius = '4px';
        messageDiv.style.maxWidth = '300px';
        messageDiv.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';

        document.body.appendChild(messageDiv);

        // Auto-remove after duration
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, duration);
    }

    showRetryOption(originalMessage) {
        const retryDiv = document.createElement('div');
        retryDiv.className = 'retry-container';
        retryDiv.innerHTML = `
            <div class="retry-message">
                <p>Failed to send message. Would you like to retry?</p>
                <div class="retry-actions">
                    <button class="btn secondary-btn retry-btn">Retry</button>
                    <button class="btn secondary-btn cancel-retry-btn">Cancel</button>
                </div>
            </div>
        `;

        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.appendChild(retryDiv);
            this.scrollToBottom();

            // Bind retry events
            const retryBtn = retryDiv.querySelector('.retry-btn');
            const cancelBtn = retryDiv.querySelector('.cancel-retry-btn');

            retryBtn.addEventListener('click', () => {
                retryDiv.remove();
                this.sendMessage(originalMessage);
            });

            cancelBtn.addEventListener('click', () => {
                retryDiv.remove();
                this.retryCount = 0;
            });
        }
    }

    // Local storage and recovery
    saveMessageToLocal(sender, content, timestamp) {
        try {
            const messages = JSON.parse(localStorage.getItem(`tod_messages_${this.sessionId}`) || '[]');
            messages.push({
                sender,
                content,
                timestamp: timestamp || new Date().toISOString(),
                turn: this.currentTurn
            });
            localStorage.setItem(`tod_messages_${this.sessionId}`, JSON.stringify(messages));
        } catch (e) {
            console.warn('Could not save message to local storage:', e);
        }
    }

    saveConversationState() {
        try {
            const state = {
                sessionId: this.sessionId,
                domain: this.domain,
                modelType: this.modelType,
                currentTurn: this.currentTurn,
                conversationActive: this.conversationActive,
                timestamp: new Date().toISOString()
            };
            localStorage.setItem(`tod_state_${this.sessionId}`, JSON.stringify(state));
        } catch (e) {
            console.warn('Could not save conversation state:', e);
        }
    }

    setupAutoSave() {
        // Auto-save conversation state every 30 seconds
        setInterval(() => {
            if (this.conversationActive) {
                this.saveConversationState();
            }
        }, 30000);
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            // Ctrl/Cmd + Enter to send message
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                const form = document.getElementById('message-form');
                if (form) {
                    form.dispatchEvent(new Event('submit'));
                }
            }

            // Escape to focus input
            if (event.key === 'Escape') {
                this.focusMessageInput();
            }
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new TODChat();
});