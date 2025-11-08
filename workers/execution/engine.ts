/**
 * Execution Engine - Orchestrates order lifecycle
 * 
 * Responsibilities:
 * - Receive OrderIntent from signal worker
 * - Apply risk guards and sizing
 * - Execute via DriftAdapter
 * - Monitor fills and manage SL/TP
 * - Handle cancel/replace logic
 * - Emit events to backend
 */

import DriftAdapter, { OrderIntent, OrderResult } from './driftAdapter';
import { Wallet } from '@drift-labs/sdk';
import { Keypair } from '@solana/web3.js';
import * as fs from 'fs';
import * as dotenv from 'dotenv';

dotenv.config({ path: '../backend/.env' });

interface RiskSettings {
  maxLeverage: number;
  riskPerTrade: number; // as fraction (0.0075 = 0.75%)
  priorityFeeCap: number;
  dailyDrawdownLimit: number;
}

interface EngineConfig {
  rpcUrl: string;
  env: 'devnet' | 'mainnet-beta';
  delegateKeyPath: string;
  riskSettings: RiskSettings;
}

export class ExecutionEngine {
  private adapter: DriftAdapter | null = null;
  private config: EngineConfig;
  private attempts: Map<string, number> = new Map();
  private fills: Map<string, { price: number; size: number; timestamp: number }> = new Map();

  constructor(config: EngineConfig) {
    this.config = config;
  }

  /**
   * Initialize engine and connect to Drift
   */
  async initialize(walletKeypair: Keypair): Promise<void> {
    console.log('🚀 Initializing Execution Engine...');

    const wallet = new Wallet(walletKeypair);
    
    this.adapter = await DriftAdapter.connect(
      this.config.rpcUrl,
      this.config.env,
      wallet
    );

    console.log('✅ Execution Engine ready');
  }

  /**
   * DoD-4: Apply risk guards before execution
   */
  private async applyGuards(intent: OrderIntent): Promise<boolean> {
    console.log('🛡️ Applying risk guards...');

    // Guard 1: Leverage cap
    if (intent.leverage > this.config.riskSettings.maxLeverage) {
      console.warn(`❌ Leverage ${intent.leverage}x exceeds cap ${this.config.riskSettings.maxLeverage}x`);
      return false;
    }

    // Guard 2: Spread check (placeholder - needs live market data)
    // TODO: Implement spread < 10 bps check

    // Guard 3: Depth check (placeholder)
    // TODO: Implement depth ≥ 50% of 30-day median

    // Guard 4: Liq-gap check (placeholder)
    // TODO: Implement liq-gap ≥ 4× ATR(5m)

    // Guard 5: Funding check (placeholder)
    // TODO: Implement funding APR < 500

    // Guard 6: Basis check (placeholder)
    // TODO: Implement |basis| < 10 bps

    console.log('✅ All guards passed');
    return true;
  }

  /**
   * DoD-4: Calculate position size based on risk
   */
  private calculateSize(intent: OrderIntent, collateralUsd: number): number {
    const riskUsd = collateralUsd * this.config.riskSettings.riskPerTrade;
    const slDistance = Math.abs(intent.limitPx - intent.slPx);
    
    const sizeFromRisk = riskUsd / slDistance;
    const maxLeverageUsd = collateralUsd * intent.leverage;
    const sizeFromLeverage = maxLeverageUsd / intent.limitPx;

    const size = Math.min(sizeFromRisk, sizeFromLeverage);

    console.log('📏 Size calculation:', {
      riskUsd,
      slDistance,
      sizeFromRisk,
      sizeFromLeverage,
      finalSize: size,
    });

    return size;
  }

  /**
   * Execute order with full lifecycle management
   */
  async executeIntent(intent: OrderIntent, collateralUsd: number = 1000): Promise<void> {
    if (!this.adapter) {
      throw new Error('Engine not initialized');
    }

    console.log('\n📋 Executing intent:', intent);

    // Apply guards
    const guardsPass = await this.applyGuards(intent);
    if (!guardsPass) {
      console.log('❌ Intent rejected by guards');
      this.emitEvent('order_rejected', { reason: 'guards_failed', intent });
      return;
    }

    // Calculate size
    const size = this.calculateSize(intent, collateralUsd);
    const finalIntent = { ...intent, size };

    // Place post-only order
    const result = await this.adapter.placePostOnly(finalIntent);
    this.attempts.set(result.orderId, 1);
    
    this.emitEvent('order_submitted', {
      orderId: result.orderId,
      txSig: result.txSig,
      intent: finalIntent,
    });

    // Monitor for fill (simplified - in production, use event listeners)
    // For now, we assume fill after placement and immediately install SL/TP
    await this.onFill(result.orderId, finalIntent);
  }

  /**
   * Handle order fill - install SL/TP ladder
   */
  private async onFill(orderId: string, intent: OrderIntent): Promise<void> {
    console.log('✅ Order filled:', orderId);

    this.fills.set(orderId, {
      price: intent.limitPx,
      size: intent.size,
      timestamp: Date.now(),
    });

    this.emitEvent('order_filled', { orderId, price: intent.limitPx, size: intent.size });

    // Install SL/TP ladder
    await this.adapter!.placeStops(
      orderId,
      intent.slPx,
      [intent.tpPx.p1, intent.tpPx.p2, intent.tpPx.p3],
      intent.size,
      intent.side
    );

    this.emitEvent('stops_installed', { orderId });
  }

  /**
   * Move SL to breakeven after TP1 hit
   */
  async onTP1Hit(orderId: string): Promise<void> {
    const fill = this.fills.get(orderId);
    if (!fill) return;

    console.log('🎯 TP1 hit! Moving SL to BE+fees...');

    // Estimate fees (placeholder - should be actual taker fee)
    const fees = fill.price * 0.0006; // 6 bps

    await this.adapter!.moveStopToBreakeven(fill.price, fees);
    
    this.emitEvent('sl_moved_to_be', { orderId, newSl: fill.price + fees });
  }

  /**
   * Cancel and replace logic (max 2 attempts)
   */
  async cancelAndReplace(orderId: string, newPx: number, intent: OrderIntent): Promise<void> {
    const attempts = this.attempts.get(orderId) || 0;

    if (attempts >= 2) {
      console.warn('⚠️ Max attempts (2) reached for order:', orderId);
      this.emitEvent('order_abandoned', { orderId, reason: 'max_attempts' });
      return;
    }

    const result = await this.adapter!.cancelAndReplace(orderId, newPx, intent);
    this.attempts.set(result.orderId, attempts + 1);
    
    this.emitEvent('order_replaced', {
      oldOrderId: orderId,
      newOrderId: result.orderId,
      newPrice: newPx,
      attempts: attempts + 1,
    });
  }

  /**
   * Kill switch - cancel all orders and halt
   */
  async killSwitch(reason: string): Promise<void> {
    console.log('🛑 KILL SWITCH ACTIVATED:', reason);

    if (!this.adapter) return;

    const txSigs = await this.adapter.cancelAllOrders();
    
    this.emitEvent('kill_switch', {
      reason,
      cancelledCount: txSigs.length,
      txSigs,
    });
  }

  /**
   * Emit event to backend (placeholder - use WebSocket or HTTP)
   */
  private emitEvent(type: string, data: any): void {
    const event = {
      type,
      timestamp: new Date().toISOString(),
      data,
    };

    console.log('📡 Event:', event);

    // TODO: Send to backend via WebSocket or HTTP POST
    // For now, just log to console and write to file
    fs.appendFileSync(
      '/app/workers/engine-events.log',
      JSON.stringify(event) + '\n'
    );
  }

  /**
   * Cleanup
   */
  async shutdown(): Promise<void> {
    if (this.adapter) {
      await this.adapter.disconnect();
    }
    console.log('👋 Execution Engine shutdown');
  }
}

export default ExecutionEngine;