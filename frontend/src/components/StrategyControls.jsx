import React from 'react';
import { Card } from './ui/card';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { Label } from './ui/label';
import { Separator } from './ui/separator';

export const StrategyControls = ({
  enabled,
  onToggle,
  leverage,
  setLeverage,
  risk,
  setRisk,
  priorityFee,
  setPriorityFee,
}) => {
  return (
    <Card className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-6 space-y-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)] h-fit sticky top-6">
      <div>
        <h2 className="text-lg font-semibold text-[#C7D2DE] mb-1">Strategy Controls</h2>
        <p className="text-xs text-[#6B7280]">Configure automation parameters</p>
      </div>

      <Separator className="bg-[#1E2937]" />

      {/* Automation Toggle */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm font-medium text-[#C7D2DE]">Automation</Label>
          <p className="text-xs text-[#6B7280]">Enable auto-trading</p>
        </div>
        <Switch
          data-testid="strategy-toggle"
          checked={enabled}
          onCheckedChange={onToggle}
          className="data-[state=checked]:bg-[#84CC16]"
        />
      </div>

      <Separator className="bg-[#1E2937]" />

      {/* Leverage Slider */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium text-[#C7D2DE]">Leverage</Label>
          <span className="font-mono text-sm text-[#84CC16]">{leverage}x</span>
        </div>
        <Slider
          data-testid="leverage-slider"
          value={[leverage]}
          onValueChange={(v) => setLeverage(v[0])}
          min={1}
          max={25}
          step={1}
          className="w-full"
          disabled={!enabled}
        />
        <p className="text-xs text-[#6B7280]">Max: 10x (safety cap)</p>
      </div>

      <Separator className="bg-[#1E2937]" />

      {/* Risk Per Trade */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium text-[#C7D2DE]">Risk per Trade</Label>
          <span className="font-mono text-sm text-[#84CC16]">{risk.toFixed(2)}%</span>
        </div>
        <Slider
          data-testid="risk-slider"
          value={[risk]}
          onValueChange={(v) => setRisk(v[0])}
          min={0.25}
          max={5}
          step={0.25}
          className="w-full"
          disabled={!enabled}
        />
        <p className="text-xs text-[#6B7280]">As % of account equity</p>
      </div>

      <Separator className="bg-[#1E2937]" />

      {/* Priority Fee */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium text-[#C7D2DE]">Priority Fee</Label>
          <span className="font-mono text-sm text-[#67E8F9]">{priorityFee} μλ</span>
        </div>
        <Slider
          data-testid="priority-fee-slider"
          value={[priorityFee]}
          onValueChange={(v) => setPriorityFee(v[0])}
          min={0}
          max={5000}
          step={100}
          className="w-full"
          disabled={!enabled}
        />
        <p className="text-xs text-[#6B7280]">Microlamports per compute unit</p>
      </div>
    </Card>
  );
};