import axios, { AxiosInstance } from 'axios';

const BASE_URL = 'http://localhost:8000';

const axiosInstance: AxiosInstance = axios.create({
    baseURL: BASE_URL
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
