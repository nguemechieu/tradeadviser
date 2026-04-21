import axios, { AxiosInstance } from 'axios';

// Determine base URL based on environment
const getBaseURL = (): string => {
  // In production (Docker), backend is on same host but port 8000
  // In development, backend is on localhost:8000
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  // For Docker/production, use relative path which will be proxied by Nginx
  // or use the same host with different port
  return window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : `http://${window.location.hostname}:8000`;
};

const BASE_URL = getBaseURL();

const axiosInstance: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  }
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
