#lets pull data at 1 minute frequency for Bank's in the nifty index 
from collections import OrderedDict
from SmartApi import SmartConnect
# from SmartApi.smartWebSocketV2 import SmartWebSocketV2
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
import psycopg2

# Database connection details
connection_params = {
    'host': 'localhost',        # or the IP address of your database server
    'database': 'Fin_data', # replace with your database name
    'user': 'postgres',    # replace with your PostgreSQL username
    'password': 'root', # replace with your PostgreSQL password
    'port': 5432                # default PostgreSQL port
}

# api_key = "0rNQURBd"
# clientId = "A51768681"
# pwd = "1960"
# smartApi = SmartConnect(api_key)
# token = "YJUZMHPGKT5PECJFEFBMOU4SXU"
# totp=pyotp.TOTP(token).now()
# data = smartApi.generateSession(clientId, pwd, totp)

arr = {
    "AXISBANK-EQ": 5900,
    "HDFCBANK-EQ": 1333,
    "ICICIBANK-EQ": 4963,
    "KOTAKBANK-EQ": 1922,
    "SBIN-EQ" : 3045
    }

currdate = current_date = datetime.now().date()
date_string = current_date.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD
previous_day = current_date - timedelta(days = 1)
previous_day = previous_day.strftime("%Y-%m-%d")
# print(previous_day)

try:
    # Establish the connection
    conn = psycopg2.connect(**connection_params)
    print("Connection successful")

    # Create a cursor
    cursor = conn.cursor()

    # Example query
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print("Database version:", db_version)

    # Close the connection
    # cursor.close()
    # conn.close()

except Exception as e:
    print("Error connecting to the database:", e)

def updateData(datas,k):
    insert_query = """
    INSERT INTO stock_candles (stock_symbol, timestamp, open_price, high_price, low_price, close_price, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (stock_symbol, timestamp) DO NOTHING; -- Prevent duplicates
    """
    try:
        conn = psycopg2.connect(**connection_params)
        print("Connection successful")
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        for data in datas:
            cursor.execute(insert_query,(str(k),data[0],data[1],data[2],data[3],data[4],data[5]))
        conn.commit()
        cursor.close()
    except Exception as e:
        print("Error inserting data:", e)


def updateScrips(previous_day,date_string):
    api_key = "0rNQURBd"
    clientId = "A51768681"
    pwd = "1960"
    smartApi = SmartConnect(api_key)
    token = "YJUZMHPGKT5PECJFEFBMOU4SXU"
    totp=pyotp.TOTP(token).now()
    data = smartApi.generateSession(clientId, pwd, totp)
    for k,v in arr.items():
        route = 'api.candle.data'
        method = 'POST'
        params = {
                "exchange": "NSE",
                "symboltoken": str(v),
                "interval": 'ONE_MINUTE',
                "fromdate": previous_day+' '+'09:15',
                "todate": date_string+' '+'15:30'
            }
        datas=smartApi._request(route=route, method=method, parameters=params)['data']
        print(str(k))
        updateData(datas,str(k))
        time.sleep(1)
        # break

def allTrades(action,quantity,price,stock_name,stock_token):
    order = {
        "product_type": "INTRADAY",
        "transaction_type": action,
        "quantity": quantity,
        "price": price,
        "exchange": "NSE",
        "symbol_name": stock_name,
        "token": stock_token
    }
    return order

    
def calculateBrokerage(orders):
    api_key = "0rNQURBd"
    clientId = "A51768681"
    pwd = "1960"
    smartApi = SmartConnect(api_key)
    token = "YJUZMHPGKT5PECJFEFBMOU4SXU"
    totp=pyotp.TOTP(token).now()
    route = 'api.estimateCharges'
    method= 'POST'
    params = {"orders":orders}
    # data = smartApi.generateSession(clientId, pwd, totp)
    response = smartApi._request(route = route, method = method,parameters = params)
    return response
    



# updateScrips()
