import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from statsmodels.tsa.stattools import coint
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from main import updateScrips

class StatArbAnalyzer:
    def __init__(self, db_connection_string):
        print("Trying to create engine...")
        self.engine = create_engine(db_connection_string)
        print("Engine created successfully!")

    def fetch_last_date(self):
        query = """
        SELECT timestamp
        FROM stock_candles
        ORDER BY timestamp DESC
        LIMIT 1
        """
        
        try:
            # Fetch the last row's timestamp
            result = pd.read_sql_query(query, self.engine)
            if result.empty:
                print("The database is empty. No data found.")
                return None
            
            # Extract and format the timestamp
            last_date = result['timestamp'].iloc[0]
            formatted_date = pd.to_datetime(last_date).strftime('%Y-%m-%d')
            print(f"Last date fetched from DB: {formatted_date}")  # Debug print
            return formatted_date
        
        except Exception as e:
            print(f"Error fetching last date: {e}")
            return None
        
    def fetch_minute_data(self, symbols, start_date, end_date):
        """Fetch minute-level data with improved error handling and validation."""
        # First check if the dates are valid trading days
        query = """
        SELECT DISTINCT DATE(timestamp) as trading_date
        FROM stock_candles
        WHERE timestamp BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY trading_date
        """
        
        try:
            trading_days = pd.read_sql_query(
                query,
                self.engine,
                params={
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
            
            if trading_days.empty:
                print(f"No trading days found between {start_date} and {end_date}")
                return None
                
            # Get the actual first and last trading days
            actual_start = trading_days['trading_date'].min()
            actual_end = trading_days['trading_date'].max()
            
            print(f"Available trading days: {actual_start} to {actual_end}")  # Debug print
            
            # Fetch the actual data
            query = """
            SELECT *
            FROM stock_candles
            WHERE stock_symbol = ANY(%(symbols)s) 
            AND timestamp BETWEEN %(start_date)s AND %(end_date)s
            AND EXTRACT(HOUR FROM timestamp) BETWEEN 9 AND 15
            AND (EXTRACT(HOUR FROM timestamp) != 15 OR EXTRACT(MINUTE FROM timestamp) <= 30)
            ORDER BY timestamp
            """
            
            df = pd.read_sql_query(
                query,
                self.engine,
                params={
                    'symbols': symbols,
                    'start_date': actual_start,
                    'end_date': actual_end
                }
            )
            
            if df.empty:
                print("No data found for the specified symbols and date range")
                return None
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Discard data from Saturday and Sunday
            df = df[~df['timestamp'].dt.dayofweek.isin([5, 6])]
            
            # Create pivot table
            pivot_df = df.pivot_table(
                index='timestamp', 
                columns='stock_symbol', 
                values='close_price'
            )
            
            # Forward fill missing values
            pivot_df = pivot_df.ffill()
            
            # Check for missing data
            missing_data = pivot_df.isnull().sum()
            if missing_data.any():
                print("Warning: Missing data detected after filling:")
                print(missing_data[missing_data > 0])
                
            return pivot_df
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def analyze_correlations(self, prices_df):
        """
        Analyze correlations between pairs of stocks with more flexible thresholds.
        """
        window = 200 # 2-hour rolling window for intraday analysis
        pairs = []
        symbols = prices_df.columns
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                stock1 = symbols[i]
                stock2 = symbols[j]
                
                # Get clean pair data
                pair_df = prices_df[[stock1, stock2]].copy()
                pair_df = pair_df.dropna()
                
                if len(pair_df) < window:
                    continue
                
                # Calculate rolling correlation
                rolling_corr = pair_df[stock1].rolling(window=window).corr(pair_df[stock2])
                current_corr = rolling_corr.iloc[-1]
                
                # Calculate rolling volatility ratio
                vol1 = pair_df[stock1].pct_change().rolling(window).std()
                vol2 = pair_df[stock2].pct_change().rolling(window).std()
                vol_ratio = (vol1 / vol2).iloc[-1]
                
                # More lenient correlation threshold
                if current_corr > 0.9:  # Changed from 0.9 to 0.7
                    # Perform cointegration test
                    _, pvalue, _ = coint(pair_df[stock1], pair_df[stock2])
                    
                    # Calculate additional stability metrics
                    correlation_stability = rolling_corr.std()
                    price_ratio = (pair_df[stock1] / pair_df[stock2]).std()
                    
                    # Calculate mean reversion strength
                    spread = pair_df[stock1] - (pair_df[stock2] * (pair_df[stock1].mean() / pair_df[stock2].mean()))
                    half_life = self.calculate_half_life(spread)
                    
                    pairs.append({
                        'stock1': stock1,
                        'stock2': stock2,
                        'correlation': current_corr,
                        'correlation_stability': correlation_stability,
                        'coint_pvalue': pvalue,
                        'volatility_ratio': vol_ratio,
                        'price_ratio_stability': price_ratio,
                        'half_life': half_life,
                        'lookback_period': window
                    })
        
        pairs_df = pd.DataFrame(pairs)
        
        # Modified quality score calculation
        if not pairs_df.empty:
            # Normalize half-life (lower is better, but we don't want negative scores)
            max_half_life = pairs_df['half_life'].max()
            normalized_half_life = 1 - (pairs_df['half_life'] / max_half_life)
            
            pairs_df['quality_score'] = (
                pairs_df['correlation'] * 0.25 +
                (1 - pairs_df['correlation_stability']) * 0.20 +
                (1 - pairs_df['coint_pvalue']) * 0.25 +
                (1 - abs(1 - pairs_df['volatility_ratio'])) * 0.15 +
                normalized_half_life * 0.15
            )
            
            # Sort by quality score
            pairs_df = pairs_df.sort_values('quality_score', ascending=False)
        
        return pairs_df

    def calculate_pair_metrics(self, prices_df, stock1, stock2):
        window = 200 # Adjusted to smaller window
        
        pair_df = prices_df[[stock1, stock2]].dropna()
        if len(pair_df) < window:
            return None, None
            
        ratio = pair_df[stock1] / pair_df[stock2]
        rolling_ratio_mean = ratio.rolling(window=window).mean()
        rolling_ratio_std = ratio.rolling(window=window).std()
        spread = pair_df[stock1] - (pair_df[stock2] * rolling_ratio_mean)
        
        rolling_spread_std = spread.rolling(window=window).std()
        rolling_spread_mean = spread.rolling(window=window).mean()
        z_score = (spread - rolling_spread_mean) / rolling_spread_std
        
        if z_score.iloc[-1] is None or np.isnan(z_score.iloc[-1]):
            return None, None
            
        metrics = {
            'ratio_mean': rolling_ratio_mean.iloc[-1],
            'ratio_std': rolling_ratio_std.iloc[-1],
            'spread_mean': rolling_spread_mean.iloc[-1],
            'spread_std': rolling_spread_std.iloc[-1],
            'half_life': self.calculate_half_life(spread),
            'z_score_current': z_score.iloc[-1]
        }
        
        return metrics, z_score

    def plot_zscore(self, prices_df, stock1, stock2):
        """Plot z-score with conservative thresholds."""
        metrics, z_score = self.calculate_pair_metrics(prices_df, stock1, stock2)
        
        if metrics is None or z_score is None:
            print(f"Unable to calculate z-score for {stock1} and {stock2}")
            return
        
        plt.figure(figsize=(15, 7))
        plt.plot(z_score.index, z_score.values, label=f'Z-score: {stock1} / {stock2}', color='blue')
        
        # Add horizontal lines for thresholds
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        plt.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Entry Threshold (1.0σ)')
        plt.axhline(y=-1.0, color='green', linestyle='--', alpha=0.5)
        plt.axhline(y=2, color='red', linestyle='--', alpha=0.5, label='Extreme Threshold (2σ)')
        plt.axhline(y=-2, color='red', linestyle='--', alpha=0.5)
        
        plt.title(f'Z-score Evolution: {stock1} vs {stock2}\nEntry Threshold: ±1.0σ')
        plt.xlabel('Time')
        plt.ylabel('Z-score (σ)')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        current_zscore = z_score.iloc[-1]
        plt.text(0.02, 0.98, f'Current Z-score: {current_zscore:.2f}σ', 
                transform=plt.gca().transAxes, 
                bbox=dict(facecolor='white', alpha=0.8))
        
        # Add trading signal annotation if applicable
        if abs(current_zscore) > 1.0:
            signal = "SHORT stock1/LONG stock2" if current_zscore > 1.0 else "LONG stock1/SHORT stock2"
            plt.text(0.02, 0.93, f'Signal: {signal}', 
                    transform=plt.gca().transAxes,
                    bbox=dict(facecolor='lightgreen', alpha=0.8))
        
        plt.show()

    def back_test_pairs(self, prices_df, pairs_df, z_score_entry=1.5, z_score_exit=1.0, max_loss=1000):
        trades = []
        pnl = 0.0
        
        for _, pair in pairs_df.iterrows():
            stock1 = pair['stock1']
            stock2 = pair['stock2']
            pair_df = prices_df[[stock1, stock2]].dropna()

            metrics, z_score = self.calculate_pair_metrics(prices_df, stock1, stock2)
            if metrics is None or z_score is None:
                continue
                
            hedge_ratio = metrics['ratio_mean']
            open_trade = None

            for i in range(len(pair_df)):
                current_zscore = z_score.iloc[i]

                # Entry Condition
                if open_trade is None and abs(current_zscore) > z_score_entry:
                    action = "short_long" if current_zscore > 0 else "long_short"
                    entry_price1 = pair_df[stock1].iloc[i]
                    entry_price2 = pair_df[stock2].iloc[i]
                    
                    open_trade = {
                        'stock1': stock1,
                        'stock2': stock2,
                        'entry_date': pair_df.index[i],
                        'entry_price1': entry_price1,
                        'entry_price2': entry_price2,
                        'hedge_ratio': hedge_ratio,
                        'action': action,
                        'entry_zscore': current_zscore
                    }
                    continue

                # Exit Condition
                if open_trade is not None:
                    exit_price1 = pair_df[stock1].iloc[i]
                    exit_price2 = pair_df[stock2].iloc[i]
                    exit_date = pair_df.index[i]

                    # Calculate PnL
                    quantity1 = 100  # Assuming 100 shares of stock 1
                    quantity2 = int(hedge_ratio * 100)
                    pnl_trade = self.calculate_pnl(
                        open_trade['action'],
                        quantity1, quantity2,
                        open_trade['entry_price1'], open_trade['entry_price2'],
                        exit_price1, exit_price2
                    )

                    # Check for stop-loss
                    if pnl_trade < -max_loss:
                        pnl += -1000
                        trades.append({
                            'stock1': stock1,
                            'stock2': stock2,
                            'entry_date': open_trade['entry_date'],
                            'exit_date': exit_date,
                            'entry_zscore': open_trade['entry_zscore'],
                            'exit_zscore': current_zscore,
                            'entry_price1': open_trade['entry_price1'],
                            'exit_price1': exit_price1,
                            'entry_price2': open_trade['entry_price2'],
                            'exit_price2': exit_price2,
                            'hedge_ratio': hedge_ratio,
                            'pnl': -1000
                        })
                        open_trade = None  # Close the trade
                        continue

                    if abs(current_zscore) < z_score_exit:
                        pnl += pnl_trade
                        trades.append({
                            'stock1': stock1,
                            'stock2': stock2,
                            'entry_date': open_trade['entry_date'],
                            'exit_date': exit_date,
                            'entry_zscore': open_trade['entry_zscore'],
                            'exit_zscore': current_zscore,
                            'entry_price1': open_trade['entry_price1'],
                            'exit_price1': exit_price1,
                            'entry_price2': open_trade['entry_price2'],
                            'exit_price2': exit_price2,
                            'hedge_ratio': hedge_ratio,
                            'pnl': pnl_trade
                        })
                        open_trade = None  # Close the trade
        
        return pd.DataFrame(trades), pnl

    def calculate_pnl(self, action, quantity1, quantity2, entry_price1, entry_price2, exit_price1, exit_price2):
        """Calculate PnL for a given trade."""
        if action == "short_long":
            pnl1 = (entry_price1 - exit_price1) * quantity1  # Short stock 1
            pnl2 = (exit_price2 - entry_price2) * quantity2  # Long stock 2
        else:  # "long_short"
            pnl1 = (exit_price1 - entry_price1) * quantity1  # Long stock 1
            pnl2 = (entry_price2 - exit_price2) * quantity2  # Short stock 2
        
        return pnl1 + pnl2

    def find_trading_opportunities(self, prices_df, pairs_df, z_score_threshold=1.0):
        opportunities = []
        
        for _, pair in pairs_df.iterrows():
            # More lenient cointegration threshold
            
            if pair['coint_pvalue'] < 0.01:  # Changed from 0.05 to 0.1
                print(pair['stock1'],pair['stock2'],pair['coint_pvalue'])
                metrics, z_score = self.calculate_pair_metrics(
                    prices_df, pair['stock1'], pair['stock2']
                )
                
                if metrics is None:
                    continue
                
                # More flexible z-score threshold with tiered signals
                z_score_current = abs(metrics['z_score_current'])
                if z_score_current > z_score_threshold:
                    momentum = self.calculate_momentum(
                        prices_df, pair['stock1'], pair['stock2']
                    )
                    
                    signal_strength = 'strong' if z_score_current > 2.0 else 'moderate'
                    
                    opportunities.append({
                        'stock1': pair['stock1'],
                        'stock2': pair['stock2'],
                        'z_score': metrics['z_score_current'],
                        'half_life': metrics['half_life'],
                        'correlation': pair['correlation'],
                        'momentum': momentum,
                        'signal_strength': signal_strength,
                        'action': 'short_long' if metrics['z_score_current'] > 0 else 'long_short',
                        'quality_score': pair['quality_score']
                    })

        print("opportunities",opportunities)
        
        return pd.DataFrame(opportunities)

    def calculate_half_life(self, spread):
        try:
            lag_spread = spread.shift(1)
            delta_spread = spread - lag_spread
            lag_spread = lag_spread[1:]
            delta_spread = delta_spread[1:]
            
            beta = np.polyfit(lag_spread, delta_spread, 1)[0]
            half_life = -np.log(2) / beta
            return half_life if half_life > 0 else np.inf
        except:
            return np.inf

    def calculate_momentum(self, prices_df, stock1, stock2, window=10):
        pair_df = prices_df[[stock1, stock2]].dropna()
        if len(pair_df) < window:
            return 0
            
        returns1 = pair_df[stock1].pct_change().rolling(window).mean().iloc[-1]
        returns2 = pair_df[stock2].pct_change().rolling(window).mean().iloc[-1]
        return returns1 - returns2

    def display_top_trades(self, trades_df):
        """Display the top 10 most profitable and the top 10 most loss trades."""
        if trades_df.empty:
            print("No trades to display.")
            return
        
        # Sort trades by PnL
        sorted_trades = trades_df.sort_values(by='pnl', ascending=False)
        
        # Top 10 most profitable trades
        print("Top 10 Most Profitable Trades:")
        print(sorted_trades.head(10))
        
        # Top 10 most loss trades
        print("\nTop 10 Most Loss Trades:")
        print(sorted_trades.tail(10))

def run_analysis():
    db_string = "postgresql://postgres:root@localhost:5432/Fin_data"
    analyzer = StatArbAnalyzer(db_string)
    last_date = analyzer.fetch_last_date()
    
    symbols = ["AXISBANK-EQ", "HDFCBANK-EQ", "ICICIBANK-EQ", "KOTAKBANK-EQ", "SBIN-EQ"]
    start_date = '2025-02-01'  # Adjusted to valid historical dates
    end_date = '2025-02-21'
    
    # Only fetch data once
    prices_df = analyzer.fetch_minute_data(symbols, start_date, end_date)
    if prices_df is None:
        print("Cannot proceed with analysis due to data fetching issues")
        return None, None, None
        
    current_time = datetime.now()
    cutoff_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    
    if current_time < cutoff_time:
        effective_date = current_time - timedelta(days=1)
    else:
        effective_date = current_time

    date_string = effective_date.date()
    print(f"Last date in DB: {last_date}, Current effective date: {date_string}")
    
    if str(last_date) != str(date_string):
        updateScrips(str(last_date), str(date_string))
    
    # Proceed with analysis only if we have valid data
    pairs_df = analyzer.analyze_correlations(prices_df)
    print(pairs_df)
    if pairs_df.empty:      
        print("No correlated pairs found")
        return prices_df, None, None
        
    trades, total_pnl = analyzer.back_test_pairs(prices_df, pairs_df, max_loss=1000)
    print(trades)
    opportunities = analyzer.find_trading_opportunities(prices_df, pairs_df)
    
    # Print results
    print("\nBacktesting Results:")
    print(f"Number of trades: {len(trades)}")
    print(f"Total PnL: {total_pnl:.2f}")
    
    # Display top trades
    analyzer.display_top_trades(trades)
    
    return prices_df, pairs_df, opportunities

# Run analysis
prices_df, pairs_df, opportunities = run_analysis()