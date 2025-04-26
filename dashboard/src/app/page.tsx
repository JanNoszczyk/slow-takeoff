import TextDisplay from '@/components/TextDisplay';
import ChartDisplay from '@/components/ChartDisplay';
import BarChartDisplay from '@/components/BarChartDisplay';
import SummaryBar from '@/components/SummaryBar';
import StatsSummary from '@/components/StatsSummary';
import MotivationCard from '@/components/MotivationCard';
import Sidebar from '@/components/Sidebar';
import Widget from '@/components/Widget';
import React from 'react';

export default function Home() {
  // Placeholder data based on WealthArc models
  const portfolioData = {
    id: 123,
    name: "Sample Portfolio",
    currency: "USD",
    mandateType: "Discretionary",
  };

  const positionData = {
    id: 456,
    assetId: 789,
    statementDate: "2024-01-26",
    quantity: 100,
    price: 50.75,
    priceCurrency: "USD",
  };

  const portfolioMetricsData = {
    id: 101,
    portfolioId: 123,
    statementDate: "2024-01-26",
    netAmount: 150000.50,
    grossAmount: 155000.75,
    currency: "USD",
  };


  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 flex flex-col items-center justify-between p-6 sm:p-12">
        <SummaryBar
          totalPortfolios={8}
          activePositions={24}
          totalValue={1200000}
          pctQuarter={2.5}
          pctYear={7.8}
        />
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 w-full">
          {/* Portfolio Details */}
          <Widget
            title="Portfolio Details"
            subtitle="Basic information about the selected portfolio"
            accentColor="#2563eb"
          >
            <div className="mb-4 overflow-x-auto">
              <div className="font-semibold text-gray-700 mb-2">Portfolio Attributes</div>
              <table className="min-w-full text-sm border border-gray-200 rounded-xl shadow">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Attribute</th>
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Portfolio ID</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioData.id}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Name</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioData.name}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Currency</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioData.currency}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium">Mandate Type</td>
                    <td className="px-4 py-2 text-gray-900">{portfolioData.mandateType}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-gray-700 text-xs">
              This widget summarizes the core attributes of the selected portfolio, providing a quick reference for its identity, base currency, and mandate type. Such information is essential for context in all subsequent analysis.
            </p>
          </Widget>


          {/* Risk Metrics Deep Dive */}
          <Widget
            title="Risk Metrics Deep Dive"
            subtitle="Key risk indicators and recent trends"
            accentColor="#f59e42"
          >
            <div className="mb-4 overflow-x-auto">
              <div className="font-semibold text-gray-700 mb-2">Risk Metrics</div>
              <table className="min-w-full text-sm border border-gray-200 rounded-xl shadow">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Metric</th>
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Volatility (1Y)</td>
                    <td className="px-4 py-2 text-gray-900 border-b">7.1%</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Max Drawdown</td>
                    <td className="px-4 py-2 text-gray-900 border-b">-5.3%</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium">Sharpe Ratio</td>
                    <td className="px-4 py-2 text-gray-900">1.12</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="mb-4">
              <ChartDisplay />
            </div>
            <p className="text-gray-700 text-xs">
              Risk metrics indicate a well-balanced portfolio: volatility is moderate, and the Sharpe ratio suggests efficient risk-adjusted returns. The recent drawdown was contained, reflecting prudent risk management.
            </p>
          </Widget>

          {/* Sample Position */}
          <Widget
            title="Sample Position"
            subtitle="Details of a representative position"
            accentColor="#059669"
          >
            <div className="mb-4 overflow-x-auto">
              <div className="font-semibold text-gray-700 mb-2">Position Details</div>
              <table className="min-w-full text-sm border border-gray-200 rounded-xl shadow">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Attribute</th>
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Position ID</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{positionData.id}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Asset ID</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{positionData.assetId}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Statement Date</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{positionData.statementDate}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Quantity</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{positionData.quantity}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Price</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{positionData.price}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium">Price Currency</td>
                    <td className="px-4 py-2 text-gray-900">{positionData.priceCurrency}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-gray-700 text-xs">
              This widget details a single position, including quantity and pricing. Such granular data is useful for position-level risk and performance analysis.
            </p>
          </Widget>

          {/* Portfolio Daily Metrics */}
          <Widget
            title="Portfolio Metrics (Latest)"
            subtitle="Latest available portfolio metrics"
            accentColor="#a21caf"
          >
            <div className="mb-4 overflow-x-auto">
              <div className="font-semibold text-gray-700 mb-2">Portfolio Metrics</div>
              <table className="min-w-full text-sm border border-gray-200 rounded-xl shadow">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Attribute</th>
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Metrics ID</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioMetricsData.id}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Portfolio ID</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioMetricsData.portfolioId}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Statement Date</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioMetricsData.statementDate}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Net AuM</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioMetricsData.netAmount}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Gross AuM</td>
                    <td className="px-4 py-2 text-gray-900 border-b">{portfolioMetricsData.grossAmount}</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium">Currency</td>
                    <td className="px-4 py-2 text-gray-900">{portfolioMetricsData.currency}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-gray-700 text-xs">
              The latest portfolio metrics provide a snapshot of assets under management and currency exposure, supporting high-level performance and risk assessment.
            </p>
          </Widget>

          {/* Mini Report Card Example */}
          <Widget
            title="Mini Report: Q1 Performance"
            subtitle="Summary of key metrics, chart, and commentary"
            accentColor="#0ea5e9"
          >
            {/* Table */}
            <div className="mb-4 overflow-x-auto">
              <div className="font-semibold text-gray-700 mb-2">Q1 Performance Metrics</div>
              <table className="min-w-full text-sm border border-gray-200 rounded-xl shadow">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Metric</th>
                    <th className="px-4 py-2 font-semibold text-gray-700 border-b w-1/2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Net Return</td>
                    <td className="px-4 py-2 text-gray-900 border-b">+4.2%</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium border-b">Volatility</td>
                    <td className="px-4 py-2 text-gray-900 border-b">7.1%</td>
                  </tr>
                  <tr className="even:bg-gray-50 hover:bg-blue-50 transition">
                    <td className="px-4 py-2 text-gray-600 font-medium">Sharpe Ratio</td>
                    <td className="px-4 py-2 text-gray-900">1.12</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {/* Chart */}
            <div className="mb-4">
              <ChartDisplay />
            </div>
            {/* Paragraph */}
            <p className="text-gray-700 text-xs">
              Q1 saw steady growth with moderate volatility. The portfolio outperformed its benchmark, driven by strong equity returns and effective risk management.
            </p>
          </Widget>
        </div>

      </main>
    </div>
  );
}
