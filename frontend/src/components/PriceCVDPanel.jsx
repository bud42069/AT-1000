import React, { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Badge } from './ui/badge';
import { TrendingUp, TrendingDown } from 'lucide-react';

export const PriceCVDPanel = () => {
  const [priceData, setPriceData] = useState([]);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [cvdTrend, setCvdTrend] = useState('neutral');

  // Mock data for POC - replace with real WebSocket stream
  useEffect(() => {
    const generateMockData = () => {
      const data = [];
      let price = 20 + Math.random() * 5;
      let cvd = 0;
      
      for (let i = 0; i < 60; i++) {
        price += (Math.random() - 0.5) * 0.5;
        const delta = (Math.random() - 0.5) * 1000;
        cvd += delta;
        
        data.push({
          t: `${i}m`,
          price: parseFloat(price.toFixed(2)),
          cvd: parseFloat(cvd.toFixed(0)),
          delta: parseFloat(delta.toFixed(0)),
        });
      }
      
      return data;
    };

    const mockData = generateMockData();
    setPriceData(mockData);
    setCurrentPrice(mockData[mockData.length - 1].price);
    setCvdTrend(mockData[mockData.length - 1].cvd > 0 ? 'bullish' : 'bearish');

    // Update every 5 seconds
    const interval = setInterval(() => {
      setPriceData(prev => {
        const last = prev[prev.length - 1];
        const newPrice = last.price + (Math.random() - 0.5) * 0.5;
        const newDelta = (Math.random() - 0.5) * 1000;
        const newCvd = last.cvd + newDelta;
        
        const updated = [...prev.slice(1), {
          t: `${prev.length}m`,
          price: parseFloat(newPrice.toFixed(2)),
          cvd: parseFloat(newCvd.toFixed(0)),
          delta: parseFloat(newDelta.toFixed(0)),
        }];
        
        setCurrentPrice(newPrice);
        setCvdTrend(newCvd > 0 ? 'bullish' : 'bearish');
        
        return updated;
      });
    }, 5000);

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