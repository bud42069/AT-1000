/**
 * Drift Liquidation Map Scanner (TypeScript/SDK Version)
 * 
 * Scans Drift user accounts using getProgramAccounts and calculates
 * oracle-based liquidation estimates using Drift SDK v2
 * 
 * Publishes to Redis Stream: onchain:drift:liq_map_v2
 * Maintains Parquet snapshot: /app/storage/parquet/drift/liq_map_v2/latest.parquet
 * 
 * Reference: https://docs.drift.trade/liquidations/liquidations
 */

import { DriftClient, Wallet, BN, initialize, PerpPosition } from '@drift-labs/sdk';
import { Connection, Keypair, PublicKey } from '@solana/web3.js';
import Redis from 'ioredis';
import * as fs from 'fs';
import * as path from 'path';
import { solveLiqPx, validateEstimate, LiquidationEstimate } from './sdkHealth';

// Configuration
const HELIUS_RPC_URL = process.env.HELIUS_RPC_URL || 'https://mainnet.helius-rpc.com/?api-key=625e29ab-4bea-4694-b7d8-9fdda5871969';
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const REDIS_STREAM = 'onchain:drift:liq_map_v2';
const PARQUET_PATH = '/app/storage/parquet/drift/liq_map_v2/latest.parquet';
const SOL_PERP_MARKET_INDEX = 0;
const SCAN_INTERVAL = 3600000; // 1 hour in milliseconds

interface LiqMapEntry {
  account: string;
  marketIndex: number;
  positionSize: number;
  avgEntryPrice: number;
  estLiqPx: number;
  collateralUsd: number;
  leverage: number;
  health: number;
  distanceBps: number;
  updatedAt: number;
}

class DriftLiqMapScanner {
  private client: DriftClient | null = null;
  private connection: Connection;
  private redis: Redis;
  private running: boolean = false;
  private entriesBuffer: LiqMapEntry[] = [];

  constructor() {
    this.connection = new Connection(HELIUS_RPC_URL, 'confirmed');
    this.redis = new Redis(REDIS_URL);
  }

  /**
   * Initialize Drift client with read-only wallet
   */
  async initialize() {
    try {
      console.log('🚀 Initializing Drift Liq-Map Scanner (SDK v2)...');
      
      // Create read-only wallet (no private key needed for reading)
      const wallet = new Wallet(Keypair.generate());
      
      // Initialize Drift client
      this.client = new DriftClient({
        connection: this.connection,
        wallet,
        env: 'mainnet-beta',
      });

      await this.client.subscribe();
      
      console.log('✅ Drift client connected');
      console.log('Environment: mainnet-beta');
      console.log('Market: SOL-PERP (index 0)');
      
    } catch (error) {
      console.error('❌ Failed to initialize:', error);
      throw error;
    }
  }

  /**
   * Get current oracle price for SOL-PERP from Redis stream
   */
  async getOraclePrice(): Promise<number> {
    try {
      // Read latest price from Binance trades stream (proxy for oracle)
      const result = await this.redis.xrevrange('market:solusdt:trades', '+', '-', 'COUNT', 1);
      
      if (result && result.length > 0) {
        const [, fields] = result[0];
        const priceField = fields.find((f, i) => i % 2 === 0 && f === 'close');
        if (priceField) {
          const priceIndex = fields.indexOf(priceField) + 1;
          return parseFloat(fields[priceIndex]);
        }
      }
      
      // Fallback: try to get from Drift SDK
      if (this.client) {
        const market = this.client.getPerpMarketAccount(SOL_PERP_MARKET_INDEX);
        if (market && market.amm) {
          const oraclePrice = market.amm.historicalOracleData.lastOraclePrice;
          return oraclePrice.toNumber() / 1e10; // Adjust for precision
        }
      }
      
      console.warn('⚠️ No oracle price available');
      return 0;
      
    } catch (error) {
      console.error('Error fetching oracle price:', error);
      return 0;
    }
  }

  /**
   * Scan all user accounts and calculate liquidation estimates
   */
  async scanOnce() {
    if (!this.client) {
      console.error('❌ Client not initialized');
      return;
    }

    try {
      console.log('🔍 Starting liquidation map scan...');
      
      const startTime = Date.now();
      
      // Get oracle price
      const oraclePrice = await this.getOraclePrice();
      
      if (oraclePrice === 0) {
        console.warn('⚠️ Skipping scan - no oracle price');
        return;
      }
      
      console.log(`Oracle price: $${oraclePrice.toFixed(2)}`);
      
      // Get all users (Note: In production, you'd page through program accounts)
      // For now, we'll use a simpler approach with the SDK's user iteration
      const users = await this.client.getUsers();
      
      console.log(`Found ${users.length} user accounts`);
      
      let processedCount = 0;
      this.entriesBuffer = [];
      
      for (const user of users) {
        try {
          // Get user account data
          const userAccount = await user.getUserAccount();
          
          // Find SOL-PERP position
          const perpPositions = userAccount.perpPositions;
          const solPerpPosition = perpPositions.find(
            pos => pos.marketIndex === SOL_PERP_MARKET_INDEX && !pos.baseAssetAmount.eq(new BN(0))
          );
          
          if (!solPerpPosition) {
            continue; // No SOL-PERP position
          }
          
          // Calculate liquidation estimate using SDK health
          const estimate = await solveLiqPx(this.client, user, solPerpPosition, oraclePrice);
          
          if (estimate.estLiqPx === 0) {
            continue; // Invalid estimate
          }
          
          // Validate estimate (optional - for testing)
          const isValid = await validateEstimate(this.client, user, estimate);
          if (!isValid) {
            console.warn(`⚠️ Estimate validation failed for ${userAccount.authority.toBase58()}`);
          }
          
          // Get position details
          const positionSize = solPerpPosition.baseAssetAmount.toNumber() / 1e9; // BASE_PRECISION
          const quoteValue = solPerpPosition.quoteAssetAmount.toNumber() / 1e6; // PRICE_PRECISION
          const avgEntryPrice = Math.abs(quoteValue / positionSize);
          const collateral = userAccount.collateral.toNumber() / 1e6; // PRICE_PRECISION
          
          // Create entry
          const entry: LiqMapEntry = {
            account: userAccount.authority.toBase58(),
            marketIndex: SOL_PERP_MARKET_INDEX,
            positionSize,
            avgEntryPrice,
            estLiqPx: estimate.estLiqPx,
            collateralUsd: collateral,
            leverage: estimate.leverage,
            health: estimate.currentHealth,
            distanceBps: estimate.distanceBps,
            updatedAt: Date.now()
          };
          
          // Publish to Redis Stream
          await this.publishEntry(entry);
          
          this.entriesBuffer.push(entry);
          processedCount++;
          
        } catch (error) {
          console.error(`Error processing user:`, error);
        }
      }
      
      // Save to Parquet
      if (this.entriesBuffer.length > 0) {
        await this.saveParquet();
      }
      
      const duration = ((Date.now() - startTime) / 1000).toFixed(2);
      console.log(`✅ Scan complete: ${processedCount} positions processed in ${duration}s`);
      
    } catch (error) {
      console.error('❌ Scan error:', error);
    }
  }

  /**
   * Publish entry to Redis Stream
   */
  async publishEntry(entry: LiqMapEntry) {
    try {
      await this.redis.xadd(
        REDIS_STREAM,
        'MAXLEN', '~', '10000', // Keep last 10k entries
        '*',
        'account', entry.account,
        'market_index', entry.marketIndex.toString(),
        'position_size', entry.positionSize.toString(),
        'avg_entry_price', entry.avgEntryPrice.toString(),
        'est_liq_px', entry.estLiqPx.toString(),
        'collateral_usd', entry.collateralUsd.toString(),
        'leverage', entry.leverage.toString(),
        'health', entry.health.toString(),
        'distance_bps', entry.distanceBps.toString(),
        'updated_at', entry.updatedAt.toString()
      );
      
    } catch (error) {
      console.error('Error publishing to Redis:', error);
    }
  }

  /**
   * Save entries to Parquet file
   * Note: This is a simplified version - production would use proper Parquet library
   */
  async saveParquet() {
    try {
      // Ensure directory exists
      const dir = path.dirname(PARQUET_PATH);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      
      // For now, save as JSON (would use parquet library in production)
      const jsonPath = PARQUET_PATH.replace('.parquet', '.json');
      fs.writeFileSync(jsonPath, JSON.stringify(this.entriesBuffer, null, 2));
      
      console.log(`💾 Saved ${this.entriesBuffer.length} entries to ${jsonPath}`);
      
    } catch (error) {
      console.error('Error saving Parquet:', error);
    }
  }

  /**
   * Main run loop
   */
  async run() {
    this.running = true;
    
    await this.initialize();
    
    console.log(`⏰ Scan interval: ${SCAN_INTERVAL / 1000}s (${SCAN_INTERVAL / 3600000}h)`);
    
    while (this.running) {
      try {
        await this.scanOnce();
        
        // Wait for next scan
        await new Promise(resolve => setTimeout(resolve, SCAN_INTERVAL));
        
      } catch (error) {
        console.error('Error in main loop:', error);
        
        // Wait 1 minute before retrying on error
        await new Promise(resolve => setTimeout(resolve, 60000));
      }
    }
  }

  /**
   * Stop scanner
   */
  async stop() {
    console.log('🛑 Stopping scanner...');
    this.running = false;
    
    if (this.client) {
      await this.client.unsubscribe();
    }
    
    this.redis.disconnect();
    
    console.log('✅ Scanner stopped');
  }
}

// Main entry point
async function main() {
  const scanner = new DriftLiqMapScanner();
  
  // Handle shutdown signals
  process.on('SIGINT', async () => {
    console.log('\n⚠️ Received SIGINT');
    await scanner.stop();
    process.exit(0);
  });
  
  process.on('SIGTERM', async () => {
    console.log('\n⚠️ Received SIGTERM');
    await scanner.stop();
    process.exit(0);
  });
  
  try {
    await scanner.run();
  } catch (error) {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}

export { DriftLiqMapScanner, LiqMapEntry };
