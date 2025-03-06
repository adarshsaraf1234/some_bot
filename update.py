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
# from ssl import 
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

Nifty_T = list(df_Nifty.iloc[0:]['Token'])

mac_address = get_mac_address()
local_ip = socket.gethostbyname(socket.gethostname())
response = requests.get('https://api.ipify.org?format=json')
public_ip = response.json()['ip']

# login api call
totp=pyotp.TOTP(token).now()
data = smartApi.generateSession(clientId, pwd, totp)

authToken = data['data']['jwtToken']
refreshToken = data['data']['refreshToken']
# print(data)
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

current_date = datetime.now().date()
date_string = current_date.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD

yesterday = current_date - timedelta(days=1)
yesterday_string = yesterday.strftime("%Y-%m-%d")

conn = http.client.HTTPSConnection("apiconnect.angelbroking.com",context=None)
payload = {
    "mode": "FULL",
    "exchangeTokens": {
        "NSE": ["3045"]
    }
}
headers = {
  'X-PrivateKey': api_key,
  'Accept': 'application/json',
  'X-SourceID': 'WEB',
  'X-ClientLocalIP': local_ip,
  'X-ClientPublicIP': public_ip,
  'X-MACAddress': mac_address,
  'X-UserType': 'USER',
  'Authorization': str(authToken),
  'Accept': 'application/json',
  'X-SourceID': 'WEB',
  'Content-Type': 'application/json'
}
# print(headers)

# conn.request("POST", "rest/secure/angelbroking/market/v1/quote/", payload, headers)
# res = conn.getresponse()
# data = res.read()
# print(data.decode("utf-8"))
nifty_list = [str(element) for element in list(df_Nifty['Token'])]
nifty_midcap = [str(element) for element in list(df_Nifty_Midcap['Token'])]
print(nifty_midcap)
# response = smartApi.getMarketData("LTP",{ "NSE": nifty_list})
for item in nifty_midcap:
    response1 = smartApi.getMarketData("LTP",{"NSE":[str(item)]})
    print(response1)



# response1 = smartApi.getMarketData("LTP",{"NSE":nifty_midcap})
# print(response1)
# def UpdateNiftyHourly():
#     for k,v in Nifty50_dict.items():
#         name = v
#         # print(name)
#         file_name = os.path.join('data/', name+'.csv')
#         file_name = "data/"+name+".csv"
#         df = pd.read_csv(file_name)
#         last_row = df.iloc[-1] 
#         last_date = last_row["Date"]
#         last_date = last_date[0:10]
#         # print(last_date)
#         response=smartApi.ltpData('NSE','ADANIENT-EQ','25')
#         break
#     print(response)

# UpdateNiftyHourly()