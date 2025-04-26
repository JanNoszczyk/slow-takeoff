// Shared types for the stock dashboard data

export interface DashboardQuoteData {
  symbol?: string | null;
  shortName?: string | null;
  currency?: string | null;
  regularMarketPrice?: number | null;
  regularMarketChange?: number | null;
  regularMarketChangePercent?: number | null;
  marketCap?: number | null;
  error?: string | null;
}

export interface DashboardNewsArticle {
  headline?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  publish_date?: string | null;
  reason?: string | null;
  transcript?: string | null;
  sentiment_score?: number | null;
}

export interface StockDashboardData {
  symbol?: string | null;
  quote?: DashboardQuoteData | null;
  overall_summary?: string | null;
  relevant_news?: DashboardNewsArticle[];
  error?: string | null; // For capturing processing errors top-level
}
