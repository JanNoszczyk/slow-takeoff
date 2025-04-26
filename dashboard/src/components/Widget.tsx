// dashboard/src/components/InfoCard.tsx

import React from "react";

interface WidgetProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  children: React.ReactNode;
}

const Widget: React.FC<WidgetProps> = ({
  title,
  subtitle,
  accentColor = "#2563eb",
  children,
}) => (
  <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex flex-col min-w-[260px] min-h-[240px]">
    {/* Uni-body header bar */}
    <div
      className="rounded-t-2xl px-6 py-4"
      style={{
        background: accentColor,
        color: "#fff",
      }}
    >
      <h2 className="text-lg font-semibold">{title}</h2>
      {subtitle && (
        <h3 className="text-sm font-medium opacity-80 mt-1">{subtitle}</h3>
      )}
    </div>
    <div className="flex-1 px-6 py-6">
      {children}
    </div>
  </div>
);

export default Widget;
