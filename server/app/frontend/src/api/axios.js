import axios from 'axios';

// Determine API base URL
// In browser: use /api (which proxies to backend via Vite)
// Vite environment variables are injected at build time
// VITE_API_URL from docker-compose.yml is used if set, otherwise fallback to /api
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Public axios instance for unauthenticated requests
const baseAxios = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Private axios instance for authenticated requests
export const axiosPrivate = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  withCredentials: true
});

// Add request interceptor to attach auth token
axiosPrivate.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('tradeadviser-token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle 401
axiosPrivate.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tradeadviser-token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default baseAxios;