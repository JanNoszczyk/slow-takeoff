// dashboard/src/components/BarChartDisplay.tsx

"use client";
import React from "react";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const defaultData = {
  labels: ["Equities", "Bonds", "Cash", "Real Estate", "Commodities"],
  datasets: [
    {
      label: "Asset Allocation (%)",
      data: [40, 25, 20, 10, 5],
      backgroundColor: [
        "#2563eb",
        "#a21caf",
        "#059669",
        "#f59e42",
        "#eab308"
      ],
      borderRadius: 6,
    },
  ],
};

const defaultOptions = {
  responsive: true,
  plugins: {
    legend: {
      display: false,
    },
    title: {
      display: true,
      text: "Sample Asset Allocation",
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 50,
      ticks: {
        stepSize: 10,
      },
    },
  },
};

const BarChartDisplay: React.FC = () => (
  <div className="bg-white rounded-lg p-4 shadow-md">
    <Bar data={defaultData} options={defaultOptions} />
  </div>
);

export default BarChartDisplay;
