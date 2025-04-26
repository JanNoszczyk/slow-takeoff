// dashboard/src/components/StatsSummary.tsx

import React from "react";

const stats = [
  {
    label: "Total Portfolios",
    value: 8,
    icon: (
      <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
        <rect x="3" y="3" width="7" height="7" rx="2" fill="#2563eb"/>
        <rect x="14" y="3" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
        <rect x="14" y="14" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
        <rect x="3" y="14" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
      </svg>
    ),
    color: "bg-white text-blue-700 border border-gray-200"
  },
  {
    label: "Active Positions",
    value: 24,
    icon: (
      <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
        <rect x="8" y="11" width="8" height="6" rx="1" fill="#2563eb"/>
        <path d="M4 17V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10" stroke="#2563eb" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    color: "bg-white text-blue-700 border border-gray-200"
  },
  {
    label: "Total Value (USD)",
    value: "$1.2M",
    icon: (
      <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
        <rect x="3" y="13" width="4" height="8" rx="1" fill="#2563eb"/>
        <rect x="10" y="9" width="4" height="12" rx="1" fill="#2563eb" fillOpacity="0.7"/>
        <rect x="17" y="5" width="4" height="16" rx="1" fill="#2563eb" fillOpacity="0.4"/>
      </svg>
    ),
    color: "bg-white text-blue-700 border border-gray-200"
  }
];

const StatsSummary: React.FC = () => (
  <section className="w-full flex flex-col sm:flex-row gap-6 justify-center items-center mb-12">
    {stats.map((stat, idx) => (
      <div
        key={stat.label}
        className={`flex items-center gap-3 px-6 py-4 rounded-xl shadow-sm transition-transform hover:scale-105 ${stat.color}`}
        style={{ minWidth: 220 }}
      >
        <div>{stat.icon}</div>
        <div>
          <div className="text-2xl font-bold">{stat.value}</div>
          <div className="text-sm font-medium opacity-80">{stat.label}</div>
        </div>
      </div>
    ))}
  </section>
);

export default StatsSummary;
