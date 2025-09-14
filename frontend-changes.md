# Frontend Changes: Dark/Light Theme Toggle

## Overview
Added a comprehensive dark/light theme toggle system to the Course Materials Assistant interface. The feature provides smooth transitions between themes while maintaining accessibility and responsive design.

## Changes Made

### 1. HTML Structure Changes (`frontend/index.html`)

**Modified Header Section:**
- Added `header-content` wrapper div for proper layout
- Added `header-text` container for existing title and subtitle
- Added theme toggle button with sun/moon icon elements
- Button includes proper ARIA label for accessibility

**New Elements Added:**
```html
<div class="header-content">
    <div class="header-text">
        <h1>Course Materials Assistant</h1>
        <p class="subtitle">Ask questions about courses, instructors, and content</p>
    </div>
    <button id="themeToggle" class="theme-toggle" aria-label="Toggle theme">
        <span class="theme-icon sun-icon">☀️</span>
        <span class="theme-icon moon-icon">🌙</span>
    </button>
</div>
```

### 2. CSS Changes (`frontend/style.css`)

**Theme Variables:**
- Enhanced CSS custom properties with dedicated light theme variables
- Added `--theme-transition: all 0.3s ease` for smooth animations
- Light theme uses high contrast colors for accessibility

**New Light Theme Colors:**
- Background: `#ffffff` (pure white)
- Surface: `#f8fafc` (light gray)
- Text Primary: `#1e293b` (dark slate)
- Text Secondary: `#64748b` (medium slate)
- Border: `#e2e8f0` (light border)
- Assistant Message Background: `#f1f5f9` (very light gray)

**Header Styling:**
- Made header visible with proper background and border
- Added flexbox layout for title/button positioning
- Responsive design for mobile screens

**Theme Toggle Button:**
- 60x32px rounded button with smooth transitions
- Animated sun/moon icons with rotation and scale effects
- Hover and focus states with proper accessibility
- Icons transition opacity and transform on theme change

**Transition Effects:**
- Added theme transitions to all major UI elements
- Smooth color changes across backgrounds, borders, and text
- Icon animations with rotation and scaling

**Responsive Design:**
- Mobile layout stacks header content vertically
- Centers theme toggle button on small screens
- Maintains accessibility across all screen sizes

### 3. JavaScript Changes (`frontend/script.js`)

**New Functions Added:**
- `initializeTheme()`: Loads saved theme preference or defaults to dark
- `toggleTheme()`: Switches between light and dark themes
- `setTheme(theme)`: Applies theme and saves preference

**Event Listeners:**
- Click handler for theme toggle button
- Keyboard accessibility (Enter and Space keys)
- Updates ARIA labels based on current theme

**Local Storage:**
- Persists user theme preference across sessions
- Automatically applies saved theme on page load

**Accessibility Features:**
- Dynamic ARIA labels ("Switch to dark theme" / "Switch to light theme")
- Keyboard navigation support
- Focus indicators with proper contrast

## Technical Features

### Theme System
- Uses CSS custom properties for efficient theme switching
- `data-theme` attribute on document element controls active theme
- Fallback to dark theme if no preference is saved

### Performance
- CSS transitions use hardware acceleration where possible
- Minimal JavaScript footprint
- No external dependencies for theme functionality

### Accessibility Compliance
- WCAG compliant color contrast ratios in both themes
- Keyboard navigation support
- Screen reader friendly with proper ARIA labels
- Focus indicators maintain visibility in both themes

### Browser Support
- Modern browsers with CSS custom properties support
- Graceful fallback for older browsers
- Local storage with error handling

## File Structure
```
frontend/
├── index.html          # Updated header structure
├── style.css          # Theme variables and styles
└── script.js          # Theme management functions
```

## Usage
- Click the sun/moon toggle button in the top-right header
- Use keyboard (Enter or Space) when button is focused
- Theme preference is automatically saved and restored
- Smooth transitions provide visual feedback during theme changes