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

    {/* KPI cards */}
    <div className="flex flex-col md:flex-row gap-6 justify-center items-stretch">
      <div className="flex-1 min-w-[220px] bg-white rounded-2xl shadow-sm border border-gray-200 px-8 py-4 flex flex-col items-center">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
          Total Portfolios
        </div>
        <div className="text-3xl font-bold text-blue-700">{totalPortfolios}</div>
        <Sparkline data={spTotal} />
      </div>

      <div className="flex-1 min-w-[220px] bg-white rounded-2xl shadow-sm border border-gray-200 px-8 py-4 flex flex-col items-center">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
          Active Positions
        </div>
        <div className="text-3xl font-bold text-blue-700">{activePositions}</div>
        <Sparkline data={spActive} color="#059669" />
      </div>

      <div className="flex-1 min-w-[260px] bg-white rounded-2xl shadow-sm border border-gray-200 px-8 py-4 flex flex-col items-center">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
          Total Value (USD)
        </div>
        <div className="text-3xl font-bold text-blue-700">
          ${totalValue.toLocaleString()}
        </div>
        <div className="flex gap-4 mt-2 text-sm">
          <span className={pctColor(pctQuarter)}>
            {pctIcon(pctQuarter)} QTD {formatPct(pctQuarter)}
          </span>
          <span className={pctColor(pctYear)}>
            {pctIcon(pctYear)} YTD {formatPct(pctYear)}
          </span>
        </div>
        <Sparkline data={spValue} color="#a21caf" />
      </div>
    </div>
  </section>
)};

export default SummaryBar;
