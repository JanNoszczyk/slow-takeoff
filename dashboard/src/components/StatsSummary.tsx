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
  <section className="w-full flex justify-center items-center mb-12">
    <div className="w-full max-w-2xl">
      <div className="overflow-hidden rounded-2xl shadow border border-gray-200">
        <div className="min-w-full divide-y divide-gray-200 bg-white">
          {stats.map((stat, idx) => (
            <div
              key={stat.label}
              className={`flex items-center gap-4 px-6 py-4 ${idx % 2 === 0 ? "bg-gray-50" : "bg-white"} hover:bg-blue-50 transition`}
              style={{ minWidth: 220 }}
            >
              <div className="flex-shrink-0">{stat.icon}</div>
              <div className="flex-1">
                <div className="text-xl font-bold text-gray-900">{stat.value}</div>
                <div className="text-sm font-medium text-gray-500">{stat.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  </section>
);

export default StatsSummary;
