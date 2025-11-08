/**
 * TelemetryCards Component
 * Displays 6 real-time market metrics cards
 * Data source: /api/engine/guards (polling every 5s)
 */

import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { TrendingUp, TrendingDown, DollarSign, Percent, AlertTriangle, Activity } from 'lucide-react';

export const TelemetryCards = () => {
  const [guards, setGuards] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchGuards = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/engine/guards`);
        const data = await response.json();
        setGuards(data);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch guards:', err);
      }
    };

    fetchGuards();
    const interval = setInterval(fetchGuards, 5000); // Poll every 5s

    return () => clearInterval(interval);
  }, []);

  if (loading || !guards) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Card key={i} className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-4 animate-pulse">
            <div className="h-20"></div>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: 'Spread',
      value: guards.spread_bps,
      unit: 'bps',
      icon: Activity,
      color: guards.spread_bps > 10 ? '#F43F5E' : guards.spread_bps > 5 ? '#FCD34D' : '#84CC16',
      decimals: 2
    },
    {
      title: 'Depth (10bps)',
      value: Math.min(guards.depth_10bps.bid_usd, guards.depth_10bps.ask_usd),
      unit: '$',
      prefix: '$',
      icon: DollarSign,
      color: guards.depth_10bps.bid_usd < 50000 || guards.depth_10bps.ask_usd < 50000 ? '#F43F5E' : '#84CC16',
      formatter: (val) => `${(val / 1000).toFixed(0)}k`
    },
    {
      title: 'Funding APR',
      value: guards.funding_apr,
      unit: '%',
      suffix: '%',
      icon: Percent,
      color: Math.abs(guards.funding_apr) > 300 ? '#F43F5E' : '#84CC16',
      decimals: 1
    },
    {
      title: 'Basis',
      value: guards.basis_bps,
      unit: 'bps',
      icon: TrendingUp,
      color: Math.abs(guards.basis_bps) > 50 ? '#FCD34D' : '#84CC16',
      decimals: 2,
      showSign: true
    },
    {
      title: 'OI Notional',
      value: guards.oi_notional,
      unit: '$',
      prefix: '$',
      icon: DollarSign,
      color: '#84CC16',
      formatter: (val) => {
        if (val >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
        if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M`;
        return `${(val / 1e3).toFixed(0)}k`;
      }
    },
    {
      title: 'Liquidations (5m)',
      value: guards.liq_events_5m,
      unit: 'events',
      icon: AlertTriangle,
      color: guards.liq_events_5m > 10 ? '#F43F5E' : guards.liq_events_5m > 5 ? '#FCD34D' : '#84CC16',
      decimals: 0
    }
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        const formattedValue = card.formatter
          ? card.formatter(card.value)
          : card.decimals !== undefined
          ? card.value.toFixed(card.decimals)
          : card.value;

        const displayValue = card.showSign && card.value > 0
          ? `+${formattedValue}`
          : formattedValue;

        return (
          <Card
            key={idx}
            data-testid={`telemetry-card-${card.title.toLowerCase().replace(/\s+/g, '-')}`}
            className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-4 shadow-[0_8px_30px_rgba(0,0,0,0.35)] transition-all duration-200 hover:border-[#84CC16]/30"
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" style={{ color: card.color }} />
                <h3 className="text-sm font-medium text-[#9AA6B2]">{card.title}</h3>
              </div>
            </div>

            <div className="flex items-baseline gap-1">
              {card.prefix && (
                <span className="text-lg font-mono text-[#9AA6B2]">{card.prefix}</span>
              )}
              <span
                className="text-3xl font-mono font-bold"
                style={{ color: card.color }}
              >
                {displayValue}
              </span>
              {card.suffix && (
                <span className="text-lg font-mono text-[#9AA6B2]">{card.suffix}</span>
              )}
            </div>

            {card.unit && !card.suffix && (
              <div className="text-xs text-[#9AA6B2] mt-1">{card.unit}</div>
            )}
          </Card>
        );
      })}

      {/* Status indicator */}
      {guards.status !== 'passing' && (
        <div className="col-span-2 md:col-span-3">
          <div className={`rounded-xl p-3 border ${
            guards.status === 'breach' 
              ? 'bg-[#F43F5E]/10 border-[#F43F5E]/30' 
              : 'bg-[#FCD34D]/10 border-[#FCD34D]/30'
          }`}>
            <div className="flex items-center gap-2">
              <AlertTriangle className={guards.status === 'breach' ? 'text-[#F43F5E]' : 'text-[#FCD34D]'} size={16} />
              <span className="text-sm font-medium text-[#C7D2DE]">
                {guards.status === 'breach' ? 'Guard Breach' : 'Warning'}:
              </span>
              <span className="text-sm text-[#9AA6B2]">
                {guards.warnings.join(', ')}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
