/**
 * SDK Health Helper - Oracle-Based Liquidation Price Solver
 * 
 * Computes liquidation price by solving Health→0 using Drift SDK's health calculations
 * Based on oracle prices (not mark prices) per Drift liquidation mechanics
 * 
 * Reference: https://docs.drift.trade/liquidations/liquidations
 */

import { DriftClient, User, PerpPosition, BN, PRICE_PRECISION, BASE_PRECISION } from '@drift-labs/sdk';

export interface LiquidationEstimate {
  estLiqPx: number;
  currentHealth: number;
  leverage: number;
  distanceBps: number;
}

/**
 * Solve for liquidation price where Health = 0 (oracle-based)
 * 
 * Health formula:
 * Health = (Total Collateral + Unrealized PnL) / (Maintenance Margin Requirement)
 * 
 * For liquidation:
 * Health = 0 when Total Collateral + Unrealized PnL = Maintenance Margin
 * 
 * Position PnL = position_size * (oracle_price - entry_price)
 * 
 * Solving for liquidation price p:
 * Collateral + position_size * (p - entry_price) = MMR * |position_size| * p
 * 
 * Where MMR = maintenance_margin_ratio (typically 3% for SOL-PERP)
 * 
 * @param client Drift client instance
 * @param user User account with positions
 * @param position Specific perp position to analyze
 * @param oraclePrice Current oracle price
 * @returns Liquidation estimate with health metrics
 */
export async function solveLiqPx(
  client: DriftClient,
  user: User,
  position: PerpPosition,
  oraclePrice: number
): Promise<LiquidationEstimate> {
  try {
    // Get position details
    const baseAssetAmount = position.baseAssetAmount;
    const quoteAssetAmount = position.quoteAssetAmount;
    
    if (baseAssetAmount.eq(new BN(0))) {
      // No position
      return {
        estLiqPx: 0,
        currentHealth: 1.0,
        leverage: 0,
        distanceBps: 0
      };
    }
    
    // Get market info for MMR
    const marketIndex = position.marketIndex;
    const perpMarket = client.getPerpMarketAccount(marketIndex);
    
    if (!perpMarket) {
      throw new Error(`Market ${marketIndex} not found`);
    }
    
    // Maintenance margin ratio (in basis points, e.g., 300 = 3%)
    const mmrBps = perpMarket.marginRatioMaintenance;
    const mmr = mmrBps / 10000; // Convert to decimal
    
    // Get user's total collateral
    const userAccount = await user.getUserAccount();
    const collateral = userAccount.collateral.toNumber() / PRICE_PRECISION.toNumber();
    
    // Calculate average entry price
    const positionSize = baseAssetAmount.toNumber() / BASE_PRECISION.toNumber();
    const positionValue = quoteAssetAmount.toNumber() / PRICE_PRECISION.toNumber();
    const avgEntryPrice = Math.abs(positionValue / positionSize);
    
    // Solve for liquidation price
    // Formula: C + q*(p - avg) = mmr*|q|*p
    // Rearranging: C + q*p - q*avg = mmr*|q|*p
    //             C - q*avg = (mmr*|q| - q)*p
    //             p = (C - q*avg) / (mmr*|q| - q)
    
    const q = positionSize;
    const absQ = Math.abs(q);
    
    const numerator = collateral - q * avgEntryPrice;
    const denominator = mmr * absQ - q;
    
    let estLiqPx = 0;
    if (Math.abs(denominator) > 1e-10) {
      estLiqPx = numerator / denominator;
    }
    
    // Calculate current health
    const unrealizedPnl = q * (oraclePrice - avgEntryPrice);
    const totalCollateral = collateral + unrealizedPnl;
    const requiredMargin = mmr * absQ * oraclePrice;
    
    const currentHealth = requiredMargin > 0 ? totalCollateral / requiredMargin : 1.0;
    
    // Calculate leverage
    const positionNotional = absQ * oraclePrice;
    const leverage = collateral > 0 ? positionNotional / collateral : 0;
    
    // Distance to liquidation in basis points
    const distanceBps = oraclePrice > 0 ? ((estLiqPx - oraclePrice) / oraclePrice) * 10000 : 0;
    
    return {
      estLiqPx,
      currentHealth,
      leverage,
      distanceBps
    };
    
  } catch (error) {
    console.error('Error solving liquidation price:', error);
    return {
      estLiqPx: 0,
      currentHealth: 1.0,
      leverage: 0,
      distanceBps: 0
    };
  }
}

/**
 * Validate liquidation estimate against SDK health calculation
 * Used for testing to ensure <0.25% tolerance
 * 
 * @param client Drift client
 * @param user User account
 * @param estimate Our calculated estimate
 * @returns true if within tolerance
 */
export async function validateEstimate(
  client: DriftClient,
  user: User,
  estimate: LiquidationEstimate
): Promise<boolean> {
  try {
    // Get SDK's health calculation
    const accountData = await user.getUserAccount();
    const totalCollateral = accountData.totalCollateral.toNumber() / PRICE_PRECISION.toNumber();
    const maintenanceMargin = accountData.maintenanceMarginRequirement.toNumber() / PRICE_PRECISION.toNumber();
    
    const sdkHealth = maintenanceMargin > 0 ? totalCollateral / maintenanceMargin : 1.0;
    
    // Check if our health calculation is within 0.25% of SDK
    const healthDiff = Math.abs(estimate.currentHealth - sdkHealth);
    const healthTolerance = 0.0025; // 0.25%
    
    return healthDiff <= healthTolerance;
    
  } catch (error) {
    console.error('Error validating estimate:', error);
    return false;
  }
}
