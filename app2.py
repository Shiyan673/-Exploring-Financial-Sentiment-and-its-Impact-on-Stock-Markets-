# import all necessary libraries
import streamlit as st
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from datetime import timedelta
from pytz import timezone
import pytz

cur_time = datetime.datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific'))

def convert_str_to_time(release_time, cur_time):
  split_time = release_time.split(' ')
  num = int(split_time[0])
  unit = split_time[1]
  if unit == 'minutes':
    return cur_time - timedelta(minutes=num)
  elif unit == 'hours':
    return cur_time - timedelta(hours=num)
  else:
    return False

def crawl_yahoo_finance():
    ua = UserAgent()
    headers = {'User-Agent': ua.random}

    # Fetch the website
    url = "https://finance.yahoo.com/topic/stock-market-news/"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Get all the news
    all_news = soup.find_all('div', class_ = 'content')

    # Get all the details from all the news
    subtitles = []
    titles = []
    release_times = []
    publishers = []
    tickerss = []

    cur_time = datetime.datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific'))

    for news in all_news:
        subtitle = news.find_all('p')[0].text
        if len(news.find_all('h2')) > 0:
            title = news.find_all('h2')[0].text
        else:
            title = news.find_all('h3')[0].text
        if len(news.find_all('div', class_='publishing'))>0:
            release_time = news.find_all('div', class_='publishing')[0].text.split(' • ')[1]
            publisher = news.find_all('div', class_='publishing')[0].text.split(' • ')[0]
            release_time = convert_str_to_time(release_time, cur_time)
        else:
            release_time = 'No Available Release Time'
            publisher = 'No Available Publisher'
        tickers = []
        for ticker in news.find_all('span', class_='symbol'):
          tickers.append(ticker.text)

        subtitles.append(subtitle)
        titles.append(title)
        release_times.append(release_time)
        publishers.append(publisher)
        tickerss.append(tickers)

    # summarize into a complete dataframe for later visualizations / analysis
    df = pd.DataFrame({'News Title':titles, 'News Content':subtitles, 'Release Time':release_times, 'Publisher':publishers, 'Ticker':tickerss})
    return df

st.title("A Very Awesome Financial Tool Created By Crystal")
df = crawl_yahoo_finance()
st.text("This is a very very very awesome tool, that I made, during spare time showing my passion ...")
st.dataframe(df)

