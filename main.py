from DataFeeder import DataFeeder
from Optimizer import Optimizer
import pandas as pd

def get_target_price(value, current_price):
    """
    If value < 1.0, treats it as a percentage drop (e.g., 0.30 = 30% drop).
    If value >= 1.0, treats it as a specific target price.
    """
    if value < 1.0:
        return current_price * (1 - value)
    return value

def run_analysis(ticker, drop_max, drop_base, days_to_event, min_dte):
    print(f"\n{'='*60}")
    print(f"⚙️  ANALYZING: {ticker}")
    print(f"{'='*60}")
    
    feeder = DataFeeder()
    opt = Optimizer()
    
    # 1. Get Live Data
    print(f"Fetching options chain and historical data...")
    df_chain, current_price, data_source = feeder.get_option_chain(ticker)
    rv = feeder.get_historical_volatility(ticker)
    
    if df_chain.empty or current_price == 0.0:
        print("Failed to fetch data or option chain is empty.")
        return

    print(f"Current Price: ${current_price:.2f} | 30-Day Realized Volatility: {rv:.1%} | Data Source: {data_source}")
    
    # Calculate max DTE (End of current calendar year)
    end_of_year = pd.Timestamp(f"{pd.Timestamp.today().year}-12-31")
    max_dte = (end_of_year - pd.Timestamp.today().normalize()).days

    # 2. Define Scenario   
    target_price_max = get_target_price(drop_max, current_price)
    target_price_base = get_target_price(drop_base, current_price)
    
    # Calculate effective percentage for display
    effective_max_pct = (current_price - target_price_max) / current_price
    effective_base_pct = (current_price - target_price_base) / current_price
 
    print(f"Scenario: Shock happens in {days_to_event} days. (Buying options with {min_dte} to {max_dte} DTE)")
    print(f"-> Max Target: ${target_price_max:.2f} (-{effective_max_pct:.1%})")
    print(f"-> Base Target: ${target_price_base:.2f} (-{effective_base_pct:.1%})")
    print("Filter: Only contracts with Volume > 0 and Expiring this year.\n")
    
    # 3. Optimize & Sort
    results = opt.analyze_chain(df_chain, current_price, target_price_max, target_price_base, days_to_event, min_dte, max_dte, rv)
    
    # 4. Display best setups
    if not results.empty:
        puts = results[results['type'] == 'put'].head(15)
        if not puts.empty:
            # Updated the column list here to match the new Optimizer output
            print("🏆 TOP PUT SETUPS (Ranked by Scenario Score: ROI adjusted for Base safety):")
            columns_to_show = [
                'strike', 'expiry', 'DTE', 'last_trade', 'vol', 'cost', 
                'delta', 'IV', 'score', 'pl_base', 'pl_max', 'ROI_base', 'ROI_max', 'exp_roi', 'cheap_vol', 'category'
            ]
            print(puts[columns_to_show].to_string(index=False))
        else:
            print("No PUT contracts found matching the criteria.")
    else:
        print("No valid contracts found matching the criteria.")

if __name__ == "__main__":
    # Define a custom dictionary of strategies per ticker
    # You can specify exact drawdown parameters and time horizons per stock
    strategies = [
        {"ticker": "VRT", "drop_max": 200, "drop_base": 250, "days_to_event": 60, "min_dte": 100}
        ,{"ticker": "STX", "drop_max": 300, "drop_base": 400, "days_to_event": 60, "min_dte": 100}
        ,{"ticker": "WDC", "drop_max": 170, "drop_base": 280, "days_to_event": 60, "min_dte": 100}
        ,{"ticker": "VRT", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100}
        ,{"ticker": "STX", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100}
        ,{"ticker": "WDC", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100}        
        #,{"ticker": "DAL", "drop_max": 0.30, "drop_base": 0.15, "days_to_event": 60, "min_dte": 90}
    ]
    
    for s in strategies:
        run_analysis(
            ticker=s["ticker"],
            drop_max=s["drop_max"],
            drop_base=s["drop_base"],
            days_to_event=s["days_to_event"],
            min_dte=s["min_dte"]
        )
