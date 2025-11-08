/**
 * API Client for Backend Communication
 */
import { authHeaders } from './siws';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Fetch with auth headers
 */
async function fetchWithAuth(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...options.headers,
  };

  const response = await fetch(`${BACKEND_URL}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get risk guards
 */
export async function getGuards() {
  return fetchWithAuth('/api/engine/guards');
}

/**
 * Place order
 */
export async function placeOrder(orderIntent) {
  return fetchWithAuth('/api/engine/orders', {
    method: 'POST',
    body: JSON.stringify(orderIntent),
  });
}

/**
 * Cancel order
 */
export async function cancelOrder(orderId) {
  return fetchWithAuth('/api/engine/cancel', {
    method: 'POST',
    body: JSON.stringify({ orderId }),
  });
}

/**
 * Emergency kill switch
 */
export async function killSwitch(reason) {
  return fetchWithAuth('/api/engine/kill', {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/**
 * Get activity log
 */
export async function getActivity() {
  return fetchWithAuth('/api/engine/activity');
}

/**
 * Get user settings
 */
export async function getSettings(userId) {
  return fetchWithAuth(`/api/settings?user_id=${userId}`);
}

/**
 * Update user settings
 */
export async function updateSettings(settings) {
  return fetchWithAuth('/api/settings/', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

/**
 * Ping backend
 */
export async function ping() {
  return fetchWithAuth('/api/engine/ping');
}