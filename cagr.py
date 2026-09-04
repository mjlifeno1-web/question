# ============================================================
# 📊 台股 AI 投資分析器 V5
# CAGR + PEG + EPS Growth + Bear/Base/Bull Valuation
# ============================================================

import os
import time
import math
import json
from typing import Optional, Dict, Any, List

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# Gemini
try:
    from google import genai
except ImportError:
    genai = None


# ============================================================
# 1. 基本設定
# ============================================================

st.set_page_config(
    page_title="台股 AI 投資分析器 V5",
    page_icon="📊",
    layout="wide"
)

st.title("📊 台股 AI 投資分析器 V5")
st.caption("CAGR + PEG + EPS 成長 + 合理價 + AI 基本面分析")


# ============================================================
# 2. Sidebar
# ============================================================

with st.sidebar:

    st.header("⚙️ 設定")

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="如果不使用 AI 分析，可以留白"
    )

    gemini_model = st.selectbox(
        "Gemini 模型",
        [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash"
        ]
    )

    st.divider()

    st.subheader("估值參數")

    forecast_years = st.slider(
        "預估年數",
        min_value=3,
        max_value=7,
        value=5
    )

    default_bear = st.slider(
        "Bear CAGR (%)",
        0.0,
        30.0,
        8.0,
        0.5
    )

    default_base = st.slider(
        "Base CAGR (%)",
        0.0,
        30.0,
        15.0,
        0.5
    )

    default_bull = st.slider(
        "Bull CAGR (%)",
        0.0,
        40.0,
        20.0,
        0.5
    )

    st.divider()

    st.info(
        "⚠️ 本程式為量化研究工具，不構成投資建議。"
    )


# ============================================================
# 3. 工具函數
# ============================================================

def safe_float(value, default=np.nan):

    try:
        if value is None:
            return default

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return default

        return value

    except Exception:
        return default


def fmt(value, digits=2):

    value = safe_float(value)

    if np.isnan(value):
        return "N/A"

    return f"{value:,.{digits}f}"


def format_symbol(symbol: str) -> str:

    symbol = symbol.strip().upper()

    if symbol.isdigit():
        return symbol + ".TW"

    if "." not in symbol:
        return symbol + ".TW"

    return symbol


def calculate_cagr(start_value, end_value, years):

    start_value = safe_float(start_value)
    end_value = safe_float(end_value)

    if (
        np.isnan(start_value)
        or np.isnan(end_value)
        or start_value <= 0
        or end_value <= 0
        or years <= 0
    ):
        return np.nan

    return (end_value / start_value) ** (1 / years) - 1


def future_value(value, cagr, years):

    value = safe_float(value)
    cagr = safe_float(cagr)

    if np.isnan(value) or np.isnan(cagr):
        return np.nan

    return value * ((1 + cagr) ** years)


def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def safe_growth_score(value):

    value = safe_float(value)

    if np.isnan(value):
        return 0

    if value >= 0.25:
        return 30

    if value >= 0.20:
        return 27

    if value >= 0.15:
        return 24

    if value >= 0.10:
        return 20

    if value >= 0.05:
        return 15

    if value >= 0:
        return 10

    return 3


# ============================================================
# 4. 取得股票資料
# ============================================================

@st.cache_data(ttl=900)
def get_stock_data(symbol):

    ticker = yf.Ticker(symbol)

    # --------------------------------------------------------
    # 基本資訊
    # --------------------------------------------------------

    try:
        info = ticker.info
    except Exception:
        info = {}

    # --------------------------------------------------------
    # 股價
    # --------------------------------------------------------

    hist = ticker.history(period="2y", auto_adjust=False)

    if hist.empty:
        raise ValueError("無法取得股票價格資料")

    hist = hist.dropna()

    current_price = safe_float(
        hist["Close"].iloc[-1]
    )

    # --------------------------------------------------------
    # 技術指標
    # --------------------------------------------------------

    hist["MA20"] = hist["Close"].rolling(20).mean()
    hist["MA60"] = hist["Close"].rolling(60).mean()
    hist["RSI"] = calculate_rsi(hist["Close"])

    ma20 = safe_float(hist["MA20"].iloc[-1])
    ma60 = safe_float(hist["MA60"].iloc[-1])
    rsi = safe_float(hist["RSI"].iloc[-1])

    # --------------------------------------------------------
    # 基本面
    # --------------------------------------------------------

    market_cap = safe_float(
        info.get("marketCap")
    )

    trailing_eps = safe_float(
        info.get("trailingEps")
    )

    forward_eps = safe_float(
        info.get("forwardEps")
    )

    trailing_pe = safe_float(
        info.get("trailingPE")
    )

    forward_pe = safe_float(
        info.get("forwardPE")
    )

    revenue_growth = safe_float(
        info.get("revenueGrowth")
    )

    earnings_growth = safe_float(
        info.get("earningsGrowth")
    )

    profit_margin = safe_float(
        info.get("profitMargins")
    )

    operating_margin = safe_float(
        info.get("operatingMargins")
    )

    roe = safe_float(
        info.get("returnOnEquity")
    )

    debt_to_equity = safe_float(
        info.get("debtToEquity")
    )

    free_cash_flow = safe_float(
        info.get("freeCashflow")
    )

    # --------------------------------------------------------
    # 財報資料
    # --------------------------------------------------------

    try:
        income_stmt = ticker.income_stmt
    except Exception:
        income_stmt = pd.DataFrame()

    try:
        cashflow_stmt = ticker.cashflow
    except Exception:
        cashflow_stmt = pd.DataFrame()

    # --------------------------------------------------------
    # Revenue CAGR
    # --------------------------------------------------------

    revenue_cagr_3y = np.nan
    revenue_cagr_5y = np.nan

    if (
        not income_stmt.empty
        and "Total Revenue" in income_stmt.index
    ):

        revenue_series = (
            income_stmt.loc["Total Revenue"]
            .dropna()
            .sort_index()
        )

        if len(revenue_series) >= 4:

            start = revenue_series.iloc[-4]
            end = revenue_series.iloc[-1]

            revenue_cagr_3y = calculate_cagr(
                start,
                end,
                3
            )

        if len(revenue_series) >= 6:

            start = revenue_series.iloc[-6]
            end = revenue_series.iloc[-1]

            revenue_cagr_5y = calculate_cagr(
                start,
                end,
                5
            )

    # --------------------------------------------------------
    # FCF CAGR
    # --------------------------------------------------------

    fcf_cagr_3y = np.nan
    fcf_cagr_5y = np.nan

    if not cashflow_stmt.empty:

        if (
            "Free Cash Flow" in cashflow_stmt.index
        ):

            fcf_series = (
                cashflow_stmt.loc["Free Cash Flow"]
                .dropna()
                .sort_index()
            )

        elif (
            "Operating Cash Flow" in cashflow_stmt.index
            and "Capital Expenditure" in cashflow_stmt.index
        ):

            ocf = cashflow_stmt.loc[
                "Operating Cash Flow"
            ]

            capex = cashflow_stmt.loc[
                "Capital Expenditure"
            ]

            fcf_series = (
                ocf + capex
            ).dropna().sort_index()

        else:

            fcf_series = pd.Series(dtype=float)

        if len(fcf_series) >= 4:

            positive_values = (
                fcf_series.iloc[-4:]
            )

            if (
                positive_values.iloc[0] > 0
                and positive_values.iloc[-1] > 0
            ):

                fcf_cagr_3y = calculate_cagr(
                    positive_values.iloc[0],
                    positive_values.iloc[-1],
                    3
                )

        if len(fcf_series) >= 6:

            positive_values = (
                fcf_series.iloc[-6:]
            )

            if (
                positive_values.iloc[0] > 0
                and positive_values.iloc[-1] > 0
            ):

                fcf_cagr_5y = calculate_cagr(
                    positive_values.iloc[0],
                    positive_values.iloc[-1],
                    5
                )

    # --------------------------------------------------------
    # EPS CAGR
    #
    # yfinance 不一定提供完整歷史 EPS。
    # 如果沒有，使用 earningsGrowth 作為輔助。
    # --------------------------------------------------------

    eps_cagr_3y = np.nan
    eps_cagr_5y = np.nan

    try:

        income_stmt_eps = ticker.income_stmt

        if (
            not income_stmt_eps.empty
            and "Diluted EPS" in income_stmt_eps.index
        ):

            eps_series = (
                income_stmt_eps
                .loc["Diluted EPS"]
                .dropna()
                .sort_index()
            )

            if len(eps_series) >= 4:

                if (
                    eps_series.iloc[-4] > 0
                    and eps_series.iloc[-1] > 0
                ):

                    eps_cagr_3y = calculate_cagr(
                        eps_series.iloc[-4],
                        eps_series.iloc[-1],
                        3
                    )

            if len(eps_series) >= 6:

                if (
                    eps_series.iloc[-6] > 0
                    and eps_series.iloc[-1] > 0
                ):

                    eps_cagr_5y = calculate_cagr(
                        eps_series.iloc[-6],
                        eps_series.iloc[-1],
                        5
                    )

    except Exception:
        pass

    # --------------------------------------------------------
    # CAGR 統合
    # --------------------------------------------------------

    cagr_candidates = [
        eps_cagr_5y,
        eps_cagr_3y,
        earnings_growth,
        revenue_cagr_5y,
        revenue_cagr_3y
    ]

    valid_cagrs = [
        x for x in cagr_candidates
        if not np.isnan(safe_float(x))
    ]

    if valid_cagrs:

        blended_cagr = np.mean(
            valid_cagrs
        )

    else:

        blended_cagr = np.nan

    return {

        "symbol": symbol,
        "name": info.get(
            "longName",
            symbol
        ),

        "price": current_price,

        "market_cap": market_cap,

        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,

        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,

        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,

        "revenue_cagr_3y": revenue_cagr_3y,
        "revenue_cagr_5y": revenue_cagr_5y,

        "eps_cagr_3y": eps_cagr_3y,
        "eps_cagr_5y": eps_cagr_5y,

        "fcf_cagr_3y": fcf_cagr_3y,
        "fcf_cagr_5y": fcf_cagr_5y,

        "blended_cagr": blended_cagr,

        "profit_margin": profit_margin,
        "operating_margin": operating_margin,

        "roe": roe,
        "debt_to_equity": debt_to_equity,

        "free_cash_flow": free_cash_flow,

        "ma20": ma20,
        "ma60": ma60,
        "rsi": rsi,

        "hist": hist
    }


# ============================================================
# 5. CAGR 情境模型
# ============================================================

def build_scenarios(
    current_eps,
    current_price,
    bear_cagr,
    base_cagr,
    bull_cagr,
    forecast_years
):

    result = {}

    scenarios = {
        "Bear": bear_cagr,
        "Base": base_cagr,
        "Bull": bull_cagr
    }

    for name, cagr in scenarios.items():

        eps = future_value(
            current_eps,
            cagr,
            forecast_years
        )

        result[name] = {
            "cagr": cagr,
            "future_eps": eps
        }

    return result


# ============================================================
# 6. 合理 PE
# ============================================================

def estimate_fair_pe(
    cagr,
    current_pe,
    scenario
):

    cagr = safe_float(cagr)
    current_pe = safe_float(current_pe)

    # --------------------------------------------------------
    # 基本邏輯
    #
    # CAGR 越高 → 可給較高 PE
    # 但設定上限避免估值無限膨脹
    # --------------------------------------------------------

    if scenario == "Bear":

        if not np.isnan(current_pe):
            pe = min(
                current_pe * 0.75,
                20
            )
        else:
            pe = 15

    elif scenario == "Base":

        if not np.isnan(current_pe):
            pe = current_pe
        else:
            pe = 20

    else:

        if not np.isnan(current_pe):
            pe = min(
                current_pe * 1.15,
                35
            )
        else:
            pe = 25

    # CAGR 調整

    if not np.isnan(cagr):

        if cagr >= 0.25:
            pe += 3

        elif cagr >= 0.20:
            pe += 2

        elif cagr >= 0.15:
            pe += 1

        elif cagr < 0.05:
            pe -= 3

    return max(8, min(pe, 40))


# ============================================================
# 7. PEG
# ============================================================

def calculate_peg(pe, cagr):

    pe = safe_float(pe)
    cagr = safe_float(cagr)

    if (
        np.isnan(pe)
        or np.isnan(cagr)
        or cagr <= 0
    ):
        return np.nan

    return pe / (cagr * 100)


# ============================================================
# 8. CAGR 合理價
# ============================================================

def valuation_model(
    data,
    bear_cagr,
    base_cagr,
    bull_cagr,
    forecast_years
):

    current_price = data["price"]

    # 優先使用 Forward EPS
    current_eps = data["forward_eps"]

    if np.isnan(current_eps):
        current_eps = data["trailing_eps"]

    if np.isnan(current_eps):
        return None

    current_pe = data["forward_pe"]

    if np.isnan(current_pe):
        current_pe = data["trailing_pe"]

    scenarios = build_scenarios(
        current_eps,
        current_price,
        bear_cagr,
        base_cagr,
        bull_cagr,
        forecast_years
    )

    for scenario in scenarios:

        cagr = scenarios[scenario]["cagr"]

        fair_pe = estimate_fair_pe(
            cagr,
            current_pe,
            scenario
        )

        future_eps = scenarios[scenario]["future_eps"]

        fair_value = (
            future_eps * fair_pe
        )

        upside = (
            fair_value / current_price
        ) - 1

        annual_return = (
            (fair_value / current_price)
            ** (1 / forecast_years)
        ) - 1

        scenarios[scenario].update({

            "fair_pe": fair_pe,

            "fair_value": fair_value,

            "upside": upside,

            "annual_return": annual_return
        })

    # PEG
    peg = calculate_peg(
        current_pe,
        base_cagr
    )

    return {

        "current_eps": current_eps,

        "current_pe": current_pe,

        "peg": peg,

        "scenarios": scenarios
    }


# ============================================================
# 9. CAGR 可信度
# ============================================================

def calculate_cagr_confidence(data):

    score = 0
    reasons = []

    revenue_cagr = data["revenue_cagr_5y"]
    eps_cagr = data["eps_cagr_5y"]
    fcf_cagr = data["fcf_cagr_5y"]

    # Revenue
    if not np.isnan(revenue_cagr):

        if revenue_cagr >= 0.15:
            score += 25
            reasons.append(
                "長期營收成長強"
            )

        elif revenue_cagr >= 0.08:
            score += 18
            reasons.append(
                "長期營收穩定成長"
            )

        elif revenue_cagr >= 0:
            score += 10

    # EPS
    if not np.isnan(eps_cagr):

        if eps_cagr >= 0.15:
            score += 30
            reasons.append(
                "EPS 長期成長強"
            )

        elif eps_cagr >= 0.08:
            score += 20
            reasons.append(
                "EPS 長期成長穩定"
            )

        elif eps_cagr >= 0:
            score += 10

    # FCF
    if not np.isnan(fcf_cagr):

        if fcf_cagr >= 0.15:
            score += 25
            reasons.append(
                "自由現金流成長強"
            )

        elif fcf_cagr >= 0.08:
            score += 18
            reasons.append(
                "自由現金流穩定"
            )

        elif fcf_cagr >= 0:
            score += 10

    # EPS vs Revenue
    if (
        not np.isnan(eps_cagr)
        and not np.isnan(revenue_cagr)
    ):

        difference = (
            eps_cagr - revenue_cagr
        )

        if difference > 0.15:

            score -= 10

            reasons.append(
                "EPS 成長明顯高於營收，需注意一次性因素或利潤率變化"
            )

    score = max(
        0,
        min(score, 100)
    )

    if score >= 75:
        level = "高"

    elif score >= 50:
        level = "中"

    else:
        level = "低"

    return score, level, reasons


# ============================================================
# 10. Quant Score
# ============================================================

def calculate_quant_score(
    data,
    valuation
):

    # --------------------------------------------------------
    # ① Growth 30
    # --------------------------------------------------------

    growth_score = 0

    cagr = data["blended_cagr"]

    if not np.isnan(cagr):

        if cagr >= 0.25:
            growth_score = 30

        elif cagr >= 0.20:
            growth_score = 27

        elif cagr >= 0.15:
            growth_score = 24

        elif cagr >= 0.10:
            growth_score = 20

        elif cagr >= 0.05:
            growth_score = 15

        else:
            growth_score = 8

    # --------------------------------------------------------
    # ② Quality 20
    # --------------------------------------------------------

    quality_score = 0

    roe = data["roe"]
    operating_margin = data["operating_margin"]

    if not np.isnan(roe):

        if roe >= 0.25:
            quality_score += 10

        elif roe >= 0.15:
            quality_score += 8

        elif roe >= 0.10:
            quality_score += 6

        else:
            quality_score += 3

    if not np.isnan(operating_margin):

        if operating_margin >= 0.25:
            quality_score += 10

        elif operating_margin >= 0.15:
            quality_score += 8

        elif operating_margin >= 0.10:
            quality_score += 6

        else:
            quality_score += 3

    quality_score = min(
        quality_score,
        20
    )

    # --------------------------------------------------------
    # ③ Valuation 25
    # --------------------------------------------------------

    valuation_score = 12

    if valuation:

        peg = valuation["peg"]

        if not np.isnan(peg):

            if peg < 0.8:
                valuation_score = 25

            elif peg < 1.0:
                valuation_score = 23

            elif peg < 1.3:
                valuation_score = 20

            elif peg < 1.6:
                valuation_score = 16

            elif peg < 2.0:
                valuation_score = 11

            else:
                valuation_score = 6

        base_return = (
            valuation["scenarios"]["Base"]
            ["annual_return"]
        )

        if base_return >= 0.15:
            valuation_score = min(
                valuation_score + 3,
                25
            )

    # --------------------------------------------------------
    # ④ Momentum 15
    # --------------------------------------------------------

    momentum_score = 8

    price = data["price"]
    ma20 = data["ma20"]
    ma60 = data["ma60"]

    if (
        not np.isnan(ma20)
        and not np.isnan(ma60)
    ):

        if (
            price > ma20
            and ma20 > ma60
        ):
            momentum_score = 15

        elif price > ma60:
            momentum_score = 11

        elif price < ma60:
            momentum_score = 6

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = data["rsi"]

    if not np.isnan(rsi):

        if 45 <= rsi <= 65:
            momentum_score += 0

        elif rsi > 75:
            momentum_score -= 3

        elif rsi < 30:
            momentum_score += 2

    momentum_score = max(
        0,
        min(momentum_score, 15)
    )

    # --------------------------------------------------------
    # ⑤ Financial Safety 10
    # --------------------------------------------------------

    financial_score = 5

    debt = data["debt_to_equity"]

    if not np.isnan(debt):

        if debt < 30:
            financial_score = 10

        elif debt < 60:
            financial_score = 8

        elif debt < 100:
            financial_score = 6

        else:
            financial_score = 3

    total = (
        growth_score
        + quality_score
        + valuation_score
        + momentum_score
        + financial_score
    )

    if total >= 85:
        rating = "STRONG BUY"

    elif total >= 75:
        rating = "BUY"

    elif total >= 65:
        rating = "ACCUMULATE"

    elif total >= 50:
        rating = "HOLD"

    elif total >= 35:
        rating = "REDUCE"

    else:
        rating = "SELL"

    return {

        "growth": growth_score,
        "quality": quality_score,
        "valuation": valuation_score,
        "momentum": momentum_score,
        "financial": financial_score,

        "total": total,

        "rating": rating
    }


# ============================================================
# 11. Gemini AI
# ============================================================

def call_gemini(
    api_key,
    model,
    data,
    valuation,
    quant
):

    if not api_key:
        return "未輸入 Gemini API Key，略過 AI 分析。"

    if genai is None:
        return (
            "尚未安裝 google-genai。\n\n"
            "請執行：pip install google-genai"
        )

    try:

        client = genai.Client(
            api_key=api_key
        )

        prompt = f"""
你是一位專業股票研究員。

請根據以下 Python 量化模型結果分析股票。

股票：
{data['name']}
{data['symbol']}

目前股價：
{data['price']}

歷史成長：

營收 CAGR 3Y：
{data['revenue_cagr_3y']}

營收 CAGR 5Y：
{data['revenue_cagr_5y']}

EPS CAGR 3Y：
{data['eps_cagr_3y']}

EPS CAGR 5Y：
{data['eps_cagr_5y']}

FCF CAGR 3Y：
{data['fcf_cagr_3y']}

FCF CAGR 5Y：
{data['fcf_cagr_5y']}

目前 EPS：
{valuation['current_eps']}

Forward PE：
{data['forward_pe']}

PEG：
{valuation['peg']}

Bear：

CAGR：
{valuation['scenarios']['Bear']['cagr']}

未來 EPS：
{valuation['scenarios']['Bear']['future_eps']}

合理 PE：
{valuation['scenarios']['Bear']['fair_pe']}

合理價：
{valuation['scenarios']['Bear']['fair_value']}

Base：

CAGR：
{valuation['scenarios']['Base']['cagr']}

未來 EPS：
{valuation['scenarios']['Base']['future_eps']}

合理 PE：
{valuation['scenarios']['Base']['fair_pe']}

合理價：
{valuation['scenarios']['Base']['fair_value']}

Bull：

CAGR：
{valuation['scenarios']['Bull']['cagr']}

未來 EPS：
{valuation['scenarios']['Bull']['future_eps']}

合理 PE：
{valuation['scenarios']['Bull']['fair_pe']}

合理價：
{valuation['scenarios']['Bull']['fair_value']}

Quant Score：
{quant['total']}/100

Rating：
{quant['rating']}

請回答：

1. CAGR 是否可信？
2. EPS 成長是否高於營收成長太多？
3. PEG 是否合理？
4. Bear/Base/Bull 哪個情境最合理？
5. 最大風險是什麼？
6. 目前價格是否已經反映未來成長？
7. 最後給出 BUY / ACCUMULATE / HOLD / REDUCE / SELL。

重要：
不要修改 Python 計算出的數字。
如果資料不足，明確說明。
不要保證未來股價。
"""

        response = client.models.generate_content(
            model=model,
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"Gemini API 錯誤：{str(e)}"


# ============================================================
# 12. 使用者輸入
# ============================================================

symbol_input = st.text_input(
    "輸入台股代碼",
    value="2330",
    placeholder="例如：2330、2317、3019"
)

analyze = st.button(
    "🚀 開始 CAGR 量化分析",
    type="primary"
)


# ============================================================
# 13. 主程式
# ============================================================

if analyze:

    symbol = format_symbol(
        symbol_input
    )

    with st.spinner(
        f"正在分析 {symbol}..."
    ):

        try:

            data = get_stock_data(
                symbol
            )

            # ------------------------------------------------
            # CAGR 預設值
            # ------------------------------------------------

            historical_cagr = data[
                "blended_cagr"
            ]

            # ------------------------------------------------
            # Base CAGR
            #
            # 優先使用歷史 CAGR
            # ------------------------------------------------

            if not np.isnan(
                historical_cagr
            ):

                base_cagr = max(
                    0,
                    min(
                        historical_cagr,
                        0.30
                    )
                )

            else:

                base_cagr = (
                    default_base / 100
                )

            # Bear / Bull
            bear_cagr = (
                default_bear / 100
            )

            bull_cagr = max(
                base_cagr + 0.05,
                default_bull / 100
            )

            # ------------------------------------------------
            # 估值
            # ------------------------------------------------

            valuation = valuation_model(
                data,
                bear_cagr,
                base_cagr,
                bull_cagr,
                forecast_years
            )

            if valuation is None:

                st.error(
                    "無法取得 EPS，無法進行 CAGR 估值。"
                )

                st.stop()

            # ------------------------------------------------
            # CAGR 信心
            # ------------------------------------------------

            confidence_score, confidence_level, confidence_reasons = (
                calculate_cagr_confidence(
                    data
                )
            )

            # ------------------------------------------------
            # Quant Score
            # ------------------------------------------------

            quant = calculate_quant_score(
                data,
                valuation
            )

            # =================================================
            # Header
            # =================================================

            st.subheader(
                f"🎯 {data['name']} ({symbol})"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "目前股價",
                fmt(data["price"])
            )

            c2.metric(
                "Forward EPS",
                fmt(data["forward_eps"])
            )

            c3.metric(
                "Forward PE",
                fmt(data["forward_pe"])
            )

            c4.metric(
                "Quant Score",
                f"{quant['total']}/100"
            )

            st.divider()

            # =================================================
            # CAGR
            # =================================================

            st.header(
                "📈 CAGR 成長分析"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "營收 CAGR 5Y",
                (
                    fmt(
                        data["revenue_cagr_5y"] * 100
                    ) + "%"
                    if not np.isnan(
                        data["revenue_cagr_5y"]
                    )
                    else "N/A"
                )
            )

            c2.metric(
                "EPS CAGR 5Y",
                (
                    fmt(
                        data["eps_cagr_5y"] * 100
                    ) + "%"
                    if not np.isnan(
                        data["eps_cagr_5y"]
                    )
                    else "N/A"
                )
            )

            c3.metric(
                "FCF CAGR 5Y",
                (
                    fmt(
                        data["fcf_cagr_5y"] * 100
                    ) + "%"
                    if not np.isnan(
                        data["fcf_cagr_5y"]
                    )
                    else "N/A"
                )
            )

            # =================================================
            # CAGR Confidence
            # =================================================

            st.subheader(
                "🔍 CAGR 可信度"
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "可信度",
                f"{confidence_score}/100"
            )

            c2.metric(
                "等級",
                confidence_level
            )

            for reason in confidence_reasons:

                st.write(
                    "• " + reason
                )

            # =================================================
            # PEG
            # =================================================

            st.header(
                "💰 PEG 估值"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "目前 PE",
                fmt(
                    valuation["current_pe"]
                )
            )

            c2.metric(
                "Base CAGR",
                f"{base_cagr * 100:.1f}%"
            )

            c3.metric(
                "PEG",
                fmt(
                    valuation["peg"]
                )
            )

            peg = valuation["peg"]

            if np.isnan(peg):

                st.warning(
                    "PEG 無法計算"
                )

            elif peg < 1:

                st.success(
                    "PEG < 1：成長相對估值便宜"
                )

            elif peg < 1.5:

                st.info(
                    "PEG 1～1.5：估值大致合理"
                )

            elif peg < 2:

                st.warning(
                    "PEG 1.5～2：估值偏高"
                )

            else:

                st.error(
                    "PEG > 2：估值偏高"
                )

            # =================================================
            # Scenario
            # =================================================

            st.header(
                f"🔮 {forecast_years} 年 CAGR 合理價"
            )

            rows = []

            for scenario in [
                "Bear",
                "Base",
                "Bull"
            ]:

                s = valuation[
                    "scenarios"
                ][scenario]

                rows.append({

                    "情境": scenario,

                    "CAGR":
                        f"{s['cagr'] * 100:.1f}%",

                    f"{forecast_years}年後 EPS":
                        fmt(
                            s["future_eps"]
                        ),

                    "合理 PE":
                        fmt(
                            s["fair_pe"]
                        ),

                    "合理股價":
                        fmt(
                            s["fair_value"]
                        ),

                    "上漲空間":
                        f"{s['upside'] * 100:.1f}%",

                    "預期年化報酬":
                        f"{s['annual_return'] * 100:.1f}%"
                })

            scenario_df = pd.DataFrame(
                rows
            )

            st.dataframe(
                scenario_df,
                use_container_width=True,
                hide_index=True
            )

            # =================================================
            # Base
            # =================================================

            base = valuation[
                "scenarios"
            ]["Base"]

            st.subheader(
                "🎯 Base 情境"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Base CAGR",
                f"{base['cagr'] * 100:.1f}%"
            )

            c2.metric(
                f"{forecast_years}年後 EPS",
                fmt(
                    base["future_eps"]
                )
            )

            c3.metric(
                "合理股價",
                fmt(
                    base["fair_value"]
                )
            )

            c4.metric(
                "年化報酬",
                f"{base['annual_return'] * 100:.1f}%"
            )

            # =================================================
            # Quant Score
            # =================================================

            st.header(
                "📊 Quant Score"
            )

            score_df = pd.DataFrame({

                "項目": [
                    "成長性",
                    "獲利品質",
                    "估值",
                    "動能",
                    "財務安全"
                ],

                "得分": [
                    quant["growth"],
                    quant["quality"],
                    quant["valuation"],
                    quant["momentum"],
                    quant["financial"]
                ],

                "滿分": [
                    30,
                    20,
                    25,
                    15,
                    10
                ]
            })

            st.dataframe(
                score_df,
                use_container_width=True,
                hide_index=True
            )

            # =================================================
            # Rating
            # =================================================

            st.subheader(
                f"🎯 投資評級：{quant['rating']}"
            )

            # =================================================
            # AI
            # =================================================

            st.header(
                "🤖 Gemini AI 基本面判讀"
            )

            with st.spinner(
                "AI 正在判讀 CAGR 是否合理..."
            ):

                ai_result = call_gemini(
                    api_key,
                    gemini_model,
                    data,
                    valuation,
                    quant
                )

            st.markdown(
                ai_result
            )

            # =================================================
            # 技術面
            # =================================================

            st.header(
                "📉 技術面"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "RSI",
                fmt(data["rsi"])
            )

            c2.metric(
                "MA20",
                fmt(data["ma20"])
            )

            c3.metric(
                "MA60",
                fmt(data["ma60"])
            )

            # ------------------------------------------------
            # Chart
            # ------------------------------------------------

            chart_data = data[
                "hist"
            ][["Close", "MA20", "MA60"]].dropna()

            st.line_chart(
                chart_data
            )

            # =================================================
            # Risks
            # =================================================

            st.header(
                "⚠️ 量化模型注意事項"
            )

            st.markdown(
                """
                1. CAGR 是過去或假設的成長速度，不代表未來一定維持。
                
                2. EPS CAGR 若遠高於營收 CAGR，必須確認是否來自毛利率、
                   營益率、稅率或股本變化。
                
                3. PEG 不能單獨作為買進依據。
                
                4. 合理 PE 是模型假設，不是市場保證。
                
                5. 台股景氣循環股不適合單純使用固定 CAGR。
                
                6. 高 CAGR 股票可能同時具有高估值風險。
                """
            )

        except Exception as e:

            st.error(
                f"分析失敗：{str(e)}"
            )

            st.exception(e)
