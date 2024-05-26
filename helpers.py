import pandas as pd
from getmac import get_mac_address
import orders as od
import numpy as np 
import os 
import http.client
import requests
import socket 
import mimetypes
from fetcher import *
import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


def fetchCurrentPositions():
    api_key = "0rNQURBd"
    clientId = "A51768681"
    pwd = "1960"
    smartApi = SmartConnect(api_key)
    token = "YJUZMHPGKT5PECJFEFBMOU4SXU"
    totp=pyotp.TOTP(token).now()
    data = smartApi.generateSession(clientId, pwd, totp)
    holding_response = smartApi.holding()
    
    return holding_response

all_holdings = fetchCurrentPositions()
#=====================================================================================
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
#======================================================================================

def processHoldings(hold):
    buy_calls = generate_calls(Nifty50_dict, NiftyMidcap_dict)
    print(buy_calls)
    new_calls = newBuyCalls(buy_calls,Nifty50_dict, NiftyMidcap_dict)
    print(new_calls)

processHoldings(all_holdings)
    