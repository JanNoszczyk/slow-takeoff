import React from 'react';
import { StockDashboardData } from '../../types/dashboard'; // Use relative path for shared types

interface StockDashboardDisplayProps {
  data: StockDashboardData | null;
}

// Helper function to format market cap
const formatMarketCap = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return 'N/A';
  if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  return value.toString();
};

// Helper function to format currency
const formatCurrency = (value: number | null | undefined, currency: string | null | undefined = 'USD'): string => {
  if (value === null || value === undefined) return 'N/A';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(value);
};

// Helper function to format percentage
const formatPercentage = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(2)}%`;
};

const StockDashboardDisplay: React.FC<StockDashboardDisplayProps> = ({ data }) => {
  if (!data) {
    return null; // Don't render anything if there's no data
  }

  // Handle potential top-level errors returned from the API/Agent
  if (data.error && !data.symbol) {
    return (
      <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded">
        <h2 className="text-lg font-bold mb-2">Error Generating Dashboard</h2>
        <pre className="text-sm whitespace-pre-wrap">{data.error}</pre>
      </div>
    );
  }

  const quote = data.quote;
  const changePositive = quote?.regularMarketChange !== null && quote?.regularMarketChange !== undefined && quote.regularMarketChange >= 0;
  const changeColor = changePositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';

  const sentimentColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined || score === 0) return 'text-gray-500 dark:text-gray-400';
    return score > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  };

  return (
    <div className="p-6 bg-gray-50 dark:bg-gray-900 rounded-lg shadow-md space-y-6">
      {/* Optional: Display top-level error/warning even if data exists */}
      {data.error && (
         <div className="p-3 bg-yellow-100 border border-yellow-400 text-yellow-800 rounded text-sm">
           <p><span className="font-semibold">Note:</span> {data.error}</p>
         </div>
       )}

      {/* Header */}
      <div className="border-b pb-4 border-gray-200 dark:border-gray-700">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {quote?.symbol || data.symbol || 'N/A'}
          <span className="text-xl text-gray-600 dark:text-gray-400 ml-2">
            ({quote?.shortName || 'Unknown Company'})
          </span>
        </h1>
      </div>

      {/* Quote Section */}
      {quote && !quote.error && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center md:text-left">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Price</p>
            <p className="text-2xl font-semibold text-gray-900 dark:text-white">
              {formatCurrency(quote.regularMarketPrice, quote.currency)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Change</p>
            <p className={`text-xl font-semibold ${changeColor}`}>
              {quote.regularMarketChange !== null && quote.regularMarketChange !== undefined ? `${changePositive ? '+' : ''}${quote.regularMarketChange.toFixed(2)}` : 'N/A'}
              <span className="text-sm ml-1">
                ({formatPercentage(quote.regularMarketChangePercent)})
              </span>
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Market Cap</p>
            <p className="text-xl font-semibold text-gray-900 dark:text-white">
              {formatMarketCap(quote.marketCap)}
            </p>
          </div>
        </div>
      )}
       {quote?.error && (
         <div className="p-3 bg-yellow-100 border border-yellow-400 text-yellow-800 rounded text-sm">
            <p><span className="font-semibold">Quote Error:</span> {quote.error}</p>
         </div>
       )}

      {/* Overall Summary Section */}
      {data.overall_summary && (
        <div>
          <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-2">Summary</h2>
          <p className="text-gray-700 dark:text-gray-300">{data.overall_summary}</p>
        </div>
      )}

      {/* News Section */}
      {data.relevant_news && data.relevant_news.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-4">News Impacting Price</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.relevant_news.map((news, index) => (
              <div key={index} className="border p-4 rounded-lg bg-white dark:bg-gray-800 shadow space-y-2 flex flex-col h-full"> {/* Added flex for consistent height */}
                <h3 className="font-bold text-md text-gray-900 dark:text-white">{news.headline || 'No Headline'}</h3>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  <span>{news.source_name || 'Unknown Source'}</span>
                  <span className="mx-1">|</span>
                  <span>{news.publish_date ? new Date(news.publish_date).toLocaleDateString() : 'No Date'}</span>
                </div>
                {news.reason && (
                  <p className="text-sm italic text-gray-600 dark:text-gray-300">{news.reason}</p>
                )}
                {news.transcript && (
                  <div className="text-sm text-gray-700 dark:text-gray-300 border-l-2 border-gray-200 dark:border-gray-600 pl-2 my-2 max-h-32 overflow-y-auto flex-grow"> {/* Added flex-grow */}
                    <p className="whitespace-pre-wrap">{news.transcript}</p>
                  </div>
                )}
                 <div className="mt-auto pt-2 text-sm font-medium"> {/* Pushed to bottom */}
                    Sentiment Score: <span className={sentimentColor(news.sentiment_score)}>
                        {news.sentiment_score !== null && news.sentiment_score !== undefined ? news.sentiment_score.toFixed(1) : 'N/A'}
                    </span>
                 </div>
                 {news.source_url && (
                     <a
                       href={news.source_url}
                       target="_blank"
                       rel="noopener noreferrer"
                       className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 self-end mt-1" // Align link to bottom right
                     >
                       Read More
                     </a>
                 )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StockDashboardDisplay;
