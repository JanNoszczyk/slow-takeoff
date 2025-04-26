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
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Portfolio ID</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioData.id}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Name</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioData.name}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Currency</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioData.currency}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Mandate Type</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioData.mandateType}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-gray-700 text-xs">
              This widget summarizes the core attributes of the selected portfolio, providing a quick reference for its identity, base currency, and mandate type. Such information is essential for context in all subsequent analysis.
            </p>
          </Widget>

          {/* Asset Allocation Overview */}
          <Widget
            title="Asset Allocation Overview"
            subtitle="Distribution of portfolio assets by class"
            accentColor="#0d9488"
          >
            <div className="mb-4 overflow-x-auto">
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Asset Class</th>
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Allocation</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Equities</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">54%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Fixed Income</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">28%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Alternatives</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">12%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Cash</td>
                    <td className="px-2 py-1 font-medium text-gray-900">6%</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="mb-4">
              <BarChartDisplay />
            </div>
            <p className="text-gray-700 text-xs">
              The portfolio is equity-heavy, with over half of assets in stocks, providing growth potential but also higher volatility. Fixed income and alternatives offer diversification, while cash reserves remain modest, supporting liquidity.
            </p>
          </Widget>

          {/* Risk Metrics Deep Dive */}
          <Widget
            title="Risk Metrics Deep Dive"
            subtitle="Key risk indicators and recent trends"
            accentColor="#f59e42"
          >
            <div className="mb-4 overflow-x-auto">
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Metric</th>
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Volatility (1Y)</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">7.1%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Max Drawdown</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">-5.3%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Sharpe Ratio</td>
                    <td className="px-2 py-1 font-medium text-gray-900">1.12</td>
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
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Position ID</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.id}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Asset ID</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.assetId}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Statement Date</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.statementDate}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Quantity</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.quantity}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Price</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.price}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Price Currency</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{positionData.priceCurrency}</td>
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
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Metrics ID</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.id}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Portfolio ID</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.portfolioId}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Statement Date</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.statementDate}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Net AuM</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.netAmount}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Gross AuM</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.grossAmount}</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Currency</td>
                    <td className="px-2 py-1 font-medium text-gray-900">{portfolioMetricsData.currency}</td>
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
              <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Metric</th>
                    <th className="px-2 py-1 font-semibold text-gray-700 border-b">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Net Return</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">+4.2%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600 border-b">Volatility</td>
                    <td className="px-2 py-1 font-medium text-gray-900 border-b">7.1%</td>
                  </tr>
                  <tr>
                    <td className="px-2 py-1 text-gray-600">Sharpe Ratio</td>
                    <td className="px-2 py-1 font-medium text-gray-900">1.12</td>
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

        {/* Default Chart */}
        <div className="w-full mt-12 max-w-2xl">
          <ChartDisplay />
        </div>

        {/* Bar Chart */}
        <div className="w-full mt-8 max-w-2xl">
          <BarChartDisplay />
        </div>
      </main>
    </div>
  );
}
