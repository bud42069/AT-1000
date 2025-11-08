import React, { useState, useEffect } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './ui/alert-dialog';
import { Activity, Power, Wallet, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

export const TopBar = ({ delegationActive, onRevoke, onEmergencyStop }) => {
  const { connected, publicKey } = useWallet();
  const { connection } = useConnection();
  const [market, setMarket] = useState('SOL-PERP');
  const [balance, setBalance] = useState(null);
  const [position, setPosition] = useState({ size: 0, pnl: 0 });

  const handleEmergencyStop = () => {
    onEmergencyStop();
    toast.error('Emergency Stop Activated', {
      description: 'All orders cancelled. Automation disabled.',
    });
  };

  const handleRevoke = () => {
    onRevoke();
    toast.success('Delegation Revoked', {
      description: 'Trading authority has been revoked.',
    });
  };

  // Fetch wallet balance
  useEffect(() => {
    if (connected && publicKey && connection) {
      const fetchBalance = async () => {
        try {
          const bal = await connection.getBalance(publicKey);
          setBalance((bal / LAMPORTS_PER_SOL).toFixed(4));
        } catch (err) {
          console.error('Failed to fetch balance:', err);
        }
      };

      fetchBalance();
      const interval = setInterval(fetchBalance, 30000); // Update every 30s

      return () => clearInterval(interval);
    } else {
      setBalance(null);
    }
  }, [connected, publicKey, connection]);

  // TODO: Fetch Drift position data (requires Drift SDK integration)
  // For now showing placeholder position data
  useEffect(() => {
    if (connected && delegationActive) {
      // Placeholder - will be replaced with actual Drift position query
      setPosition({ size: 0, pnl: 0 });
    } else {
      setPosition({ size: 0, pnl: 0 });
    }
  }, [connected, delegationActive]);

  return (
    <Card className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-4 mb-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
      <div className="grid grid-cols-1 md:grid-cols-12 items-center gap-4">
        {/* Logo/Network - Left */}
        <div className="md:col-span-3 flex items-center gap-3">
          <Activity className="w-6 h-6 text-[#84CC16]" />
          <div>
            <h1 className="text-lg font-semibold text-[#C7D2DE]">Auto-Trader</h1>
            <Badge className="text-xs bg-[#1E2937] text-[#67E8F9] border-none">Devnet</Badge>
          </div>
        </div>

        {/* Market Selector - Center */}
        <div className="md:col-span-6 flex justify-center">
          <Select value={market} onValueChange={setMarket}>
            <SelectTrigger
              data-testid="market-selector"
              className="w-48 bg-[#0B0F14] border-[#1E2937] text-[#C7D2DE] focus:ring-[#84CC16]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#11161C] border-[#1E2937]">
              <SelectItem value="SOL-PERP">SOL-PERP</SelectItem>
              <SelectItem value="BTC-PERP" disabled>BTC-PERP (Soon)</SelectItem>
              <SelectItem value="ETH-PERP" disabled>ETH-PERP (Soon)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Wallet + Delegation + Emergency Stop - Right */}
        <div className="md:col-span-3 flex items-center justify-end gap-3 flex-wrap">
          {/* Delegation Badge */}
          {connected && (
            <div className="flex items-center gap-2">
              <Badge
                data-testid="delegation-status-badge"
                className="rounded-md"
                style={{
                  backgroundColor: delegationActive ? '#84CC16' : '#1E2937',
                  color: delegationActive ? '#0B0F14' : '#C7D2DE',
                }}
              >
                {delegationActive ? 'Delegation: Active' : 'Delegation: Inactive'}
              </Badge>
              {delegationActive && (
                <Button
                  data-testid="revoke-delegation-button"
                  variant="outline"
                  size="sm"
                  className="border-[#1E2937] text-[#C7D2DE] hover:bg-[#1E2937]"
                  onClick={handleRevoke}
                >
                  Revoke
                </Button>
              )}
            </div>
          )}

          {/* Wallet Connect */}
          <WalletMultiButton className="!bg-[#84CC16] !text-[#0B0F14] hover:!bg-[#A3E635] !rounded-xl !transition-colors !duration-150" />

          {/* Emergency Stop */}
          {connected && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  data-testid="emergency-stop-button"
                  className="rounded-xl bg-[#F43F5E] text-white hover:bg-[#fb7185] focus-visible:ring-2 focus-visible:ring-[#F43F5E] transition-colors duration-150"
                  size="icon"
                >
                  <Power className="w-4 h-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="rounded-2xl bg-[#11161C] border border-[#1E2937]">
                <AlertDialogHeader>
                  <AlertDialogTitle className="text-[#C7D2DE]">Confirm Emergency Stop</AlertDialogTitle>
                  <AlertDialogDescription className="text-[#9AA6B2]">
                    Immediately cancel all open orders and disable automation. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="flex justify-end gap-3 mt-4">
                  <AlertDialogCancel className="rounded-xl bg-transparent border border-[#1E2937] text-[#C7D2DE] hover:bg-[#1E2937]">
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleEmergencyStop}
                    className="rounded-xl bg-[#F43F5E] hover:bg-[#fb7185] text-white"
                  >
                    Confirm Stop
                  </AlertDialogAction>
                </div>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </div>
    </Card>
  );
};