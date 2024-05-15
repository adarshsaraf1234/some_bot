import pandas as pd
import json
import csv
import orders as od
import numpy as np 
import os 
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# df_1 = pd.read_json('https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json')


def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def generate_signals(filePath,name):
    data = pd.read_csv(filePath)
    # Calculate 20-day rolling mean and standard deviation (volatility)
    data['20-day MA'] = data['Close'].rolling(window=20).mean()
    data['20-day Volatility'] = data['Close'].rolling(window=20).std()
    # Define trading signals for mean reversion
    data['Signal'] = 'No Signal'
    # Buy Signal: Price above 20-day MA and high volatility
    data.loc[
        (data['Close'] > data['20-day MA']) &
        (data['20-day Volatility'] > data['20-day Volatility'].rolling(window=20).mean()),
        'Signal'
    ] = 'Buy'
    # Sell Signal: Price below 20-day MA or low volatility
    data.loc[
        (data['Close'] < data['20-day MA']) |
        (data['20-day Volatility'] < data['20-day Volatility'].rolling(window=20).mean()),
        'Signal'
    ] = 'Sell'

    return data

def generate_trading_scrips(filePath,name,buy_signals,sell_signals,token):
    data=pd.read_csv(filePath)
    last_row=data.iloc[-1]
    # print(last_row)
    trade_signal = last_row['Signal']
    if trade_signal == "Sell":
        sell_signals[name] = token
    elif trade_signal == "Buy":
        buy_signals[name] = token
    return buy_signals,sell_signals
    
def signals52WhighVol(filePath):
    df = pd.read_csv(filePath)
    # Calculate 52-week high
    df['52-week High'] = df.groupby('Symbol')['Close'].transform(lambda x: x.rolling(window=252).max())

    # Calculate 52-week high threshold (5% below the 52-week high)
    df['Threshold'] = df['52-week High'] * 0.95

    # Calculate historical volatility (e.g., 20-day rolling standard deviation)
    df['Volatility'] = df.groupby('Symbol')['Close'].transform(lambda x: x.rolling(window=20).std())

    # Filter stocks within 5% of 52-week high with positive volatility
    filtered_stocks = df[(df['Close'] >= df['Threshold']) & (df['Volatility'] > 0)]

    # Display the filtered stocks
    print(filtered_stocks[['Symbol', 'Date', 'Close', 'Volatility']])

def newSignals52WhighVol(filePath):

  df = pd.read_csv(filePath)
  # Calculate 52-week high
  df['52-week High'] = df['Close'].transform(lambda x: x.rolling(window=252).max())
  # Calculate 52-week high threshold (5% below the 52-week high)
  df['Threshold'] = df['52-week High'] * 0.95
  # Calculate historical volatility (e.g., 20-day rolling standard deviation)
  df['Volatility'] = df['Close'].transform(lambda x: x.rolling(window=20).std())
  # Calculate 10-day Moving Average (MA)
  df['10-day MA'] = df['Close'].transform(lambda x: x.rolling(window=10).mean())
  # Calculate 20-day Moving Average (MA)
  df['20-day SMA'] = df['Close'].transform(lambda x: x.rolling(window=20).mean())
  df['50-day SMA'] = df['Close'].transform(lambda x: x.rolling(window=50).mean())
  # Generate Buy/Sell Signal based on SMA comparison
  def buy_sell(row):
     #row['20-day SMA'] < row['10-day MA'] and
    if row['50-day SMA'] < row['10-day MA']:
      return 'Buy'
    else:
      return 'Sell'
  df['Signal'] = df.apply(buy_sell, axis=1)  # Apply function row-wise
  # Display the DataFrame with all columns
  return df

def maxVoltilityMidcap(buy_signals_midcap):
    buy_scrips=list()
    top_3_scrips = []  # List to store the top 3 most volatile stocks
    for k, v in buy_signals_midcap.items():
        name = k
        df = pd.read_csv("midcap_signals/" + name + ".csv")
        last_row = df.iloc[-1]
        volatility = last_row['Volatility']
        # Check if this script has higher volatility than any of the current top 3
        if len(top_3_scrips) < 3 or volatility > min(top_3_scrips, key=lambda x: x[1])[1]:
            # If there are less than 3 scripts or if this script has higher volatility, add it to the top 3
            top_3_scrips.append((k, volatility))
            # Sort the top 3 scripts by volatility in descending order
            top_3_scrips = sorted(top_3_scrips, key=lambda x: x[1], reverse=True)
        buy_scrips.append([k, v])
    # Only keep the scripts of the top 3 most volatile stocks
    buy_scrips = [script for script in buy_scrips if script[0] in [top[0] for top in top_3_scrips]]
    print("Expect max volatility in these midcap stocks :")
    print(buy_scrips)

def maxVoltilityNifty(buy_signals):
    buy_scrips=list()
    top_3_scrips = []  # List to store the top 3 most volatile stocks
    for k, v in buy_signals.items():
        name = k
        df = pd.read_csv("signals/" + name + ".csv")
        last_row = df.iloc[-1]
        volatility = last_row['Volatility']
        # Check if this script has higher volatility than any of the current top 3
        if len(top_3_scrips) < 3 or volatility > min(top_3_scrips, key=lambda x: x[1])[1]:
            # If there are less than 3 scripts or if this script has higher volatility, add it to the top 3
            top_3_scrips.append((k, volatility))
            # Sort the top 3 scripts by volatility in descending order
            top_3_scrips = sorted(top_3_scrips, key=lambda x: x[1], reverse=True)
        buy_scrips.append([k, v])
    # Only keep the scripts of the top 3 most volatile stocks
    buy_scrips = [script for script in buy_scrips if script[0] in [top[0] for top in top_3_scrips]]
    print("Expect Max Volatility in these Nifty stocks :")
    print(buy_scrips)
    
def RetMidcap(name):
    ret_arr=[]
    df = pd.read_csv("midcap_signals/"+name+".csv")
    x=False
    for index,row in df.iterrows():
        if row['Signal']=="Buy" and x is False:
            low = row['Low']
            high = row['High']
            x=True
        elif row['Signal']=="Sell" and x is True:
            high = row['High']
            ret_arr.append(((high-low)/low)*100)
            x=False  
    print("the return for:"+name)
    print(sum(ret_arr)/len(ret_arr)) if len(ret_arr) > 0 else print("No returns to calculate")
    # print(ret_arr)

                
def RetNifty(name):
    ret_arr=[]
    df = pd.read_csv("signals/"+name+".csv")
    
    x=False
    for index,row in df.iterrows():
        if row['Signal']=="Buy" and x is False:
            low = row['Low']
            high = row['High']
            x=True
        elif row['Signal']=="Sell" and x is True:
            high = row['High']
            ret_arr.append(((high-low)/low)*100)
            x=False
            
    print("the return is :")
    print(sum(ret_arr)/len(ret_arr)) if len(ret_arr) > 0 else print("No returns to calculate")    

buy_signals = {}
sell_signals = {}
df_Nifty = pd.read_csv("Nifty50.csv")
df_Nifty_Midcap = pd.read_csv("NiftyMidcap.csv")

df_Nifty = df_Nifty.reset_index(drop=True)
df_Nifty_Midcap = df_Nifty_Midcap.reset_index(drop=True)

df_1 = df_Nifty.set_index('Token')
df_2 = df_Nifty_Midcap.set_index('Token')

nifty1 = df_1.to_dict()
Nifty50_dict = nifty1["Symbol"]
nifty2 = df_2.to_dict()
NiftyMidcap_dict = nifty2["Symbol"]

Nifty_T = list(df_Nifty.iloc[0:]['Token'])

for k,v in Nifty50_dict.items():
    name = v
    file_name = os.path.join('data/', name+'.csv')
    file_name = "data/"+name+".csv"
    # data = generate_signals(file_name,name)
    data = newSignals52WhighVol(file_name)
    signal_file_path ="signals/"+name+".csv"
    data.to_csv(signal_file_path)
    buy_signals,sell_signals = generate_trading_scrips(signal_file_path,name,buy_signals,sell_signals,k)


maxVoltilityNifty(buy_signals)

print("Buy Signals")
for k,v in buy_signals.items():
    print(k,v,"Buy")
    RetNifty(k)
   
print("Sell Signals")
for k,v in sell_signals.items():
    print(k,v,"Sell")

buy_signals_midcap = {}
sell_signals_midcap= {}
    
for k,v in NiftyMidcap_dict.items():
    name = v
    file_name = os.path.join('midcap_data/', name+'.csv')
    file_name = "midcap_data/"+name+".csv"
    # data = generate_signals(file_name,name)
    data = newSignals52WhighVol(file_name)
    signal_file_path ="midcap_signals/"+name+".csv"
    data.to_csv(signal_file_path)
    buy_signals_midcap,sell_signals_midcap = generate_trading_scrips(signal_file_path,name,buy_signals_midcap,sell_signals_midcap,k)

maxVoltilityMidcap(buy_signals_midcap)


print("Buy Signals midcap")
print("")
for k,v in buy_signals_midcap.items():
    RetMidcap(k)
    print(k,v,"Buy")
print("Sell Signals midcap")
print("")
for k,v in sell_signals_midcap.items():
    print(k,v,"Sell")

# test("REC-EQ")


