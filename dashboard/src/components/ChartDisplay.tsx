// dashboard/src/components/ChartDisplay.tsx

"use client";
import React from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const defaultData = {
  labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
  datasets: [
    {
      label: "Sample Data",
      data: [12, 19, 3, 5, 2, 3],
      fill: false,
      borderColor: "#2563eb",
      backgroundColor: "#2563eb",
      tension: 0.4,
    },
  ],
};

const defaultOptions = {
  responsive: true,
  plugins: {
    legend: {
      display: true,
      position: "top" as const,
    },
    title: {
      display: true,
      text: "Default Line Chart",
    },
  },
};

const ChartDisplay: React.FC = () => (
  <div className="bg-white rounded-lg p-4 shadow-md">
    <Line data={defaultData} options={defaultOptions} />
  </div>
);

export default ChartDisplay;
