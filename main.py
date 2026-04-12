import os
from DataFeeder import DataFeeder
from Optimizer import Optimizer
from PricingEngine import BlackScholes
import pandas as pd
from datetime import datetime

def get_target_price(value, current_price):
    if value < 1.0:
        return current_price * (1 - value)
    return value

def enrich_with_greeks(df, current_price):
    """Injects calculated Delta into the archive CSV."""
    if df.empty:
        return df
    
    bs = BlackScholes()
    df['delta'] = df.apply(lambda row: bs.delta(
        S=current_price, 
        K=row['strike'], 
        T=max(0.001, row['days_to_expiry']/365), 
        sigma=max(0.01, row['impliedVolatility']), 
        option_type=row['type']
    ), axis=1)
    return df

def run_analysis_scenario(s, df_chain, current_price, rv, opt):
    target_max = get_target_price(s['drop_max'], current_price)
    target_base = get_target_price(s['drop_base'], current_price)
    
    print(f"\n⚙️  ANALYZING: {s['ticker']}")
    print(f"Scenario: Shock in {s['days_to_event']} days | Targets: ${target_max:.2f} / ${target_base:.2f}")

    max_dte_limit = (pd.Timestamp(f"{pd.Timestamp.today().year}-12-31") - pd.Timestamp.today().normalize()).days
    
    results = opt.analyze_chain(
        df_chain, current_price, target_max, target_base, 
        s['days_to_event'], s['min_dte'], max_dte_limit, rv
    )
    
    if not results.empty:
        # Filter for display and saving (Puts only as per your standard logic)
        puts = results[results['type'] == 'put'].head(15).copy()
        if not puts.empty:
            puts['ticker'] = s['ticker'] # Tag for the setups CSV
            print("🏆 TOP PUT SETUPS:")
            columns_to_show = [
                'strike', 'expiry', 'DTE', 'last_trade', 'vol', 'cost', 
                'delta', 'IV', 'score', 'pl_base', 'pl_max', 'ROI_base', 
                'ROI_max', 'exp_roi', 'cheap_vol', 'category'
            ]
            print(puts[columns_to_show].to_string(index=False))
            return puts
    else:
        print("No valid contracts found matching the criteria.")
    
    return pd.DataFrame()

if __name__ == "__main__":
    strategies = [
        {"ticker": "VRT", "drop_max": 200, "drop_base": 250, "days_to_event": 60, "min_dte": 90},
        {"ticker": "STX", "drop_max": 300, "drop_base": 400, "days_to_event": 60, "min_dte": 100},
        {"ticker": "WDC", "drop_max": 170, "drop_base": 280, "days_to_event": 60, "min_dte": 100},
        {"ticker": "VRT", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100},
        {"ticker": "STX", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100},
        {"ticker": "WDC", "drop_max": 0.3, "drop_base": 0.15, "days_to_event": 60, "min_dte": 100}
    ]
    
    # 0. Setup Output Directory
    output_dir = "Output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    feeder = DataFeeder()
    opt = Optimizer()
    
    unique_tickers = {s['ticker'] for s in strategies}
    data_cache = {} 
    all_top_setups = []

    # 1. Fetch Unique Data
    print(f"🚀 INITIALIZING DATA FETCH...")
    for ticker in unique_tickers:
        relevant_s = [s for s in strategies if s['ticker'] == ticker]
        min_d = min(s['min_dte'] for s in relevant_s)
        max_d = (pd.Timestamp(f"{pd.Timestamp.today().year}-12-31") - pd.Timestamp.today().normalize()).days

        print(f"📥 Downloading: {ticker} (DTE > {min_d})...")
        df_raw, price, source = feeder.get_option_chain(ticker, min_d, max_d)
        rv = feeder.get_historical_volatility(ticker)
        
        df_enriched = enrich_with_greeks(df_raw, price)
        data_cache[ticker] = (df_enriched, price, rv)

    # 2. Run Analysis
    for s in strategies:
        df_chain, current_price, rv = data_cache[s['ticker']]
        if not df_chain.empty:
            setup_df = run_analysis_scenario(s, df_chain, current_price, rv, opt)
            if not setup_df.empty:
                all_top_setups.append(setup_df)

    # 3. Save Archives to Output folder
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Save Raw Chains
    if data_cache:
        final_raw = pd.concat([v[0] for v in data_cache.values()], ignore_index=True)
        raw_path = os.path.join(output_dir, f"chains_{timestamp}.csv")
        final_raw.to_csv(raw_path, index=False)
        print(f"\n💾 RAW ARCHIVE: {raw_path}")

    # Save Top Setups
    if all_top_setups:
        final_setups = pd.concat(all_top_setups, ignore_index=True)
        setups_path = os.path.join(output_dir, f"setups_{timestamp}.csv")
        final_setups.to_csv(setups_path, index=False)
        print(f"📊 SETUPS ARCHIVE: {setups_path}")