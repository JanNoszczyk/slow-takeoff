// dashboard/types/wealtharc.ts

export enum MandateType {
  ADVISORY = "Advisory",
  DISCRETIONARY = "Discretionary",
  EXECUTION_ONLY = "ExecutionOnly",
  OFF_MANAGEMENT = "OffManagement",
  READ_ONLY = "ReadOnly",
}

export enum PortfolioType {
  CLIENT = "Client",
  MODEL = "Model",
  NON_FINANCIAL = "NonFinancial",
  CONSOLIDATED = "Consolidated",
  EXTERNAL = "External",
  FUND = "Fund",
  BENCHMARK = "Benchmark",
  SUBACCOUNT = "Subaccount",
}

export enum TransactionType {
  UNCLASSIFIED = "Unclassified",
  BUY = "Buy",
  SELL = "Sell",
  INCOME = "Income",
  FX_TRADE = "FxTrade",
  FEES = "Fees",
  DEPOSIT_WITHDRAWAL = "DepositWithdrawal",
  TAX = "Tax",
  SUBSCRIPTION = "Subscription",
  REDEMPTION = "Redemption",
  OPERATIONAL_FEES = "OperationalFees",
  CORPORATE_ACTION = "CorporateAction",
  INTERNAL_TRANSFER = "InternalTransfer",
  OTHER = "Other",
  ASSET_TRANSFER = "AssetTransfer",
  EXPENSE = "Expense",
  OPEN_DEPOSIT = "OpenDeposit",
  CLOSE_DEPOSIT = "CloseDeposit",
  EXPIRY = "Expiry",
  CALL = "Call",
  CONVERSION = "Conversion",
  WITHHOLDING_TAX = "WithholdingTax",
  INTEREST = "Interest",
  DIVIDEND = "Dividend",
  COUPON = "Coupon",
  BANK_FEE = "BankFee",
  MANAGEMENT_FEE = "ManagementFee",
  PERFORMANCE_FEE = "PerformanceFee",
  OPEN_LOAN = "OpenLoan",
  CLOSE_LOAN = "CloseLoan",
  FX_SPOT = "FxSpot",
  EXCHANGE = "Exchange",
  MERGER = "Merger",
  SPLIT = "Split",
  SPIN_OFF = "SpinOff",
  CASH_IN_LIEU = "CashInLieu",
  FX_FORWARD = "FxForward",
  CANCELLATION = "Cancellation",
  COMMISSION = "Commission",
  STAMP_DUTY = "StampDuty",
  MARGIN_PAYMENT = "MarginPayment",
  ASSIMILATION = "Assimilation",
  BONUS_ISSUE = "BonusIssue",
  CAPITAL_DECREASE = "CapitalDecrease",
  CAPITAL_INCREASE = "CapitalIncrease",
  DELISTING = "Delisting",
  NAME_CHANGE = "NameChange",
  PARTIAL_REDEMPTION = "PartialRedemption",
  REVERSE_SPLIT = "ReverseSplit",
  OPEN_LONG_POSITION = "OpenLongPosition",
  OPEN_SHORT_POSITION = "OpenShortPosition",
}

export interface Asset {
  id: number;
  name?: string;
  currency?: string;
  assetClass?: string;
  assetSubClass?: string;
  investmentType?: string;
  description?: string;
  quotationFactor?: number;
  interestRate?: number;
  maturityDate?: string; // Using string for date types from API/JSON
  riskScore?: number;
}

export interface CashAccount extends Asset {
  iban?: string;
}

export interface Instrument extends Asset {
  isin?: string;
  valor?: string;
  region?: string;
  country?: string;
  sector?: string;
  industryGroup?: string;
  industry?: string;
  subIndustry?: string;
  instrumentInfo?: string;
  wkn?: string;
  cusip?: string;
  sedol?: string;
  ric?: string;
  figi?: string;
  optionType?: string;
  underlyingInstrument?: string;
  underlyingInstrumentIsin?: string;
  strikePrice?: number;
  multiplier?: number;
  instrumentIssuer?: string;
  suitabilityScore?: number;
  appropriatenessScore?: number;
  priceSourceForManualPortfolio?: string;
}

export type AnyAsset = CashAccount | Instrument;

export interface Portfolio {
  id: number;
  name?: string;
  shortName?: string;
  custodianId?: string;
  custodian?: string;
  currency?: string;
  wealthArcCurrency?: string;
  description?: string;
  additionalInfo?: string;
  isActive?: boolean;
  inceptionDate?: string; // Using string for date types
  endDate?: string; // Using string for date types
  relationshipManager?: string;
  portfolioManager?: string;
  assistant?: string;
  branch?: string;
  profitCenter?: string;
  parentPortfolioId?: number;
  investmentGroup?: string;
  modelPortfolioId?: number;
  mandateType?: MandateType;
  isManual?: boolean;
  type?: PortfolioType;
}

export interface PositionValue {
  id: number;
  positionId: number;
  amount?: number;
  currency?: string;
  fxRateDate?: string; // Using string for datetime types
  fxRateFrom?: string;
  fxRateTo?: string;
  fxRate?: number;
  fxRateSource?: string;
}

export interface PositionPnl {
  positionId: number;
  totalPnL?: number;
  totalPnLPercentage?: number;
  marketPnL?: number;
  marketPnLPercentage?: number;
  pnLCurrencyEffect?: number;
  totalPnLWithCashflow?: number;
  totalPnLWithCashflowPercentage?: number;
  cumulativeCashflow?: number;
}

export interface PositionPerformance {
  positionId: number;
  ytdMarket?: number;
  mtdMarket?: number;
  ytdCurrencyEffect?: number;
  mtdCurrencyEffect?: number;
  ytdPerformance?: number;
  mtdPerformance?: number;
}

export interface Position {
  id: number;
  portfolioId: number;
  assetId: number;
  statementDate: string; // Using string for date types
  quantity: number;
  price?: number;
  priceCurrency?: string;
  valueDate?: string; // Using string for date types
  priceSource?: string;
  unitCostInPriceCurrency?: number;
  allocation?: number;
  portfolioCurrency?: string;
  bookCostInPortfolioCurrency?: number;
  fxRate?: number;
  fxRateSource?: string;
  accruedInterestInPriceCurrency?: number;
  accruedInterestInPortfolioCurrency?: number;
  cumulativeCashflowInPriceCurrency?: number;
  values?: PositionValue[];
  pnl?: PositionPnl[];
  performances?: PositionPerformance[];
}

export interface TransactionValue {
  id: string; // Using string for UUID
  transactionId: number;
  amount?: number;
  currency?: string;
  fxRateDate?: string; // Using string for datetime types
  fxRateFrom?: string;
  fxRateTo?: string;
  fxRate?: number;
  fxRateSource?: string;
}

export interface Transaction {
  id: number;
  portfolioId: number;
  assetId: number;
  type: TransactionType;
  description?: string;
  transactionDate: string; // Using string for date types
  tradeDate?: string; // Using string for date types
  valueDate?: string; // Using string for date types
  quantity?: number;
  price?: number;
  priceCurrency?: string;
  portfolioCurrency?: string;
  fxRate?: number;
  fxRateSource?: string;
  externalOrderId?: string;
  referencedInstrumentId?: number;
  referencedInstrumentQuantity?: number;
  interest?: number;
  isReversal?: boolean;
  isRiskIncreased?: boolean;
  values?: TransactionValue[];
}

export interface CustodianPortfolioPerformance {
  portfolioId: number;
  statementDate: string; // Using string for date types
  portfolioCurrency?: string;
  ytdCalculationStartDate?: string; // Using string for date types
  ytdGross?: number;
  ytdNet?: number;
  mtdGross?: number;
  mtdNet?: number;
}

export interface PortfolioAum {
  portfolioDailyMetricsId: number;
  statementDate: string; // Using string for date types
  netAmount: number;
  grossAmount: number;
  currency?: string;
}

export interface PortfolioDailyMetrics {
  id: number;
  portfolioId: number;
  statementDate: string; // Using string for date types
  overdraftsCount?: number;
  custodianPerformances?: CustodianPortfolioPerformance[];
  aums?: PortfolioAum[];
  performances?: PositionPerformance[];
}

// OData Response Interfaces (Optional, depending on how data is fetched)
export interface ODataResponse<T> {
    "@odata.context"?: string;
    "@odata.count"?: number;
    value?: T;
}

export interface ODataCollectionResponse<T> {
    "@odata.context"?: string;
    "@odata.count"?: number;
    value?: T[];
}

// Specific OData response types based on the OpenAPI spec
export type AssetODataCollectionResponse = ODataCollectionResponse<AnyAsset>;
export type AssetODataResponse = ODataResponse<AnyAsset>;
export type CashAccountODataCollectionResponse = ODataCollectionResponse<CashAccount>;
export type InstrumentODataCollectionResponse = ODataCollectionResponse<Instrument>;
export type PortfolioODataCollectionResponse = ODataCollectionResponse<Portfolio>;
export type PortfolioODataResponse = ODataResponse<Portfolio>;
export type PositionODataCollectionResponse = ODataCollectionResponse<Position>;
export type PositionODataResponse = ODataResponse<Position>;
export type TransactionODataCollectionResponse = ODataCollectionResponse<Transaction>;
export type TransactionODataResponse = ODataResponse<Transaction>;
export type PortfolioDailyMetricsODataCollectionResponse = ODataCollectionResponse<PortfolioDailyMetrics>;
export type PortfolioDailyMetricsODataResponse = ODataResponse<PortfolioDailyMetrics>;
