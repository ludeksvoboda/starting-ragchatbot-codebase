// API base URL - detect current host and use absolute URL for better reliability
const API_URL = window.location.origin + '/api';

// Global state
let currentSessionId = null;

// DOM elements
let chatMessages,
  chatInput,
  sendButton,
  totalCourses,
  courseTitles,
  newChatButton,
  themeToggle;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM Content Loaded - Initializing chat application');
  console.log('API URL configured as:', API_URL);

  // Get DOM elements after page loads
  chatMessages = document.getElementById('chatMessages');
  chatInput = document.getElementById('chatInput');
  sendButton = document.getElementById('sendButton');
  totalCourses = document.getElementById('totalCourses');
  courseTitles = document.getElementById('courseTitles');
  newChatButton = document.getElementById('newChatButton');
  themeToggle = document.getElementById('themeToggle');

  // Verify all elements exist
  const elements = {
    chatMessages,
    chatInput,
    sendButton,
    totalCourses,
    courseTitles,
    newChatButton,
    themeToggle,
  };
  for (const [name, element] of Object.entries(elements)) {
    if (!element) {
      console.error(`Missing DOM element: ${name}`);
    } else {
      console.log(`Found DOM element: ${name}`);
    }
  }

  setupEventListeners();
  initializeTheme();
  createNewSession();
  loadCourseStats();

  console.log('Chat application initialization complete');
});

// Event Listeners
function setupEventListeners() {
  // Chat functionality
  sendButton.addEventListener('click', sendMessage);
  chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });

  // New chat button
  newChatButton.addEventListener('click', clearCurrentChat);

  // Theme toggle button
  themeToggle.addEventListener('click', toggleTheme);

  // Keyboard accessibility for theme toggle
  themeToggle.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleTheme();
    }
  });

  // Suggested questions
  document.querySelectorAll('.suggested-item').forEach(button => {
    button.addEventListener('click', e => {
      const question = e.target.getAttribute('data-question');
      chatInput.value = question;
      sendMessage();
    });
  });
}

// Chat Functions
async function sendMessage() {
  const query = chatInput.value.trim();
  if (!query) {
    return;
  }

  // Disable input
  chatInput.value = '';
  chatInput.disabled = true;
  sendButton.disabled = true;

  // Add user message
  addMessage(query, 'user');

  // Add loading message - create a unique container for it
  const loadingMessage = createLoadingMessage();
  chatMessages.appendChild(loadingMessage);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    console.log('Making request to:', `${API_URL}/query`);
    console.log('Request payload:', { query, session_id: currentSessionId });

    const response = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
        session_id: currentSessionId,
      }),
    });

    console.log('Response status:', response.status);
    console.log('Response ok:', response.ok);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error Response:', errorText);
      throw new Error(`API Error (${response.status}): ${errorText}`);
    }

    const data = await response.json();
    console.log('Response data:', data);

    // Update session ID if new
    if (!currentSessionId) {
      currentSessionId = data.session_id;
    }

    // Replace loading message with response
    loadingMessage.remove();
    addMessage(data.answer, 'assistant', data.sources);
  } catch (error) {
    console.error('Request failed:', error);

    // Replace loading message with error
    loadingMessage.remove();

    let errorMessage = `Error: ${error.message}`;

    // Provide more specific error messages based on error type
    if (
      error.name === 'TypeError' &&
      error.message.includes('Failed to fetch')
    ) {
      errorMessage =
        'Connection Error: Cannot connect to the server. Please ensure the server is running on http://localhost:8000 and try refreshing the page.';
    } else if (error.name === 'NetworkError') {
      errorMessage =
        'Network Error: Please check your internet connection and server status.';
    } else if (error.message.includes('API Error')) {
      errorMessage = error.message; // Already formatted above
    }

    addMessage(errorMessage, 'assistant');
  } finally {
    chatInput.disabled = false;
    sendButton.disabled = false;
    chatInput.focus();
  }
}

function createLoadingMessage() {
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
  const messageId = Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
  messageDiv.id = `message-${messageId}`;

  // Convert markdown to HTML for assistant messages
  const displayContent =
    type === 'assistant' ? marked.parse(content) : escapeHtml(content);

  let html = `<div class="message-content">${displayContent}</div>`;

  if (sources && sources.length > 0) {
    // Handle both old string format and new object format for backward compatibility
    const sourceLinks = sources
      .map(source => {
        if (typeof source === 'string') {
          // Legacy string format
          return escapeHtml(source);
        } else if (source && typeof source === 'object' && source.link) {
          // New format with link
          return `<a href="${escapeHtml(source.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.text)}</a>`;
        } else if (source && typeof source === 'object' && source.text) {
          // New format without link
          return escapeHtml(source.text);
        } else {
          // Fallback for unexpected format
          return escapeHtml(String(source));
        }
      })
      .join(', ');

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

  return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
  currentSessionId = null;
  chatMessages.innerHTML = '';
  addMessage(
    'Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?',
    'assistant',
    null,
    true
  );
}

async function clearCurrentChat() {
  // Clear backend session if one exists
  if (currentSessionId) {
    try {
      await fetch(`${API_URL}/clear-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: currentSessionId,
        }),
      });
    } catch (error) {
      console.error('Error clearing backend session:', error);
      // Continue with frontend cleanup even if backend fails
    }
  }

  // Clear frontend state and UI
  createNewSession();

  // Focus input for new conversation
  if (chatInput) {
    chatInput.focus();
  }
}

// Load course statistics
async function loadCourseStats() {
  try {
    console.log('Loading course stats from:', `${API_URL}/courses`);
    const response = await fetch(`${API_URL}/courses`);
    console.log('Course stats response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Course stats error:', errorText);
      throw new Error(
        `Failed to load course stats (${response.status}): ${errorText}`
      );
    }

    const data = await response.json();
    console.log('Course data received:', data);

    // Update stats in UI
    if (totalCourses) {
      totalCourses.textContent = data.total_courses;
    }

    // Update course titles
    if (courseTitles) {
      if (data.course_titles && data.course_titles.length > 0) {
        courseTitles.innerHTML = data.course_titles
          .map(title => `<div class="course-title-item">${title}</div>`)
          .join('');
      } else {
        courseTitles.innerHTML =
          '<span class="no-courses">No courses available</span>';
      }
    }
  } catch (error) {
    console.error('Error loading course stats:', error);
    // Set default values on error
    if (totalCourses) {
      totalCourses.textContent = '0';
    }
    if (courseTitles) {
      courseTitles.innerHTML =
        '<span class="error">Failed to load courses</span>';
    }
  }
}

// Theme Management Functions
function initializeTheme() {
  // Check for saved theme preference or default to 'dark'
  const savedTheme = localStorage.getItem('theme') || 'dark';
  setTheme(savedTheme);
  console.log('Theme initialized:', savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  setTheme(newTheme);
  console.log('Theme toggled from', currentTheme, 'to', newTheme);
}

function setTheme(theme) {
  // Apply theme to document
  document.documentElement.setAttribute('data-theme', theme);

  // Save preference
  localStorage.setItem('theme', theme);

  // Update button aria-label for accessibility
  if (themeToggle) {
    const label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
    themeToggle.setAttribute('aria-label', label);
  }

  console.log('Theme set to:', theme);
}