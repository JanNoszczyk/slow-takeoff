# WealthArc Data Analysis Report

# Analysis for: all_assets.json

## Analysis Results for `all_assets.csv` (Data Type: Assets)

### DataFrame Info

```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 8029 entries, 0 to 8028
Data columns (total 36 columns):
 #   Column                         Non-Null Count  Dtype  
---  ------                         --------------  -----  
 0   @odata.type                    8029 non-null   object 
 1   id                             8029 non-null   int64  
 2   name                           8029 non-null   object 
 3   currency                       7967 non-null   object 
 4   assetClass                     7879 non-null   object 
 5   assetSubClass                  7879 non-null   object 
 6   investmentType                 7829 non-null   object 
 7   description                    78 non-null     object 
 8   quotationFactor                8029 non-null   float64
 9   interestRate                   22 non-null     float64
 10  maturityDate                   860 non-null    object 
 11  riskScore                      2703 non-null   float64
 12  isin                           3074 non-null   object 
 13  valor                          1217 non-null   object 
 14  region                         1534 non-null   object 
 15  country                        1534 non-null   object 
 16  sector                         557 non-null    object 
 17  industryGroup                  832 non-null    object 
 18  industry                       850 non-null    object 
 19  subIndustry                    898 non-null    object 
 20  instrumentInfo                 3 non-null      object 
 21  wkn                            460 non-null    object 
 22  cusip                          672 non-null    object 
 23  sedol                          582 non-null    object 
 24  ric                            1636 non-null   object 
 25  figi                           15 non-null     object 
 26  optionType                     98 non-null     object 
 27  underlyingInstrument           99 non-null     object 
 28  underlyingInstrumentIsin       131 non-null    object 
 29  strikePrice                    13 non-null     float64
 30  multiplier                     3679 non-null   float64
 31  instrumentIssuer               1254 non-null   object 
 32  suitabilityScore               2113 non-null   float64
 33  appropriatenessScore           2111 non-null   float64
 34  priceSourceForManualPortfolio  374 non-null    object 
 35  iban                           1029 non-null   object 
dtypes: float64(7), int64(1), object(28)
memory usage: 2.2+ MB

```

### First 5 Rows

| @odata.type           | id    | name                       | currency   | assetClass   | assetSubClass   | investmentType   | description   | quotationFactor   | interestRate   | maturityDate   | riskScore   | isin         | valor            | region          | country   | sector                 | industryGroup              | industry                               | subIndustry                           | instrumentInfo                          | wkn    | cusip     | sedol   | ric     | figi   | optionType   | underlyingInstrument   | underlyingInstrumentIsin   | strikePrice   | multiplier   | instrumentIssuer   | suitabilityScore   | appropriatenessScore   | priceSourceForManualPortfolio   | iban   |
|:----------------------|:------|:---------------------------|:-----------|:-------------|:----------------|:-----------------|:--------------|:------------------|:---------------|:---------------|:------------|:-------------|:-----------------|:----------------|:----------|:-----------------------|:---------------------------|:---------------------------------------|:--------------------------------------|:----------------------------------------|:-------|:----------|:--------|:--------|:-------|:-------------|:-----------------------|:---------------------------|:--------------|:-------------|:-------------------|:-------------------|:-----------------------|:--------------------------------|:-------|
| #WealthArc.Instrument | 25202 | UBS Group AG&GA            | CHF        | Equities     | Equities        | Equities         | ASDF & FDSA   | 1                 | nan            | 2025-07-30     | 5           | CH0244767585 | 24476758& 222222 | Poland          | PL        | Financials             | Diversified Financials     | Capital Markets                        | Diversified Capital Markets           | sdksjfkldsjfdslkfjdslfsssssssss & sssss | A12DFH | H42097107 | BRJL176 | UBSG.S  |        |              |                        |                            | nan           | 1            |                    | 1                  | 2                      | feedUBS                         | nan    |
| #WealthArc.Instrument | 25203 | Swisscom AG                | CHF        | Equities     | Equities        | Equities         |               | 1                 | nan            |                | 4           | CH0008742519 | 874251           | Switzerland     | CH        | Communication Services | Telecommunication Services | Diversified Telecommunication Services | Integrated Telecommunication Services |                                         | 916234 | H8398N104 | 5533976 | SCMN.S  |        |              |                        |                            | nan           | 1            |                    | 4                  | 4                      | manual                          | nan    |
| #WealthArc.Instrument | 25204 | Swiss Prime Site AG        | CHF        | Equities     | Equities        | Equities         |               | 1                 | nan            |                | 3           | CH0008038389 | 000803838        | Switzerland     | CH        | Real Estate            | Real Estate                | Real Estate Management & Development   | Real Estate Operating Companies       |                                         | 927016 | H8403W107 | B083BH4 | SPSN.S  |        |              |                        |                            | nan           | 1            |                    | 3                  | 3                      | xignite                         | nan    |
| #WealthArc.Instrument | 25205 | Banque Cantonale Vaudoisec | CHF        | Equities     | Equities        | Equities         |               | 1                 | nan            |                | 4           | CH0015251710 | 1525171          | Switzerland     | CH        | Financials             | Banks                      | Banks                                  | Regional Banks                        |                                         |        | H0482P863 | 7520794 | BCVN.S  |        |              |                        |                            | nan           | 1            | BC Vaudoise        | 4                  | 4                      | xignite                         | nan    |
| #WealthArc.Instrument | 25206 | Royal Dutch Shell PLCc     | EUR        | Equities     | Equities        | Equities         |               | 1                 | nan            |                | 4           | GB00B03MLX29 | 1987674          | Netherlands the | NL        | Energy                 | Energy                     | Oil, Gas & Consumable Fuels            | Integrated Oil & Gas                  |                                         | A0D94M | G7690A100 | B09CBL4 | RDSa.AS |        |              |                        |                            | nan           | 1            | ROYAL DUTCH SHELL  | 4                  | 4                      | xignite                         | nan    |

### Value Counts for Key Columns (Top 20)

#### Value Counts for `assetClass`

| assetClass              | count   |
|:------------------------|:--------|
| Cash                    | 4367    |
| Equities                | 1994    |
| Fixed Income            | 907     |
| Alternative Investments | 423     |
| None                    | 150     |
| Real Estate             | 90      |
| Commodities             | 84      |
| Collectible Items       | 7       |
| Liabilities             | 4       |
| Aircraft                | 2       |
| Art                     | 1       |

#### Value Counts for `assetSubClass`

| assetSubClass        | count   |
|:---------------------|:--------|
| Cash                 | 2757    |
| Equities             | 1310    |
| Forwards             | 1146    |
| Fixed Income         | 714     |
| Equity Options       | 317     |
| Equity Funds         | 257     |
| Deposits             | 191     |
| Loans                | 167     |
| Bond Funds           | 158     |
| None                 | 150     |
| Other Funds          | 117     |
| Equity ETFs          | 110     |
| Miscellaneous        | 90      |
| Private Equity Funds | 64      |
| Receivables          | 61      |
| Real Estate Funds    | 61      |
| Commodities          | 44      |
| Hedge Funds          | 43      |
| Guarantee            | 32      |
| Structured Products  | 32      |

#### Value Counts for `investmentType`

| investmentType       | count   |
|:---------------------|:--------|
| Cash                 | 2757    |
| Equities             | 1340    |
| Forwards             | 1147    |
| Fixed Income         | 726     |
| Equity Options       | 296     |
| Equity Funds         | 255     |
| None                 | 200     |
| Deposits             | 189     |
| Loans                | 168     |
| Bond Funds           | 139     |
| Other Funds          | 117     |
| Equity ETFs          | 99      |
| Miscellaneous        | 87      |
| Private Equity Funds | 63      |
| Receivables          | 61      |
| Real Estate Funds    | 58      |
| Commodities          | 46      |
| Hedge Funds          | 40      |
| Guarantee            | 32      |
| Structured Products  | 30      |

#### Value Counts for `sector`

| sector                 | count   |
|:-----------------------|:--------|
| nan                    | 4348    |
| None                   | 3124    |
| Financials             | 124     |
| Industrials            | 61      |
| Materials              | 60      |
| Health Care            | 60      |
| Information Technology | 56      |
| Consumer Discretionary | 50      |
| Energy                 | 41      |
| Consumer Staples       | 40      |
| Communication Services | 34      |
| Real Estate            | 19      |
| Utilities              | 12      |

#### Value Counts for `name`

| name                         | count   |
|:-----------------------------|:--------|
| CASH ACCOUNT IN CHF          | 899     |
| CASH ACCOUNT IN EUR          | 633     |
| CASH ACCOUNT IN USD          | 591     |
| CASH ACCOUNT IN GBP          | 254     |
| LOAN IN CHF                  | 82      |
| CASH ACCOUNT IN AUD          | 71      |
| CASH ACCOUNT IN JPY          | 60      |
| DEPOSIT IN USD               | 48      |
| CASH ACCOUNT IN CAD          | 42      |
| DEPOSIT IN CHF               | 41      |
| CASH ACCOUNT IN ZAR          | 34      |
| INCOME TO BE RECEIVED IN USD | 33      |
| Fiduciary call deposit       | 27      |
| INCOME TO BE RECEIVED IN CHF | 26      |
| INCOME TO BE RECEIVED IN EUR | 20      |
| Cash Account in CHF          | 15      |
| CASH ACCOUNT IN HKD          | 13      |
| LOAN IN USD                  | 13      |
| CASH ACCOUNT IN SEK          | 13      |
| DEPOSIT IN GBP               | 12      |

#### Value Counts for `isin`

| isin         | count   |
|:-------------|:--------|
| nan          | 4348    |
| None         | 607     |
| CH0244767585 | 1       |
| CH0011786628 | 1       |
| US4834971032 | 1       |
| XS1668078758 | 1       |
| CH0454664027 | 1       |
| US4878361082 | 1       |
| LU0106244444 | 1       |
| IM00BF4LVF57 | 1       |
| LU1883305846 | 1       |
| ZZ00WDDSGW 0 | 1       |
| ZZ00WDDSHK 0 | 1       |
| ZZ00WDGMAW 0 | 1       |
| ZZ00WDJ8BD 0 | 1       |
| ZZ00WDP6HU 0 | 1       |
| ZZ00WE11HO 0 | 1       |
| ZZ00WE78TI 0 | 1       |
| ZZ00WEFWMU 0 | 1       |
| ZZ00WEFWN2 0 | 1       |

#### Value Counts for `ric`

| ric        | count   |
|:-----------|:--------|
| nan        | 4348    |
| None       | 2045    |
| LP40181910 | 2       |
| ITCI.OQ    | 2       |
| TGTX.OQ    | 2       |
| STMN.S     | 2       |
| AXSM.OQ    | 2       |
| NVAX.OQ    | 2       |
| BCVN.S     | 2       |
| EUFI.PA    | 2       |
| LP68611010 | 1       |
| CHRY.L     | 1       |
| LP68575893 | 1       |
| LP68611025 | 1       |
| LP68488239 | 1       |
| ABX.TO     | 1       |
| LP40225239 | 1       |
| LP68295470 | 1       |
| UBSG.S     | 1       |
| VARN.S     | 1       |

#### Value Counts for `wkn`

| wkn    | count   |
|:-------|:--------|
| nan    | 4348    |
| None   | 3221    |
| A1XDTL | 5       |
| A1JXW7 | 5       |
| A2AA7B | 5       |
| 747206 | 3       |
| A2PKMZ | 3       |
| A2P6UE | 2       |
| A2JNFS | 2       |
| A2PNGL | 2       |
| A2DG49 | 2       |
| A1KCL6 | 2       |
| A0NBNG | 2       |
| A14VPK | 2       |
| A2ALQV | 2       |
| A1CX3T | 2       |
| A14RE8 | 1       |
| A2PC0N | 1       |
| 769088 | 1       |
| A2H5Z1 | 1       |

#### Value Counts for `cusip`

| cusip     | count   |
|:----------|:--------|
| nan       | 4348    |
| None      | 3009    |
| 05464T104 | 5       |
| 88322Q108 | 5       |
| 46116X101 | 5       |
| 46090E103 | 3       |
| D22359133 | 3       |
| 670002401 | 3       |
| 87918A105 | 2       |
| 399473206 | 2       |
| 483497103 | 2       |
| 85858C107 | 2       |
| 023111206 | 2       |
| 75615P103 | 2       |
| 88160R101 | 2       |
| 08862L103 | 2       |
| 860897107 | 1       |
| 848637104 | 1       |
| D0066B185 | 1       |
| H893AG202 | 1       |

#### Value Counts for `region`

| region                   | count   |
|:-------------------------|:--------|
| nan                      | 4348    |
| None                     | 2147    |
| United States of America | 438     |
| Switzerland              | 255     |
| Luxembourg               | 206     |
| France                   | 113     |
| Germany                  | 81      |
| United Kingdom           | 58      |
| Ireland                  | 47      |
| Netherlands the          | 44      |
| Canada                   | 35      |
| Australia                | 33      |
| China                    | 28      |
| Japan                    | 26      |
| Pakistan                 | 18      |
| Belgium                  | 13      |
| Guernsey                 | 12      |
| Cayman Islands           | 11      |
| India                    | 9       |
| Mexico                   | 8       |

#### Value Counts for `industryGroup`

| industryGroup                                  | count   |
|:-----------------------------------------------|:--------|
| nan                                            | 4348    |
| None                                           | 2849    |
| Financials                                     | 213     |
| Banks                                          | 70      |
| Materials                                      | 68      |
| Pharmaceuticals, Biotechnology & Life Sciences | 44      |
| Diversified Financials                         | 44      |
| Energy                                         | 42      |
| Capital Goods                                  | 40      |
| Food, Beverage & Tobacco                       | 33      |
| Software & Services                            | 25      |
| Utilities                                      | 23      |
| Semiconductors & Semiconductor Equipment       | 19      |
| Real Estate                                    | 19      |
| Media & Entertainment                          | 18      |
| Industrials                                    | 17      |
| Automobiles & Components                       | 17      |
| Health Care Equipment & Services               | 16      |
| Telecommunication Services                     | 16      |
| Consumer Durables & Apparel                    | 13      |

#### Value Counts for `industry`

| industry                                       | count   |
|:-----------------------------------------------|:--------|
| nan                                            | 4348    |
| None                                           | 2831    |
| Diversified Financials                         | 212     |
| Banks                                          | 71      |
| Capital Markets                                | 35      |
| Metals & Mining                                | 33      |
| Oil, Gas & Consumable Fuels                    | 32      |
| Biotechnology                                  | 24      |
| Chemicals                                      | 20      |
| Food Products                                  | 20      |
| Semiconductors & Semiconductor Equipment       | 19      |
| Machinery                                      | 19      |
| Software                                       | 17      |
| Pharmaceuticals                                | 17      |
| Automobiles                                    | 14      |
| Diversified Telecommunication Services         | 13      |
| Equity Real Estate Investment Trusts (REITs)   | 12      |
| Pharmaceuticals, Biotechnology & Life Sciences | 12      |
| Financials                                     | 11      |
| Health Care Equipment & Supplies               | 11      |

#### Value Counts for `subIndustry`

| subIndustry                           | count   |
|:--------------------------------------|:--------|
| nan                                   | 4348    |
| None                                  | 2783    |
| Diversified Financial Services        | 194     |
| Diversified Banks                     | 63      |
| Biotechnology                         | 29      |
| Pharmaceuticals                       | 24      |
| Diversified Capital Markets           | 19      |
| Packaged Foods & Meats                | 18      |
| Semiconductors                        | 17      |
| Capital Markets                       | 15      |
| Industrial Machinery                  | 15      |
| Automobile Manufacturers              | 14      |
| Integrated Telecommunication Services | 12      |
| Gold                                  | 12      |
| Electric Utilities                    | 11      |
| Diversified Metals & Mining           | 11      |
| Integrated Oil & Gas                  | 11      |
| Oil & Gas Exploration & Production    | 10      |
| Aerospace & Defense                   | 10      |
| Banks                                 | 10      |

### Summary Statistics for Numeric Columns

|       |   quotationFactor |   interestRate |   riskScore |   strikePrice |   multiplier |   suitabilityScore |   appropriatenessScore |
|:------|------------------:|---------------:|------------:|--------------:|-------------:|-------------------:|-----------------------:|
| count |           8029.00 |          22.00 |     2703.00 |         13.00 |      3679.00 |            2113.00 |                2111.00 |
| mean  |             12.07 |           3.93 |        3.59 |        163.46 |         1.65 |               3.03 |                   3.07 |
| std   |             32.95 |           1.98 |        1.91 |         84.54 |         7.97 |               1.35 |                   1.41 |
| min   |              1.00 |           0.10 |        1.00 |         35.00 |         1.00 |               1.00 |                   1.00 |
| 25%   |              1.00 |           3.25 |        2.00 |        100.00 |         1.00 |               1.00 |                   1.00 |
| 50%   |              1.00 |           5.00 |        4.00 |        105.00 |         1.00 |               4.00 |                   4.00 |
| 75%   |              1.00 |           5.00 |        4.00 |        250.00 |         1.00 |               4.00 |                   4.00 |
| max   |           1000.00 |           7.00 |        9.00 |        255.00 |       100.00 |               7.00 |                  10.00 |

### Potential Public Entity Identification

Identified **3220** potential public entity candidates based on identifiers or name frequency (>= 3).

#### Potential Public Entities (Assets, Top 20)

| cusip     | assetSubClass   | investmentType   | isin         | wkn    | ric             | assetClass              | name                                     |
|:----------|:----------------|:-----------------|:-------------|:-------|:----------------|:------------------------|:-----------------------------------------|
| H42097107 | Equities        | Equities         | CH0244767585 | A12DFH | UBSG.S          | Equities                | UBS Group AG&GA                          |
| H8398N104 | Equities        | Equities         | CH0008742519 | 916234 | SCMN.S          | Equities                | Swisscom AG                              |
| H8403W107 | Equities        | Equities         | CH0008038389 | 927016 | SPSN.S          | Equities                | Swiss Prime Site AG                      |
| H0482P863 | Equities        | Equities         | CH0015251710 |        | BCVN.S          | Equities                | Banque Cantonale Vaudoisec               |
| G7690A100 | Equities        | Equities         | GB00B03MLX29 | A0D94M | RDSa.AS         | Equities                | Royal Dutch Shell PLCc                   |
| H3698D419 | Equities        | Equities         | CH0012138530 | 876800 | CSGN.S          | Equities                | Credit Suisse Group AG                   |
| H57312649 | Equities        | Equities         | CH0038863350 | A0Q4DC | NESN.S          | Equities                | Nestle SA                                |
| 02079K107 | Equities        | Equities         | US02079K1079 | A14Y6H | GOOG.O          | Equities                | Alphabet Inc Class C                     |
| H9870Y105 | Equities        | Equities         | CH0011075394 | 579919 | ZURN.S          | Equities                | Zurich Insurance Group AG                |
| H8431B109 | Equities        | Equities         | CH0126881561 | A1H81M | SRENH.S         | Equities                | Swiss Re AG/GA                           |
|           | Hedge Funds     | Hedge Funds      | KYG891801063 |        |                 | Alternative Investments | Ton Poh A USD                            |
| H69293217 | Equities        | Equities         | CH0012032048 | 855167 | ROG.S           | Equities                | Roche Holding AG                         |
| H721US280 | Equity Funds    | Miscellaneous    | CH0372809415 | US8Y0L | CH0372809415.VI | Equities                | Silex Biomed Certificate CHF             |
| L79804107 | Bond Funds      | Bond Funds       | LU0084302339 | 912419 | LP60025791      | Fixed Income            | Robeco QI Global Dynamic Duration DH EUR |
| G29608141 | Equity Funds    | Equity Funds     | IE00B5VJPM77 | A1H7UC | LP68076040      | Equities                | EI Sturdza Strategic Europe Quality EUR  |
| F7090C137 | Equity Funds    | Equity Funds     | FR0010346817 | A0RMBR | LP65043479      | Equities                | WWW Perf                                 |
| H5820Q150 | Equities        | Equities         | CH0012005267 | 904278 | NOVN.S          | Equities                | Novartis AG                              |
| L6074A227 | Equity Funds    | Other Funds      | LU1302865008 |        | LP68482664      | Equities                | LONGRUN EQUITY FD P A CHF                |
| H01301128 | Equities        | Equities         | CH0432492467 | A2PDXE | ALCC.S          | Equities                | Alcon AG                                 |
| H2082J107 | Equities        | Equities         | CH0023405456 | A0HMLM | DUFN.S          | Equities                | Dufry AG                                 |

*Saved 3220 candidates to `all_assets_public_entities.csv`.*

### Aggregations and Further Analysis

#### Asset Count per Asset Class

| Asset Class             | Count   |
|:------------------------|:--------|
| Cash                    | 4367    |
| Equities                | 1994    |
| Fixed Income            | 907     |
| Alternative Investments | 423     |
| None                    | 150     |
| Real Estate             | 90      |
| Commodities             | 84      |
| Collectible Items       | 7       |
| Liabilities             | 4       |
| Aircraft                | 2       |
| Art                     | 1       |


# Analysis for: all_transactions.json

## Analysis Results for `all_transactions.csv` (Data Type: Transactions)

### DataFrame Info

```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 109042 entries, 0 to 109041
Data columns (total 20 columns):
 #   Column                        Non-Null Count   Dtype  
---  ------                        --------------   -----  
 0   id                            109042 non-null  int64  
 1   portfolioId                   109042 non-null  int64  
 2   assetId                       109042 non-null  int64  
 3   type                          109042 non-null  object 
 4   description                   108888 non-null  object 
 5   transactionDate               109042 non-null  object 
 6   tradeDate                     87976 non-null   object 
 7   valueDate                     86819 non-null   object 
 8   quantity                      108853 non-null  float64
 9   price                         104134 non-null  float64
 10  priceCurrency                 105120 non-null  object 
 11  portfolioCurrency             109016 non-null  object 
 12  fxRate                        56583 non-null   float64
 13  fxRateSource                  105256 non-null  object 
 14  externalOrderId               104307 non-null  object 
 15  referencedInstrumentId        8086 non-null    float64
 16  referencedInstrumentQuantity  36 non-null      float64
 17  interest                      113 non-null     float64
 18  isReversal                    143 non-null     object 
 19  isRiskIncreased               98 non-null      object 
dtypes: float64(6), int64(3), object(11)
memory usage: 16.6+ MB

```

### First 5 Rows

| id   | portfolioId   | assetId   | type              | description                                  | transactionDate   | tradeDate   | valueDate   | quantity   | price   | priceCurrency   | portfolioCurrency   | fxRate   | fxRateSource   | externalOrderId   | referencedInstrumentId   | referencedInstrumentQuantity   | interest   | isReversal   | isRiskIncreased   |
|:-----|:--------------|:----------|:------------------|:---------------------------------------------|:------------------|:------------|:------------|:-----------|:--------|:----------------|:--------------------|:---------|:---------------|:------------------|:-------------------------|:-------------------------------|:-----------|:-------------|:------------------|
| 2    | 32662         | 32664     | DepositWithdrawal |                                              | 2020-05-25        | 2020-05-25  | 2020-05-25  | 2e+06      | 1       | EUR             | CHF                 | nan      | Manual         | WA.000002         | nan                      | nan                            | nan        |              |                   |
| 3    | 32662         | 32665     | DepositWithdrawal |                                              | 2020-05-15        | 2020-05-15  | 2020-05-15  | 4e+06      | 1       | CHF             | CHF                 | nan      | Manual         | WA.000003         | nan                      | nan                            | nan        |              |                   |
| 4    | 32662         | 32665     | Buy               | Buy Roche Holding AG (CH0012032048)          | 2020-06-10        | 2020-06-10  | 2020-06-10  | -527250    | 1       | CHF             | CHF                 | 1        | Manual         | WA.000004         | nan                      | nan                            | nan        |              |                   |
| 5    | 32662         | 25213     | Buy               | Buy Roche Holding AG (CH0012032048)          | 2020-06-10        | 2020-06-10  | 2020-06-10  | 1500       | 351.5   | CHF             | CHF                 | 1        | Manual         | WA.000004         | nan                      | nan                            | nan        |              |                   |
| 6    | 32662         | 32665     | Buy               | Buy KLMR   5.750 Perp     '21 (CH0005362097) | 2020-08-05        | 2020-08-05  | 2020-08-05  | -84300     | 1       | CHF             | CHF                 | 1        | Manual         | WA.000005         | nan                      | nan                            | nan        |              |                   |

### Value Counts for Key Columns (Top 20)

#### Value Counts for `type`

| type              | count   |
|:------------------|:--------|
| DepositWithdrawal | 29249   |
| Income            | 11221   |
| Fees              | 11048   |
| OperationalFees   | 7838    |
| Buy               | 7291    |
| FxTrade           | 6307    |
| Sell              | 5382    |
| Tax               | 4478    |
| WithholdingTax    | 4385    |
| Other             | 4082    |
| Redemption        | 2781    |
| Subscription      | 2335    |
| AssetTransfer     | 2328    |
| StampDuty         | 1879    |
| Interest          | 1390    |
| CorporateAction   | 975     |
| FxSpot            | 940     |
| Dividend          | 808     |
| Call              | 711     |
| BankFee           | 693     |

#### Value Counts for `description`

| description                                                          | count   |
|:---------------------------------------------------------------------|:--------|
| Transaction description                                              | 99876   |
| 9010/DEBIT CARD PAYMENT                                              | 349     |
| 0031/E-BANKING ORDER                                                 | 297     |
| None                                                                 | 154     |
| Portfolio closure                                                    | 154     |
| 0030/PAYMENT                                                         | 112     |
| DBO MM TRANSACTION                                                   | 93      |
| SERVICE CHARGE CALCULATION ALLOCATE CHARGES - Service Charges Amount | 88      |
| SERVICE CHARGE CALCULATION ALLOCATE CHARGES - Account Keeping Amount | 59      |
| IB0168/MM CALL                                                       | 54      |
| Option grant vesting event Meetly ES-135                             | 48      |
| Option grant vesting event Meetly ES-206                             | 48      |
| Option grant vesting event Meetly ES-202                             | 48      |
| Option grant vesting event Meetly ES-204                             | 48      |
| Option grant vesting event Meetly ES-207                             | 48      |
| Option grant vesting event Get Liquid ES-130                         | 48      |
| Option grant vesting event Meetly ES-190                             | 48      |
| Option grant vesting event Meetly ES-205                             | 48      |
| Option grant vesting event Meetly ES-134                             | 48      |
| Option grant vesting event Get Liquid ES-179                         | 48      |

### Summary Statistics for Numeric Columns

|       |      quantity |       price |   fxRate |   referencedInstrumentId |   referencedInstrumentQuantity |   interest |
|:------|--------------:|------------:|---------:|-------------------------:|-------------------------------:|-----------:|
| count |     108853.00 |   104134.00 | 56583.00 |                  8086.00 |                          36.00 |     113.00 |
| mean  |       3896.18 |     1699.95 |     1.48 |                 33004.31 |                      340434.29 |      31.11 |
| std   |    3325965.01 |   217953.09 |    73.72 |                  6021.08 |                      779117.55 |     322.98 |
| min   | -525076105.00 |       -1.00 |     0.00 |                 25202.00 |                           4.00 |       0.00 |
| 25%   |       -618.60 |        1.00 |     1.00 |                 26035.00 |                          52.00 |       0.00 |
| 50%   |        -30.00 |        1.00 |     1.00 |                 37351.00 |                        1300.00 |       0.03 |
| 75%   |        225.00 |        1.00 |     1.00 |                 38668.00 |                      100000.00 |       0.20 |
| max   |  525076105.00 | 45000000.00 | 12300.00 |                 40111.00 |                     3725000.00 |    3434.00 |

### Potential Public Entity Identification

Identified **106831** potential public entity candidates based on identifiers or name frequency (>= 3).

#### Potential Public Entities (Transactions, Top 20)

| type              | id   | price   | description                                       | quantity   |
|:------------------|:-----|:--------|:--------------------------------------------------|:-----------|
| DepositWithdrawal | 2    | 1       |                                                   | 2e+06      |
| DepositWithdrawal | 3    | 1       |                                                   | 4e+06      |
| DepositWithdrawal | 8    | 1       |                                                   | 2.5e+06    |
| DepositWithdrawal | 13   | 1       |                                                   | 6e+06      |
| DepositWithdrawal | 14   | 1       |                                                   | 1.5e+06    |
| DepositWithdrawal | 15   | 1       |                                                   | 2e+06      |
| DepositWithdrawal | 16   | 1       |                                                   | 800000     |
| DepositWithdrawal | 17   | 1       |                                                   | 1.4e+06    |
| Buy               | 26   | 15.53   | Buy Royal Dutch Shell PLC (GB00B03MLX29)          | 18000      |
| Buy               | 27   | 1       | Buy Royal Dutch Shell PLC (GB00B03MLX29)          | -279540    |
| Buy               | 28   | 1       | Buy Amazon.com Inc (US0231351067)                 | -119400    |
| Buy               | 29   | 2388    | Buy Amazon.com Inc (US0231351067)                 | 50         |
| DepositWithdrawal | 45   | 1       |                                                   | 3e+06      |
| DepositWithdrawal | 46   | 1       |                                                   | 2e+06      |
| Buy               | 47   | 102.94  | Buy 1.125 SHELL INTL FINANCE 20/24 (XS2154418144) | 300000     |
| Buy               | 48   | 1       | Buy 1.125 SHELL INTL FINANCE 20/24 (XS2154418144) | -308820    |
| DepositWithdrawal | 73   | 1       |                                                   | 500000     |
| DepositWithdrawal | 74   | 1       |                                                   | 500000     |
| DepositWithdrawal | 75   | 1       |                                                   | 500000     |
| DepositWithdrawal | 76   | 1       |                                                   | 500000     |

*Saved 106831 candidates to `all_transactions_public_entities.csv`.*

### Aggregations and Further Analysis


# Analysis for: all_portfolios.json

## Analysis Results for `all_portfolios.csv` (Data Type: Portfolios)

### DataFrame Info

```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 643 entries, 0 to 642
Data columns (total 23 columns):
 #   Column               Non-Null Count  Dtype  
---  ------               --------------  -----  
 0   id                   643 non-null    int64  
 1   name                 643 non-null    object 
 2   shortName            643 non-null    object 
 3   custodianId          511 non-null    object 
 4   custodian            531 non-null    object 
 5   currency             635 non-null    object 
 6   wealthArcCurrency    643 non-null    object 
 7   description          5 non-null      object 
 8   additionalInfo       3 non-null      object 
 9   isActive             643 non-null    bool   
 10  inceptionDate        7 non-null      object 
 11  endDate              14 non-null     object 
 12  relationshipManager  320 non-null    object 
 13  portfolioManager     309 non-null    object 
 14  assistant            1 non-null      object 
 15  branch               0 non-null      object 
 16  profitCenter         0 non-null      object 
 17  parentPortfolioId    57 non-null     float64
 18  investmentGroup      4 non-null      object 
 19  modelPortfolioId     51 non-null     float64
 20  mandateType          392 non-null    object 
 21  isManual             643 non-null    bool   
 22  type                 643 non-null    object 
dtypes: bool(2), float64(2), int64(1), object(18)
memory usage: 106.9+ KB

```

### First 5 Rows

| id    | name                         | shortName                    | custodianId   | custodian     | currency   | wealthArcCurrency   | description          | additionalInfo   | isActive   | inceptionDate   | endDate   | relationshipManager   | portfolioManager   | assistant   | branch   | profitCenter   | parentPortfolioId   | investmentGroup   | modelPortfolioId   | mandateType   | isManual   | type   |
|:------|:-----------------------------|:-----------------------------|:--------------|:--------------|:-----------|:--------------------|:---------------------|:-----------------|:-----------|:----------------|:----------|:----------------------|:-------------------|:------------|:---------|:---------------|:--------------------|:------------------|:-------------------|:--------------|:-----------|:-------|
| 32662 | Stefan Meier - Julius Bar    | Stefan Meier - Julius Bar    | 542975        | Julius Bär    | CHF        | CHF                 |                      |                  | True       |                 |           | David Gaser           | David Gaser        |             |          |                | 32682               |                   | nan                | Discretionary | True       | Client |
| 32667 | Stefan Meier - Pictet        | Stefan Meier - Pictet        | 6.60394e+07   | Pictet        | CHF        | USD                 |                      |                  | True       | 2018-06-24      |           | David Gaser           | David Gaser        |             |          |                | 32682               |                   | 32679              | Advisory      | True       | Client |
| 32673 | Stefan Meier - Non-Financial | Stefan Meier - Non-Financial |               |               | CHF        | CHF                 | Non-Financial Assets |                  | True       | 2020-01-16      |           | David Gaser           | David Gaser        |             |          |                | 32683               |                   | nan                | Advisory      | True       | Client |
| 32675 | Stefan Meier - Credit Suisse | Stefan Meier - Credit Suisse | 807523        | Credit Suisse | CHF        | EUR                 |                      |                  | True       |                 |           | David Gaser           | David Gaser        |             |          |                | 32682               |                   | 32678              | Advisory      | True       | Client |
| 32678 | Balanced Strategy (A)        | Balanced Strategy (A)        |               |               | CHF        | CHF                 |                      |                  | True       |                 |           |                       |                    |             |          |                | nan                 |                   | nan                |               | False      | Model  |

### Value Counts for Key Columns (Top 20)

#### Value Counts for `name`

| name                             | count   |
|:---------------------------------|:--------|
| Stefan Meier - Julius Bar        | 1       |
| Test Consolidated Portfolio      | 1       |
| 235930fe0eca3f8539cbc19c89de3c82 | 1       |
| d855f4c2027838297e37e0f20e0d04d1 | 1       |
| dae11117b596980176d4538e64f715d5 | 1       |
| 78d56cefd3ada498e04d93792a9f797e | 1       |
| ffe2efa7da60a5c939fee25a156719eb | 1       |
| 71f20bc50dbcaf72625522b58e2b2d3a | 1       |
| 9394db035976be57c47dc811e3ee67f9 | 1       |
| e318e9b6e51f975ec903b2f6c873736c | 1       |
| c5c1def260e30cae928bd8e12dc788e0 | 1       |
| be2ed851c078fa1f5ca07f632f652fe9 | 1       |
| 0d6ae88b46b8d1d97a3cd1935f84f81d | 1       |
| 1b3ae0091363b1f5e5c49063103e8028 | 1       |
| 4f774d006fb0e41720016cdb402a6fbc | 1       |
| fba7b2659c470fcc87693b12ff8354d9 | 1       |
| 423ed1dd0b3120268a98ff8f58c47596 | 1       |
| 71daa23826422416419a26edac278b3e | 1       |
| cfa28132669fd83e8c1924e5e5a0ad9a | 1       |
| 0dfa3e2c7e71d3495692699723268681 | 1       |

#### Value Counts for `type`

| type         | count   |
|:-------------|:--------|
| Subaccount   | 406     |
| Client       | 193     |
| Consolidated | 30      |
| Model        | 9       |
| NonFinancial | 5       |

#### Value Counts for `mandateType`

| mandateType   | count   |
|:--------------|:--------|
| None          | 251     |
| Advisory      | 207     |
| Discretionary | 180     |
| OffManagement | 3       |
| ReadOnly      | 1       |
| ExecutionOnly | 1       |

### Summary Statistics for Numeric Columns

|       |   parentPortfolioId |   modelPortfolioId |
|:------|--------------------:|-------------------:|
| count |               57.00 |              51.00 |
| mean  |            37760.77 |           32725.27 |
| std   |             2080.13 |             335.47 |
| min   |            32682.00 |           32678.00 |
| 25%   |            37535.00 |           32678.00 |
| 50%   |            37986.00 |           32678.00 |
| 75%   |            38945.00 |           32679.00 |
| max   |            40014.00 |           35074.00 |

### Potential Public Entity Identification

*No potential public entity candidates identified based on current criteria (min frequency: 3).*

### Aggregations and Further Analysis

#### Portfolio Count by Type

| Type         |   Count |
|:-------------|--------:|
| Subaccount   |     406 |
| Client       |     193 |
| Consolidated |      30 |
| Model        |       9 |
| NonFinancial |       5 |


# Analysis for: all_positions.json

## Analysis Results for `all_positions.csv` (Data Type: Positions)

### DataFrame Info

```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 10000 entries, 0 to 9999
Data columns (total 18 columns):
 #   Column                              Non-Null Count  Dtype  
---  ------                              --------------  -----  
 0   id                                  10000 non-null  int64  
 1   portfolioId                         10000 non-null  int64  
 2   assetId                             10000 non-null  int64  
 3   statementDate                       10000 non-null  object 
 4   quantity                            10000 non-null  float64
 5   price                               9539 non-null   float64
 6   priceCurrency                       10000 non-null  object 
 7   valueDate                           9323 non-null   object 
 8   priceSource                         6460 non-null   object 
 9   unitCostInPriceCurrency             5519 non-null   float64
 10  allocation                          6360 non-null   float64
 11  portfolioCurrency                   10000 non-null  object 
 12  bookCostInPortfolioCurrency         5475 non-null   float64
 13  fxRate                              7849 non-null   float64
 14  fxRateSource                        7849 non-null   object 
 15  accruedInterestInPortfolioCurrency  9086 non-null   float64
 16  accruedInterestInPriceCurrency      9086 non-null   float64
 17  cumulativeCashflowInPriceCurrency   0 non-null      object 
dtypes: float64(8), int64(3), object(7)
memory usage: 1.4+ MB

```

### First 5 Rows

| id   | portfolioId   | assetId   | statementDate   | quantity   | price   | priceCurrency   | valueDate   | priceSource   | unitCostInPriceCurrency   | allocation   | portfolioCurrency   | bookCostInPortfolioCurrency   | fxRate   | fxRateSource   | accruedInterestInPortfolioCurrency   | accruedInterestInPriceCurrency   | cumulativeCashflowInPriceCurrency   |
|:-----|:--------------|:----------|:----------------|:-----------|:--------|:----------------|:------------|:--------------|:--------------------------|:-------------|:--------------------|:------------------------------|:---------|:---------------|:-------------------------------------|:---------------------------------|:------------------------------------|
| 204  | 32662         | 32664     | 2020-05-25      | 2e+06      | 1       | EUR             | 2020-05-25  |               | nan                       | 0.247677     | CHF                 | nan                           | 1.05822  | Calculated     | 0                                    | 0                                |                                     |
| 205  | 32662         | 32664     | 2020-05-26      | 2e+06      | 1       | EUR             | 2020-05-26  |               | nan                       | 0.248813     | CHF                 | nan                           | 1.06307  | Calculated     | 0                                    | 0                                |                                     |
| 206  | 32662         | 32664     | 2020-05-27      | 2e+06      | 1       | EUR             | 2020-05-27  |               | nan                       | 0.248865     | CHF                 | nan                           | 1.06433  | Calculated     | 0                                    | 0                                |                                     |
| 207  | 32662         | 32664     | 2020-05-28      | 2e+06      | 1       | EUR             | 2020-05-28  |               | nan                       | 0.24973      | CHF                 | nan                           | 1.06745  | Calculated     | 0                                    | 0                                |                                     |
| 208  | 32662         | 32664     | 2020-05-29      | 2e+06      | 1       | EUR             | 2020-05-29  |               | nan                       | 0.250282     | CHF                 | nan                           | 1.06839  | Calculated     | 0                                    | 0                                |                                     |

### Value Counts for Key Columns (Top 20)

### Summary Statistics for Numeric Columns

|       |     quantity |    price |   unitCostInPriceCurrency |   allocation |   bookCostInPortfolioCurrency |   fxRate |   accruedInterestInPortfolioCurrency |   accruedInterestInPriceCurrency |
|:------|-------------:|---------:|--------------------------:|-------------:|------------------------------:|---------:|-------------------------------------:|---------------------------------:|
| count |     10000.00 |  9539.00 |                   5519.00 |      6360.00 |                       5475.00 |  7849.00 |                              9086.00 |                          9086.00 |
| mean  |    630773.44 |   383.02 |                    428.85 |         0.17 |                     425034.00 |     1.82 |                               351.66 |                           336.43 |
| std   |   1161128.17 |  1682.29 |                   1796.23 |         0.22 |                    1340292.36 |    36.54 |                              1336.88 |                          1266.57 |
| min   | -16109999.49 |    -2.43 |                 -15200.00 |        -0.02 |                    -548467.22 |     0.01 |                                -1.00 |                            -1.00 |
| 25%   |      1500.00 |     1.00 |                     52.71 |         0.04 |                     100797.59 |     0.92 |                                 0.00 |                             0.00 |
| 50%   |     78852.57 |    58.88 |                    102.89 |         0.08 |                     300684.41 |     1.00 |                                 0.00 |                             0.00 |
| 75%   |    800000.00 |   113.75 |                    222.14 |         0.25 |                     790650.00 |     1.09 |                                 0.00 |                             0.00 |
| max   |  45000000.00 | 54032.86 |                  47022.86 |         1.00 |                   92061702.21 |  1741.65 |                             22564.00 |                         22564.00 |

### Potential Public Entity Identification

*No potential public entity candidates identified based on current criteria (min frequency: 3).*

### Aggregations and Further Analysis


# Analysis for: all_portfolio_metrics.json

## Analysis Results for `all_portfolio_metrics.csv` (Data Type: Portfolio_metrics)

### DataFrame Info

```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 10000 entries, 0 to 9999
Data columns (total 4 columns):
 #   Column           Non-Null Count  Dtype  
---  ------           --------------  -----  
 0   id               10000 non-null  int64  
 1   portfolioId      10000 non-null  int64  
 2   statementDate    10000 non-null  object 
 3   overdraftsCount  7749 non-null   float64
dtypes: float64(1), int64(2), object(1)
memory usage: 312.6+ KB

```

### First 5 Rows

| id   | portfolioId   | statementDate   | overdraftsCount   |
|:-----|:--------------|:----------------|:------------------|
| 24   | 37739         | 2024-01-17      | 0                 |
| 25   | 37616         | 2024-01-17      | 0                 |
| 26   | 37863         | 2024-01-17      | 0                 |
| 27   | 37714         | 2024-01-17      | 0                 |
| 28   | 37651         | 2024-01-17      | nan               |

### Value Counts for Key Columns (Top 20)

### Summary Statistics for Numeric Columns

|       |   overdraftsCount |
|:------|------------------:|
| count |           7749.00 |
| mean  |              0.18 |
| std   |              0.44 |
| min   |              0.00 |
| 25%   |              0.00 |
| 50%   |              0.00 |
| 75%   |              0.00 |
| max   |              2.00 |

### Potential Public Entity Identification

*No potential public entity candidates identified based on current criteria (min frequency: 3).*

### Aggregations and Further Analysis

*Portfolio name column not found for metrics aggregation.*

