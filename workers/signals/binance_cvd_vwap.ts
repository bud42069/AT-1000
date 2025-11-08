/**
 * Binance Signal Worker - CVD + VWAP Strategy
 * 
 * Strategy: Long-B (deviation→reclaim)
 * - Price crosses back above VWAP
 * - 1m CVD rising for 3 bars
 * 
 * Strategy: Short-B (inverse)
 * - Price crosses back below VWAP
 * - 1m CVD falling for 3 bars
 * 
 * Emits OrderIntent JSON to:
 * - File: /app/data/signals/solusdt-1m.jsonl
 * - Backend: POST /api/engine/intents
 */

import WebSocket from 'ws';
import * as fs from 'fs';
import * as path from 'path';

interface AggTrade {
  e: string; // Event type
  E: number; // Event time
  s: string; // Symbol
  a: number; // Aggregate trade ID
  p: string; // Price
  q: string; // Quantity
  f: number; // First trade ID
  l: number; // Last trade ID
  T: number; // Trade time
  m: boolean; // Is buyer maker
  M: boolean; // Ignore
}

interface Bar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  buyVolume: number;
  sellVolume: number;
  cvd: number;
  vwap: number;
  trades: number;
}

interface Signal {
  ts: number;
  symbol: string;
  signal: 'longB' | 'shortB' | null;
  confirm: {
    vwap_reclaim: boolean;
    cvd_trend: 'up' | 'down' | 'neutral';
  };
  intent?: {
    side: 'long' | 'short';
    limitPx: number;
    size: number;
    slPx: number;
    tpPx: { p1: number; p2: number; p3: number };
    leverage: number;
  };
}

class BinanceSignalWorker {
  private ws: WebSocket | null = null;
  private bars: Bar[] = [];
  private currentBar: Partial<Bar> | null = null;
  private barStartTime: number = 0;
  private barInterval: number = 60000; // 1 minute
  
  private vwapSum: number = 0;
  private vwapVolume: number = 0;
  
  private lastSignal: 'longB' | 'shortB' | null = null;
  private outputPath: string;

  constructor(outputPath: string = '/app/data/signals/solusdt-1m.jsonl') {
    this.outputPath = outputPath;
    
    // Ensure output directory exists
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  /**
   * Connect to Binance WebSocket and start processing
   */
  async start(): Promise<void> {
    console.log('🚀 Starting Binance Signal Worker...');
    console.log('Symbol: SOLUSDT');
    console.log('Strategy: CVD + VWAP reclaim');
    console.log('Output:', this.outputPath);

    const wsUrl = 'wss://fstream.binance.com/ws/solusdt@aggTrade';
    
    this.ws = new WebSocket(wsUrl);

    this.ws.on('open', () => {
      console.log('✅ Connected to Binance futures WebSocket');
      this.initializeBar();
    });

    this.ws.on('message', (data: Buffer) => {
      try {
        const trade: AggTrade = JSON.parse(data.toString());
        this.processTrade(trade);
      } catch (error) {
        console.error('❌ Failed to process trade:', error);
      }
    });

    this.ws.on('error', (error) => {
      console.error('❌ WebSocket error:', error);
    });

    this.ws.on('close', () => {
      console.log('🔌 WebSocket closed. Reconnecting...');
      setTimeout(() => this.start(), 5000);
    });
  }

  /**
   * Initialize a new bar
   */
  private initializeBar(): void {
    const now = Date.now();
    this.barStartTime = Math.floor(now / this.barInterval) * this.barInterval;
    
    this.currentBar = {
      timestamp: this.barStartTime,
      open: 0,
      high: -Infinity,
      low: Infinity,
      close: 0,
      volume: 0,
      buyVolume: 0,
      sellVolume: 0,
      cvd: 0,
      vwap: 0,
      trades: 0,
    };

    this.vwapSum = 0;
    this.vwapVolume = 0;
  }

  /**
   * Process incoming trade
   */
  private processTrade(trade: AggTrade): void {
    const price = parseFloat(trade.p);
    const quantity = parseFloat(trade.q);
    const isBuy = !trade.m; // m = true means buyer is maker (sell)
    
    const now = Date.now();
    const currentBarTime = Math.floor(now / this.barInterval) * this.barInterval;

    // Check if we need to finalize current bar and start new one
    if (currentBarTime > this.barStartTime) {
      this.finalizeBar();
      this.initializeBar();
    }

    if (!this.currentBar) return;

    // Update OHLC
    if (this.currentBar.open === 0) {
      this.currentBar.open = price;
    }
    this.currentBar.high = Math.max(this.currentBar.high || -Infinity, price);
    this.currentBar.low = Math.min(this.currentBar.low || Infinity, price);
    this.currentBar.close = price;

    // Update volume
    this.currentBar.volume = (this.currentBar.volume || 0) + quantity;
    
    if (isBuy) {
      this.currentBar.buyVolume = (this.currentBar.buyVolume || 0) + quantity;
    } else {
      this.currentBar.sellVolume = (this.currentBar.sellVolume || 0) + quantity;
    }

    // Update CVD (Cumulative Volume Delta)
    const delta = isBuy ? quantity : -quantity;
    this.currentBar.cvd = (this.currentBar.cvd || 0) + delta;

    // Update VWAP
    this.vwapSum += price * quantity;
    this.vwapVolume += quantity;
    this.currentBar.vwap = this.vwapVolume > 0 ? this.vwapSum / this.vwapVolume : price;

    this.currentBar.trades = (this.currentBar.trades || 0) + 1;
  }

  /**
   * Finalize current bar and check for signals
   */
  private finalizeBar(): void {
    if (!this.currentBar || !this.currentBar.close) return;

    const completedBar: Bar = this.currentBar as Bar;
    this.bars.push(completedBar);

    // Keep only last 100 bars
    if (this.bars.length > 100) {
      this.bars.shift();
    }

    console.log(`📊 Bar closed:`, {
      time: new Date(completedBar.timestamp).toISOString(),
      close: completedBar.close.toFixed(2),
      cvd: completedBar.cvd.toFixed(0),
      vwap: completedBar.vwap.toFixed(2),
      volume: completedBar.volume.toFixed(2),
    });

    // Check for signals
    this.checkSignals();
  }

  /**
   * Check for Long-B or Short-B signals
   */
  private checkSignals(): void {
    if (this.bars.length < 4) return; // Need at least 4 bars

    const current = this.bars[this.bars.length - 1];
    const prev = this.bars[this.bars.length - 2];
    const prev2 = this.bars[this.bars.length - 3];
    const prev3 = this.bars[this.bars.length - 4];

    // Check CVD trend (3 bars rising or falling)
    const cvdTrend = this.getCVDTrend([prev3, prev2, prev, current]);
    
    // Check VWAP reclaim
    const vwapReclaimLong = prev.close < prev.vwap && current.close > current.vwap;
    const vwapReclaimShort = prev.close > prev.vwap && current.close < current.vwap;

    let signal: 'longB' | 'shortB' | null = null;

    // Long-B: VWAP reclaim + CVD rising
    if (vwapReclaimLong && cvdTrend === 'up') {
      signal = 'longB';
    }
    // Short-B: VWAP reclaim down + CVD falling
    else if (vwapReclaimShort && cvdTrend === 'down') {
      signal = 'shortB';
    }

    // Only emit if signal changed (avoid duplicates)
    if (signal && signal !== this.lastSignal) {
      this.emitSignal(signal, {
        vwap_reclaim: signal === 'longB' ? vwapReclaimLong : vwapReclaimShort,
        cvd_trend: cvdTrend,
      });
      this.lastSignal = signal;
    } else if (!signal && this.lastSignal) {
      // Signal ended
      this.lastSignal = null;
    }
  }

  /**
   * Determine CVD trend over last 3 bars
   */
  private getCVDTrend(bars: Bar[]): 'up' | 'down' | 'neutral' {
    if (bars.length < 3) return 'neutral';

    const cvds = bars.map(b => b.cvd);
    const rising = cvds[1] > cvds[0] && cvds[2] > cvds[1];
    const falling = cvds[1] < cvds[0] && cvds[2] < cvds[1];

    if (rising) return 'up';
    if (falling) return 'down';
    return 'neutral';
  }

  /**
   * Emit signal with OrderIntent
   */
  private emitSignal(
    signal: 'longB' | 'shortB',
    confirm: { vwap_reclaim: boolean; cvd_trend: 'up' | 'down' | 'neutral' }
  ): void {
    const current = this.bars[this.bars.length - 1];
    
    // Calculate SL and TPs (placeholder logic - should be ATR-based in production)
    const atrEstimate = Math.abs(current.high - current.low) * 1.5;
    const side = signal === 'longB' ? 'long' : 'short';
    
    const slDistance = atrEstimate * 1.5;
    const tpDistance1 = atrEstimate * 2.0;
    const tpDistance2 = atrEstimate * 3.0;
    const tpDistance3 = atrEstimate * 4.0;

    const slPx = side === 'long' ? current.close - slDistance : current.close + slDistance;
    const tp1 = side === 'long' ? current.close + tpDistance1 : current.close - tpDistance1;
    const tp2 = side === 'long' ? current.close + tpDistance2 : current.close - tpDistance2;
    const tp3 = side === 'long' ? current.close + tpDistance3 : current.close - tpDistance3;

    const signalData: Signal = {
      ts: Date.now(),
      symbol: 'SOLUSDT',
      signal,
      confirm,
      intent: {
        side,
        limitPx: current.close,
        size: 0, // Will be calculated by engine based on risk
        slPx,
        tpPx: { p1: tp1, p2: tp2, p3: tp3 },
        leverage: 5, // Default leverage
      },
    };

    console.log('🎯 SIGNAL DETECTED:', signal);
    console.log('Confirm:', confirm);
    console.log('Intent:', signalData.intent);

    // Write to file
    fs.appendFileSync(this.outputPath, JSON.stringify(signalData) + '\n');

    // TODO: Send to backend via POST /api/engine/intents
    // For now, just log
    console.log('✅ Signal emitted to', this.outputPath);
  }

  /**
   * Stop the worker
   */
  stop(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    console.log('👋 Binance Signal Worker stopped');
  }
}

// Run worker if executed directly
if (require.main === module) {
  const worker = new BinanceSignalWorker();
  worker.start();

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log('\n⚠️  Received SIGINT, shutting down...');
    worker.stop();
    process.exit(0);
  });
}

export default BinanceSignalWorker;
