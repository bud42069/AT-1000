import React from 'react';
import { Card } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Badge } from './ui/badge';

export const ActivityLog = ({ logs = [] }) => {
  return (
    <Card className="rounded-2xl bg-[#11161C] border border-[#1E2937] p-6 shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[#C7D2DE]">Activity Log</h2>
        <p className="text-xs text-[#6B7280]">Recent trading events and notifications</p>
      </div>

      <div className="rounded-xl border border-[#1E2937] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-[#1E2937] hover:bg-[#0B0F14]/50">
              <TableHead className="text-[#9AA6B2] font-medium">Time</TableHead>
              <TableHead className="text-[#9AA6B2] font-medium">Type</TableHead>
              <TableHead className="text-[#9AA6B2] font-medium">Details</TableHead>
              <TableHead className="text-[#9AA6B2] font-medium text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-[#6B7280] py-8">
                  No activity yet. Waiting for events...
                </TableCell>
              </TableRow>
            ) : (
              logs.slice(-50).reverse().map((log, i) => (
                <TableRow
                  key={i}
                  data-testid="activity-row"
                  className="border-b border-[#1E2937] hover:bg-[#0B0F14]/50"
                >
                  <TableCell className="font-mono text-xs text-[#C7D2DE]">
                    {new Date(log.time).toLocaleTimeString()}
                  </TableCell>
                  <TableCell className="text-sm text-[#C7D2DE] capitalize">
                    {log.type.replace(/_/g, ' ')}
                  </TableCell>
                  <TableCell className="text-sm text-[#9AA6B2]">{log.details}</TableCell>
                  <TableCell className="text-right">
                    <Badge
                      style={{
                        backgroundColor: log.statusBg,
                        color: '#0B0F14',
                      }}
                      className="font-mono text-xs"
                    >
                      {log.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
};