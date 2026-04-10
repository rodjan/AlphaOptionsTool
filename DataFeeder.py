import yfinance as yf
import pandas as pd
import numpy as np
# import requests  # Commented out with Polygon
# import os  # Commented out with Polygon

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
        # Polygon.io commented out - free tier doesn't include snapshot
        # api_key = os.getenv('POLYGON_API_KEY')
        # if api_key:
        #     try:
        #         url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={api_key}"
        #         response = requests.get(url)
        #         response.raise_for_status()
        #         data = response.json()
        #         
        #         if 'results' in data:
        #             current_price = data['results']['underlying']['price']
        #             chain_data = []
        #             
        #             for option in data['results']['options']:
        #                 opt_type = 'call' if option['contract_type'] == 'call' else 'put'
        #                 row = {
        #                     'strike': option['strike_price'],
        #                     'expirationDate': option['expiration_date'],
        #                     'type': opt_type,
        #                     'bid': option.get('bid', 0.0),
        #                     'ask': option.get('ask', 0.0),
        #                     'lastPrice': option.get('last_trade', {}).get('price', 0.0) if 'last_trade' in option else 0.0,
        #                     'volume': option.get('day', {}).get('volume', 0),
        #                     'impliedVolatility': option.get('implied_volatility', 0.0),
        #                     'lastTradeDate': pd.to_datetime(option.get('last_trade', {}).get('sip_timestamp', 0), unit='ns') if 'last_trade' in option else pd.NaT,
        #                     'openInterest': option.get('open_interest', 0)
        #                 }
        #                 chain_data.append(row)
        #             
        #             df = pd.DataFrame(chain_data)
        #             df['days_to_expiry'] = (pd.to_datetime(df['expirationDate']) - pd.Timestamp.today().normalize()).dt.days
        #             return df, current_price, "Polygon.io"
        #     except Exception as e:
        #         print(f"Polygon.io failed: {e}. Falling back to yfinance.")
        
        # Fallback to yfinance
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
            return pd.DataFrame(), current_price, "yfinance"
            
        df = pd.concat(chain_data, ignore_index=True)
        # Calculate Days to Expiration (DTE)
        df['days_to_expiry'] = (pd.to_datetime(df['expirationDate']) - pd.Timestamp.today().normalize()).dt.days
        
        return df, current_price, "yfinance"

    @staticmethod
    def load_from_excel(filepath):
        """Loads custom target prices or chains from an Excel file."""
        return pd.read_excel(filepath)
