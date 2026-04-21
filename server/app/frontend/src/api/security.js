/**
 * Security utilities for XSS prevention and input sanitization
 */

/**
 * Sanitize HTML to prevent XSS attacks
 * @param {string} html - HTML string to sanitize
 * @returns {string} Sanitized HTML
 */
export const sanitizeHTML = (html) => {
    const element = document.createElement('div');
    element.textContent = html;
    return element.innerHTML;
};

/**
 * Sanitize user input to prevent XSS
 * @param {string} input - User input
 * @returns {string} Sanitized input
 */
export const sanitizeInput = (input) => {
    if (typeof input !== 'string') return input;
    return input
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;');
};

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid email
 */
export const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
};

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {object} Validation result
 */
export const validatePasswordStrength = (password) => {
    const minLength = 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);

    const issues = [];
    if (password.length < minLength) issues.push(`Password must be at least ${minLength} characters`);
    if (!hasUpperCase) issues.push('Password must contain uppercase letters');
    if (!hasLowerCase) issues.push('Password must contain lowercase letters');
    if (!hasNumbers) issues.push('Password must contain numbers');
    if (!hasSpecialChar) issues.push('Password must contain special characters');

    return {
        isValid: issues.length === 0,
        issues,
        strength: 5 - issues.length,
    };
};

/**
 * Secure localStorage with optional encryption
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 */
export const secureSetStorage = (key, value) => {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
        console.error('Failed to store data securely:', error);
    }
};

/**
 * Retrieve secure data from localStorage
 * @param {string} key - Storage key
 * @returns {any} Retrieved value or null
 */
export const secureGetStorage = (key) => {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
    } catch (error) {
        console.error('Failed to retrieve secure data:', error);
        return null;
    }
};

/**
 * Clear sensitive data from localStorage
 * @param {string[]} keys - Keys to remove
 */
export const secureClearStorage = (keys) => {
    keys.forEach(key => {
        try {
            localStorage.removeItem(key);
            // Overwrite with random data for security
            localStorage.setItem(key, Math.random().toString());
            localStorage.removeItem(key);
        } catch (error) {
            console.error(`Failed to clear storage key ${key}:`, error);
        }
    });
};

/**
 * Generate CSRF token for forms
 * @returns {string} CSRF token
 */
export const generateCSRFToken = () => {
    return Math.random().toString(36).substr(2) + Date.now().toString(36);
};

/**
 * Validate CSRF token
 * @param {string} token - Token to validate
 * @returns {boolean} True if valid
 */
export const validateCSRFToken = (token) => {
    const storedToken = secureGetStorage('csrf-token');
    return storedToken === token;
};

/**
 * Rate limit helper
 * @param {string} key - Rate limit key
 * @param {number} maxAttempts - Max attempts allowed
 * @param {number} windowMs - Time window in milliseconds
 * @returns {boolean} True if rate limit exceeded
 */
export const checkRateLimit = (key, maxAttempts = 5, windowMs = 60000) => {
    const now = Date.now();
    const attempts = secureGetStorage(`ratelimit-${key}`) || [];
    
    // Remove old attempts outside the window
    const recentAttempts = attempts.filter(time => now - time < windowMs);
    
    if (recentAttempts.length >= maxAttempts) {
        return true; // Rate limit exceeded
    }
    
    // Record this attempt
    recentAttempts.push(now);
    secureSetStorage(`ratelimit-${key}`, recentAttempts);
    
    return false;
};
