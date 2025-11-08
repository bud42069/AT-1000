/**
 * LiqHeatmap Component
 * Displays liquidation events as a price-bucketed heatmap using D3.js
 * Data source: /api/history/liqs (6h window, 25bps buckets)
 */

import React, { useState, useEffect, useRef } from 'react';
import { Card } from './ui/card';
import * as d3 from 'd3';
import { AlertTriangle } from 'lucide-react';

export const LiqHeatmap = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const svgRef = useRef(null);

  useEffect(() => {
    const fetchLiqData = async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_BACKEND_URL}/api/history/liqs?symbol=SOLUSDT&window=6h&bucket_bps=25`
        );
        const result = await response.json();
        setData(result);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch liq heatmap:', err);
        setLoading(false);
      }
    };

    fetchLiqData();
    const interval = setInterval(fetchLiqData, 5000); // Update every 5s for real-time

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!data || data.length === 0 || !svgRef.current) return;

    // Clear previous chart
    d3.select(svgRef.current).selectAll('*').remove();

    // Dimensions
    const margin = { top: 20, right: 30, bottom: 40, left: 60 };
    const width = 800 - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    // Create SVG
    const svg = d3.select(svgRef.current)
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Scales
    const xScale = d3.scaleLinear()
      .domain(d3.extent(data, d => d.px_mid))
      .range([0, width]);

    const maxCount = d3.max(data, d => d.count);
    const yScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([height, 0]);

    // Color scale (green = low, yellow = medium, red = high)
    const colorScale = d3.scaleSequential()
      .domain([0, maxCount])
      .interpolator(t => {
        if (t < 0.33) return d3.interpolateRgb('#84CC16', '#FCD34D')(t * 3);
        if (t < 0.67) return d3.interpolateRgb('#FCD34D', '#F59E0B')((t - 0.33) * 3);
        return d3.interpolateRgb('#F59E0B', '#F43F5E')((t - 0.67) * 3);
      });

    // Bars
    const barWidth = width / data.length;

    svg.selectAll('.bar')
      .data(data)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => xScale(d.px_mid) - barWidth / 2)
      .attr('y', d => yScale(d.count))
      .attr('width', barWidth * 0.9)
      .attr('height', d => height - yScale(d.count))
      .attr('fill', d => colorScale(d.count))
      .attr('opacity', 0.8)
      .on('mouseover', function(event, d) {
        // Tooltip
        d3.select(this).attr('opacity', 1);
        
        svg.append('text')
          .attr('class', 'tooltip-text')
          .attr('x', xScale(d.px_mid))
          .attr('y', yScale(d.count) - 10)
          .attr('text-anchor', 'middle')
          .attr('fill', '#C7D2DE')
          .attr('font-size', '12px')
          .attr('font-family', 'IBM Plex Mono')
          .text(`$${d.px_mid.toFixed(2)} | ${d.count} liqs | $${(d.notional / 1e6).toFixed(2)}M`);
      })
      .on('mouseout', function() {
        d3.select(this).attr('opacity', 0.8);
        svg.selectAll('.tooltip-text').remove();
      });

    // X Axis
    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(xScale).ticks(8).tickFormat(d => `$${d.toFixed(0)}`))
      .selectAll('text')
      .attr('fill', '#9AA6B2')
      .attr('font-size', '11px');

    svg.selectAll('.domain, .tick line')
      .attr('stroke', '#1E2937');

    // Y Axis
    svg.append('g')
      .call(d3.axisLeft(yScale).ticks(5))
      .selectAll('text')
      .attr('fill', '#9AA6B2')
      .attr('font-size', '11px');

    svg.selectAll('.domain, .tick line')
      .attr('stroke', '#1E2937');

    // Labels
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', height + 35)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9AA6B2')
      .attr('font-size', '12px')
      .text('Price ($)');

    svg.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -height / 2)
      .attr('y', -45)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9AA6B2')
      .attr('font-size', '12px')
      .text('Liquidations Count');

  }, [data]);

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
      data-testid="liq-heatmap"
    >
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-[#F43F5E]" />
        <h2 className="text-lg font-semibold text-[#C7D2DE]">Liquidation Heatmap (6h)</h2>
        <span className="text-sm text-[#9AA6B2] ml-auto">25 bps buckets</span>
      </div>

      {data.length > 0 ? (
        <div className="overflow-x-auto">
          <svg ref={svgRef}></svg>
        </div>
      ) : (
        <div className="flex items-center justify-center h-64 text-[#9AA6B2]">
          No liquidation events in the last 6 hours
        </div>
      )}
    </Card>
  );
};
