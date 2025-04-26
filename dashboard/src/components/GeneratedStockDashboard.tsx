import React from "react";

// Types
type Quote = {
  symbol: string;
  shortName: string;
  regularMarketPrice: number;
  regularMarketChange: number;
  regularMarketChangePercent: number;
  marketCap: number;
};

type NewsArticle = {
  headline: string;
  source_name: string;
  source_url: string;
  summary: string;
  publish_date: string;
  reason: string;
  transcript: string;
  sentiment_score: number;
};

type StockDashboardProps = {
  symbol: string;
  shortName: string;
  regularMarketPrice: number;
  regularMarketChange: number;
  regularMarketChangePercent: number;
  marketCap: number;
  overallSummary: string;
  relevantNews: NewsArticle[];
};

function formatCurrency(num: number, currency = "USD") {
  return num.toLocaleString("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  });
}

function formatNumber(num: number) {
  if (num >= 1e12) return (num / 1e12).toFixed(2) + "T";
  if (num >= 1e9) return (num / 1e9).toFixed(2) + "B";
  if (num >= 1e6) return (num / 1e6).toFixed(2) + "M";
  if (num >= 1e3) return (num / 1e3).toFixed(2) + "K";
  return num.toLocaleString();
}

function formatPercent(num: number) {
  return num.toFixed(2) + "%";
}

function getChangeColor(value: number) {
  return value > 0
    ? "text-green-600"
    : value < 0
    ? "text-red-600"
    : "text-gray-700 dark:text-gray-300";
}

function getSentimentColor(value: number) {
  return value > 0
    ? "text-green-600"
    : value < 0
    ? "text-red-600"
    : "text-gray-600 dark:text-gray-300";
}

const StockDashboard = ({
  symbol,
  shortName,
  regularMarketPrice,
  regularMarketChange,
  regularMarketChangePercent,
  marketCap,
  overallSummary,
  relevantNews,
}: StockDashboardProps) => {
  return (
    <div className="max-w-6xl mx-auto my-8 p-6 bg-gray-50 dark:bg-gray-900 rounded-xl shadow">
      {/* Header */}
      <div className="mb-4 flex flex-col md:flex-row items-start md:items-center gap-2">
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white">{symbol}</h1>
        <span className="ml-0 md:ml-3 text-xl text-gray-500 dark:text-gray-300">{shortName}</span>
      </div>

      {/* Quote Section */}
      <div className="mb-6 flex flex-wrap gap-x-8 gap-y-2 items-end">
        <div>
          <span className="uppercase text-sm text-gray-500">Price</span>
          <div className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(regularMarketPrice)}
          </div>
        </div>
        <div>
          <span className="uppercase text-sm text-gray-500">Change</span>
          <div className={`text-lg font-semibold ${getChangeColor(regularMarketChange)}`}>
            {regularMarketChange >= 0 ? "+" : ""}
            {regularMarketChange.toFixed(2)}
            {" "}
            <span className={`ml-1 ${getChangeColor(regularMarketChangePercent)}`}>
              ({regularMarketChangePercent >= 0 ? "+" : ""}
              {formatPercent(regularMarketChangePercent)})
            </span>
          </div>
        </div>
        <div>
          <span className="uppercase text-sm text-gray-500">Market Cap</span>
          <div className="text-lg font-medium text-gray-800 dark:text-gray-200">
            {formatCurrency(marketCap, "USD")} ({formatNumber(marketCap)})
          </div>
        </div>
      </div>

      {/* Summary Section */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-gray-800 dark:text-white mb-2">Summary</h2>
        <p className="text-gray-700 dark:text-gray-300">{overallSummary}</p>
      </div>

      {/* News Section */}
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-white mb-4">News Impacting Price</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {relevantNews.map((article, idx) => (
            <div
              key={idx}
              className="border border-gray-200 dark:border-gray-700 p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm flex flex-col h-full"
            >
              <a
                href={article.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                <div className="font-bold text-gray-900 dark:text-white mb-1">{article.headline}</div>
              </a>
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                {article.source_name} • {article.publish_date}
              </div>
              <div className="italic text-sm text-gray-700 dark:text-gray-300 mb-1">{article.reason}</div>
              <div className="bg-gray-100 dark:bg-gray-900 rounded p-2 mb-2 text-sm text-gray-800 dark:text-gray-200 max-h-32 overflow-y-auto">
                {article.transcript}
              </div>
              <div className={`mt-auto text-sm font-semibold ${getSentimentColor(article.sentiment_score)}`}>
                Sentiment: {article.sentiment_score > 0 ? "+" : ""}
                {article.sentiment_score}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default async function StockDashboardRSC({
  researchJson,
}: {
  researchJson: string;
}) {
  let parsed: any;
  try {
    parsed = JSON.parse(researchJson);
  } catch (e) {
    return (
      <>
        {/* Error: Failed to parse research JSON input */}
      </>
    );
  }

  if (
    !parsed ||
    !parsed.report ||
    !Array.isArray(parsed.report) ||
    parsed.report.length === 0
  ) {
    return (
      <>
        {/* Error: No report data found in research input */}
      </>
    );
  }

  const report = parsed.report[0];
  const quote = report?.yahoo_quote?.quote;

  if (!quote) {
    return (
      <>
        {/* Error: No yahoo_quote/quote found for symbol */}
      </>
    );
  }

  const symbol = report.symbol || quote.symbol || "N/A";
  const shortName = quote.shortName || "N/A";
  const regularMarketPrice = Number(quote.regularMarketPrice) ?? 0;
  const regularMarketChange = Number(quote.regularMarketChange) ?? 0;
  const regularMarketChangePercent = Number(quote.regularMarketChangePercent) ?? 0;
  const marketCap = Number(quote.marketCap) ?? 0;

  const overallSummary = report?.web_search?.overall_summary ?? "No summary available.";
  const relevantNews: NewsArticle[] =
    report?.web_search?.relevant_news && Array.isArray(report.web_search.relevant_news)
      ? report.web_search.relevant_news
      : [];

  return (
    <StockDashboard
      symbol={symbol}
      shortName={shortName}
      regularMarketPrice={regularMarketPrice}
      regularMarketChange={regularMarketChange}
      regularMarketChangePercent={regularMarketChangePercent}
      marketCap={marketCap}
      overallSummary={overallSummary}
      relevantNews={relevantNews}
    />
  );
}