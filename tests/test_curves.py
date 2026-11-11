"""Offline tests: run with `python -m unittest discover -s tests` from the repo root.

Synthetic data for the mechanics; the cached EIA file in data/ for checks against real history.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import curves as cv  # noqa: E402
import strategy as st  # noqa: E402
import update  # noqa: E402
from data import load_futures  # noqa: E402


class ExpiryTests(unittest.TestCase):
    def test_wti_may_2020_expired_on_21_april(self):
        self.assertEqual(cv.expiry("CL", 2020, 5), pd.Timestamp("2020-04-21"))

    def test_products_expire_last_business_day_of_prior_month(self):
        self.assertEqual(cv.expiry("RB", 2024, 1), pd.Timestamp("2023-12-29"))
        self.assertEqual(cv.expiry("HO", 2020, 6), pd.Timestamp("2020-05-29"))

    def test_gas_expires_three_business_days_before_delivery(self):
        self.assertEqual(cv.expiry("NG", 2024, 1), pd.Timestamp("2023-12-27"))

    def test_roll_flag_follows_expiry_even_across_a_data_gap(self):
        dates = pd.DatetimeIndex(["2020-04-20", "2020-04-23", "2020-04-24"])  # 21st (expiry) and 22nd missing
        self.assertEqual(cv.roll_flags(dates, "CL").tolist(), [False, True, False])


class RealDataTests(unittest.TestCase):
    """On predicted roll days the calendar spreads should shift by one contract."""

    @classmethod
    def setUpClass(cls):
        cls.prices = load_futures().loc["2008":]

    def test_predicted_rolls_match_the_data(self):
        for r in ["CL", "RB", "HO", "NG"]:
            px = self.prices[[f"{r}{k}" for k in range(1, 5)]].dropna()
            px = px[(px > 0).all(axis=1)]
            lp = np.log(px)
            s = {k: lp[f"{r}{k}"] - lp[f"{r}{k + 1}"] for k in (1, 2, 3)}
            stay = (s[1] - s[1].shift()).abs() + (s[2] - s[2].shift()).abs()
            move = (s[1] - s[2].shift()).abs() + (s[2] - s[3].shift()).abs()
            flags = cv.roll_flags(px.index, r)
            self.assertGreater((move < stay)[flags].mean(), 0.8, r)
            self.assertLess((move < stay)[~flags].mean(), 0.25, r)

    def test_second_month_return_on_negative_price_day(self):
        r = cv.held_returns(self.prices, "CL", 2)
        self.assertAlmostEqual(r.loc["2020-04-20"], 20.43 / 25.03 - 1, places=6)
        self.assertAlmostEqual(r.loc["2020-04-21"], 11.57 / 20.43 - 1, places=6)
        # 22 April: June is now contract 1
        self.assertAlmostEqual(r.loc["2020-04-22"], 13.78 / 11.57 - 1, places=6)


class CurveMathTests(unittest.TestCase):
    def setUp(self):
        idx = pd.bdate_range("2021-01-04", periods=5)
        self.idx = idx

    def test_held_returns_switch_contract_on_roll_day(self):
        # CL Feb-2021 contract expired 2021-01-20; 2021-01-21 is the roll day
        idx = pd.DatetimeIndex(["2021-01-19", "2021-01-20", "2021-01-21"])
        px = pd.DataFrame({"CL1": [50, 51, 60], "CL2": [55, 56, 66], "CL3": [60, 61, 72], "CL4": [65, 66, 78]},
                          index=idx, dtype=float)
        r = cv.held_returns(px, "CL", 2)
        self.assertAlmostEqual(r.loc["2021-01-20"], 56 / 55 - 1)
        self.assertAlmostEqual(r.loc["2021-01-21"], 60 / 56 - 1)  # yesterday's 2nd is today's 1st
        r1 = cv.held_returns(px, "CL", 1)
        self.assertAlmostEqual(r1.loc["2021-01-21"], 60 / 56 - 1)  # front rolled into 2nd at expiry close

    def test_carry_sign(self):
        px = pd.DataFrame({"CL2": [100.0, 100.0], "CL4": [90.0, 110.0]}, index=self.idx[:2])
        c = cv.carry(px, "CL")
        self.assertGreater(c.iloc[0], 0)   # backwardation
        self.assertLess(c.iloc[1], 0)      # contango
        self.assertAlmostEqual(c.iloc[0], np.log(100 / 90) * 6)

    def test_seasonal_adjust_uses_only_past_years(self):
        idx = pd.date_range("2010-01-31", periods=120, freq="ME")
        s = pd.Series(np.random.default_rng(0).normal(size=120), index=idx)
        a = cv.seasonal_adjust(s)
        shocked = s.copy()
        shocked.iloc[80:] += 100
        b = cv.seasonal_adjust(shocked)
        pd.testing.assert_series_equal(a.iloc[:80], b.iloc[:80])
        self.assertTrue(a.iloc[:36].isna().all())  # needs three past years


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.DatetimeIndex(["2021-01-29", "2021-02-26"])
        self.iv = pd.DataFrame(1.0, index=self.dates, columns=st.ROOTS)

    def test_long_short_is_dollar_neutral(self):
        sig = pd.DataFrame([[0.3, -0.1, 0.2, -0.4]] * 2, index=self.dates, columns=st.ROOTS)
        w = st.long_short(sig, self.iv, 2).iloc[0]
        self.assertAlmostEqual(w.sum(), 0.0)
        self.assertAlmostEqual(w.abs().sum(), 1.0)
        self.assertEqual(list(w[w > 0].index), ["CL", "HO"])

    def test_time_series_is_flat_in_contango(self):
        sig = pd.DataFrame([[0.3, -0.1, 0.2, -0.4]] * 2, index=self.dates, columns=st.ROOTS)
        w = st.time_series(sig, self.iv).iloc[0]
        self.assertEqual(w.to_dict(), {"CL": 0.25, "RB": 0.0, "HO": 0.25, "NG": 0.0})

    def test_simulate_compounds_and_never_uses_returns_before_the_decision(self):
        days = pd.bdate_range("2021-01-25", "2021-02-26")
        rets = pd.DataFrame(0.0, index=days, columns=st.ROOTS)
        rets.loc[:"2021-01-29", "CL"] = 0.5  # huge moves before the first rebalance must not count
        rets.loc["2021-02-01":"2021-02-02", "CL"] = 0.01
        w = pd.DataFrame(0.0, index=self.dates, columns=st.ROOTS)
        w["CL"] = 1.0
        rolls = pd.DataFrame(False, index=days, columns=st.ROOTS)
        sim = st.simulate(w, rets, rolls, st.Config(cost_bps=0, roll_bps=0))
        self.assertAlmostEqual((1 + sim.ret).prod(), 1.01 ** 2)

    def test_drawdown(self):
        r = pd.Series([0.10, -0.50, 0.20])
        self.assertAlmostEqual(st.drawdown(r).min(), -0.5)


class UpdateTests(unittest.TestCase):
    def test_live_carry_matches_backtest_definition(self):
        curve = pd.Series([80, 78, 77, 75, 74.0], index=pd.date_range("2027-01-01", periods=5, freq="MS"))
        self.assertAlmostEqual(update.live_carry(curve), np.log(78 / 75) * 6)

    def test_live_carry_needs_four_contracts(self):
        self.assertTrue(np.isnan(update.live_carry(pd.Series([1.0, 2.0], index=pd.date_range("2027-01-01", periods=2, freq="MS")))))

    def test_headline_filter(self):
        self.assertTrue(update.ENERGY_WORDS.search("OPEC crude production rises"))
        self.assertTrue(update.ENERGY_WORDS.search("Diesel still costing close to £2"))
        self.assertIsNone(update.ENERGY_WORDS.search("Food prices in Latvia could rise again"))
        self.assertIsNone(update.ENERGY_WORDS.search("Gasket maker beats estimates"))


if __name__ == "__main__":
    unittest.main()
