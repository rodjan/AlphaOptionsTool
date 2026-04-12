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
    def get_option_chain(ticker, min_dte=0, max_dte=999):
        """Pulls option chain with pre-filtering to avoid unnecessary downloads."""
        tk = yf.Ticker(ticker)
        all_expirations = tk.options
        today = pd.Timestamp.today().normalize()
        
        # Filter expirations BEFORE downloading data
        valid_expirations = []
        for exp in all_expirations:
            dte = (pd.to_datetime(exp) - today).days
            if min_dte <= dte <= max_dte:
                valid_expirations.append(exp)
        
        chain_data = []
        try:
            hist = tk.history(period="1d")['Close']
            current_price = float(hist.iloc[-1]) if not hist.empty else 0.0
        except Exception:
            current_price = 0.0

        for exp in valid_expirations:
            opts = tk.option_chain(exp)
            
            # Process Puts
            puts = opts.puts.copy()
            puts['type'] = 'put'
            puts['ticker'] = ticker
            puts['expirationDate'] = exp
            puts['days_to_expiry'] = (pd.to_datetime(exp) - today).days
            if 'lastTradeDate' in puts.columns:
                puts['lastTradeDate'] = pd.to_datetime(puts['lastTradeDate'])
            
            # Process Calls
            calls = opts.calls.copy()
            calls['type'] = 'call'
            calls['ticker'] = ticker
            calls['expirationDate'] = exp
            calls['days_to_expiry'] = (pd.to_datetime(exp) - today).days
            if 'lastTradeDate' in calls.columns:
                calls['lastTradeDate'] = pd.to_datetime(calls['lastTradeDate'])
            
            chain_data.extend([puts, calls])
            
        if not chain_data:
            return pd.DataFrame(), current_price, "yfinance"
            
        df = pd.concat(chain_data, ignore_index=True)
        return df, current_price, "yfinance"