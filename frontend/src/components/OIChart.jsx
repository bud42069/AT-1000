/**
 * OIChart Component
 * Displays Open Interest history as an area chart
 * Data source: /api/history/oi (24h lookback, 1-minute resolution)
 */

import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';

export const OIChart = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOIHistory = async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_BACKEND_URL}/api/history/oi?symbol=SOLUSDT&tf=1m&lookback=24h`
        );
        const result = await response.json();
        
        // Transform data for Recharts
        const chartData = result.map(item => ({
          time: new Date(item.ts).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false 
          }),
          notional: item.notional,
          timestamp: item.ts
        }));
        
        setData(chartData);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch OI history:', err);
        setLoading(false);
      }
    };

    fetchOIHistory();
    const interval = setInterval(fetchOIHistory, 60000); // Update every minute

    return () => clearInterval(interval);
  }, []);

  const formatYAxis = (value) => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
    return `$${(value / 1e3).toFixed(0)}k`;
  };

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[#11161C] border border-[#1E2937] rounded-lg p-3 shadow-lg">
          <p className="text-sm text-[#9AA6B2] mb-1">{payload[0].payload.time}</p>
          <p className="text-lg font-mono font-semibold text-[#84CC16]">
            {formatYAxis(payload[0].value)}
          </p>
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)] animate-pulse">
        <div className="h-80"></div>
      </Card>
    );
  }

  return (
    <Card 
      className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)]"
      data-testid="oi-chart"
    >
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-5 h-5 text-[#84CC16]" />
        <h2 className="text-lg font-semibold text-[#C7D2DE]">Open Interest (24h)</h2>
        <span className="text-sm text-[#9AA6B2] ml-auto">SOL-PERP</span>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart 
          data={data}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorOI" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#84CC16" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#84CC16" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1E2937" />
          <XAxis 
            dataKey="time" 
            stroke="#9AA6B2"
            tick={{ fill: '#9AA6B2', fontSize: 12 }}
            interval="preserveStartEnd"
            minTickGap={50}
          />
          <YAxis 
            stroke="#9AA6B2"
            tick={{ fill: '#9AA6B2', fontSize: 12 }}
            tickFormatter={formatYAxis}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area 
            type="monotone" 
            dataKey="notional" 
            stroke="#84CC16" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorOI)" 
          />
        </AreaChart>
      </ResponsiveContainer>

      {data.length === 0 && (
        <div className="flex items-center justify-center h-64 text-[#9AA6B2]">
          No data available
        </div>
      )}
    </Card>
  );
};
