import pandas as pd
import json
import csv
import orders as od
import numpy as np 
import os 
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# df_1 = pd.read_json('https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json')


def calculate_rsi(data):
    period=14
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adx(df):
    # Calculate True Range (TR)
    period=14
    df['H-L'] = df['High'] - df['Low']
    df['H-C'] = np.abs(df['High'] - df['Close'].shift(1))
    df['L-C'] = np.abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)
    del df['H-L'], df['H-C'], df['L-C']

    # Calculate Average True Range (ATR)
    alpha = 1 / period
    df['ATR'] = df['TR'].ewm(alpha=alpha, adjust=False).mean()

    # Calculate +DM and -DM
    df['H-pH'] = df['High'] - df['High'].shift(1)
    df['pL-L'] = df['Low'].shift(1) - df['Low']
    df['+DX'] = np.where((df['H-pH'] > df['pL-L']) & (df['H-pH'] > 0), df['H-pH'], 0.0)
    df['-DX'] = np.where((df['H-pH'] < df['pL-L']) & (df['pL-L'] > 0), df['pL-L'], 0.0)
    del df['H-pH'], df['pL-L']

    # Calculate smoothed +DMI and -DMI
    df['S+DM'] = df['+DX'].ewm(alpha=alpha, adjust=False).mean()
    df['S-DM'] = df['-DX'].ewm(alpha=alpha, adjust=False).mean()

    # Calculate Directional Index (DX)
    df['DX'] = (np.abs(df['S+DM'] - df['S-DM']) / (df['S+DM'] + df['S-DM'])) * 100

    # Calculate ADX
    df['ADX'] = df['DX'].ewm(alpha=alpha, adjust=False).mean()
    adx_value = df['ADX'].iloc[-1]  # Get the last ADX value

    # Cleanup (optional, removes ADX column from the dataframe)
    del df['DX'], df['TR'], df['+DX'], df['-DX'], df['S+DM'], df['S-DM']
    return df


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
    
    trade_signal = last_row['Signal']
    if trade_signal == "Sell":
        sell_signals[name] = token
    elif trade_signal == "Buy":
        buy_signals[name] = token

    return buy_signals,sell_signals
    
def newSignals52WhighVol(filePath):
    """
    This function analyzes a pandas dataframe and generates buy and sell signals based on 
    Average True Range (ATR), ADX, RSI, and proximity to 52-week high.

    Args:
        filePath (str): The path to the CSV file containing OHLC data.

    Returns:
        pandas.DataFrame: The original dataframe with new columns 'Buy Signal' and 'Sell Signal' indicating 
                            buying and selling opportunities.
    """
    df = pd.read_csv(filePath)
    # print(df.head())
    df['RSI']=calculate_rsi(df)  # Assuming calculate_rsi function calculates RSI
    df=calculate_adx(df)

    # Calculate 52-week high
    df['52-week High'] = df['Close'].transform(lambda x: x.rolling(window=252).max())
    # Calculate 52-week high threshold (5% below the 52-week high)
    df['Threshold'] = df['52-week High'] * 0.95

    # Calculate historical volatility (e.g., 20-day rolling standard deviation)
    df['Volatility'] = ((df['Close'].transform(lambda x: x.rolling(window=20).std())) / df['Close'])*100
    df['14-day MA'] = df['Close'].transform(lambda x: x.rolling(window=14).mean())
    # Calculate 10-day Moving Average (MA)
    df['10-day MA'] = df['Close'].transform(lambda x: x.rolling(window=10).mean())
    # Calculate 20-day Moving Average (MA)
    df['20-day SMA'] = df['Close'].transform(lambda x: x.rolling(window=20).mean())
    df['50-day SMA'] = df['Close'].transform(lambda x: x.rolling(window=50).mean())

    adx_threshold = 25  # Adjust as needed
    volatility_threshold = 0.2  # Adjust as needed
    rsi_threshold_buy = 40  # Oversold buy signal
    rsi_threshold_sell = 60  # Overbought sell signal

    df.loc[(df['10-day MA'] > df['20-day SMA']) & (df['ADX'] > adx_threshold) ,'Signal'] = 'Buy'
    df.loc[(df['10-day MA'] < df['20-day SMA']) | (df['ADX'] < adx_threshold) ,'Signal'] = 'Sell'
    
    df.loc[(df['Signal']!='Buy') & (df['Signal']!='Sell'),'Signal'] = 'No Signal'
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
    # print("Expect max volatility in these midcap stocks :")
    # print(top_3_scrips)
    return top_3_scrips

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
    # print("Expect Max Volatility in these Nifty stocks :")
    # print(top_3_scrips)
    return top_3_scrips

    
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

def generate_calls(Nifty50_dict, NiftyMidcap_dict ):
    buy_signals={}
    sell_signals={}
    for k,v in Nifty50_dict.items():
        name = v
        # print(name)
        file_name = os.path.join('data/', name+'.csv')
        file_name = "data/"+name+".csv"
        # data = generate_signals(file_name,name)
        data = newSignals52WhighVol(file_name)
        signal_file_path ="signals/"+name+".csv"
        data.to_csv(signal_file_path)
        buy_signals,sell_signals = generate_trading_scrips(signal_file_path,name,buy_signals,sell_signals,k)
    
    # print(buy_signals)

    buy_nifty_call = maxVoltilityNifty(buy_signals)

    buy_signals_midcap = {}
    sell_signals_midcap = {}

    for k,v in NiftyMidcap_dict.items():
        name = v
        file_name = os.path.join('midcap_data/', name+'.csv')
        file_name = "midcap_data/"+name+".csv"
        # data = generate_signals(file_name,name)
        data = newSignals52WhighVol(file_name)
        signal_file_path ="midcap_signals/"+name+".csv"
        data.to_csv(signal_file_path)
        buy_signals_midcap,sell_signals_midcap = generate_trading_scrips(signal_file_path,name,buy_signals_midcap,sell_signals_midcap,k)

    # print(buy_signals_midcap)

    buy_mid_call = maxVoltilityMidcap(buy_signals_midcap)
    # print(buy_nifty_call,buy_mid_call)
    buy_calls = {}
    for x in buy_mid_call:
        buy_calls[x[0]] = x[1]

    for y in buy_nifty_call:
        buy_calls[y[0]] = y[1]

    return buy_calls

def newBuyCalls(buy_calls,Nifty50_dict, NiftyMidcap_dict):
    new_signals=[]
    for k,v in buy_calls.items():
        name=k
        if os.path.exists("signals/"+name+".csv"):
            filePath = "signals/"+name+".csv"
            
        elif os.path.exists("midcap_signals/"+name+".csv"):
            filePath = "midcap_signals/"+name+'.csv'
            
        data = pd.read_csv(filePath, nrows=1000)
        # print(filePath)
        second_last_row = data.loc[data.index[-2]]
        last_row = data.loc[data.index[-1]]
        # print(second_last_row)
        # print(last_row)
        if(second_last_row['Signal']=="Sell" and last_row['Signal'] == "Buy"):
            # print(name)
            new_signals.append(name)
    return new_signals


