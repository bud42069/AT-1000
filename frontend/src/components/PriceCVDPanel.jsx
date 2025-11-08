import React, { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Badge } from './ui/badge';
import { TrendingUp, TrendingDown } from 'lucide-react';

export const PriceCVDPanel = () => {
  const [priceData, setPriceData] = useState([]);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [cvdTrend, setCvdTrend] = useState('neutral');
  const [loading, setLoading] = useState(true);

  // Fetch live price and CVD data from Binance trades worker
  useEffect(() => {
    const fetchLiveData = async () => {
      try {
        // Fetch last 60 bars from Redis via backend API
        const response = await fetch(
          `${process.env.REACT_APP_BACKEND_URL}/api/market/bars?symbol=SOLUSDT&limit=60`
        );
        
        if (!response.ok) {
          console.warn('Market bars API not available, using fallback');
          return;
        }
        
        const bars = await response.json();
        
        if (!bars || bars.length === 0) {
          console.warn('No market data available yet');
          return;
        }
        
        // Transform bars for chart
        const chartData = bars.map((bar, idx) => ({
          t: new Date(bar.timestamp).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false 
          }),
          price: parseFloat(bar.close.toFixed(2)),
          cvd: parseFloat(bar.cvd.toFixed(0)),
          delta: parseFloat((bar.buy_volume - bar.sell_volume).toFixed(0)),
        }));
        
        setPriceData(chartData);
        
        // Set current price and trend from latest bar
        const latest = chartData[chartData.length - 1];
        setCurrentPrice(latest.price);
        setCvdTrend(latest.cvd > 0 ? 'bullish' : 'bearish');
        setLoading(false);
        
      } catch (err) {
        console.error('Failed to fetch live market data:', err);
      }
    };

    fetchLiveData();
    const interval = setInterval(fetchLiveData, 5000); // Update every 5s

    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-sm text-[#9AA6B2] mb-1">SOL-PERP</h2>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-bold font-mono text-[#C7D2DE]">
              ${currentPrice.toFixed(2)}
            </span>
            <Badge
              className="gap-1"
              style={{
                backgroundColor: cvdTrend === 'bullish' ? '#84CC16' : '#F43F5E',
                color: '#0B0F14',
              }}
            >
              {cvdTrend === 'bullish' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {cvdTrend.toUpperCase()}
            </Badge>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-[#6B7280]">1m CVD</p>
          <p className="text-lg font-mono text-[#67E8F9]">
            {priceData.length > 0 ? priceData[priceData.length - 1].cvd : 0}
          </p>
        </div>
      </div>

      {/* Price Chart */}
      <div className="mb-6">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={priceData} margin={{ left: 0, right: 0, top: 8, bottom: 8 }}>
            <CartesianGrid stroke="#1A2430" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              stroke="#6B7280"
              tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
              interval="preserveStartEnd"
            />
            <YAxis
              yAxisId="left"
              stroke="#6B7280"
              tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
              domain={['auto', 'auto']}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#6B7280"
              tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            />
            <Tooltip
              contentStyle={{
                background: '#0B0F14',
                border: '1px solid #1E2937',
                borderRadius: '8px',
                fontFamily: 'IBM Plex Mono',
              }}
              labelStyle={{ color: '#C7D2DE' }}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="price"
              stroke="#9AA6B2"
              strokeWidth={2}
              dot={false}
              name="Price"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="cvd"
              stroke="#84CC16"
              strokeWidth={1.5}
              dot={false}
              name="CVD"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* CVD Delta Bar Chart */}
      <div>
        <p className="text-xs text-[#6B7280] mb-2">CVD Delta (1m bars)</p>
        <ResponsiveContainer width="100%" height={80}>
          <BarChart data={priceData}>
            <CartesianGrid horizontal={false} stroke="#1A2430" />
            <XAxis dataKey="t" hide />
            <YAxis hide />
            <Bar dataKey="delta" fill="#84CC16" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};