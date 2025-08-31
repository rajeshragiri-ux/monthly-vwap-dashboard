import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import matplotlib.pyplot as plt
import datetime as dt

# ===== SETTINGS =====
index_stocks = {
    "Nifty50": {
        "Reliance": "RELIANCE.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "Infosys": "INFY.NS",
        "TCS": "TCS.NS"
    },
    "BankNifty": {
        "HDFC Bank": "HDFCBANK.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "Axis Bank": "AXISBANK.NS",
        "Kotak Bank": "KOTAKBANK.NS",
        "SBI": "SBIN.NS"
    },
    "FinNifty": {
        "HDFC Bank": "HDFCBANK.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "HDFC Ltd": "HDFC.NS",
        "Axis Bank": "AXISBANK.NS",
        "Kotak Bank": "KOTAKBANK.NS"
    }
}

index_tickers = {
    "Nifty50": "^NSEI",
    "BankNifty": "^NSEBANK",
    "FinNifty": "^NSEFINNIFTY"
}

interval = "5m"
period = "12mo"

# ===== VWAP Backtest Function =====
def backtest_vwap(ticker):
    df = yf.download(ticker, interval=interval, period=period)
    df["Date"] = df.index.date
    df["Month"] = pd.to_datetime(df["Date"]).to_period("M")

    # VWAP calc
    df["CumVol"] = df["Volume"].cumsum()
    df["CumPV"] = (df["Close"] * df["Volume"]).cumsum()
    df["VWAP"] = df["CumPV"] / df["CumVol"]

    # Last-day VWAP
    last_day_vwaps = df.groupby("Month").apply(
        lambda x: x[x["Date"] == x["Date"].max()]["VWAP"].iloc[-1]
    )
    last_day_vwaps = last_day_vwaps.shift(1)

    # Daily OHLC
    daily = yf.download(ticker, interval="1d", period=period)
    daily["Month"] = pd.to_datetime(daily.index).to_period("M")

    results = []
    for m in daily["Month"].unique()[1:]:
        month_data = daily[daily["Month"] == m]
        if len(month_data) == 0:
            continue
        vwap_ref = last_day_vwaps.get(m, np.nan)
        if pd.isna(vwap_ref):
            continue

        entry = month_data["Close"].iloc[0]
        high = month_data["High"].max()
        low = month_data["Low"].min()
        end = month_data["Close"].iloc[-1]

        if entry > vwap_ref:
            bias = "Long"
            if high >= entry:
                exit_price = high
                outcome = "Target Hit ✅"
            elif low <= entry:
                exit_price = low
                outcome = "Stopped ❌"
            else:
                exit_price = end
                outcome = "Expired ⏳"
            pnl = exit_price - entry
        else:
            bias = "Short"
            if low <= entry:
                exit_price = low
                outcome = "Target Hit ✅"
            elif high >= entry:
                exit_price = high
                outcome = "Stopped ❌"
            else:
                exit_price = end
                outcome = "Expired ⏳"
            pnl = entry - exit_price

        results.append({
            "Month": str(m),
            "VWAP Ref": round(vwap_ref,2),
            "Entry": round(entry,2),
            "Bias": bias,
            "Exit": round(exit_price,2),
            "Outcome": outcome,
            "PnL": round(pnl,2)
        })

    df_results = pd.DataFrame(results)
    df_results["Cumulative PnL"] = df_results["PnL"].cumsum()
    return df_results, last_day_vwaps

# ===== STREAMLIT UI =====
st.set_page_config(page_title="Monthly VWAP Dashboard", layout="wide")
st.title("📊 Monthly VWAP Dashboard with Stock ↔ Index Bias Alignment")

# Dropdowns
index_choice = st.selectbox("Choose Index:", list(index_stocks.keys()))
stock_choice = st.selectbox("Choose Stock:", list(index_stocks[index_choice].keys()))
stock_ticker = index_stocks[index_choice][stock_choice]
index_ticker = index_tickers[index_choice]

# Backtests
st.subheader(f"📌 {stock_choice} ({stock_ticker}) vs {index_choice} ({index_ticker})")

stock_results, stock_vwaps = backtest_vwap(stock_ticker)
index_results, index_vwaps = backtest_vwap(index_ticker)

col1, col2 = st.columns(2)
with col1:
    st.write(f"**{stock_choice} Results**")
    st.dataframe(stock_results)
    st.metric(label=f"{stock_choice} Total PnL", value=f"{stock_results['PnL'].sum()} pts")

with col2:
    st.write(f"**{index_choice} Results**")
    st.dataframe(index_results)
    st.metric(label=f"{index_choice} Total PnL", value=f"{index_results['PnL'].sum()} pts")

# ===== Live Forward Signal =====
st.subheader("🔮 Live Forward Signal Alignment")

today = dt.date.today()
this_month = pd.to_datetime(today).to_period("M")

# Stock live
stock_vwap_ref = stock_vwaps.get(this_month, np.nan)
stock_live = yf.download(stock_ticker, interval="5m", period="1d")
stock_price = stock_live["Close"].iloc[-1]
stock_bias = "Bullish" if stock_price > stock_vwap_ref else "Bearish"

# Index live
index_vwap_ref = index_vwaps.get(this_month, np.nan)
index_live = yf.download(index_ticker, interval="5m", period="1d")
index_price = index_live["Close"].iloc[-1]
index_bias = "Bullish" if index_price > index_vwap_ref else "Bearish"

col1, col2 = st.columns(2)
with col1:
    st.metric(label=f"{stock_choice} VWAP Ref", value=round(stock_vwap_ref,2))
    st.metric(label=f"{stock_choice} Price", value=round(stock_price,2))
    st.metric(label=f"{stock_choice} Bias", value=stock_bias)

with col2:
    st.metric(label=f"{index_choice} VWAP Ref", value=round(index_vwap_ref,2))
    st.metric(label=f"{index_choice} Price", value=round(index_price,2))
    st.metric(label=f"{index_choice} Bias", value=index_bias)

# Alignment Check
if stock_bias == index_bias:
    st.success(f"✅ Alignment: {stock_choice} and {index_choice} both {stock_bias}")
else:
    st.warning(f"⚠️ Divergence: {stock_choice} is {stock_bias}, but {index_choice} is {index_bias}")
