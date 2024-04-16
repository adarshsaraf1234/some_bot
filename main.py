
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi import FastAPI, HTTPException, Form,Depends
from pydantic import BaseModel
from collections import OrderedDict
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import threading as td
import os 
import time
from datetime import datetime,timedelta
import numpy as np 
import pyotp
# import orders
import pandas as pd
import asyncio 
import csv
import socket
import requests
from getmac import get_mac_address

app = FastAPI()

origins = ["http://localhost:8080","http://localhost:5173"]

class User(BaseModel):
    username: str
    password: str

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
hardcoded_users: dict[str, User] = {
    "user1": User(username="user1", password="password123"),
} 

def cleanData(filePath):
    df=pd.read_csv(filePath)
    # Remove rows with all NaN or empty values (blank rows)
    df_cleaned = df.dropna(how='all')
    # Save the cleaned DataFrame back to a CSV file
    df_cleaned.to_csv(filePath, index=False)

def initialise_SmartAPI():
    global smartApi
    api_key = "0rNQURBd"
    clientId = "A51768681"
    pwd = "1960"
    smartApi = SmartConnect(api_key)
    token = "YJUZMHPGKT5PECJFEFBMOU4SXU"

    correlation_id = "abcd123"
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
    return smartApi

@app.post('/login')
async def login(user: User):
    if user.username not in hardcoded_users:
        raise HTTPException(status_code=401, detail="Username not found")

    stored_user = hardcoded_users[user.username]
    print(stored_user.password,user.password)
    # In production, you should compare the hashed password
    if user.password != stored_user.password:
        raise HTTPException(status_code=401, detail="Incorrect password")

    return {"message": "Login successful"}
async def updateNiftyScrips(smartApi,Nifty50_dict,date_string):
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
                    time.sleep(10)
            else:
                continue
    for k,v in Nifty50_dict.items():
        name = v
        file_name = "data/"+name+".csv"
        cleanData(file_name)
async def updateMidcapScrips(smartApi,NiftyMidcap_dict,date_string):
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
        
        if(last_date!=date_string):
            with open(file_name,'a',newline='') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerows(data)
                time.sleep(10)
        else:
            continue
    for k,v in NiftyMidcap_dict.items():
        name = v
        file_name = "midcap_data/"+name+".csv"
        cleanData(file_name)

@app.get('/updateScrips')
async def UpdateScrips(smartApi:SmartConnect = Depends(initialise_SmartAPI)):
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

    current_date = datetime.now().date()
    date_string = current_date.strftime("%Y-%m-%d")
    try:
        await updateNiftyScrips(smartApi,Nifty50_dict,date_string)
        await updateMidcapScrips(smartApi,NiftyMidcap_dict,date_string)
       
        return{"message":"Updated all nifty scrips"}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))



