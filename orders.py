import pandas as pd 
import numpy as np
import os 
import json
import http.client
import mimetypes
import orders as od
from getmac import get_mac_address
import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import requests

def getLtpData(name, token):
    
    api_key = "0rNQURBd"
    clientId = "A51768681"
    pwd = "1960"
    smartApi = SmartConnect(api_key)
    token = "YJUZMHPGKT5PECJFEFBMOU4SXU"
    # response = requests.get('https://api.ipify.org?format=json')
    totp=pyotp.TOTP(token).now()
    data = smartApi.generateSession(clientId, pwd, totp)
    conn  = http.client.HTTPSConnection("apiconnect.angelbroking.com")
    
    payload_ltp = {
        "exchange": "BSE",
        "tradingsymbol": "ADANIENT",  # Encode with the appropriate encoding
        "symboltoken": 25  # Encode with the appropriate encoding
    }
    payload_ltp_json = json.dumps(payload_ltp)
    response=smartApi.ltpData('NSE',name,token)
    print(response)
    return response

def setBuyOrders(buy_signals):
    conn = http.client.HTTPSConnection("apiconnect.angelbroking.com")
    # ltp=getLtpData(v,k)
    for k,v in buy_signals.items():
        print(k,v)
        ltp=getLtpData(v,k)
        amt = abs(10000/ltp)
    #     payload = {
    #    "exchange": "NSE",
    #    "tradingsymbol": "INFY-EQ",
    #    "quantity": 5,
    #    "disclosedquantity": 3,
    #    "transactiontype": "BUY",
    #    "ordertype": "MARKET",
    #    "variety": "STOPLOSS",
    #    "producttype": "INTRADAY"
    #    }


# getLtpData("ADANIENT-EQ","25")

