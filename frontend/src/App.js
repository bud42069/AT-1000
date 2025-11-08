import React, { useState, useEffect } from 'react';
import { WalletContextProvider } from './contexts/WalletContext';
import { useWallet } from '@solana/wallet-adapter-react';
import { TopBar } from './components/TopBar';
import { StrategyControls } from './components/StrategyControls';
import { PriceCVDPanel } from './components/PriceCVDPanel';
import { ActivityLog } from './components/ActivityLog';
import { ConsentModal } from './components/ConsentModal';
import { Toaster, toast } from 'sonner';
import { getActivity, killSwitch } from './lib/api';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function AppContent() {
  const { connected, publicKey } = useWallet();
  const [showConsent, setShowConsent] = useState(false);
  const [delegationActive, setDelegationActive] = useState(false);
  const [strategyEnabled, setStrategyEnabled] = useState(false);
  const [leverage, setLeverage] = useState(5);
  const [risk, setRisk] = useState(0.75);
  const [priorityFee, setPriorityFee] = useState(1000);
  const [activityLogs, setActivityLogs] = useState([]);
  const [ws, setWs] = useState(null);

  // Show consent modal when wallet connects (first time)
  useEffect(() => {
    if (connected && !delegationActive) {
      setShowConsent(true);
    }
  }, [connected, delegationActive]);

  // Connect WebSocket for real-time events
  useEffect(() => {
    if (connected) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/ws/engine.events`;
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log('✅ WebSocket connected');
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleEngineEvent(data);
        } catch (err) {
          console.error('WS parse error:', err);
        }
      };

      socket.onerror = (err) => {
        console.error('WS error:', err);
      };

      socket.onclose = () => {
        console.log('WebSocket closed');
      };

      setWs(socket);

      return () => {
        socket.close();
      };
    }
  }, [connected]);

  // Handle engine events from WebSocket
  const handleEngineEvent = (event) => {
    switch (event.type) {
      case 'order_submitted':
        toast.info('Order Submitted', {
          description: `${event.data.side.toUpperCase()} ${event.data.size} @ $${event.data.px}`,
        });
        break;
      case 'order_filled':
        toast.success('Order Filled', {
          description: `Position opened at $${event.data.px}`,
        });
        break;
      case 'order_cancelled':
        toast('Order Cancelled', {
          description: `Order ${event.orderId.slice(0, 8)}... cancelled`,
        });
        break;
      case 'kill_switch':
        toast.error('Kill Switch Activated', {
          description: event.reason,
        });
        setStrategyEnabled(false);
        break;
      default:
        break;
    }
  };

  // Fetch activity logs
  useEffect(() => {
    if (connected) {
      const fetchLogs = async () => {
        try {
          const response = await getActivity();
          setActivityLogs(response.logs || []);
        } catch (err) {
          console.error('Failed to fetch logs:', err);
        }
      };

      fetchLogs();
      const interval = setInterval(fetchLogs, 10000); // Poll every 10s

      return () => clearInterval(interval);
    }
  }, [connected]);

  // Consent confirmation
  const handleConsentConfirm = async () => {
    setShowConsent(false);
    setDelegationActive(true);
    toast.success('Delegation Authorized', {
      description: 'Trading authority granted. You can revoke at any time.',
    });
  };

  // Revoke delegation
  const handleRevoke = () => {
    setDelegationActive(false);
    setStrategyEnabled(false);
    toast.success('Delegation Revoked', {
      description: 'Trading authority has been revoked.',
    });
  };

  // Emergency stop
  const handleEmergencyStop = async () => {
    try {
      await axios.post(`${BACKEND_URL}/engine/kill`, {
        reason: 'User-initiated emergency stop',
      });
      setStrategyEnabled(false);
      toast.error('Emergency Stop Activated', {
        description: 'All orders cancelled. Automation disabled.',
      });
    } catch (err) {
      console.error('Emergency stop failed:', err);
      toast.error('Emergency Stop Failed', {
        description: 'Please try again or revoke delegation manually.',
      });
    }
  };

  // Toggle strategy
  const handleToggleStrategy = (enabled) => {
    if (!delegationActive) {
      toast.error('Delegation Required', {
        description: 'Please authorize delegation first.',
      });
      return;
    }
    setStrategyEnabled(enabled);
    toast(enabled ? 'Strategy Enabled' : 'Strategy Disabled', {
      description: enabled
        ? 'Automation is now active. Monitor activity log.'
        : 'Automation paused. No new orders will be placed.',
    });
  };

  return (
    <div className="min-h-screen bg-[#0B0F14] pb-12">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Top Bar */}
        <TopBar
          delegationActive={delegationActive}
          onRevoke={handleRevoke}
          onEmergencyStop={handleEmergencyStop}
        />

        {/* Main Content */}
        {!connected ? (
          <div className="flex items-center justify-center py-32">
            <div className="text-center space-y-4">
              <h2 className="text-2xl font-semibold text-[#C7D2DE]">Welcome to Auto-Trader</h2>
              <p className="text-[#9AA6B2]">Connect your Phantom wallet to get started</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Price Chart (8 cols) */}
            <div className="lg:col-span-8 space-y-6">
              <PriceCVDPanel />
              <ActivityLog logs={activityLogs} />
            </div>

            {/* Right: Strategy Controls (4 cols) */}
            <div className="lg:col-span-4">
              <StrategyControls
                enabled={strategyEnabled}
                onToggle={handleToggleStrategy}
                leverage={leverage}
                setLeverage={setLeverage}
                risk={risk}
                setRisk={setRisk}
                priorityFee={priorityFee}
                setPriorityFee={setPriorityFee}
              />
            </div>
          </div>
        )}
      </div>

      {/* Consent Modal */}
      <ConsentModal
        open={showConsent}
        onOpenChange={setShowConsent}
        onConfirm={handleConsentConfirm}
      />

      {/* Toast Notifications */}
      <Toaster position="top-right" richColors theme="dark" />
    </div>
  );
}

function App() {
  return (
    <WalletContextProvider>
      <AppContent />
    </WalletContextProvider>
  );
}

export default App;