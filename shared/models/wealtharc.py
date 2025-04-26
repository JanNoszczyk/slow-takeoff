# --- Pydantic Models for WealthArc API ---

from __future__ import annotations
from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

# Enums
class MandateType(str, Enum):
    ADVISORY = "Advisory"
    DISCRETIONARY = "Discretionary"
    EXECUTION_ONLY = "ExecutionOnly"
    OFF_MANAGEMENT = "OffManagement"
    READ_ONLY = "ReadOnly"

class PortfolioType(str, Enum):
    CLIENT = "Client"
    MODEL = "Model"
    NON_FINANCIAL = "NonFinancial"
    CONSOLIDATED = "Consolidated"
    EXTERNAL = "External"
    FUND = "Fund"
    BENCHMARK = "Benchmark"
    SUBACCOUNT = "Subaccount"

class TransactionType(str, Enum):
    UNCLASSIFIED = "Unclassified"
    BUY = "Buy"
    SELL = "Sell"
    INCOME = "Income"
    FX_TRADE = "FxTrade"
    FEES = "Fees"
    DEPOSIT_WITHDRAWAL = "DepositWithdrawal"
    TAX = "Tax"
    SUBSCRIPTION = "Subscription"
    REDEMPTION = "Redemption"
    OPERATIONAL_FEES = "OperationalFees"
    CORPORATE_ACTION = "CorporateAction"
    INTERNAL_TRANSFER = "InternalTransfer"
    OTHER = "Other"
    ASSET_TRANSFER = "AssetTransfer"
    EXPENSE = "Expense"
    OPEN_DEPOSIT = "OpenDeposit"
    CLOSE_DEPOSIT = "CloseDeposit"
    EXPIRY = "Expiry"
    CALL = "Call"
    CONVERSION = "Conversion"
    WITHHOLDING_TAX = "WithholdingTax"
    INTEREST = "Interest"
    DIVIDEND = "Dividend"
    COUPON = "Coupon"
    BANK_FEE = "BankFee"
    MANAGEMENT_FEE = "ManagementFee"
    PERFORMANCE_FEE = "PerformanceFee"
    OPEN_LOAN = "OpenLoan"
    CLOSE_LOAN = "CloseLoan"
    FX_SPOT = "FxSpot"
    EXCHANGE = "Exchange"
    MERGER = "Merger"
    SPLIT = "Split"
    SPIN_OFF = "SpinOff"
    CASH_IN_LIEU = "CashInLieu"
    FX_FORWARD = "FxForward"
    CANCELLATION = "Cancellation"
    COMMISSION = "Commission"
    STAMP_DUTY = "StampDuty"
    MARGIN_PAYMENT = "MarginPayment"
    ASSIMILATION = "Assimilation"
    BONUS_ISSUE = "BonusIssue"
    CAPITAL_DECREASE = "CapitalDecrease"
    CAPITAL_INCREASE = "CapitalIncrease"
    DELISTING = "Delisting"
    NAME_CHANGE = "NameChange"
    PARTIAL_REDEMPTION = "PartialRedemption"
    REVERSE_SPLIT = "ReverseSplit"
    OPEN_LONG_POSITION = "OpenLongPosition"
    OPEN_SHORT_POSITION = "OpenShortPosition"

# --- Base Models ---
class Asset(BaseModel):
    id: int
    name: Optional[str] = None
    currency: Optional[str] = None
    assetClass: Optional[str] = None
    assetSubClass: Optional[str] = None
    investmentType: Optional[str] = None
    description: Optional[str] = None
    quotationFactor: Optional[float] = None
    interestRate: Optional[float] = None
    maturityDate: Optional[date] = None
    riskScore: Optional[int] = Field(None, ge=1, le=10)

class CashAccount(Asset):
    iban: Optional[str] = None
    odata_type: str = Field("#WealthArc.CashAccount", alias="@odata.type", exclude=True) # Exclude from model dump but use for type checking

class Instrument(Asset):
    isin: Optional[str] = None
    valor: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None
    industryGroup: Optional[str] = None
    industry: Optional[str] = None
    subIndustry: Optional[str] = None
    instrumentInfo: Optional[str] = None
    wkn: Optional[str] = None
    cusip: Optional[str] = None
    sedol: Optional[str] = None
    ric: Optional[str] = None
    figi: Optional[str] = None
    optionType: Optional[str] = None
    underlyingInstrument: Optional[str] = None
    underlyingInstrumentIsin: Optional[str] = None
    strikePrice: Optional[float] = None
    multiplier: Optional[float] = None
    instrumentIssuer: Optional[str] = None
    suitabilityScore: Optional[int] = None
    appropriatenessScore: Optional[int] = None
    priceSourceForManualPortfolio: Optional[str] = None
    odata_type: str = Field("#WealthArc.Instrument", alias="@odata.type", exclude=True)

AnyAsset = Union[CashAccount, Instrument] # For use in responses

class Portfolio(BaseModel):
    id: int
    name: Optional[str] = None
    shortName: Optional[str] = None
    custodianId: Optional[str] = None
    custodian: Optional[str] = None
    currency: Optional[str] = None
    wealthArcCurrency: Optional[str] = None
    description: Optional[str] = None
    additionalInfo: Optional[str] = None
    isActive: Optional[bool] = None
    inceptionDate: Optional[date] = None
    endDate: Optional[date] = None
    relationshipManager: Optional[str] = None
    portfolioManager: Optional[str] = None
    assistant: Optional[str] = None
    branch: Optional[str] = None
    profitCenter: Optional[str] = None
    parentPortfolioId: Optional[int] = None
    investmentGroup: Optional[str] = None
    modelPortfolioId: Optional[int] = None
    mandateType: Optional[MandateType] = None
    isManual: Optional[bool] = None
    type: Optional[PortfolioType] = None # Schema implies required, but Optional okay for flexibility

class PositionValue(BaseModel):
    id: int # Corrected: Schema implies required
    positionId: int # Corrected: Schema implies required
    amount: Optional[float] = None
    currency: Optional[str] = None
    fxRateDate: Optional[datetime] = None # Using datetime reflects schema format
    fxRateFrom: Optional[str] = None
    fxRateTo: Optional[str] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None

class PositionPnl(BaseModel):
    positionId: int # Corrected: Schema implies required
    # portfolioId: Optional[int] = None # REMOVED - Not in schema definition
    totalPnL: Optional[float] = None
    totalPnLPercentage: Optional[float] = None
    marketPnL: Optional[float] = None
    marketPnLPercentage: Optional[float] = None
    pnLCurrencyEffect: Optional[float] = None
    totalPnLWithCashflow: Optional[float] = None
    totalPnLWithCashflowPercentage: Optional[float] = None
    cumulativeCashflow: Optional[float] = None

# Only one definition now, used for Position and PortfolioDailyMetrics
class PositionPerformance(BaseModel):
    positionId: int # Corrected: Schema implies required
    # NOTE: Schema shows this model under Position, but PortfolioDailyMetrics also references it.
    # The properties below match the schema for PositionPerformance.
    ytdMarket: Optional[float] = None
    mtdMarket: Optional[float] = None
    ytdCurrencyEffect: Optional[float] = None
    mtdCurrencyEffect: Optional[float] = None
    ytdPerformance: Optional[float] = None
    mtdPerformance: Optional[float] = None
    # The following fields were specific to the DailyMetrics version and seem redundant/mistakenly duplicated
    # statementDate: date # This is in PortfolioDailyMetrics level
    # ytdCalculationStartDate: Optional[date] = None # This is in PortfolioDailyMetrics level
    # ytdGross: Optional[float] = None # This is in PortfolioDailyMetrics level
    # ytdNet: Optional[float] = None # This is in PortfolioDailyMetrics level
    # mtdGross: Optional[float] = None # This is in PortfolioDailyMetrics level
    # mtdNet: Optional[float] = None # This is in PortfolioDailyMetrics level


class Position(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    assetId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    quantity: float # Corrected: Schema implies required
    price: Optional[float] = None # Optional, matches schema
    priceCurrency: Optional[str] = None # Optional, matches schema
    valueDate: Optional[date] = None
    priceSource: Optional[str] = None
    unitCostInPriceCurrency: Optional[float] = None
    allocation: Optional[float] = None
    portfolioCurrency: Optional[str] = None
    bookCostInPortfolioCurrency: Optional[float] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None
    accruedInterestInPriceCurrency: Optional[float] = None
    accruedInterestInPortfolioCurrency: Optional[float] = None
    cumulativeCashflowInPriceCurrency: Optional[float] = None
    values: Optional[List[PositionValue]] = None # Structure matches, uses corrected PositionValue
    pnl: Optional[List[PositionPnl]] = None # Structure matches, uses corrected PositionPnl
    performances: Optional[List[PositionPerformance]] = None # Structure matches, uses corrected PositionPerformance

class TransactionValue(BaseModel):
    id: UUID # Corrected: Schema implies required UUID
    transactionId: int # Corrected: Schema implies required int
    amount: Optional[float] = None # Optional, matches schema
    currency: Optional[str] = None # Optional, matches schema
    fxRateDate: Optional[datetime] = None # Using datetime reflects schema format
    fxRateFrom: Optional[str] = None
    fxRateTo: Optional[str] = None
    fxRate: Optional[float] = None
    fxRateSource: Optional[str] = None

class Transaction(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    assetId: int # Corrected: Schema implies required
    type: TransactionType # Corrected: Schema implies required
    description: Optional[str] = None # Optional, matches schema
    transactionDate: date # Required, matches schema
    tradeDate: Optional[date] = None
    valueDate: Optional[date] = None
    quantity: Optional[float] = None # Optional, matches schema
    price: Optional[float] = None # Optional, matches schema
    priceCurrency: Optional[str] = None # Optional, matches schema
    portfolioCurrency: Optional[str] = None # Optional, matches schema
    fxRate: Optional[float] = None # Optional, matches schema
    fxRateSource: Optional[str] = None # Optional, matches schema
    externalOrderId: Optional[str] = None # Optional, matches schema
    referencedInstrumentId: Optional[int] = None # Optional, matches schema
    referencedInstrumentQuantity: Optional[float] = None # Optional, matches schema
    interest: Optional[float] = None # Optional, matches schema
    isReversal: Optional[bool] = None # Optional, matches schema
    isRiskIncreased: Optional[bool] = None # Optional, matches schema
    values: Optional[List[TransactionValue]] = None # Structure matches, uses corrected TransactionValue


# --- Models related to PortfolioDailyMetrics ---

# ADDED MISSING MODEL based on schema
class CustodianPortfolioPerformance(BaseModel):
    portfolioId: int # Schema implies required
    statementDate: date # Required
    portfolioCurrency: Optional[str] = None # Optional, matches schema
    ytdCalculationStartDate: Optional[date] = None
    ytdGross: Optional[float] = None
    ytdNet: Optional[float] = None
    mtdGross: Optional[float] = None
    mtdNet: Optional[float] = None

class PortfolioAum(BaseModel):
    portfolioDailyMetricsId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    netAmount: float # Corrected: Schema implies required
    grossAmount: float # Corrected: Schema implies required
    currency: Optional[str] = None # Optional, matches schema

# REMOVED DUPLICATE/SECOND Definition of PortfolioPerformance

# Corrected PortfolioDailyMetrics (single definition)
class PortfolioDailyMetrics(BaseModel):
    id: int # Required, matches schema
    portfolioId: int # Corrected: Schema implies required
    statementDate: date # Required, matches schema
    overdraftsCount: Optional[int] = None # Optional, matches schema
    custodianPerformances: Optional[List[CustodianPortfolioPerformance]] = None # Structure matches, uses added CustodianPortfolioPerformance
    aums: Optional[List[PortfolioAum]] = None # Structure matches, uses corrected PortfolioAum
    performances: Optional[List[PositionPerformance]] = None # Structure matches, uses corrected PositionPerformance


# --- OData Response Models ---
# Note: These might be useful if parsing the direct API response,
# but the client module might just return the 'value' part.
class ODataResponseBase(BaseModel):
    context: Optional[str] = Field(None, alias="@odata.context")
    count: Optional[int] = Field(None, alias="@odata.count")

class AssetODataCollectionResponse(ODataResponseBase):
    value: Optional[List[AnyAsset]] = None # Handles CashAccount or Instrument

class AssetODataResponse(ODataResponseBase):
    value: Optional[AnyAsset] = None

class CashAccountODataCollectionResponse(ODataResponseBase):
    value: Optional[List[CashAccount]] = None

class InstrumentODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Instrument]] = None

class PortfolioODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Portfolio]] = None

class PortfolioODataResponse(ODataResponseBase):
    value: Optional[Portfolio] = None

class PositionODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Position]] = None

class PositionODataResponse(ODataResponseBase):
    value: Optional[Position] = None

class TransactionODataCollectionResponse(ODataResponseBase):
    value: Optional[List[Transaction]] = None

class TransactionODataResponse(ODataResponseBase):
    value: Optional[Transaction] = None

class PortfolioDailyMetricsODataCollectionResponse(ODataResponseBase):
    value: Optional[List[PortfolioDailyMetrics]] = None

class PortfolioDailyMetricsODataResponse(ODataResponseBase):
    value: Optional[PortfolioDailyMetrics] = None
