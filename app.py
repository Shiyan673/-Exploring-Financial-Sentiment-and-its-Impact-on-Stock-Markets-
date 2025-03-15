import re
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from bs4 import BeautifulSoup
from textblob import TextBlob
import yfinance as yf  
from datetime import datetime, timedelta
from fake_useragent import UserAgent

# ---- FUNCTION TO GENERATE SAFE KEYS ----
def safe_ticker_key(ticker):
    """Removes special characters from tickers and generates a unique key."""
    clean_ticker = re.sub(r'\W+', '_', ticker)  # Replace non-alphanumeric characters with underscores
    unique_suffix = str(uuid.uuid4())[:8]  # Generate a short unique suffix
    return f"{clean_ticker}_{unique_suffix}"  # Append suffix to ensure uniqueness

# Function to convert "43 minutes ago" to a timestamp (in local time)
def convert_relative_time(time_str):
    """Converts relative time (e.g., '43 minutes ago') to an approximate timestamp in local time."""
    now = datetime.now()  # Get current time in local timezone
    
    if time_str == 'yesterday':
        return now - timedelta(days=1)
    elif "minute" in time_str:
        minutes = int(time_str.split()[0])
        return now - timedelta(minutes=minutes)
    elif "hour" in time_str:
        hours = int(time_str.split()[0])
        return now - timedelta(hours=hours)
    elif "day" in time_str:
        days = int(time_str.split()[0])
        return now - timedelta(days=days)
    else:
        return None  # If the format is unrecognized, return None

# Function to scrape financial news
def get_financial_news():
    ua = UserAgent()
    headers = {'User-Agent': ua.random}

    # Fetch the website
    url = "https://finance.yahoo.com/topic/stock-market-news/"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    articles = soup.find_all("div", class_="content")  # Adjust selector
    news_list = []

    for article in articles:
        title = article.text
        link = article.a["href"]
        para = article.p.text
        press = article.find("div", class_="publishing").text.split(' • ')[0] if article.find("div", class_="publishing") else None
        time_str = article.find("div", class_="publishing").text.split(' • ')[1] if article.find("div", class_="publishing") else None
        timestamp = convert_relative_time(time_str) if time_str else None
        a_ticker = article.find("a", class_="ticker")
        ticker = a_ticker.find("span", class_="symbol").get_text(strip=True) if a_ticker else None
        
        news_list.append({"title": title, "link": link, "paragraph": para, "Press": press, 
                          "Publishing Time": timestamp, "Ticker": ticker})

    return pd.DataFrame(news_list)

# Function to analyze sentiment
def analyze_sentiment(text):
    analysis = TextBlob(text)
    return "Positive" if analysis.sentiment.polarity > 0 else "Negative" if analysis.sentiment.polarity < 0 else "Neutral"

# Function to analyze subjectivity
def analyze_subjectivity(text):
    return TextBlob(text).sentiment.subjectivity

# Function to fetch intraday stock price flows for multiple tickers
def get_intraday_stock_prices(tickers):
    all_data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="15m")  # Fetch intraday data (30-minute interval)
            hist["Percentage Change"] = hist["Close"].pct_change() * 100  # Convert to percentage change
            hist = hist.dropna()  # Remove NaN values
            hist.reset_index(inplace=True)  # Reset index for plotting

            # Ensure stock timestamps remain in local time
            hist["Datetime"] = hist["Datetime"].dt.tz_localize(None)  

            hist["Ticker"] = ticker  # Add ticker column
            all_data.append(hist)
        except:
            pass  # If an error occurs, skip the ticker

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return None

# Function to get real-time stock price trends (percentage change)
def get_stock_price_trend(tickers):
    stock_data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")  # Get last 2 days of data
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]  # Previous day's close
                latest_close = hist["Close"].iloc[-1]  # Latest close
                percent_change = ((latest_close - prev_close) / prev_close) * 100
                stock_data[ticker] = round(percent_change, 2)  # Round to 2 decimals
            else:
                stock_data[ticker] = None  # Handle missing data
        except:
            stock_data[ticker] = None  # Handle missing data
    return stock_data

# Streamlit UI
st.title("📊 Financial News Sentiment & Stock Price Trend Analysis")
st.write("Latest financial news with real-time stock price change comparison")

# Get and display news
news_df = get_financial_news()
st.dataframe(news_df)
news_df["Sentiment"] = news_df["title"].apply(analyze_sentiment)
news_df["Subjectivity"] = news_df["title"].apply(analyze_subjectivity)

# Fetch real-time stock price trends
unique_tickers = news_df["Ticker"].dropna().unique()
stock_trends = get_stock_price_trend(unique_tickers)
news_df["Stock Price Change (%)"] = news_df["Ticker"].map(stock_trends)
# Replace NaN or None with 0 for valid plotting
news_df["Stock Price Change (%)"] = news_df["Stock Price Change (%)"].fillna(0)

# ---- INTRADAY STOCK PRICE FLOW CHART (MULTI-TICKER COMPARISON) ----
st.subheader("📈 Intraday Stock Price & Sentiment Timeline")

# Multi-select filter for multiple stock tickers
selected_stocks = st.multiselect("Select Stocks for Timeline", unique_tickers, default=unique_tickers[:2])

if selected_stocks:
    intraday_df = get_intraday_stock_prices(selected_stocks)
    news_timeline_df = news_df[news_df["Ticker"].isin(selected_stocks)][["Publishing Time", "Sentiment", "Subjectivity", "Ticker", "title"]]
    news_timeline_df = news_timeline_df.dropna()  # Remove missing timestamps

    # Ensure news timestamps remain in local time
    news_timeline_df["Publishing Time"] = pd.to_datetime(news_timeline_df["Publishing Time"])

    # Determine min and max timestamps for shared x-axis range
    all_timestamps = pd.concat([intraday_df["Datetime"], news_timeline_df["Publishing Time"]])
    x_min, x_max = all_timestamps.min() - timedelta(minutes=30), all_timestamps.max() + timedelta(minutes=30)  # 30-min buffer

    if intraday_df is not None and not news_timeline_df.empty:
        # Stock Price Timeline
        fig_stock = px.line(
            intraday_df,
            x="Datetime",
            y="Percentage Change",
            color="Ticker",
            title="Intraday Stock Price Flow",
            labels={"Percentage Change": "Stock Price % Change"},
        )
        fig_stock.update_layout(xaxis_range=[x_min, x_max])  # Set common x-axis span
        st.plotly_chart(fig_stock, use_container_width=True, key=f"chart_{safe_ticker_key('_'.join(selected_stocks))}")

        # Sentiment Timeline
        fig_sentiment = px.scatter(
            news_timeline_df, 
            x="Publishing Time", 
            y="Sentiment", 
            color="Ticker",
            hover_data=["title"],
            title="News Sentiment Timeline",
            category_orders={"Sentiment": ["Negative", "Neutral", "Positive"]}  # Order sentiment categories
        )
        fig_sentiment.update_layout(xaxis_range=[x_min, x_max])  # Set common x-axis span
        st.plotly_chart(fig_sentiment, use_container_width=True, key=f"sentiment_chart_{safe_ticker_key('_'.join(selected_stocks))}")

        # Subjectivity Timeline
        fig_subjectivity = px.scatter(
            news_timeline_df, 
            x="Publishing Time", 
            y="Subjectivity",
            color="Ticker",
            hover_data=["title"],
            title="News Subjectivity Timeline",
            labels={"Subjectivity": "Subjectivity Score (0 = Objective, 1 = Subjective)"}
        )
        fig_subjectivity.update_layout(xaxis_range=[x_min, x_max])  # Set common x-axis span
        st.plotly_chart(fig_subjectivity, use_container_width=True, key=f"subjectivity_chart_{safe_ticker_key('_'.join(selected_stocks))}")

    else:
        st.write("No intraday or news sentiment data available for the selected stocks.")


if "Stock Price Change (%)" in news_df.columns:
    filtered_df = news_df.dropna(subset=["Stock Price Change (%)"])  # Remove NaNs before plotting
    filtered_df["Abs Stock Price Change (%)"] = filtered_df["Stock Price Change (%)"].abs()  # Ensure all sizes are positive

    st.subheader("📉 In-time Stock Price Change vs. Sentiment")
    fig = px.scatter(
        filtered_df,
        x="Stock Price Change (%)",
        y="Sentiment",
        color="Sentiment",
        size="Abs Stock Price Change (%)",  # Use absolute value to ensure positive sizes
        hover_data=["Ticker"],
        title="Stock Price Movement vs Sentiments"
    )
    st.plotly_chart(fig, use_container_width=True)