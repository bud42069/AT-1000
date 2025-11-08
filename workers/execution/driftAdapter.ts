/**
 * Drift Protocol Adapter - Production Implementation
 * 
 * Handles all Drift-specific operations:
 * - Delegation (set/revoke)
 * - Post-only order placement
 * - Stop-loss and take-profit ladder management
 * - Order modification (cancel/replace)
 * - Position management
 */

import { DriftClient, BN, Wallet, User, OrderType, PositionDirection, BASE_PRECISION, PRICE_PRECISION } from '@drift-labs/sdk';
import { Connection, PublicKey, Keypair, Transaction } from '@solana/web3.js';

export interface OrderIntent {
  side: 'long' | 'short';
  limitPx: number;
  size: number;
  slPx: number;
  tpPx: { p1: number; p2: number; p3: number };
  leverage: number;
  notes?: string;
}

export interface OrderResult {
  orderId: string;
  txSig: string;
  timestamp: number;
}

export class DriftAdapter {
  private client: DriftClient;
  private user: User;
  private connection: Connection;
  private marketIndex: number = 0; // SOL-PERP market index

  constructor(client: DriftClient, user: User, connection: Connection) {
    this.client = client;
    this.user = user;
    this.connection = connection;
  }

  /**
   * Factory method to create and initialize DriftAdapter
   */
  static async connect(
    rpcUrl: string,
    env: 'devnet' | 'mainnet-beta',
    wallet: Wallet
  ): Promise<DriftAdapter> {
    const connection = new Connection(rpcUrl, 'confirmed');
    
    const client = new DriftClient({
      connection,
      wallet,
      env,
    });

    await client.subscribe();
    
    // Get user account
    const user = client.getUser();
    
    console.log('✅ DriftAdapter connected');
    console.log('User:', wallet.publicKey.toBase58());
    console.log('Env:', env);

    return new DriftAdapter(client, user, connection);
  }

  /**
   * DoD-1: Set delegate authority for automated trading
   * @returns Transaction signature
   */
  async setDelegate(delegatePublicKey: string): Promise<string> {
    try {
      console.log('🔐 Setting delegate:', delegatePublicKey);
      
      const delegatePk = new PublicKey(delegatePublicKey);
      
      const tx = await this.client.updateUserDelegate(
        delegatePk,
        0 // subAccountId
      );

      console.log('✅ Delegate set! TX:', tx);
      
      // Wait for confirmation
      await this.connection.confirmTransaction(tx, 'confirmed');
      
      return tx;
    } catch (error) {
      console.error('❌ Failed to set delegate:', error);
      throw new Error(`Delegate setup failed: ${error.message}`);
    }
  }

  /**
   * DoD-1: Revoke delegate authority
   * @returns Transaction signature
   */
  async revokeDelegate(): Promise<string> {
    try {
      console.log('🔓 Revoking delegate...');
      
      // Set delegate to null/zero address to revoke
      const tx = await this.client.updateUserDelegate(
        PublicKey.default, // null delegate
        0 // subAccountId
      );

      console.log('✅ Delegate revoked! TX:', tx);
      
      await this.connection.confirmTransaction(tx, 'confirmed');
      
      return tx;
    } catch (error) {
      console.error('❌ Failed to revoke delegate:', error);
      throw new Error(`Delegate revocation failed: ${error.message}`);
    }
  }

  /**
   * DoD-2: Place post-only limit order
   * @returns Order ID and transaction signature
   */
  async placePostOnly(intent: OrderIntent): Promise<OrderResult> {
    try {
      console.log('📊 Placing post-only order:', intent);

      // Convert to Drift SDK units
      const direction = intent.side === 'long' ? PositionDirection.LONG : PositionDirection.SHORT;
      const baseAssetAmount = new BN(Math.floor(intent.size * BASE_PRECISION.toNumber()));
      const price = new BN(Math.floor(intent.limitPx * PRICE_PRECISION.toNumber()));

      const orderParams = {
        orderType: OrderType.LIMIT,
        marketIndex: this.marketIndex,
        direction,
        baseAssetAmount,
        price,
        postOnly: true,
        reduceOnly: false,
        userOrderId: Date.now(), // Use timestamp as order ID
      };

      const tx = await this.client.placePerpOrder(orderParams);

      console.log('✅ Order placed! TX:', tx);
      
      await this.connection.confirmTransaction(tx, 'confirmed');

      return {
        orderId: orderParams.userOrderId.toString(),
        txSig: tx,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('❌ Failed to place order:', error);
      throw new Error(`Order placement failed: ${error.message}`);
    }
  }

  /**
   * DoD-2: Place stop-loss and take-profit ladder
   * @param orderId Original order ID
   * @param slPx Stop-loss price
   * @param tps Take-profit prices [p1, p2, p3]
   */
  async placeStops(
    orderId: string,
    slPx: number,
    tps: [number, number, number],
    totalSize: number,
    side: 'long' | 'short'
  ): Promise<void> {
    try {
      console.log('🎯 Placing SL/TP ladder for order:', orderId);

      const direction = side === 'long' ? PositionDirection.SHORT : PositionDirection.LONG; // Opposite for closing

      // Place stop-loss (full size)
      const slPrice = new BN(Math.floor(slPx * PRICE_PRECISION.toNumber()));
      const slSize = new BN(Math.floor(totalSize * BASE_PRECISION.toNumber()));

      await this.client.placePerpOrder({
        orderType: OrderType.TRIGGER_MARKET,
        marketIndex: this.marketIndex,
        direction,
        baseAssetAmount: slSize,
        triggerPrice: slPrice,
        triggerCondition: side === 'long' ? 'below' : 'above',
        reduceOnly: true,
      });

      // Place take-profit ladder: 50% @ TP1, 30% @ TP2, 20% @ TP3
      const tpSizes = [
        Math.floor(totalSize * 0.5),
        Math.floor(totalSize * 0.3),
        Math.floor(totalSize * 0.2),
      ];

      for (let i = 0; i < 3; i++) {
        const tpPrice = new BN(Math.floor(tps[i] * PRICE_PRECISION.toNumber()));
        const tpSize = new BN(Math.floor(tpSizes[i] * BASE_PRECISION.toNumber()));

        await this.client.placePerpOrder({
          orderType: OrderType.TRIGGER_LIMIT,
          marketIndex: this.marketIndex,
          direction,
          baseAssetAmount: tpSize,
          price: tpPrice,
          triggerPrice: tpPrice,
          triggerCondition: side === 'long' ? 'above' : 'below',
          reduceOnly: true,
        });
      }

      console.log('✅ SL/TP ladder placed');
    } catch (error) {
      console.error('❌ Failed to place stops:', error);
      throw new Error(`Stop placement failed: ${error.message}`);
    }
  }

  /**
   * DoD-2: Cancel and replace order with new price
   * @param orderId Order ID to cancel
   * @param newPx New limit price
   */
  async cancelAndReplace(orderId: string, newPx: number, intent: OrderIntent): Promise<OrderResult> {
    try {
      console.log('🔄 Cancel and replace order:', orderId, '→', newPx);

      // Cancel existing order
      const userOrderId = parseInt(orderId);
      await this.client.cancelOrder(userOrderId);

      // Place new order with updated price
      const updatedIntent = { ...intent, limitPx: newPx };
      return await this.placePostOnly(updatedIntent);
    } catch (error) {
      console.error('❌ Failed to cancel/replace:', error);
      throw new Error(`Cancel/replace failed: ${error.message}`);
    }
  }

  /**
   * DoD-2: Close position at market with slippage protection
   * @param symbol Market symbol (default: SOL-PERP)
   * @param slipBpsCap Maximum slippage in basis points
   */
  async closePositionMarket(symbol?: string, slipBpsCap: number = 50): Promise<string> {
    try {
      console.log('🚪 Closing position at market');

      // Get current position
      const position = this.user.getPerpPosition(this.marketIndex);
      if (!position || position.baseAssetAmount.isZero()) {
        throw new Error('No open position to close');
      }

      const direction = position.baseAssetAmount.isNeg()
        ? PositionDirection.LONG
        : PositionDirection.SHORT;

      const size = position.baseAssetAmount.abs();

      // Calculate slippage-protected price
      const markPrice = this.user.getMarketAccount(this.marketIndex).amm.lastMarkPriceTwap;
      const slippageFactor = slipBpsCap / 10000;
      const limitPrice = direction === PositionDirection.LONG
        ? markPrice.muln(1 + slippageFactor)
        : markPrice.muln(1 - slippageFactor);

      const tx = await this.client.placePerpOrder({
        orderType: OrderType.LIMIT,
        marketIndex: this.marketIndex,
        direction,
        baseAssetAmount: size,
        price: limitPrice,
        reduceOnly: true,
      });

      console.log('✅ Position closed! TX:', tx);
      
      await this.connection.confirmTransaction(tx, 'confirmed');
      
      return tx;
    } catch (error) {
      console.error('❌ Failed to close position:', error);
      throw new Error(`Position close failed: ${error.message}`);
    }
  }

  /**
   * Get current position for a market
   */
  getPosition(marketIndex: number = 0) {
    return this.user.getPerpPosition(marketIndex);
  }

  /**
   * Get all open orders
   */
  getOpenOrders() {
    return this.user.getOpenOrders();
  }

  /**
   * Cancel all open orders
   */
  async cancelAllOrders(): Promise<string[]> {
    try {
      console.log('🛑 Cancelling all orders...');
      
      const openOrders = this.getOpenOrders();
      const txSigs: string[] = [];

      for (const order of openOrders) {
        const tx = await this.client.cancelOrder(order.orderId);
        txSigs.push(tx);
      }

      console.log(`✅ Cancelled ${txSigs.length} orders`);
      
      return txSigs;
    } catch (error) {
      console.error('❌ Failed to cancel all orders:', error);
      throw new Error(`Cancel all failed: ${error.message}`);
    }
  }

  /**
   * Move stop-loss to breakeven + fees
   */
  async moveStopToBreakeven(entryPrice: number, fees: number): Promise<void> {
    try {
      console.log('⚖️ Moving SL to breakeven + fees');

      // Cancel existing SL
      const openOrders = this.getOpenOrders();
      const slOrder = openOrders.find(o => o.orderType === OrderType.TRIGGER_MARKET);
      
      if (slOrder) {
        await this.client.cancelOrder(slOrder.orderId);
      }

      // Place new SL at BE + fees
      const position = this.getPosition(this.marketIndex);
      const side = position.baseAssetAmount.isNeg() ? 'short' : 'long';
      const bePx = side === 'long' ? entryPrice + fees : entryPrice - fees;

      const direction = side === 'long' ? PositionDirection.SHORT : PositionDirection.LONG;
      const slPrice = new BN(Math.floor(bePx * PRICE_PRECISION.toNumber()));

      await this.client.placePerpOrder({
        orderType: OrderType.TRIGGER_MARKET,
        marketIndex: this.marketIndex,
        direction,
        baseAssetAmount: position.baseAssetAmount.abs(),
        triggerPrice: slPrice,
        triggerCondition: side === 'long' ? 'below' : 'above',
        reduceOnly: true,
      });

      console.log('✅ SL moved to BE + fees:', bePx);
    } catch (error) {
      console.error('❌ Failed to move SL to BE:', error);
      throw new Error(`Move SL to BE failed: ${error.message}`);
    }
  }

  /**
   * Cleanup and unsubscribe
   */
  async disconnect(): Promise<void> {
    await this.client.unsubscribe();
    console.log('👋 DriftAdapter disconnected');
  }
}

export default DriftAdapter;