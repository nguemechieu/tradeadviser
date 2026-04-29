import axios from "axios";
import axiosRetry from "axios-retry";

// if using React context (only usable in a hook!)

const BASE_URL = "http://localhost:8080";

// 🔓 Public instance (no auth)
const axiosPublic = axios.create({
    baseURL: BASE_URL,
});

// 🔐 Private instance (with credentials)
const axiosPrivate = axios.create({
    baseURL: BASE_URL,
    withCredentials: true,
});

// 🔁 Retry on network or 5xx
axiosRetry(axiosPrivate, {
    retries: 3,
    retryDelay: axiosRetry.exponentialDelay,
    retryCondition: (error: { response: { status: number; }; }) => {
        if (!error.response) return true;
        return [500, 502, 503, 504].includes(error.response.status);
    },
});

// 🔑 Add access token from localStorage
axiosPrivate.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem("accessToken");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// // 🔄 Refresh token on 401 and retry original request
// axiosPrivate.interceptors.response.use(
//     (response) => response,
//     async (error) => {
//         const originalRequest = error.config;
//
//         if (error.response?.status === 401 && !originalRequest._retry) {
//             originalRequest._retry = true;
//             try {
//                 const newToken = await refreshAccessToken();
//                 if (newToken) {
//                     localStorage.setItem("accessToken", newToken);
//                     originalRequest.headers.Authorization = `Bearer ${newToken}`;
//                     return axiosPrivate(originalRequest);
//                 }
//             } catch (err) {
//                 console.error("Token refresh failed:", err);
//             }
//         }
//
//         return Promise.reject(error);
//     }
// );

// // 🔄 Refresh token on 401 and retry original request
// axiosPrivate.interceptors.response.use(
//     (response) => response,
//     async (error) => {
//         const originalRequest = error.config;
//
//         if (error.response?.status === 401 && !originalRequest._retry) {
//             originalRequest._retry = true;
//             try {
//                 const newToken = await refreshAccessToken();
//                 if (newToken) {
//                     localStorage.setItem("accessToken", newToken);
//                     originalRequest.headers.Authorization = `Bearer ${newToken}`;
//                     return axiosPrivate(originalRequest);
//                 }
//             } catch (err) {
//                 console.error("Token refresh failed:", err);
//             }
//         }
//
//         return Promise.reject(error);
//     }
// );
export { axiosPublic, axiosPrivate };
