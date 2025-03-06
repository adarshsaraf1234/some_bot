import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from main import updateScrips

class MeanReversionAnalyzer:
    def __init__(self, db_connection_string):
        self.engine = create_engine(db_connection_string)

    def fetch_last_date(self):
        query = "SELECT timestamp FROM stock_candles ORDER BY timestamp DESC LIMIT 1"
        try:
            result = pd.read_sql_query(query, self.engine)
            if result.empty:
                return None
            return pd.to_datetime(result['timestamp'].iloc[0]).strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Error fetching last date: {e}")
            return None

    def fetch_stock_data(self, symbol, start_date, end_date):
        query = """
        SELECT timestamp, close_price
        FROM stock_candles
        WHERE stock_symbol = %(symbol)s 
        AND timestamp BETWEEN %(start_date)s AND %(end_date)s
        AND EXTRACT(HOUR FROM timestamp) BETWEEN 9 AND 15
        AND (EXTRACT(HOUR FROM timestamp) != 15 OR EXTRACT(MINUTE FROM timestamp) <= 30)
        ORDER BY timestamp
        """
        
        try:
            df = pd.read_sql_query(
                query,
                self.engine,
                params={'symbol': symbol, 'start_date': start_date, 'end_date': end_date}
            )
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df[~df['timestamp'].dt.dayofweek.isin([5, 6])]  # Remove weekends
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def calculate_mean_reversion_signals(self, df, lookback_period=20):
        """Calculate mean reversion signals using Bollinger Bands and RSI"""
        # Calculate moving average and standard deviation
        df['MA'] = df['close_price'].rolling(window=lookback_period).mean()
        df['STD'] = df['close_price'].rolling(window=lookback_period).std()
        
        # Calculate Bollinger Bands
        df['Upper_Band'] = df['MA'] + (2 * df['STD'])
        df['Lower_Band'] = df['MA'] - (2 * df['STD'])
        
        # Calculate RSI
        delta = df['close_price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=lookback_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=lookback_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Calculate z-score
        df['z_score'] = (df['close_price'] - df['MA']) / df['STD']
        
        return df

    def find_trading_opportunities(self, df, z_score_threshold=2.0, rsi_oversold=30, rsi_overbought=70):
        opportunities = []
        
        for timestamp, row in df.iterrows():
            signal = None
            
            # Long signal: Price below lower band (oversold) and RSI below oversold threshold
            if (row['close_price'] < row['Lower_Band'] and 
                row['RSI'] < rsi_oversold and 
                row['z_score'] < -z_score_threshold):
                signal = 'LONG'
                
            # Short signal: Price above upper band (overbought) and RSI above overbought threshold
            elif (row['close_price'] > row['Upper_Band'] and 
                  row['RSI'] > rsi_overbought and 
                  row['z_score'] > z_score_threshold):
                signal = 'SHORT'
                
            if signal:
                opportunities.append({
                    'timestamp': timestamp,
                    'price': row['close_price'],
                    'z_score': row['z_score'],
                    'RSI': row['RSI'],
                    'signal': signal
                })
        
        return pd.DataFrame(opportunities)

    def backtest_strategy(self, df, z_score_threshold=2.0, rsi_oversold=30, rsi_overbought=70):
        position = 0
        trades = []
        
        for i in range(len(df)):
            if position == 0:  # No position
                # Long entry
                if (df['z_score'].iloc[i] < -z_score_threshold and 
                    df['RSI'].iloc[i] < rsi_oversold):
                    position = 1
                    entry_price = df['close_price'].iloc[i]
                    entry_time = df.index[i]
                
                # Short entry
                elif (df['z_score'].iloc[i] > z_score_threshold and 
                      df['RSI'].iloc[i] > rsi_overbought):
                    position = -1
                    entry_price = df['close_price'].iloc[i]
                    entry_time = df.index[i]
            
            elif position == 1:  # Long position
                # Exit when price reverts to mean or stop loss hit
                if (abs(df['z_score'].iloc[i]) < 0.5 or 
                    df['close_price'].iloc[i] < entry_price * 0.98):
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': df['close_price'].iloc[i],
                        'position': 'LONG',
                        'pnl': df['close_price'].iloc[i] - entry_price
                    })
                    position = 0
            
            elif position == -1:  # Short position
                # Exit when price reverts to mean or stop loss hit
                if (abs(df['z_score'].iloc[i]) < 0.5 or 
                    df['close_price'].iloc[i] > entry_price * 1.02):
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': df['close_price'].iloc[i],
                        'position': 'SHORT',
                        'pnl': entry_price - df['close_price'].iloc[i]
                    })
                    position = 0
        
        return pd.DataFrame(trades)

    def plot_signals(self, df):
        plt.figure(figsize=(15, 10))
        
        # Price and Bollinger Bands
        plt.subplot(2, 1, 1)
        plt.plot(df.index, df['close_price'], label='Price', color='blue')
        plt.plot(df.index, df['MA'], label='Moving Average', color='black')
        plt.plot(df.index, df['Upper_Band'], label='Upper Band', color='red', linestyle='--')
        plt.plot(df.index, df['Lower_Band'], label='Lower Band', color='green', linestyle='--')
        plt.title('Price with Bollinger Bands')
        plt.legend()
        
        # RSI and Z-score
        plt.subplot(2, 1, 2)
        plt.plot(df.index, df['RSI'], label='RSI', color='purple')
        plt.plot(df.index, df['z_score'], label='Z-score', color='orange')
        plt.axhline(y=70, color='r', linestyle='--')
        plt.axhline(y=30, color='g', linestyle='--')
        plt.title('RSI and Z-score')
        plt.legend()
        
        plt.tight_layout()
        plt.show()

def run_analysis():
    db_string = "postgresql://postgres:root@localhost:5432/Fin_data"
    analyzer = MeanReversionAnalyzer(db_string)
    
    symbol = "AXISBANK-EQ"  # Example stock
    start_date = '2025-02-01'
    end_date = '2025-02-21'
    
    # Fetch and process data
    df = analyzer.fetch_stock_data(symbol, start_date, end_date)
    if df is None:
        return None, None
    
    # Calculate signals
    df = analyzer.calculate_mean_reversion_signals(df)
    
    # Find opportunities and backtest
    opportunities = analyzer.find_trading_opportunities(df)
    trades = analyzer.backtest_strategy(df)
    
    # Plot signals
    analyzer.plot_signals(df)
    
    return opportunities, trades

# Run analysis
opportunities, trades = run_analysis()
if opportunities is not None and trades is not None:
    print("\nTrading Opportunities:")
    print(opportunities)
    print("\nBacktest Results:")
    print(f"Number of trades: {len(trades)}")
    print(f"Total PnL: {trades['pnl'].sum():.2f}")