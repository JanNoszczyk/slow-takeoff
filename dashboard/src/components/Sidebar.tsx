// dashboard/src/components/Sidebar.tsx

import React from "react";

const navItems = [
  {
    label: "Dashboard",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <rect x="3" y="3" width="7" height="7" rx="2" fill="#2563eb"/>
        <rect x="14" y="3" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
        <rect x="14" y="14" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
        <rect x="3" y="14" width="7" height="7" rx="2" fill="#2563eb" fillOpacity="0.2"/>
      </svg>
    ),
  },
  {
    label: "Portfolios",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <rect x="3" y="7" width="18" height="10" rx="2" fill="#2563eb" fillOpacity="0.2"/>
        <rect x="7" y="3" width="10" height="18" rx="2" fill="#2563eb"/>
      </svg>
    ),
  },
  {
    label: "Positions",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <path d="M4 17V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10" stroke="#2563eb" strokeWidth="2" strokeLinecap="round"/>
        <rect x="8" y="11" width="8" height="6" rx="1" fill="#2563eb"/>
      </svg>
    ),
  },
  {
    label: "Analytics",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <rect x="3" y="13" width="4" height="8" rx="1" fill="#2563eb"/>
        <rect x="10" y="9" width="4" height="12" rx="1" fill="#2563eb" fillOpacity="0.7"/>
        <rect x="17" y="5" width="4" height="16" rx="1" fill="#2563eb" fillOpacity="0.4"/>
      </svg>
    ),
  },
  {
    label: "Transactions",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <path d="M4 12h16M12 4v16" stroke="#2563eb" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    label: "Settings",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="3" fill="#2563eb"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 8.6 15a1.65 1.65 0 0 0-1.82-.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0 .33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 15.4 9c.14.14.3.26.47.33" stroke="#2563eb" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
];

const Sidebar: React.FC = () => (
  <aside className="flex flex-col w-56 h-screen bg-blue-50 border-r border-blue-100 shadow-md py-8 px-4">
    <div className="mb-10 flex items-center gap-2 px-2">
      <span className="text-2xl font-extrabold text-blue-700 tracking-tight">no<span className="font-light">name</span></span>
    </div>
    <nav className="flex-1">
      <ul className="space-y-2">
        {navItems.map((item) => (
          <li key={item.label}>
            <a
              href="#"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-700 font-medium transition"
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
    <div className="mt-auto pt-8 border-t border-gray-100 text-xs text-gray-400 px-2">
      &copy; {new Date().getFullYear()} noname
    </div>
  </aside>
);

export default Sidebar;
