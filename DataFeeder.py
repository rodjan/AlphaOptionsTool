import yfinance as yf
import pandas as pd
import numpy as np

class DataFeeder:
    @staticmethod
    def get_historical_volatility(ticker, days=30):
        """Fetches Realized Volatility (RV) to compare against IV."""
        try:
            hist = yf.download(ticker, period="3mo", progress=False)['Close']
            if isinstance(hist, pd.DataFrame):
                hist = hist.squeeze()
            
            # Calculate daily logarithmic returns
            returns = np.log(hist / hist.shift(1))
            # Annualize standard deviation
            rv = returns.tail(days).std() * np.sqrt(252)
            return float(rv)
        except Exception:
            return 0.3 # Fallback

    @staticmethod
    def get_option_chain(ticker):
        """Pulls option chain and current price via yfinance."""
        tk = yf.Ticker(ticker)
        expirations = tk.options
        
        chain_data = []
        try:
            hist = tk.history(period="1d")['Close']
            current_price = float(hist.iloc[-1]) if not hist.empty else 0.0
        except Exception:
            current_price = 0.0

        for exp in expirations: # All expirations
            opts = tk.option_chain(exp)
            
            # Label & Append Puts
            puts = opts.puts.copy()
            puts['type'] = 'put'
            puts['expirationDate'] = exp
            if 'lastTradeDate' in puts.columns:
                puts['lastTradeDate'] = pd.to_datetime(puts['lastTradeDate'])
            
            # Label & Append Calls
            calls = opts.calls.copy()
            calls['type'] = 'call'
            calls['expirationDate'] = exp
            if 'lastTradeDate' in calls.columns:
                calls['lastTradeDate'] = pd.to_datetime(calls['lastTradeDate'])
            
            chain_data.extend([puts, calls])
            
        if not chain_data:
            return pd.DataFrame(), current_price
            
        df = pd.concat(chain_data, ignore_index=True)
        # Calculate Days to Expiration (DTE)
        df['days_to_expiry'] = (pd.to_datetime(df['expirationDate']) - pd.Timestamp.today().normalize()).dt.days
        
        return df, current_price

    @staticmethod
    def load_from_excel(filepath):
        """Loads custom target prices or chains from an Excel file."""
        return pd.read_excel(filepath)
