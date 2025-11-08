/**
 * Drift Worker Service
 * HTTP service that wraps DriftAdapter for backend API calls
 * Runs on port 8002
 * 
 * Security: Uses managed signer from environment variable (not generated keypair)
 */

import express from 'express';
import { DriftAdapter } from './execution/driftAdapter';
import { Wallet } from '@drift-labs/sdk';
import { Keypair } from '@solana/web3.js';
import * as bs58 from 'bs58';

const app = express();
app.use(express.json());

const PORT = 8002;
const HELIUS_RPC_URL = process.env.HELIUS_RPC_URL || 'https://mainnet.helius-rpc.com/?api-key=625e29ab-4bea-4694-b7d8-9fdda5871969';
const DELEGATE_PRIVATE_KEY = process.env.DELEGATE_PRIVATE_KEY; // Base58-encoded private key

// Global adapter instance (initialized on first request)
let adapter: DriftAdapter | null = null;

/**
 * Load managed signer from environment
 * Fails fast if key not provided (security)
 */
function loadManagedSigner(): Keypair {
  if (!DELEGATE_PRIVATE_KEY) {
    console.error('❌ DELEGATE_PRIVATE_KEY environment variable not set');
    console.error('💡 Generate a key: solana-keygen new --no-outfile');
    console.error('💡 Set env: export DELEGATE_PRIVATE_KEY=<base58_private_key>');
    throw new Error('DELEGATE_PRIVATE_KEY not configured');
  }
  
  try {
    // Decode base58 private key
    const secretKey = bs58.decode(DELEGATE_PRIVATE_KEY);
    const keypair = Keypair.fromSecretKey(secretKey);
    
    console.log('✅ Loaded managed signer:', keypair.publicKey.toBase58());
    console.log('🔐 Signer fingerprint:', keypair.publicKey.toBase58().slice(0, 8));
    
    return keypair;
    
  } catch (error) {
    console.error('❌ Failed to load DELEGATE_PRIVATE_KEY:', error);
    throw new Error('Invalid DELEGATE_PRIVATE_KEY format (expected base58)');
  }
}

/**
 * Initialize adapter for a specific wallet
 */
async function getAdapter(walletPubkey: string): Promise<DriftAdapter> {
  if (!adapter) {
    // Load managed signer from environment (NOT generated)
    const delegateKeypair = loadManagedSigner();
    
    // Create wallet wrapper
    const wallet = new Wallet(delegateKeypair);
    
    adapter = await DriftAdapter.connect(
      HELIUS_RPC_URL,
      'mainnet-beta',
      wallet
    );
  }
  
  return adapter;
}

/**
 * POST /delegate/set
 * Set delegate authority for user
 */
app.post('/delegate/set', async (req, res) => {
  try {
    const { wallet, delegate_pubkey, sub_account_id } = req.body;
    
    if (!wallet || !delegate_pubkey) {
      return res.status(400).json({ error: 'Missing required fields' });
    }
    
    console.log(`Setting delegate for ${wallet} → ${delegate_pubkey}`);
    
    const driftAdapter = await getAdapter(wallet);
    
    const txSignature = await driftAdapter.setDelegate(delegate_pubkey);
    
    res.json({
      tx_signature: txSignature,
      delegate_pubkey,
      status: 'success'
    });
    
  } catch (error) {
    console.error('Set delegate error:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /delegate/revoke
 * Revoke delegate authority for user
 */
app.post('/delegate/revoke', async (req, res) => {
  try {
    const { wallet, sub_account_id } = req.body;
    
    if (!wallet) {
      return res.status(400).json({ error: 'Missing wallet' });
    }
    
    console.log(`Revoking delegate for ${wallet}`);
    
    const driftAdapter = await getAdapter(wallet);
    
    const txSignature = await driftAdapter.revokeDelegate();
    
    res.json({
      tx_signature: txSignature,
      status: 'success'
    });
    
  } catch (error) {
    console.error('Revoke delegate error:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /delegate/status
 * Get current delegation status
 */
app.get('/delegate/status', async (req, res) => {
  try {
    const { wallet } = req.query;
    
    if (!wallet) {
      return res.status(400).json({ error: 'Missing wallet parameter' });
    }
    
    const driftAdapter = await getAdapter(wallet as string);
    
    // TODO: Query on-chain account to check current delegate
    // For now, return placeholder
    res.json({
      delegate_pubkey: null,
      status: 'inactive'
    });
    
  } catch (error) {
    console.error('Status check error:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Health check
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'drift-worker',
    timestamp: Date.now()
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`✅ Drift Worker Service running on port ${PORT}`);
  console.log(`RPC: ${HELIUS_RPC_URL}`);
});
