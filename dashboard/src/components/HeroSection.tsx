// dashboard/src/components/HeroSection.tsx

import React from "react";

const HeroSection: React.FC = () => (
  <section className="w-full bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-500 text-white py-12 px-6 rounded-2xl shadow-lg mb-12 flex flex-col items-center">
    <div className="flex items-center gap-4 mb-4">
      <svg width="48" height="48" fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" fill="#fff" fillOpacity="0.15"/>
        <path d="M7 17l5-5 5 5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M7 7h10" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
      </svg>
      <h1 className="text-4xl font-extrabold tracking-tight drop-shadow-lg">WealthArc Dashboard</h1>
    </div>
    <p className="text-lg font-medium opacity-90 drop-shadow-sm">
      Your financial overview, insights, and inspiration—all in one place.
    </p>
  </section>
);

export default HeroSection;
