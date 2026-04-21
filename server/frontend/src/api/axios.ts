import axios, { AxiosInstance } from 'axios';

// Determine base URL based on environment
const getBaseURL = (): string => {
  // In Vite development (port 5173), use Vite proxy to localhost:8000
  if (typeof window !== 'undefined' && window.location.port === '5173') {
    return 'http://localhost:8000';
  }
  // In Docker or production, use relative paths
  // The frontend (Nginx) will proxy these to the backend
  // This works because:
  // - Browser on localhost:3000 makes request to /auth/login
  // - Nginx proxies it to http://backend:8000/auth/login (same container network)
  // - or in production, the same host with proper routing
  return '';
};

const BASE_URL = getBaseURL();

const axiosInstance: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
});

export const axiosPrivate: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  withCredentials: true
});

export default axiosInstance;
