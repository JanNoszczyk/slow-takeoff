"use client";
// dashboard/src/components/SummaryBar.tsx

import React, { useState } from "react";
import Sparkline from "./Sparkline";

interface SummaryBarProps {
  totalPortfolios: number;
  activePositions: number;
  totalValue: number;
  pctQuarter: number;
  pctYear: number;
}

const formatPct = (pct: number) =>
  `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;

const pctColor = (pct: number) =>
  pct > 0 ? "text-green-600" : pct < 0 ? "text-red-600" : "text-gray-500";

const pctIcon = (pct: number) =>
  pct > 0 ? (
    <svg className="inline w-4 h-4" fill="none" viewBox="0 0 24 24">
      <path d="M12 5v14M5 12l7-7 7 7" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ) : pct < 0 ? (
    <svg className="inline w-4 h-4" fill="none" viewBox="0 0 24 24">
      <path d="M12 19V5M5 12l7 7 7-7" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ) : null;

const SummaryBar: React.FC<SummaryBarProps> = ({
  totalPortfolios,
  activePositions,
  totalValue,
  pctQuarter,
  pctYear,
}) => {
  const [range, setRange] = useState("1M");

  // placeholder sparkline datasets
  const spTotal = [5, 6, 6, 7, 8, 9, 10];
  const spActive = [15, 14, 16, 18, 17, 19, 20];
  const spValue = [900, 920, 915, 930, 940, 960, 980];

  return (
  <section className="w-full bg-white/90 backdrop-blur border-b border-gray-200 px-6 py-3 mb-8 flex flex-col gap-4">
    {/* Prompt row */}
    <div className="flex w-full items-center gap-4">
      <input
        type="text"
        placeholder="Describe what you want to see…"
        className="flex-1 md:w-96 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <select
        value={range}
        onChange={(e) => setRange(e.target.value)}
        className="text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="1D">Today</option>
        <option value="1W">1&nbsp;Week</option>
        <option value="1M">1&nbsp;Month</option>
        <option value="YTD">YTD</option>
      </select>
    </div>

    {/* Unified blue KPI bar */}
    <div className="w-full rounded-2xl bg-blue-700 flex flex-row justify-between items-start gap-8 px-10 py-6 mb-2 shadow-md">
      <div className="flex flex-col items-start flex-1 min-w-[160px]">
        <div className="text-lg uppercase tracking-wide text-blue-100 mb-1 font-semibold" style={{ fontSize: "1.35rem" }}>
          Total Portfolios
        </div>
        <div className="text-5xl font-extrabold text-white leading-tight">{totalPortfolios}</div>
      </div>
      <div className="flex flex-col items-start flex-1 min-w-[160px]">
        <div className="text-lg uppercase tracking-wide text-blue-100 mb-1 font-semibold" style={{ fontSize: "1.35rem" }}>
          Active Positions
        </div>
        <div className="text-5xl font-extrabold text-white leading-tight">{activePositions}</div>
      </div>
      <div className="flex flex-col items-start flex-1 min-w-[220px]">
        <div className="text-lg uppercase tracking-wide text-blue-100 mb-1 font-semibold" style={{ fontSize: "1.35rem" }}>
          Total Value (USD)
        </div>
        <div className="text-5xl font-extrabold text-white leading-tight">
          ${totalValue.toLocaleString()}
        </div>
        <div className="flex gap-6 mt-2 text-base">
          <span className={pctQuarter > 0 ? "text-green-200" : pctQuarter < 0 ? "text-red-200" : "text-blue-100"}>
            {pctIcon(pctQuarter)} QTD {formatPct(pctQuarter)}
          </span>
          <span className={pctYear > 0 ? "text-green-200" : pctYear < 0 ? "text-red-200" : "text-blue-100"}>
            {pctIcon(pctYear)} YTD {formatPct(pctYear)}
          </span>
        </div>
      </div>
    </div>
  </section>
)};

export default SummaryBar;
