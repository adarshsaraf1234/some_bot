
from collections import OrderedDict
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import os 
import time
from datetime import datetime,timedelta
import numpy as np 
import pyotp
import json
import pandas as pd
import http.client
import csv
import socket
import requests
from getmac import get_mac_address

api_key = "0rNQURBd"
clientId = "A51768681"
pwd = "1960"
smartApi = SmartConnect(api_key)
token = "YJUZMHPGKT5PECJFEFBMOU4SXU"

correlation_id = "abcd123"

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

# result = dict(reversed(list(Nifty50_dict.items())))
# nifty_names = result['Symbol']

Nifty_T = list(df_Nifty.iloc[0:]['Token'])

mac_address = get_mac_address()
local_ip = socket.gethostbyname(socket.gethostname())
# response = requests.get('https://api.ipify.org?format=json')
# public_ip = response.json()['ip']

# login api call
totp=pyotp.TOTP(token).now()
data = smartApi.generateSession(clientId, pwd, totp)

authToken = data['data']['jwtToken']
refreshToken = data['data']['refreshToken']
print(data)
# fetch the feedtoken
feedToken = smartApi.getfeedToken()

# fetch User Profile
res = smartApi.getProfile(refreshToken)
smartApi.generateToken(refreshToken)
res=res['data']['exchanges']

correlation_id = "abc123"
action = 1
mode = 1
token_list = [
    {
        "exchangeType": 1, 
        "tokens": ["3045","10794"]
    }
]
conn = http.client.HTTPSConnection("apiconnect.angelbroking.com")
current_date = datetime.now().date()
date_string = current_date.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD

yesterday = current_date - timedelta(days=1)
yesterday_string = yesterday.strftime("%Y-%m-%d")
# for t in Nifty_T:
#     route = 'api.candle.data'
#     method = 'POST'
#     params = {
#             "exchange": "NSE",
#             "symboltoken": str(t),
#             "interval": 'ONE_DAY',
#             "fromdate": '2022-07-01'+' '+'09:15',
#             "todate": date_string+' '+'15:30'
#         }
#     data=smartApi._request(route=route, method=method, parameters=params)['data']
#     columns=["Date","Open","High","Low","Close","Volume"]
#     data[0]=columns
#     name = nifty_names[t]
#     file_name = os.path.join('data/', name+'.csv')
#     file_name = "data/"+name+".csv"
#     with open(file_name,'w',newline='') as csv_file:
#         csv_writer = csv.writer(csv_file)
#         csv_writer.writerows(data)
#     time.sleep(60)
def remove_last_line_from_csv(file_name):
    # Read the content of the CSV file into a list of lines
    with open(file_name, 'r') as csv_file:
        lines = csv_file.readlines()

    # Remove the last line if the file has content
    if lines:
        lines.pop()
        # Write the modified content back to the CSV file
        with open(file_name, 'w') as csv_file:
            csv_file.writelines(lines)

def cleanData(filePath):
    df=pd.read_csv(filePath)
    # Remove rows with all NaN or empty values (blank rows)
    df_cleaned = df.dropna(how='all')
    # Save the cleaned DataFrame back to a CSV file
    df_cleaned.to_csv(filePath, index=False)

def updateNiftyScrips():
    for k,v in Nifty50_dict.items():
        name = v
        print(name)
        file_name = os.path.join('data/', name+'.csv')
        file_name = "data/"+name+".csv"
        df = pd.read_csv(file_name)
        last_row = df.iloc[-1] 
        last_date = last_row["Date"]
        last_date = last_date[0:10]
        print(last_date)
        route='api.candle.data'
        method='POST'
        params = {
                "exchange": "NSE",
                "symboltoken": str(k),
                "interval": 'ONE_DAY',
                "fromdate": last_date+' '+'09:15',
                "todate": date_string+' '+'15:30'
            }
        data=smartApi._request(route=route, method=method, parameters=params)['data']    
        print(data)
        
        if(last_date!=date_string and data is not None):
            with open(file_name,'a',newline='') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerows(data)
                time.sleep(2)
        else:
            time.sleep(2)
    for k,v in Nifty50_dict.items():
        name = v
        file_name = "data/"+name+".csv"
        cleanData(file_name)

def updateNiftyMidcapScrips():
    for k,v in NiftyMidcap_dict.items():
        name = v
        print(name)
        file_name = os.path.join('midcap_data/', name+'.csv')
        file_name = "midcap_data/"+name+".csv"
        df = pd.read_csv(file_name)
        last_row = df.iloc[-1] 
        last_date = last_row["Date"]
        last_date = last_date[0:10]
        print(last_date)
        route='api.candle.data'
        method='POST'
        params = {
                "exchange": "NSE",
                "symboltoken": str(k),
                "interval": 'ONE_DAY',
                "fromdate": last_date+' '+'09:15',
                "todate": date_string+' '+'15:30'
            }
        data=smartApi._request(route=route, method=method, parameters=params)['data']    
        if data!=None:
            if(last_date!=date_string):
                with open(file_name,'a',newline='') as csv_file:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerows(data)
                    time.sleep(2)
            else:
                time.sleep(2)
        
        time.sleep(2)
        continue
    for k,v in NiftyMidcap_dict.items():
        name = v
        file_name = "midcap_data/"+name+".csv"
        cleanData(file_name)
        

# response = smartApi.ltpData('NSE','SBIN-EQ','3045')['data']
# print(response)

updateNiftyScrips()
updateNiftyMidcapScrips()


def getNiftyMidcapIndicies():
    for k,v in NiftyMidcap_dict.items():
        route = 'api.candle.data'
        method = 'POST'
        params = {
                "exchange": "NSE",
                "symboltoken": str(k),
                "interval": 'ONE_DAY',
                "fromdate": '2022-07-01'+' '+'09:15',
                "todate": date_string+' '+'15:30'
            }
        data=smartApi._request(route=route, method=method, parameters=params)['data']
        columns=["Date","Open","High","Low","Close","Volume"]
        data[0]=columns
        name = v
        file_name = os.path.join('midcap_data/', name+'.csv')
        file_name = "midcap_data/"+name+".csv"
        with open(file_name,'w',newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(data)
        time.sleep(10)

def getNiftyindicies():
    for k,v in Nifty50_dict.items():
        route = 'api.candle.data'
        method = 'POST'
        params = {
                "exchange": "NSE",
                "symboltoken": str(k),
                "interval": 'ONE_DAY',
                "fromdate": '2022-07-01'+' '+'09:15',
                "todate": date_string+' '+'15:30'
            }
        data=smartApi._request(route=route, method=method, parameters=params)['data']
        columns=["Date","Open","High","Low","Close","Volume"]
        data[0]=columns
        name = v
        # file_name = os.path.join('data/', name+'.csv')
        file_name = "data/"+name+".csv"
        print(file_name)
        with open(file_name,'w',newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(data)
            time.sleep(10)


# setBuyOrders(buy_signals)


