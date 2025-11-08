{
  "meta": {
    "app_name": "Auto-Trader dApp (Solana · Drift)",
    "app_type": "trading dApp (perps) with automation and delegation",
    "audience": ["crypto-native traders", "quants", "automation-focused power users"],
    "primary_success_actions": [
      "Connect Phantom wallet",
      "Review live telemetry (price, CVD, funding/basis, liquidations)",
      "Enable strategy with leverage/risk sliders",
      "Set risk limits and priority fees",
      "Use emergency stop instantly when needed",
      "Monitor activity log and notifications",
      "Delegate/revoke trading permissions"
    ],
    "brand_attributes": ["precision", "trustworthy", "performant", "calm-under-pressure", "no-neon-glare"]
  },

  "typography": {
    "fonts": {
      "ui_primary": "Inter",
      "numeric_mono": "IBM Plex Mono",
      "fallbacks": "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
    },
    "google_fonts": {
      "links": [
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap"
      ]
    },
    "usage": {
      "headings": "Inter 600–700",
      "body": "Inter 400–500",
      "numbers_prices_sizes_pnl": "IBM Plex Mono (tabular-nums, lining-nums)",
      "css_examples": "font-feature-settings: 'tnum' 1, 'lnum' 1;"
    },
    "text_scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl",
      "h2": "text-base sm:text-lg",
      "body": "text-sm sm:text-base",
      "small": "text-xs sm:text-sm"
    }
  },

  "color_system": {
    "locked_preferences": {
      "background": "#0B0F14",
      "panel": "#11161C",
      "text_soft": "#C7D2DE",
      "accent_lime": "#84CC16",
      "accent_lime_hover": "#A3E635",
      "dividers": "#1E2937",
      "chart_grid": "#1A2430",
      "price_line": "#9AA6B2",
      "states": {
        "success": "#84CC16",
        "warning": "#F59E0B",
        "danger": "#F43F5E",
        "info": "#67E8F9"
      },
      "focus_ring": {
        "color": "#84CC16",
        "width": "1.5px"
      }
    },
    "semantics": {
      "primary": "#84CC16",
      "secondary": "#9AA6B2",
      "muted": "#94A3B8",
      "muted_on_dark": "#6B7280",
      "panel_border": "#1E2937",
      "positive": "#84CC16",
      "negative": "#F43F5E",
      "warning": "#F59E0B",
      "info": "#67E8F9"
    },
    "usage_notes": [
      "Use lime accent only for primary CTAs, toggles-on, and positive PnL.",
      "Charts: grid in #1A2430; price line #9AA6B2; signals/thresholds in lime; liquidation clusters as soft lime halos.",
      "Dividers: 1px #1E2937; shadows: rgba(0,0,0,0.35).",
      "Comply with gradient restriction rule; avoid saturated purple/pink anywhere."
    ]
  },

  "css_custom_properties": {
    "instructions": "Add/override these tokens in src/index.css under :root and .dark. They align Tailwind CSS variables with the locked theme.",
    "snippet": """
@layer base {
  :root {
    --background: 210 30% 5%; /* #0B0F14 */
    --foreground: 213 24% 82%; /* #C7D2DE */
    --card: 210 28% 7%; /* #11161C */
    --card-foreground: 213 24% 82%;
    --popover: 210 28% 7%;
    --popover-foreground: 213 24% 82%;
    --primary: 84 78% 45%; /* #84CC16 */
    --primary-foreground: 210 30% 5%;
    --secondary: 213 17% 63%; /* #9AA6B2 */
    --secondary-foreground: 0 0% 100%;
    --muted: 214 13% 47%; /* #6B7280 */
    --muted-foreground: 214 13% 70%;
    --accent: 84 78% 45%;
    --accent-foreground: 210 30% 5%;
    --destructive: 347 89% 61%; /* #F43F5E */
    --destructive-foreground: 210 30% 5%;
    --border: 213 25% 18%; /* #1E2937 */
    --input: 213 25% 18%;
    --ring: 84 78% 45%;
    --radius: 1rem; /* rounded-2xl */

    /* charts */
    --chart-grid: 214 24% 14%; /* #1A2430 */
    --price-line: 208 16% 63%; /* #9AA6B2 */
    --state-success: 84 78% 45%;
    --state-warning: 36 92% 51%; /* #F59E0B */
    --state-danger: 347 89% 61%;
    --state-info: 189 89% 69%; /* #67E8F9 */

    /* buttons */
    --btn-radius: 0.75rem;
    --btn-shadow: 0 6px 18px rgba(132, 204, 22, 0.18);
    --btn-motion: 120ms ease-out;
  }
  .dark { /* mirror tokens for dark mode class toggle, if used */ }
}
    """
  },

  "layout_grid": {
    "patterns": ["Split-Screen Layout for chart + controls", "Bento Grid for telemetry", "12-column desktop grid, 4-column on md, 2-column on sm"],
    "container": {
      "max_width": "max-w-[1400px]",
      "padding_x": "px-4 sm:px-6 lg:px-8",
      "gaps": "gap-3 sm:gap-4 lg:gap-6"
    },
    "cards": {
      "radius": "rounded-2xl",
      "shadow": "shadow-[0_8px_30px_rgba(0,0,0,0.35)]",
      "padding": "p-3 sm:p-4 lg:p-6",
      "divider": "border-t border-[#1E2937]"
    },
    "page_structure": [
      "Top App Bar: left logo+network badge, center market selector, right wallet/delegation+emergency stop",
      "Primary Row: price chart (7–8 cols) + strategy controls panel (4–5 cols)",
      "Second Row Bento: CVD, funding/basis, liquidation clusters preview, PnL summary",
      "Bottom: Activity log table full width"
    ]
  },

  "components": {
    "WalletConnectModal": {
      "base": "Dialog, Button, Tooltip",
      "imports": ["./components/ui/dialog", "./components/ui/button", "./components/ui/tooltip"],
      "behavior": "Lists wallets (Phantom primary). Shows QR help for mobile. On connect -> show address + network.",
      "data_testids": ["connect-wallet-button", "wallet-option-phantom", "wallet-connected-address"],
      "classes": "rounded-2xl bg-[#11161C] text-[#C7D2DE] border border-[#1E2937]",
      "snippet": """
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './components/ui/dialog';
import { Button } from './components/ui/button';

export const WalletConnectModal = ({ open, onOpenChange, onConnect }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className=\"rounded-2xl bg-[#11161C] border border-[#1E2937]\">
      <DialogHeader>
        <DialogTitle className=\"font-semibold text-[#C7D2DE]\">Connect Wallet</DialogTitle>
      </DialogHeader>
      <div className=\"space-y-3\">
        <Button data-testid=\"wallet-option-phantom\" onClick={onConnect} className=\"w-full rounded-xl bg-[#84CC16] text-[#0B0F14] hover:bg-[#A3E635] focus-visible:ring-2 focus-visible:ring-[#84CC16] transition-colors\">Phantom</Button>
      </div>
    </DialogContent>
  </Dialog>
);
      """
    },

    "ConsentSIWSModal": {
      "base": "Dialog + Checkbox + Button",
      "imports": ["./components/ui/dialog", "./components/ui/checkbox", "./components/ui/button"],
      "data_testids": ["siws-accept-terms-checkbox", "siws-continue-button"],
      "notes": "User must accept terms before enabling automation.",
      "snippet": """
import { Checkbox } from './components/ui/checkbox';
import { Button } from './components/ui/button';

export const ConsentSIWSBody = ({ checked, setChecked, onConfirm }) => (
  <div className=\"space-y-4\">
    <label className=\"flex items-center gap-3 text-sm text-[#C7D2DE]\">
      <Checkbox data-testid=\"siws-accept-terms-checkbox\" checked={checked} onCheckedChange={setChecked} />
      I agree to the Terms and authorize delegated trading.
    </label>
    <Button data-testid=\"siws-continue-button\" disabled={!checked} onClick={onConfirm} className=\"rounded-xl bg-[#84CC16] text-[#0B0F14] hover:bg-[#A3E635]\">Continue</Button>
  </div>
);
      """
    },

    "TopBar": {
      "base": "Card + Button + Badge + Separator + DropdownMenu",
      "imports": ["./components/ui/card", "./components/ui/button", "./components/ui/badge", "./components/ui/separator", "./components/ui/dropdown-menu"],
      "layout": "grid grid-cols-12 items-center gap-3",
      "content": "logo/network left (cols 3), market selector center (cols 6), wallet+delegation+emergency stop right (cols 3)",
      "data_testids": ["market-selector", "delegation-status-badge", "emergency-stop-button"],
      "micro_interaction": "Emergency button glows on hover (rose), confirmation via AlertDialog",
      "snippet": """
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogCancel, AlertDialogAction, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription } from './components/ui/alert-dialog';
import { Button } from './components/ui/button';

export const EmergencyStop = ({ onConfirm }) => (
  <AlertDialog>
    <AlertDialogTrigger asChild>
      <Button data-testid=\"emergency-stop-button\" className=\"rounded-xl bg-[#F43F5E] text-white hover:bg-[#fb7185] focus-visible:ring-2 focus-visible:ring-[#F43F5E] transition-colors\">Emergency Stop</Button>
    </AlertDialogTrigger>
    <AlertDialogContent className=\"rounded-2xl bg-[#11161C] border border-[#1E2937]\">
      <AlertDialogHeader>
        <AlertDialogTitle className=\"text-[#C7D2DE]\">Confirm Emergency Stop</AlertDialogTitle>
        <AlertDialogDescription>Immediately cancel orders and disable automation.</AlertDialogDescription>
      </AlertDialogHeader>
      <div className=\"flex justify-end gap-3\">
        <AlertDialogCancel className=\"rounded-xl bg-transparent border border-[#1E2937]\">Cancel</AlertDialogCancel>
        <AlertDialogAction onClick={onConfirm} className=\"rounded-xl bg-[#F43F5E] hover:bg-[#fb7185]\">Confirm</AlertDialogAction>
      </div>
    </AlertDialogContent>
  </AlertDialog>
);
      """
    },

    "StrategyControls": {
      "base": "Card + Switch + Slider + Select",
      "imports": ["./components/ui/card", "./components/ui/switch", "./components/ui/slider", "./components/ui/select", "./components/ui/label"],
      "data_testids": ["strategy-toggle", "leverage-slider", "risk-slider", "priority-fee-slider"],
      "notes": "Place in right rail panel. Use lime when ON.",
      "classes": "space-y-4",
      "snippet": """
import { Card } from './components/ui/card';
import { Switch } from './components/ui/switch';
import { Slider } from './components/ui/slider';
import { Label } from './components/ui/label';

export const StrategyControls = ({ enabled, onToggle, leverage, setLeverage, risk, setRisk, fee, setFee }) => (
  <Card className=\"rounded-2xl bg-[#11161C] border border-[#1E2937] p-4 space-y-6\">
    <div className=\"flex items-center justify-between\">
      <span className=\"text-sm text-[#C7D2DE]\">Automation</span>
      <Switch data-testid=\"strategy-toggle\" checked={enabled} onCheckedChange={onToggle} className=\"data-[state=checked]:bg-[#84CC16]\" />
    </div>
    <div>
      <div className=\"flex items-center justify-between mb-2\"><Label>Leverage</Label><span className=\"font-mono text-sm\">{leverage}x</span></div>
      <Slider data-testid=\"leverage-slider\" value={[leverage]} onValueChange={(v)=>setLeverage(v[0])} min={1} max={25} step={1} />
    </div>
    <div>
      <div className=\"flex items-center justify-between mb-2\"><Label>Risk %</Label><span className=\"font-mono text-sm\">{risk}%</span></div>
      <Slider data-testid=\"risk-slider\" value={[risk]} onValueChange={(v)=>setRisk(v[0])} min={0} max={5} step={0.25} />
    </div>
    <div>
      <div className=\"flex items-center justify-between mb-2\"><Label>Priority Fee (microlamports)</Label><span className=\"font-mono text-sm\">{fee}</span></div>
      <Slider data-testid=\"priority-fee-slider\" value={[fee]} onValueChange={(v)=>setFee(v[0])} min={0} max={5000} step={50} />
    </div>
  </Card>
);
      """
    },

    "ActivityLogTable": {
      "base": "Table",
      "imports": ["./components/ui/table"],
      "data_testids": ["activity-row", "activity-error-badge"],
      "states": "Render types: order, fill, stop, error (use state colors)",
      "snippet": """
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './components/ui/table';

export const ActivityLogTable = ({ rows }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Time</TableHead>
        <TableHead>Type</TableHead>
        <TableHead>Details</TableHead>
        <TableHead>Status</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {rows.map((r, i) => (
        <TableRow key={i} data-testid=\"activity-row\">
          <TableCell className=\"font-mono\">{r.time}</TableCell>
          <TableCell>{r.type}</TableCell>
          <TableCell>{r.details}</TableCell>
          <TableCell>
            <span className=\"px-2 py-0.5 rounded text-xs\" style={{backgroundColor: r.statusBg, color: '#0B0F14'}}>
              {r.status}
            </span>
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);
      """
    },

    "DelegationBadge": {
      "base": "Badge + Button",
      "imports": ["./components/ui/badge", "./components/ui/button"],
      "states": ["active", "inactive"],
      "data_testids": ["delegation-status-badge", "revoke-delegation-button"],
      "snippet": """
import { Badge } from './components/ui/badge';
import { Button } from './components/ui/button';

export const DelegationBadge = ({ active, onRevoke }) => (
  <div className=\"flex items-center gap-2\">
    <Badge data-testid=\"delegation-status-badge\" className=\"rounded-md\" style={{backgroundColor: active ? '#84CC16' : '#1E2937', color: active ? '#0B0F14' : '#C7D2DE'}}>
      {active ? 'Delegation: Active' : 'Delegation: Inactive'}
    </Badge>
    {active && (
      <Button data-testid=\"revoke-delegation-button\" variant=\"outline\" className=\"border-[#1E2937] text-[#C7D2DE] hover:bg-[#1E2937]\" onClick={onRevoke}>Revoke</Button>
    )}
  </div>
);
      """
    },

    "NotificationsToaster": {
      "base": "Sonner",
      "imports": ["./components/ui/sonner"],
      "note": "Use for order fills, errors, and risk alerts.",
      "snippet": """
import { Toaster, toast } from './components/ui/sonner';
export const notifyFill = (msg) => toast.success(msg);
export const notifyError = (msg) => toast.error(msg);
export const NotificationsToaster = () => <Toaster position=\"top-right\" richColors />;
      """
    }
  },

  "data_visualization": {
    "libraries": ["Recharts for price/CVD/funding", "D3 for liquidation heatmap halos"],
    "install": "npm i recharts d3 framer-motion @solana/web3.js @solana/wallet-adapter-react @solana/wallet-adapter-phantom",
    "chart_theme": {
      "grid_color": "#1A2430",
      "price_line": "#9AA6B2",
      "accent": "#84CC16",
      "down": "#F43F5E",
      "up": "#84CC16"
    },
    "price_and_cvd_scaffold": """
// Price + CVD (Recharts)
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, BarChart, Bar } from 'recharts';

export const PriceCVDPanel = ({ data }) => (
  <div className=\"rounded-2xl bg-[#11161C] border border-[#1E2937] p-3\">
    <ResponsiveContainer width=\"100%\" height={320}>
      <LineChart data={data} margin={{ left: 12, right: 12, top: 8, bottom: 8 }}>
        <CartesianGrid stroke=\"#1A2430\" strokeDasharray=\"3 3\" />
        <XAxis dataKey=\"t\" stroke=\"#6B7280\" tick={{ fontSize: 12 }} />
        <YAxis yAxisId=\"left\" stroke=\"#6B7280\" tick={{ fontSize: 12 }} />
        <YAxis yAxisId=\"right\" orientation=\"right\" stroke=\"#6B7280\" tick={{ fontSize: 12 }} />
        <Tooltip contentStyle={{ background: '#0B0F14', border: '1px solid #1E2937' }} labelStyle={{ color: '#C7D2DE' }} />
        <Line yAxisId=\"left\" type=\"monotone\" dataKey=\"price\" stroke=\"#9AA6B2\" strokeWidth={1.5} dot={false} />
        <Line yAxisId=\"right\" type=\"monotone\" dataKey=\"cvd\" stroke=\"#84CC16\" strokeWidth={1.25} dot={false} />
      </LineChart>
    </ResponsiveContainer>
    <div className=\"mt-3\">
      <ResponsiveContainer width=\"100%\" height={80}>
        <BarChart data={data}>
          <CartesianGrid horizontal={false} />
          <XAxis dataKey=\"t\" hide />
          <YAxis hide />
          <Bar dataKey=\"delta\" fill=\"#84CC16\" radius={[4,4,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);
    """,
    "liquidation_heatmap_scaffold": """
// Liquidation clusters heatmap (D3)
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

export const LiquidationHeatmap = ({ points = [] /* {price, intensity} */ }) => {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const width = el.clientWidth, height = el.clientHeight;
    const svg = d3.select(el).append('svg').attr('width', width).attr('height', height);
    const y = d3.scaleLinear().domain(d3.extent(points, d => d.price)).range([height-8, 8]);
    // halos
    svg.selectAll('g.cluster').data(points).join('g').attr('class','cluster')
      .append('circle')
      .attr('cx', width/2)
      .attr('cy', d => y(d.price))
      .attr('r', d => 4 + d.intensity * 10)
      .style('fill', '#84CC16')
      .style('opacity', 0.15);
    return () => { svg.remove(); };
  }, [points]);
  return <div ref={ref} className=\"rounded-2xl bg-[#11161C] border border-[#1E2937] h-72\" />;
};
    """,
    "empty_states": {
      "text": "No live data yet. Waiting for stream...",
      "classes": "text-sm text-[#6B7280] font-medium"
    }
  },

  "motion_and_microinteractions": {
    "principles": [
      "100–150ms ease-out for hover/press",
      "Focus-visible ring lime 1.5px",
      "Micro glow only on primary CTAs (box-shadow: var(--btn-shadow))",
      "Charts and telemetry fade-in on mount",
      "Parallax: subtle scroll-based transform on dashboard header background texture"
    ],
    "framer_motion_scaffold": """
import { motion } from 'framer-motion';
export const FadeIn = ({ children, delay = 0 }) => (
  <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay, ease: 'easeOut' }}>
    {children}
  </motion.div>
);
    """
  },

  "accessibility": {
    "contrast": "Maintain WCAG AA minimum (lime on graphite easily passes).",
    "focus": "Use focus-visible with lime ring; never rely on color only.",
    "keyboard": "All modals/dialogs trap focus and close with ESC; sliders/arrows accessible.",
    "labels": "Every control must have an associated Label, aria- attributes where appropriate.",
    "reduce_motion": "Respect prefers-reduced-motion and reduce entrance animations"
  },

  "testing_and_qa": {
    "data_testid_rule": "All interactive and key informational elements MUST include a data-testid attribute using kebab-case and role-based naming.",
    "examples": [
      "data-testid=\"connect-wallet-button\"",
      "data-testid=\"strategy-toggle\"",
      "data-testid=\"emergency-stop-button\"",
      "data-testid=\"activity-row\"",
      "data-testid=\"delegation-status-badge\""
    ]
  },

  "libraries_and_setup": {
    "packages": [
      "recharts",
      "d3",
      "framer-motion",
      "@solana/web3.js",
      "@solana/wallet-adapter-react",
      "@solana/wallet-adapter-phantom"
    ],
    "install": "npm i recharts d3 framer-motion @solana/web3.js @solana/wallet-adapter-react @solana/wallet-adapter-phantom",
    "wallet_connect_scaffold": """
import { ConnectionProvider, WalletProvider, useWallet } from '@solana/wallet-adapter-react';
import { PhantomWalletAdapter } from '@solana/wallet-adapter-phantom';

export const WalletGate = ({ children }) => {
  const wallets = [new PhantomWalletAdapter()];
  return (
    <ConnectionProvider endpoint=\"https://api.mainnet-beta.solana.com\"> 
      <WalletProvider wallets={wallets} autoConnect>
        {children}
      </WalletProvider>
    </ConnectionProvider>
  );
};

export const ConnectButton = () => {
  const { connected, connect, publicKey } = useWallet();
  if (connected) return <div className=\"font-mono text-xs\" data-testid=\"wallet-connected-address\">{publicKey?.toBase58().slice(0,4)}…{publicKey?.toBase58().slice(-4)}</div>;
  return <button data-testid=\"connect-wallet-button\" onClick={connect} className=\"rounded-xl px-4 py-2 bg-[#84CC16] text-[#0B0F14] hover:bg-[#A3E635]\">Connect</button>;
};
    """
  },

  "image_urls": [
    {
      "url": "https://images.unsplash.com/photo-1759185301753-e63dd521c597?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzd8MHwxfHNlYXJjaHwxfHxkYXJrJTIwYWJzdHJhY3QlMjBncmlkJTIwdGV4dHVyZSUyMGdyYXBoaXRlJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NjI1NzIzNTJ8MA&ixlib=rb-4.1.0&q=85",
      "category": "texture/background",
      "where": "global body background subtle texture overlay (opacity 0.08)",
      "description": "Dark graphite woven fabric texture (avoid gradient; boosts depth on large screens)."
    },
    {
      "url": "https://images.unsplash.com/photo-1740345688853-e30046759b5e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzd8MHwxfHNlYXJjaHwyfHxkYXJrJTIwYWJzdHJhY3QlMjBncmlkJTIwdGV4dHVyZSUyMGdyYXBoaXRlJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NjI1NzIzNTJ8MA&ixlib=rb-4.1.0&q=85",
      "category": "decor",
      "where": "dashboard header parallax background (cover <20% viewport)",
      "description": "Fractal linework texture; use very low opacity with parallax transform."
    },
    {
      "url": "https://images.unsplash.com/photo-1568092822270-bacac1aa4d41?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzd8MHwxfHNlYXJjaHwzfHxkYXJrJTIwYWJzdHJhY3QlMjBncmlkJTIwdGV4dHVyZSUyMGdyYXBoaXRlJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NjI1NzIzNTJ8MA&ixlib=rb-4.1.0&q=85",
      "category": "empty-states",
      "where": "empty widget backgrounds",
      "description": "Concrete interwoven pattern for empty states (soft vignette)."
    }
  ],

  "component_path": {
    "button": "./components/ui/button",
    "card": "./components/ui/card",
    "dialog": "./components/ui/dialog",
    "alert_dialog": "./components/ui/alert-dialog",
    "checkbox": "./components/ui/checkbox",
    "switch": "./components/ui/switch",
    "slider": "./components/ui/slider",
    "table": "./components/ui/table",
    "badge": "./components/ui/badge",
    "separator": "./components/ui/separator",
    "dropdown_menu": "./components/ui/dropdown-menu",
    "tabs": "./components/ui/tabs",
    "select": "./components/ui/select",
    "tooltip": "./components/ui/tooltip",
    "sonner": "./components/ui/sonner"
  },

  "instructions_to_main_agent": [
    "Install required packages (recharts, d3, framer-motion, wallet adapter).",
    "Add Google Fonts links for Inter and IBM Plex Mono to index.html head.",
    "Override Tailwind CSS tokens in src/index.css with provided css_custom_properties snippet.",
    "Set body background to #0B0F14 and apply subtle noise/texture image at low opacity (do not exceed 20% viewport coverage).",
    "Build TopBar with ConnectButton, DelegationBadge, and EmergencyStop. Ensure data-testid attributes exactly match provided names.",
    "Implement StrategyControls in right rail using Switch and Sliders with lime ON state.",
    "Create Dashboard rows: PriceCVDPanel (Recharts), Bento cards (CVD, funding/basis, liquidation preview), ActivityLogTable bottom.",
    "Use Sonner for notifications; mount <NotificationsToaster /> once at root.",
    "Respect motion rules: specific transitions only; no 'transition: all'.",
    "Adhere to gradient restriction rule and color usage notes strictly.",
    "Ensure all interactive elements and key informational texts include data-testid attributes for E2E testing.",
    "Use rounded-2xl, 1px #1E2937 borders, and rgba(0,0,0,0.35) shadows across cards.",
    "Mobile-first: stack controls below chart, collapse bento to 2-col then 1-col on small screens.",
    "Use monospace (IBM Plex Mono) for all numeric values in tables, sliders readouts, and charts axes labels.",
    "Use success/warn/danger/info state colors for statuses and alerts consistently.",
    "Emergency Stop must always be visible in TopBar on all breakpoints."
  ]
}


<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>
