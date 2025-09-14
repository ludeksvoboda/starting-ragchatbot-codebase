// Enhanced frontend JavaScript with debugging and better error handling
// This file contains the same logic as script.js but with extensive debugging

// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;
let debugMode = true; // Enable detailed logging

// Enhanced logging function
function debugLog(message, data = null) {
    if (debugMode) {
        console.log(`[DEBUG] ${new Date().toISOString()} - ${message}`, data || '');
    }
}

// Enhanced error logging
function errorLog(message, error = null) {
    console.error(`[ERROR] ${new Date().toISOString()} - ${message}`, error || '');
}

// DOM elements
let chatMessages, chatInput, sendButton, totalCourses, courseTitles, newChatButton;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    debugLog('DOM Content Loaded - Initializing application');
    
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalCourses = document.getElementById('totalCourses');
    courseTitles = document.getElementById('courseTitles');
    newChatButton = document.getElementById('newChatButton');
    
    // Verify all elements exist
    const elements = {
        chatMessages, chatInput, sendButton, 
        totalCourses, courseTitles, newChatButton
    };
    
    for (const [name, element] of Object.entries(elements)) {
        if (!element) {
            errorLog(`Missing DOM element: ${name}`);
        } else {
            debugLog(`Found DOM element: ${name}`);
        }
    }
    
    setupEventListeners();
    createNewSession();
    loadCourseStats();
    
    // Test API connectivity on startup
    testApiConnectivity();
});

// Test API connectivity
async function testApiConnectivity() {
    debugLog('Testing API connectivity...');
    try {
        const response = await fetch(`${API_URL}/courses`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        debugLog(`API connectivity test response status: ${response.status}`);
        
        if (response.ok) {
            const data = await response.json();
            debugLog('API connectivity test successful', data);
        } else {
            errorLog(`API connectivity test failed with status: ${response.status}`);
            const errorText = await response.text();
            errorLog('API error response', errorText);
        }
    } catch (error) {
        errorLog('API connectivity test failed with exception', error);
        
        // Provide specific error diagnosis
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            errorLog('DIAGNOSIS: Network request failed - server may not be running or CORS issue');
        } else if (error.name === 'AbortError') {
            errorLog('DIAGNOSIS: Request was aborted - timeout or network interruption');
        } else {
            errorLog('DIAGNOSIS: Unknown network error', error.stack);
        }
    }
}

// Event Listeners
function setupEventListeners() {
    debugLog('Setting up event listeners');
    
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            debugLog('Enter key pressed, sending message');
            sendMessage();
        }
    });
    
    // New chat button
    newChatButton.addEventListener('click', clearCurrentChat);
    
    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            debugLog(`Suggested question clicked: ${question}`);
            chatInput.value = question;
            sendMessage();
        });
    });
    
    debugLog('Event listeners setup complete');
}

// Enhanced sendMessage with detailed error handling
async function sendMessage() {
    const query = chatInput.value.trim();
    debugLog(`Sending message: "${query}"`);
    
    if (!query) {
        debugLog('Empty query, aborting send');
        return;
    }

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(query, 'user');

    // Add loading message
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const requestPayload = {
        query: query,
        session_id: currentSessionId
    };
    
    debugLog('Request payload', requestPayload);
    debugLog(`Making request to: ${API_URL}/query`);

    try {
        const requestStart = Date.now();
        
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload)
        });

        const requestDuration = Date.now() - requestStart;
        debugLog(`Request completed in ${requestDuration}ms with status: ${response.status}`);
        
        // Enhanced response handling
        if (!response.ok) {
            const errorText = await response.text();
            debugLog('Response error details', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries()),
                body: errorText
            });
            
            // Provide specific error messages based on status
            let errorMessage = 'Query failed';
            if (response.status === 500) {
                errorMessage = 'Server error - check backend logs';
            } else if (response.status === 402) {
                errorMessage = 'API credit balance too low';
            } else if (response.status === 400) {
                errorMessage = 'Bad request - check query format';
            } else if (response.status === 404) {
                errorMessage = 'API endpoint not found';
            } else if (response.status === 429) {
                errorMessage = 'Rate limit exceeded - try again later';
            }
            
            throw new Error(`${errorMessage} (${response.status})`);
        }

        const data = await response.json();
        debugLog('Response data received', {
            answerLength: data.answer ? data.answer.length : 0,
            sourcesCount: data.sources ? data.sources.length : 0,
            sessionId: data.session_id
        });
        
        // Validate response structure
        if (!data.answer) {
            errorLog('Response missing answer field', data);
        }
        if (!data.session_id) {
            errorLog('Response missing session_id field', data);
        }
        
        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
            debugLog(`Session ID set to: ${currentSessionId}`);
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources);
        
        debugLog('Message successfully processed and displayed');

    } catch (error) {
        errorLog('Message sending failed', error);
        
        // Replace loading message with detailed error
        loadingMessage.remove();
        
        let userErrorMessage = `Error: ${error.message}`;
        
        // Enhanced error diagnosis
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            userErrorMessage = 'Network Error: Cannot connect to server. Please check if the server is running on http://localhost:8000';
            errorLog('DIAGNOSIS: Failed to fetch - likely server not running or network issue');
        } else if (error.name === 'SyntaxError' && error.message.includes('JSON')) {
            userErrorMessage = 'Error: Server returned invalid response format';
            errorLog('DIAGNOSIS: JSON parsing error - server returned non-JSON response');
        } else if (error.name === 'AbortError') {
            userErrorMessage = 'Error: Request timeout - server may be overloaded';
            errorLog('DIAGNOSIS: Request aborted - likely timeout');
        }
        
        addMessage(userErrorMessage, 'assistant');
        
    } finally {
        // Re-enable input
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
        debugLog('Input controls re-enabled');
    }
}

function createLoadingMessage() {
    debugLog('Creating loading message');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false) {
    debugLog(`Adding message: type=${type}, contentLength=${content.length}, sourcesCount=${sources ? sources.length : 0}`);
    
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;
    
    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);
    
    let html = `<div class="message-content">${displayContent}</div>`;
    
    if (sources && sources.length > 0) {
        debugLog('Adding sources to message', sources);
        
        // Handle both old string format and new object format for backward compatibility
        const sourceLinks = sources.map(source => {
            if (typeof source === 'string') {
                return escapeHtml(source);
            } else if (source && typeof source === 'object' && source.link) {
                return `<a href="${escapeHtml(source.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.text)}</a>`;
            } else if (source && typeof source === 'object' && source.text) {
                return escapeHtml(source.text);
            } else {
                return escapeHtml(String(source));
            }
        }).join(', ');
        
        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">Sources</summary>
                <div class="sources-content">${sourceLinks}</div>
            </details>
        `;
    }
    
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    debugLog(`Message added with ID: ${messageId}`);
    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function createNewSession() {
    debugLog('Creating new session');
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?', 'assistant', null, true);
}

async function clearCurrentChat() {
    debugLog('Clearing current chat');
    
    // Clear backend session if one exists
    if (currentSessionId) {
        try {
            debugLog(`Clearing backend session: ${currentSessionId}`);
            const response = await fetch(`${API_URL}/clear-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: currentSessionId
                })
            });
            
            if (response.ok) {
                debugLog('Backend session cleared successfully');
            } else {
                errorLog(`Failed to clear backend session: ${response.status}`);
            }
        } catch (error) {
            errorLog('Error clearing backend session', error);
        }
    }
    
    // Clear frontend state and UI
    createNewSession();
    
    // Focus input for new conversation
    if (chatInput) {
        chatInput.focus();
    }
}

// Enhanced loadCourseStats with better error handling
async function loadCourseStats() {
    debugLog('Loading course statistics');
    
    try {
        const response = await fetch(`${API_URL}/courses`);
        debugLog(`Course stats response status: ${response.status}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to load course stats: ${response.status} - ${errorText}`);
        }
        
        const data = await response.json();
        debugLog('Course stats loaded', data);
        
        // Update stats in UI
        if (totalCourses) {
            totalCourses.textContent = data.total_courses;
            debugLog(`Updated total courses display: ${data.total_courses}`);
        }
        
        // Update course titles
        if (courseTitles) {
            if (data.course_titles && data.course_titles.length > 0) {
                courseTitles.innerHTML = data.course_titles
                    .map(title => `<div class="course-title-item">${escapeHtml(title)}</div>`)
                    .join('');
                debugLog(`Updated course titles: ${data.course_titles.length} courses`);
            } else {
                courseTitles.innerHTML = '<span class="no-courses">No courses available</span>';
                debugLog('No courses available');
            }
        }
        
    } catch (error) {
        errorLog('Error loading course stats', error);
        
        // Set error values in UI
        if (totalCourses) {
            totalCourses.textContent = '?';
        }
        if (courseTitles) {
            courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
        }
        
        // Provide diagnosis
        if (error.message.includes('Failed to fetch')) {
            errorLog('DIAGNOSIS: Cannot connect to courses API - server may not be running');
        }
    }
}

// Global error handler
window.addEventListener('error', (event) => {
    errorLog('Global JavaScript error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error
    });
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    errorLog('Unhandled promise rejection', event.reason);
});

// Export for debugging
window.debugChat = {
    debugMode,
    currentSessionId,
    testApiConnectivity,
    sendMessage,
    loadCourseStats
};