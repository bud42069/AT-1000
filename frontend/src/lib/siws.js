/**
 * Sign-In With Solana (SIWS) Client Library
 */
import nacl from 'tweetnacl';
import { encodeUTF8, decodeBase64 } from 'tweetnacl-util';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Perform SIWS login flow
 * @param {Object} wallet - Solana wallet adapter instance
 * @returns {Promise<{token: string, wallet: string}>}
 */
export async function siwsLogin(wallet) {
  if (!wallet?.publicKey || !wallet.signMessage) {
    throw new Error('Wallet not ready');
  }

  const pk = wallet.publicKey.toBase58();

  // Step 1: Get challenge from backend
  const chal = await fetch(`${BACKEND_URL}/auth/siws/challenge`)
    .then(r => {
      if (!r.ok) throw new Error('Failed to get challenge');
      return r.json();
    });

  console.log('✅ Challenge received:', chal);

  // Step 2: Sign challenge message
  const msg = new TextEncoder().encode(chal.message);
  const sig = await wallet.signMessage(msg);

  console.log('✅ Message signed');

  // Step 3: Verify signature and get JWT
  const body = {
    publicKey: pk,
    message: chal.message,
    signature: Buffer.from(sig).toString('base64'), // Use base64 for JSON transport
    nonce: chal.nonce,
  };

  const res = await fetch(`${BACKEND_URL}/auth/siws/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => {
    if (!r.ok) throw new Error('Signature verification failed');
    return r.json();
  });

  console.log('✅ SIWS verification successful');

  // Store token
  localStorage.setItem('at_token', res.token);
  localStorage.setItem('at_wallet', res.wallet);

  return res;
}

/**
 * Get authorization headers for API calls
 * @returns {Object} Headers object with Authorization if token exists
 */
export function authHeaders() {
  const token = localStorage.getItem('at_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export function isAuthenticated() {
  const token = localStorage.getItem('at_token');
  if (!token) return false;

  try {
    // Basic JWT expiry check (not secure, but good enough for client-side)
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

/**
 * Logout and clear stored credentials
 */
export function logout() {
  localStorage.removeItem('at_token');
  localStorage.removeItem('at_wallet');
  console.log('✅ Logged out');
}

/**
 * Get stored wallet address
 * @returns {string|null}
 */
export function getStoredWallet() {
  return localStorage.getItem('at_wallet');
}