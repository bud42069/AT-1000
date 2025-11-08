import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { Label } from './ui/label';
import { Separator } from './ui/separator';
import { AlertTriangle } from 'lucide-react';

export const ConsentModal = ({ open, onOpenChange, onConfirm }) => {
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [acceptedRisks, setAcceptedRisks] = useState(false);

  const canContinue = acceptedTerms && acceptedRisks;

  const handleConfirm = () => {
    if (canContinue) {
      onConfirm();
      setAcceptedTerms(false);
      setAcceptedRisks(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl bg-[#11161C] border border-[#1E2937] max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-[#C7D2DE] flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
            Consent & Risk Disclosure
          </DialogTitle>
          <DialogDescription className="text-[#9AA6B2]">
            Please read and accept the following before enabling automated trading.
          </DialogDescription>
        </DialogHeader>

        <Separator className="bg-[#1E2937]" />

        <div className="space-y-6 max-h-96 overflow-y-auto pr-2">
          {/* Terms */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-[#C7D2DE]">Terms of Service</h3>
            <ul className="text-sm text-[#9AA6B2] space-y-2 list-disc list-inside">
              <li>This is a <strong className="text-[#C7D2DE]">non-custodial</strong> application. Your keys remain with you.</li>
              <li>Delegation authority is <strong className="text-[#C7D2DE]">scoped</strong> to placing and canceling orders only.</li>
              <li>The delegate <strong className="text-[#C7D2DE]">cannot withdraw</strong> funds from your account.</li>
              <li>You can <strong className="text-[#C7D2DE]">revoke delegation</strong> at any time via the UI.</li>
              <li>Automated trading executes within your configured risk limits.</li>
            </ul>
          </div>

          <Separator className="bg-[#1E2937]" />

          {/* Risks */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-[#C7D2DE]">Risk Warnings</h3>
            <ul className="text-sm text-[#9AA6B2] space-y-2 list-disc list-inside">
              <li><strong className="text-[#F59E0B]">High Risk:</strong> Automated trading can result in significant losses, especially during volatile markets.</li>
              <li><strong className="text-[#F59E0B]">Leverage:</strong> Using leverage amplifies both gains and losses.</li>
              <li><strong className="text-[#F59E0B]">Execution:</strong> Orders may be delayed or fail during network congestion.</li>
              <li><strong className="text-[#F59E0B]">No Guarantees:</strong> Past performance does not indicate future results.</li>
              <li><strong className="text-[#F59E0B]">Fees:</strong> Priority fees and trading fees apply to all transactions.</li>
            </ul>
          </div>

          <Separator className="bg-[#1E2937]" />

          {/* Disclaimer */}
          <div className="p-4 rounded-xl bg-[#0B0F14] border border-[#1E2937]">
            <p className="text-xs text-[#6B7280] leading-relaxed">
              This application is provided "as is" without any warranties. It is not financial advice.
              You are solely responsible for your trading decisions and their outcomes.
            </p>
          </div>
        </div>

        <Separator className="bg-[#1E2937]" />

        {/* Acceptance Checkboxes */}
        <div className="space-y-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <Checkbox
              data-testid="siws-accept-terms-checkbox"
              checked={acceptedTerms}
              onCheckedChange={setAcceptedTerms}
              className="mt-0.5"
            />
            <div className="flex-1">
              <Label className="text-sm text-[#C7D2DE] cursor-pointer">
                I have read and accept the Terms of Service
              </Label>
            </div>
          </label>

          <label className="flex items-start gap-3 cursor-pointer">
            <Checkbox
              checked={acceptedRisks}
              onCheckedChange={setAcceptedRisks}
              className="mt-0.5"
            />
            <div className="flex-1">
              <Label className="text-sm text-[#C7D2DE] cursor-pointer">
                I understand the risks and authorize delegated trading
              </Label>
            </div>
          </label>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="rounded-xl border-[#1E2937] text-[#C7D2DE] hover:bg-[#1E2937]"
          >
            Cancel
          </Button>
          <Button
            data-testid="siws-continue-button"
            disabled={!canContinue}
            onClick={handleConfirm}
            className="rounded-xl bg-[#84CC16] text-[#0B0F14] hover:bg-[#A3E635] disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
          >
            Continue
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};