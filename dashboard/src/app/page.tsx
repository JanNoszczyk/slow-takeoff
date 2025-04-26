'use client';

import React, { useState, FormEvent } from 'react';
import { StockDashboardData } from '../../types/dashboard';
import StockDashboardDisplay from '../components/StockDashboardDisplay';

export default function Home() {
  const [stockQuery, setStockQuery] = useState<string>('');
  const [dashboardData, setDashboardData] = useState<StockDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setDashboardData(null);
    setError(null);

    try {
      const response = await fetch('/api/generate-dashboard', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ stockQuery }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data: StockDashboardData = await response.json();
      setDashboardData(data);

    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(`Failed to fetch dashboard data: ${err.message}`);
      } else {
        setError('An unexpected error occurred.');
      }
      console.error(err); // Log the error for debugging
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-12 bg-slate-50">
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Stock Research Dashboard</h1>

      <form onSubmit={handleSubmit} className="mb-8 w-full max-w-md flex gap-2">
        <input
          type="text"
          value={stockQuery}
          onChange={(e) => setStockQuery(e.target.value)}
          placeholder="Enter stock symbol (e.g., NVDA)"
          className="flex-grow p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          disabled={isLoading || !stockQuery.trim()}
        >
          {isLoading ? 'Loading...' : 'Get Dashboard'}
        </button>
      </form>

      {isLoading && <p className="text-gray-600">Generating dashboard, please wait...</p>}

      {error && <p className="text-red-600 bg-red-100 border border-red-400 rounded p-4 w-full max-w-4xl">{error}</p>}

      {dashboardData && !isLoading && !error && (
        <div className="mt-6 w-full max-w-6xl">
           <StockDashboardDisplay data={dashboardData} />
        </div>
      )}
    </main>
  );
}
