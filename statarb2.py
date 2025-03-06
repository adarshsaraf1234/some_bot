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
            result = pd.read_sql_query(query, self.engine)
            if result.empty:
                print("The database is empty. No data found.")
                return None
            
            last_date = result['timestamp'].iloc[0]
            formatted_date = pd.to_datetime(last_date).strftime('%Y-%m-%d')
            print(f"Last date fetched from DB: {formatted_date}")
            return formatted_date
        
        except Exception as e:
            print(f"Error fetching last date: {e}")
            return None

    def fetch_minute_data(self, symbols, start_date, end_date):
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
                
            actual_start = trading_days['trading_date'].min()
            actual_end = trading_days['trading_date'].max()
            
            print(f"Available trading days: {actual_start} to {actual_end}")
            
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
            df = df[~df['timestamp'].dt.dayofweek.isin([5, 6])]
            
            pivot_df = df.pivot_table(
                index='timestamp', 
                columns='stock_symbol', 
                values='close_price'
            )
            
            pivot_df = pivot_df.ffill()
            
            missing_data = pivot_df.isnull().sum()
            if missing_data.any():
                print("Warning: Missing data detected after filling:")
                print(missing_data[missing_data > 0])
                
            return pivot_df
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def analyze_correlations(self, prices_df):
        window = 200
        pairs = []
        symbols = prices_df.columns
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                stock1 = symbols[i]
                stock2 = symbols[j]
                
                pair_df = prices_df[[stock1, stock2]].copy()
                pair_df = pair_df.dropna()
                
                if len(pair_df) < window:
                    continue
                
                rolling_corr = pair_df[stock1].rolling(window=window).corr(pair_df[stock2])
                current_corr = rolling_corr.iloc[-1]
                
                vol1 = pair_df[stock1].pct_change().rolling(window).std()
                vol2 = pair_df[stock2].pct_change().rolling(window).std()
                vol_ratio = (vol1 / vol2).iloc[-1]
                
                if current_corr > 0.7:
                    _, pvalue, _ = coint(pair_df[stock1], pair_df[stock2])
                    
                    correlation_stability = rolling_corr.std()
                    price_ratio = (pair_df[stock1] / pair_df[stock2]).std()
                    
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
        
        if not pairs_df.empty:
            max_half_life = pairs_df['half_life'].max()
            normalized_half_life = 1 - (pairs_df['half_life'] / max_half_life)
            
            pairs_df['quality_score'] = (
                pairs_df['correlation'] * 0.25 +
                (1 - pairs_df['correlation_stability']) * 0.20 +
                (1 - pairs_df['coint_pvalue']) * 0.25 +
                (1 - abs(1 - pairs_df['volatility_ratio'])) * 0.15 +
                normalized_half_life * 0.15
            )
            
            pairs_df = pairs_df.sort_values('quality_score', ascending=False)
        
        return pairs_df

    def analyze_pair_trading_opportunities(self, prices_df, pairs_df, z_score_entry=1.0, z_score_exit=0.8, max_loss_pct=1):
        all_trades = []
        current_opportunities = []
        
        for _, pair in pairs_df.iterrows():
            stock1 = pair['stock1']
            stock2 = pair['stock2']
            
            if pair['coint_pvalue'] >= 0.05:
                continue
                
            pair_df = prices_df[[stock1, stock2]].copy().dropna()
            if len(pair_df) < 200:
                continue
                
            metrics, z_score = self.calculate_pair_metrics(prices_df, stock1, stock2)
            if metrics is None or z_score is None:
                continue
                
            hedge_ratio = metrics['ratio_mean']
            current_zscore = metrics['z_score_current']
            
            if abs(current_zscore) > z_score_entry:
                opportunity = {
                    'stock1': stock1,
                    'stock2': stock2,
                    'z_score': current_zscore,
                    'hedge_ratio': hedge_ratio,
                    'action': 'short_long' if current_zscore > 0 else 'long_short',
                    'signal_strength': 'strong' if abs(current_zscore) > 2.0 else 'moderate',
                    'correlation': pair['correlation'],
                    'quality_score': pair['quality_score'],
                    'timestamp': prices_df.index[-1]
                }
                current_opportunities.append(opportunity)
            
            position = None
            for i in range(200, len(pair_df)):
                current_z = z_score.iloc[i]
                prices1 = pair_df[stock1].iloc[i]
                prices2 = pair_df[stock2].iloc[i]
                
                if position is None and abs(current_z) > z_score_entry:
                    position = {
                        'stock1': stock1,
                        'stock2': stock2,
                        'entry_date': pair_df.index[i],
                        'entry_price1': prices1,
                        'entry_price2': prices2,
                        'hedge_ratio': hedge_ratio,
                        'action': 'short_long' if current_z > 0 else 'long_short',
                        'entry_zscore': current_z,
                        'quantity1': 100
                    }
                    position['quantity2'] = int(position['quantity1'] * hedge_ratio)
                    continue
                
                if position is not None:
                    if position['action'] == 'short_long':
                        pnl = (position['entry_price1'] - prices1) * position['quantity1'] + \
                              (prices2 - position['entry_price2']) * position['quantity2']
                    else:
                        pnl = (prices1 - position['entry_price1']) * position['quantity1'] + \
                              (position['entry_price2'] - prices2) * position['quantity2']
                    
                    position_value = (position['entry_price1'] * position['quantity1'] + 
                                    position['entry_price2'] * position['quantity2'])
                    
                    exit_reason = None
                    if abs(current_z) < z_score_exit:
                        exit_reason = 'target'
                    elif pnl < -position_value * max_loss_pct:
                        exit_reason = 'stop_loss'
                    
                    if exit_reason:
                        trade = {
                            **position,
                            'exit_date': pair_df.index[i],
                            'exit_price1': prices1,
                            'exit_price2': prices2,
                            'exit_zscore': current_z,
                            'pnl': pnl,
                            'exit_reason': exit_reason,
                            'trade_duration': (pair_df.index[i] - position['entry_date']).total_seconds() / 3600
                        }
                        all_trades.append(trade)
                        position = None
            
        opportunities_df = pd.DataFrame(current_opportunities)
        trades_df = pd.DataFrame(all_trades)
        
        performance_metrics = {}
        if not trades_df.empty:
            performance_metrics = {
                'total_trades': len(trades_df),
                'profitable_trades': len(trades_df[trades_df['pnl'] > 0]),
                'total_pnl': trades_df['pnl'].sum(),
                'win_rate': len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100,
                'avg_trade_duration': trades_df['trade_duration'].mean(),
                'sharpe_ratio': trades_df['pnl'].mean() / trades_df['pnl'].std() if trades_df['pnl'].std() != 0 else 0,
                'max_drawdown': self.calculate_max_drawdown(trades_df['pnl'].cumsum())
            }
        
        return opportunities_df, trades_df, performance_metrics

    def calculate_pair_metrics(self, prices_df, stock1, stock2):
        window = 200
        
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

    def calculate_max_drawdown(self, cumulative_pnl):
        rolling_max = cumulative_pnl.expanding().max()
        drawdowns = cumulative_pnl - rolling_max
        return abs(drawdowns.min()) if len(drawdowns) > 0 else 0

    def plot_pair_analysis(self, prices_df, stock1, stock2, z_score=None):
        if z_score is None:
            _, z_score = self.calculate_pair_metrics(prices_df, stock1, stock2)
            
        if z_score is None:
            return
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        
        ratio = prices_df[stock1] / prices_df[stock2]
        ax1.plot(ratio.index, ratio.values, label='Price Ratio', color='blue')
        ax1.set_title(f'Price Ratio: {stock1} / {stock2}')
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(z_score.index, z_score.values, label='Z-score', color='green')
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax2.axhline(y=1.5, color='red', linestyle='--', alpha=0.5, label='Entry (±1.5σ)')
        ax2.axhline(y=-1.5, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(y=0.5, color='green', linestyle='--', alpha=0.5, label='Exit (±0.5σ)')
        ax2.axhline(y=-0.5, color='green', linestyle='--', alpha=0.5)
        
        ax2.set_title('Z-score Evolution')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.show()

def run_analysis():
    db_string = "postgresql://postgres:root@localhost:5432/Fin_data"
    analyzer = StatArbAnalyzer(db_string)
    last_date = analyzer.fetch_last_date()
    
    symbols = ["AXISBANK-EQ", "HDFCBANK-EQ", "ICICIBANK-EQ", "KOTAKBANK-EQ", "SBIN-EQ"]
    start_date = '2025-01-20'
    end_date = '2025-02-22'
    
    prices_df = analyzer.fetch_minute_data(symbols, start_date, end_date)
    if prices_df is None:
        print("Cannot proceed with analysis due to data fetching issues")
        return None, None, None, None
        
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
    
    pairs_df = analyzer.analyze_correlations(prices_df)
    if pairs_df.empty:
        print("No correlated pairs found")
        return prices_df, None, None, None
    
    opportunities_df, trades_df, performance_metrics = analyzer.analyze_pair_trading_opportunities(
        prices_df, 
        pairs_df,
        z_score_entry=1.0,
        z_score_exit=0.9,
        max_loss_pct=1
    )
    
    print("\nAnalysis Results:")
    print("\nCorrelated Pairs:")
    print(pairs_df[['stock1', 'stock2', 'correlation', 'coint_pvalue', 'quality_score']])
    
    print("\nPerformance Metrics:")
    for metric, value in performance_metrics.items():
        print(f"{metric}: {value:.2f}" if isinstance(value, float) else f"{metric}: {value}")
    
    if not opportunities_df.empty:
        print("\nCurrent Trading Opportunities:")
        print(opportunities_df[['stock1', 'stock2', 'z_score', 'action', 'signal_strength']])
    
    # Plot analysis for the highest quality pair if available
    if not pairs_df.empty:
        best_pair = pairs_df.iloc[0]
        analyzer.plot_pair_analysis(prices_df, best_pair['stock1'], best_pair['stock2'])
    
    return prices_df, pairs_df, opportunities_df, trades_df, performance_metrics

if __name__ == "__main__":
    prices_df, pairs_df, opportunities_df, trades_df, performance_metrics = run_analysis()