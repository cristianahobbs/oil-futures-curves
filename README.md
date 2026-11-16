# oil-futures-curves

[![tests](https://github.com/cristianahobbs/oil-futures-curves/actions/workflows/tests.yml/badge.svg)](https://github.com/cristianahobbs/oil-futures-curves/actions/workflows/tests.yml)
[![daily brief](https://github.com/cristianahobbs/oil-futures-curves/actions/workflows/daily.yml/badge.svg)](https://github.com/cristianahobbs/oil-futures-curves/actions/workflows/daily.yml)

What does the shape of the oil futures curve tell you, and what does it cost you as an investor?

This repo tracks the futures curves for WTI crude, RBOB gasoline, heating oil (ULSD) and natural gas.
It has three parts:

1. **A daily brief.** Every weekday evening a GitHub Action pulls today's curves, spot prices, Cushing
   stocks and energy headlines, and updates the section below.
2. **A carry backtest.** Does a backwardated curve predict returns, and can you trade on it?
   Tested on daily data from 2008 to 2024.
3. **A case study of 20 April 2020**, the day WTI settled at −$37.63.

There is also a [Streamlit app](#curve-explorer-app) for looking at the curve on any date since the 1980s.

**Key terms.** A futures curve is the price of the same commodity for delivery in different months.
- **Contango:** later months cost more. The usual state when supply is plentiful and storage costs money.
- **Backwardation:** later months cost less. The usual state when supply is tight.

## Today

<!-- today:start -->
### Energy brief: Monday 16 November 2026

**Curves and signals** (futures from Yahoo Finance; carry is the annualised slope between the 2nd and
4th listed contracts, the same definition as the backtest)

| | Front month | 12th month | Curve | Carry vs 5-year norm for November | Long only when backwardated | Carry long-short |
|---|---|---|---|---|---|---|
| WTI crude oil | $85.23 (Dec 2026) | $73.49 | backwardation (+21.3%) | +19.5% | long | long |
| RBOB gasoline | $2.525 (Dec 2026) | $2.304 | flat (-1.6%) | +3.1% | flat | short |
| Heating oil / ULSD | $4.074 (Dec 2026) | $3.317 | backwardation (+23.8%) | +14.2% | long | short |
| Natural gas | $3.13 (Dec 2026) | $3.27 | backwardation (+221.2%) | +152.0% | long | long |

**Spot** (EIA, as of 11 Nov 2026). Brent trades $2.52 above WTI.

| | Price | 1 week | 1 month |
|---|---|---|---|
| WTI | $89.62 | -2.3% | -5.7% |
| Brent | $92.14 | +0.3% | -29.1% |

**Cushing crude stocks** (EIA weekly, 06 Nov 2026): 27.4 million barrels,
+0.1 million on the week, vs 25.0 million on average for this week over the past five years.

**Headlines**

- [Fall’s Arrival Brings Deceleration To Spiking WKY Gas Prices](https://news.google.com/rss/articles/CBMiqwFBVV95cUxQSlJYRVlHYWpqVXdxTmxqRjNDUkJ6cGllZ01fSHF2SkpLeFZUUmxlN3NrWnhuU012WnNMNE40M1o1WnZKUWdZSEloUDlSQ3hYbGNnSDBwYUdRY21uT19BLUVGZkJTTy0tQlJHMzFIRlh0alBkczJtb0VtUklPVzhZemZuVmRPYjB6Q3NfU2p6RGY0aURuZ2FvV1FqWDJTVHJwNHpZbWlYR05ESTA?oc=5) (WKDZ)
- [Heating oil prices go down slightly, but costs still hurting Mainers](https://news.google.com/rss/articles/CBMigAJBVV95cUxQallnU201WDNVLTh4cFJ6a1pQVXUwMkZiNEVuV2owNnoxMnp0ZXp6UlRzN1QzRXJKY1V1ZURfTDB5bWRYTmhyRWR1T0NCWnRjVllVMEt3RWxVenpYS1ZZY1FvV1VDTWktMURiOGs4WXdSdGZVUDE2UXRKSE5FNEhPbFpmRUJrTFBiaEhxYnFUMWZrYXV3bmRLbktjZTZ4MjlqU2VrY3pCdTBEUnlnSXJGdnpNQmV1Rk9YNklsMDhqUDBUNWF3TFh4NW1JMzNiSWxYTU02RVlqNTBLYWJnX2I3TUIxRXZiZzI0ZTBHZ2hkcW44V2lrSVQwbDhXYUpnOWpJ?oc=5) (newscentermaine.com)
- [NY gas prices fall as Thanksgiving travel approaches](https://news.google.com/rss/articles/CBMimgFBVV95cUxQMng3anJZc19lWHVYZVlDOU9ITXlsYUZIMmp0NnpNdVlKUVFQTkJ2T09qb25UN2EzYXJJcUFjRGZSdXhxU2JUN3JiaUIyZFdSQkNjQzRYeFN3S093M2RqVkE2ZEhOaEJxWUE3cmc0c05xbndZZWw2R0hMbkZtR1NIZ3otZkVxa3pnREtLMVBsLXRuYjBGNk5rRXBB?oc=5) (Olean Times Herald)
- [El Niño could lower US natural gas heating bills, but heating oil prices may rise 21%](https://news.google.com/rss/articles/CBMieEFVX3lxTE42dDBfMnpBVnRzNGlGYzhxNU53R0ozX2l6bVV1M0VfOGdibUM2S2tLZ2ZmWm9ZMVVkcFdWZG1QNkdvYXBZTWl3N1BrTnRSSjBFcHZKbERCbU9laUdoRXRfT1dZVjVqTG1kazlCWlpUcXlkUGZMcDBaMg?oc=5) (The Cool Down)
- [Oil Is Falling. Why Aren’t Prices?](https://news.google.com/rss/articles/CBMidkFVX3lxTE5GajY4dlNBOVV2VnpfWjI1UlpFRldMWEN2QUZiVFpZcnRXVVhpZnV4Zm8xTGl2cm84N1h6NXJvdnRKSmVuYjV6c1JVN1ptdkRXM2hONUV0Rm5pYjdFTkg2QWp0NzZ3MEJYR0xrcUQtRS1COFpQa0HSAXtBVV95cUxQRENVMHlZR1l6RGF4NVY3MWtxM3RISTNLR205MHJTNTU2LUVISDJWWG5vcTFSY2hhdGQ5VDlKcUxLMG9NN3NDNmJwMFJCVTE1bGo5Vk1tNVlXN0hkelVwSzU3aVFiM2dXaGEyMDltMnA3enpyWUpPT010YXM?oc=5) (Inquirer.net)
- [Southwest Airlines gains as lower oil prices and steadier post-outage recovery support shares](https://news.google.com/rss/articles/CBMixAFBVV95cUxQbHNiN2RSMnZ2NUNRZFpaUmMwdFpfdkJ3aUktUTJ5MWpLWnJnT2FnQW9qS2wxdjhTYlJFajJmWmRCMWZ3emZyVE0xVEpKNXlZY0pNUVFqOHdWajdJWUNwLXJpNVBMVk9fU3pBOThvME1zeVBjMDNqMmZHRkhvMUNQQ0NtWlk0MGdLd21DTTRNWno2dFBSaHdTcUJsQnpPbENSNmdnbnU3dndTQzJ3YVpscFBmY3FBR2ptTlczUmg5ejJYei1y?oc=5) (Quiver Quantitative)
- [TREASURIES-US yields ease as oil prices drop 3%](https://news.google.com/rss/articles/CBMioAFBVV95cUxNT0Jzc2wtd05MQXE2U1BVMnhCUVAyUjJoemlzNW9uRXV4R1l2QTNXdUcxOTJuN3kzeGxMajVEU3NoNXowTVBPcEpVMXk0aHJ3eWxMZlU4M2FVVnBQM0EwaHUtaEo2RU5OdXQzN1lidDhFekl3dmlZYlo2N3V6RkJoelNLdncxVHpndmktRnNLMnlfRzJjOTJRVENEeUo1RnI0?oc=5) (marketscreener.com)
- [AAA: Tennessee gas prices fall 17 cents](https://news.google.com/rss/articles/CBMifkFVX3lxTE5CWFpzOVZ2T0VDazBCWWJ0UTIwMnp1M0RMM0FDLVV2aUt0Ynk1NlNHbnFFb1k1cVV6eUViQW0xS0xNcV9TY2xLbUxsdm5meV9idnlGaDNLOEJ3blhQX2xqMHdiS2hVU1FJUkliYm1NYlh0Ml9OdUN5QTBoQVl4QQ?oc=5) (Kingsport Times News)

**From EIA**

- [Hydropower generation in the Southwest fell to record lows this summer](https://www.eia.gov/todayinenergy/detail.php?id=68445)
- [EIA forecasts Alaskan crude oil production to grow 13% in 2027](https://www.eia.gov/todayinenergy/detail.php?id=68444)
- [U.S. crude oil imports from Venezuela in July were highest since 2017](https://www.eia.gov/todayinenergy/detail.php?id=68425)

<sub>Signals follow the rules tested in this repo. The backtest shows they are weak, so treat them as
a description of the curve, not a recommendation. Not investment advice.</sub>

[Previous briefs](docs/daily/)
<!-- today:end -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/charts/live_curves-dark.png">
  <img alt="Today's futures curves for WTI, gasoline, heating oil and natural gas by delivery month" src="docs/charts/live_curves.png">
</picture>

## Findings

<!-- findings:start -->
**What owning oil through futures actually earned.** Anything that holds futures (most oil and gas ETFs and ETCs) earns the futures return, not the price change. In contango every roll sells the cheap expiring contract and buys a dearer one.

| | Front-month price, per year | Holding rolled futures, per year | Difference (roll yield) |
|---|---|---|---|
| WTI crude oil | -1.1% | -8.8% | -7.7% |
| RBOB gasoline | +0.4% | +3.6% | +3.1% |
| Heating oil / ULSD | -0.3% | -0.3% | -0.0% |
| Natural gas | -8.8% | -29.8% | -21.0% |

**Carry strategies.** Backtest 2008-01 to 2024-03, daily data, monthly rebalancing, second-month contracts, net of costs, excess of cash. Generated by `python main.py`; raw numbers are in [`output/`](output/).

| | Long-only, all four | Long only when backwardated | Carry long-short | Carry long-short, seasonally adjusted |
|---|---|---|---|---|
| Annual return | -6.4% | -1.1% | -1.8% | 1.9% |
| Volatility | 30.3% | 16.4% | 13.6% | 13.1% |
| Sharpe | -0.07 | 0.01 | -0.06 | 0.21 |
| t-stat (Newey-West) | -0.26 | 0.03 | -0.37 | 0.90 |
| Max drawdown | -93.6% | -55.3% | -59.8% | -42.4% |
| Worst month | -38.4% | -24.3% | -16.1% | -17.4% |
| Annual turnover | 0.9x | 2.2x | 6.5x | 7.2x |

**By commodity.** Does a backwardated curve at month-end predict next month's return?

| | Share of months backwardated | Next-month return, backwardated | Next-month return, contango | Sharpe, always long | Sharpe, long only when backwardated |
|---|---|---|---|---|---|
| WTI crude oil | 40% | +1.3% | -1.1% | -0.02 | 0.33 |
| RBOB gasoline | 61% | -0.4% | +2.9% | 0.28 | -0.12 |
| Heating oil / ULSD | 41% | +1.2% | -0.1% | 0.16 | 0.26 |
| Natural gas | 22% | -4.9% | -1.2% | -0.52 | -0.49 |

Historical simulation, not investment advice.
<!-- findings:end -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/charts/equity-dark.png">
  <img alt="Growth of $1 for each carry strategy and a long-only energy basket, with drawdowns, 2008 to 2024" src="docs/charts/equity.png">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/charts/predictive-dark.png">
  <img alt="Average next-month return after backwardated and contango month-ends for each commodity" src="docs/charts/predictive.png">
</picture>

**What this means for an investor:**

- **Holding oil through futures has been expensive.** Contango made the rolled WTI position lose about
  8 points a year more than the price itself fell. Natural gas was much worse. Before buying a
  commodity ETF or ETC, check the curve. If it's in steep contango, the price has to rise just for you
  to break even.
- **Backwardation is a mildly useful signal for crude and heating oil, not a strategy on its own.**
  Holding WTI only while its curve was backwardated raised its Sharpe ratio from about 0 to 0.3.
  Across all four commodities the effect is not statistically significant.
- **Gasoline and natural gas curves are seasonal.** Gasoline costs more for summer delivery and gas
  for winter. The raw slope of those curves mostly measures the calendar, which is why carry pointed
  the wrong way for them. Comparing today's slope with the usual slope for the same month (the
  "seasonally adjusted" strategy) fixes some of this.

## 20 April 2020: when oil cost less than nothing

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/charts/april_2020-dark.png">
  <img alt="Front and second-month WTI futures in spring 2020, with the front contract falling to minus 37.63 dollars on 20 April, above a chart of Cushing crude stocks rising to 65 million barrels" src="docs/charts/april_2020.png">
</picture>

On 2 January 2020 the WTI curve was almost flat, at around $61 for each of the first four months.
Then COVID-19 lockdowns cut demand while production kept flowing, and the extra crude had to be stored.
WTI futures are settled by physical delivery at Cushing, Oklahoma. Crude stocks there rose from
**37.2 million barrels** at the end of February to **65.4 million** by 1 May.

The May contract expired on 21 April. Anyone still holding it then had to take delivery of oil at
Cushing, and with storage almost full, almost nobody could. On 20 April, holders sold at any price,
and the contract settled at **−$37.63**, down from $18.27 the previous day. The June contract settled
at **$20.43** the same day, $58 above May. The problem was in one contract and one location, not the
oil market as a whole.

The case study shows two lessons for investors:

- **Which contract you hold matters.** A position in the front-month contract lost 306% of its value
  in one day; it ended the day owing money. A position in the second month lost 58% from 1 March to
  20 April, which was painful but never negative. This is why the backtest holds the second contract
  and rolls before expiry. Commodity indices and ETFs follow similar rules.
- **The curve warned you.** By 20 April, the annualised slope between the 2nd and 4th contracts was
  about −200%: the market was charging heavily to store oil for later.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/charts/snapshots-dark.png">
  <img alt="WTI curves for contracts 1 to 4 on three dates: flat in July 2008, steep contango in April 2020, backwardation in March 2022" src="docs/charts/snapshots.png">
</picture>

## Method

| | |
|---|---|
| History | Daily NYMEX settlements for contracts 1–4 from the [EIA](https://www.eia.gov/dnav/pet/pet_pri_fut_s1_d.htm), cached in [`data/futures.csv`](data/futures.csv). EIA stopped publishing these on 5 April 2024, so the backtest ends in March 2024. |
| Today's curves | Last prices for each listed contract from Yahoo Finance, refreshed daily. |
| Spot and stocks | WTI and Brent spot prices, and weekly Cushing crude stocks, from the EIA. |
| Contract rolls | EIA labels contracts by position, not delivery month. [`curves.py`](curves.py) rebuilds each contract's expiry date from the exchange rules, so returns never mix two different contracts. A test checks that on predicted roll days the price gaps between contracts shift by one in over 80% of cases, against under 25% on other days. |
| Position | The second-month contract, rolled when it becomes the front month. It is never held into expiry. |
| Carry | Annualised slope between contracts 2 and 4: ln(C2 / C4) × 6. Positive means backwardation. |
| Seasonal adjustment | Carry minus its average for the same calendar month over the previous five years. Only past data is used. |
| Strategies | Rebalanced at each month-end and sized by inverse 60-day volatility. Long-short holds the two highest-carry commodities long and the two lowest short. |
| Costs | 5 bps per unit traded at rebalancing, plus 2 bps per roll. |

## Limitations

- Four commodities is a small universe. Published carry studies use 20 or more futures across energy,
  metals and agriculture, where carry works better because the commodities are less correlated.
- Returns are excess returns: they leave out the interest earned on collateral.
- EIA history stops in April 2024. Yahoo only covers contracts that are still trading, so the
  2024–2026 period can't be backtested from free data.
- The seasonal adjustment needs three years of history, so it starts later for gasoline (from 2008).

## Curve explorer app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Pick a commodity and a date to see the first four contracts that day, labelled with their delivery
months. You can compare two dates, view today's full curve, or browse the month-end carry history.
Presets include the 2008 peak, April 2020 and March 2022.

## Run it

```bash
python main.py               # backtest and case study; rewrites the Findings section
python charts.py             # README charts
python update.py             # today's brief: live curves, spot, Cushing, headlines; rewrites Today
python -m unittest discover -s tests -v
```

| File | |
|---|---|
| [`data.py`](data.py) | EIA and Yahoo downloads with on-disk cache |
| [`curves.py`](curves.py) | Expiry calendar, roll-adjusted returns, carry, seasonal adjustment |
| [`strategy.py`](strategy.py) | Signals, monthly portfolio simulation with costs, statistics |
| [`main.py`](main.py) | Backtest, robustness checks, roll cost and 2020 case study; writes `output/` |
| [`update.py`](update.py) | Daily brief, run by [`.github/workflows/daily.yml`](.github/workflows/daily.yml) |
| [`app.py`](app.py) | Streamlit curve explorer |

Headlines link to their publishers through Google News. EIA articles are from
[Today in Energy](https://www.eia.gov/todayinenergy/). Nothing here is investment advice.

## References

- Koijen, R., Moskowitz, T., Pedersen, L. H. and Vrugt, E. (2018). Carry. *Journal of Financial Economics*.
- Gorton, G. and Rouwenhorst, K. G. (2006). Facts and Fantasies about Commodity Futures. *Financial Analysts Journal*.
- Erb, C. and Harvey, C. (2006). The Strategic and Tactical Value of Commodity Futures. *Financial Analysts Journal*.
