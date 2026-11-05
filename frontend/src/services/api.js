import axios from 'axios';

// Override with VITE_API_URL in frontend/.env when the backend runs elsewhere.
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  // ngrok's free plan answers browser-like requests with a warning page unless
  // this header is present. Harmless for every other backend address.
  headers: { 'ngrok-skip-browser-warning': 'true' },
});

// Attach token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// The backend stores and returns UTC timestamps WITHOUT a timezone designator
// (e.g. "2026-11-04T10:00:00"). Browsers parse such strings as LOCAL time,
// which shifted every deadline, countdown and "x minutes ago" by the user's
// UTC offset. Appending "Z" makes `new Date()` treat them as UTC everywhere.
const NAIVE_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

function normalizeDates(value) {
  if (typeof value === 'string') {
    return NAIVE_ISO.test(value) ? `${value}Z` : value;
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) value[i] = normalizeDates(value[i]);
    return value;
  }
  if (value && typeof value === 'object' && value.constructor === Object) {
    for (const key of Object.keys(value)) value[key] = normalizeDates(value[key]);
    return value;
  }
  return value;
}

// Handle common errors
api.interceptors.response.use(
  (response) => {
    if (response && response.data && typeof response.data === 'object') {
      normalizeDates(response.data);
    }
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || '';
    // A wrong password is also a 401. Redirecting on it reloaded the login
    // page and wiped the "Incorrect email or password" message.
    const isAuthCall = /\/auth\/(login|register)\/?$/.test(url);
    if (status === 401 && !isAuthCall) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      localStorage.removeItem('userId');
      localStorage.removeItem('userName');
      // Respect the deployment sub-path (BASE_URL is '/' locally, '/<repo>/' on GitHub Pages).
      window.location.href = `${import.meta.env.BASE_URL.replace(/\/?$/, '/')}login`;
    }
    // Sanitize role-mismatch 403s so the raw "Teacher role required" message
    // never reaches the UI for the wrong role. Components can still see the
    // status code but the detail will be a generic placeholder.
    const detail = error.response?.data?.detail;
    if (
      status === 403 &&
      typeof detail === 'string' &&
      /role required/i.test(detail)
    ) {
      if (error.response.data) error.response.data.detail = null;
    }
    return Promise.reject(error);
  }
);

export default api;
