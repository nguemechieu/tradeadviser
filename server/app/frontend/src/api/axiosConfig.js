import axios from 'axios';
import { sanitizeHTML } from './security';

// Create axios instance with security defaults
const axiosInstance = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest', // CSRF protection
  },
  // Prevent credential leaking
  withCredentials: false,
});

// Request interceptor to add auth token and security headers
axiosInstance.interceptors.request.use(
  (config) => {
    // Add authorization token if available
    const token = localStorage.getItem('tradeadviser-token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add security headers
    config.headers['X-Requested-With'] = 'XMLHttpRequest';
    config.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate';
    config.headers['Pragma'] = 'no-cache';
    
    // Validate request data isn't too large (prevent DOS)
    if (config.data && JSON.stringify(config.data).length > 1000000) {
      return Promise.reject(new Error('Request payload too large'));
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle security issues
axiosInstance.interceptors.response.use(
  (response) => {
    // Validate response has expected content-type
    const contentType = response.headers['content-type'];
    if (!contentType?.includes('application/json')) {
      console.warn('Unexpected content-type:', contentType);
    }
    
    // Check for security headers in response
    const securityHeaders = [
      'x-content-type-options',
      'x-frame-options',
      'x-xss-protection',
      'content-security-policy'
    ];
    
    for (const header of securityHeaders) {
      if (!response.headers[header]) {
        console.warn(`Missing security header: ${header}`);
      }
    }
    
    return response;
  },
  (error) => {
    // Handle 401 unauthorized - clear auth and redirect
    if (error.response?.status === 401) {
      localStorage.removeItem('tradeadviser-token');
      localStorage.removeItem('tradeadviser-user');
      localStorage.removeItem('remember-identifier');
      window.location.href = '/login';
      return Promise.reject(new Error('Unauthorized - please login again'));
    }
    
    // Handle 403 forbidden
    if (error.response?.status === 403) {
      return Promise.reject(new Error('Access denied'));
    }
    
    // Handle network errors
    if (!error.response) {
      console.error('Network error:', error.message);
      return Promise.reject(new Error('Network error - please check your connection'));
    }
    
    // Generic error handling with sanitization
    const errorMessage = error.response?.data?.detail || error.message;
    return Promise.reject(new Error(sanitizeHTML(errorMessage)));
  }
);

export default axiosInstance;
