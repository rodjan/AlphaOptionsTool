import pandas as pd
from PricingEngine import BlackScholes
import numpy as np

class Optimizer:
    def __init__(self):
        self.pricer = BlackScholes()

    def analyze_chain(self, df_chain, current_price, target_price_max, target_price_base, days_to_event, min_dte, max_dte, rv=None):
        results = []
        
        # Define Commissions (Per share: $1.05 / 100 = 0.0105)
        # Total round trip (buy + sell) = 0.021
        COMMISSION_ROUND_TRIP = 0.021 
        
        now_utc = pd.Timestamp.utcnow()
        freshness_cutoff = now_utc - pd.Timedelta(hours=48)

        for _, row in df_chain.iterrows():
            try:
                K = row['strike']
                T_days = row['days_to_expiry']
                iv = row['impliedVolatility']
                opt_type = row['type']
                vol = row.get('volume', 0)
                last_trade_date = row.get('lastTradeDate', pd.NaT)

                # 1. Delta Calculation (Used for the pricing "slide")
                delta_val = self.pricer.delta(current_price, K, T_days/365, iv, opt_type)
                abs_delta = abs(delta_val)
                
                # Calculate Distance (Moneyness)
                # Negative means Out-of-the-Money (OTM) for Puts
                strike_dist_pct = (K - current_price) / current_price

                # 2. Market Cost Logic (Mid-to-Ask slide)
                bid = row.get('bid', 0.0)
                ask = row.get('ask', 0.0)
                last_price = row.get('lastPrice', 0.0)
                
                if bid > 0 and ask > 0:
                    mid = (bid + ask) / 2
                    # Penalty: Weight Mid by Delta, Ask by (1-Delta)
                    market_cost = (abs_delta * mid) + ((1 - abs_delta) * ask)
                elif ask > 0:
                    market_cost = ask
                else:
                    market_cost = last_price
                
                # 3. Apply Commissions (Round Trip)
                # We add it to the cost so that ROI calculations are based on total capital outflow
                cost = round(market_cost + COMMISSION_ROUND_TRIP, 3)
                
                # Check freshness
                traded_recently = False
                if pd.notna(last_trade_date):
                    if last_trade_date.tz is None:
                        last_trade_date = last_trade_date.tz_localize('UTC')
                    if last_trade_date >= freshness_cutoff:
                        traded_recently = True
                        
                # Get Open Interest as a backup for Volume
                #open_interest = row.get('openInterest', 0)
            
                if abs_delta < 0.12:
                    continue
                    
                #Hard Filter: Reality Check
                # If a put is more than 50% OTM, the math gets "noisy". 
                # Also, skip deeply ITM puts (dist > 10%) as they lack leverage.
                if strike_dist_pct < -0.50 or strike_dist_pct > 0.10:
                    continue
                    
                # Basic Filters (Note: minimum cost increased to 0.10 + commission)
                if not traded_recently or pd.isna(vol) or vol <= 0 or T_days < min_dte or T_days > max_dte or cost <= 0.12 or iv < 0.01:
                #if iv < 0.01:
                    continue
                    
                # 4. Profitability at Targets (Calculated net of commissions)
                profit_base = self.pricer.calc_profit_at_target(
                    current_cost=cost,
                    S_current=current_price,
                    S_target=target_price_base,
                    K=K,
                    T_total_days=T_days,
                    days_to_target=days_to_event,
                    sigma=iv,
                    option_type=opt_type
                )
                
                profit_max = self.pricer.calc_profit_at_target(
                    current_cost=cost,
                    S_current=current_price,
                    S_target=target_price_max,
                    K=K,
                    T_total_days=T_days,
                    days_to_target=days_to_event,
                    sigma=iv,
                    option_type=opt_type
                )
                
                # 5. Metrics & Ranking
                roi_max = profit_max / cost if cost > 0 else 0
                roi_base = profit_base / cost if cost > 0 else -1
                
                # Penalty for low delta (Square root for non-linear weighting)
                delta_weight = np.sqrt(abs_delta + 0.1)
                
                is_cheap_vol = (iv < rv) if rv else False
                
                # Define your custom probability weights
                P_FAIL, R_FAIL = 0.30, -0.90
                P_BASE = 0.40
                P_TARGET = 0.30

                # Calculate Expected ROI (The 'Edge')
                expected_roi = round((P_FAIL * R_FAIL) + (P_BASE * roi_base) + (P_TARGET * roi_max), 3)
                
                # Category Logic
                if expected_roi > 0.30 and is_cheap_vol:
                    cat = "🔥 FAT PITCH"
                elif strike_dist_pct < -0.25 and roi_max > 2.0:
                    cat = "🎰 LOTTO" # Far OTM but high payout
                elif expected_roi > 0.15 and is_cheap_vol:
                    cat = "💎 VALUE EDGE"
                elif strike_dist_pct > -0.05:
                    cat = "🛡️ INSURANCE" # Near-the-money, high probability
                else:
                    cat = "⚖️ NEUTRAL"
                
                # The final Scenario Score
                scenario_score = roi_max * (1 + roi_base) * delta_weight

                results.append({
                    'strike': K,
                    'type': opt_type,
                    'expiry': row['expirationDate'],
                    'DTE': T_days,
                    'vol': int(vol),
                    'last_trade': last_trade_date.strftime('%Y-%m-%d'),
                    'cost': round(cost, 2), # Rounded for cleaner UI
                    'delta': round(delta_val, 2),
                    'IV': iv,
                    'scenario_score': round(scenario_score, 3),
                    'profit_base': profit_base,
                    'profit_max': profit_max,
                    'ROI_base': roi_base,
                    'ROI_max': roi_max,
                    'expected_roi': expected_roi,
                    'cheap_vol_flag': is_cheap_vol
                    ,'category': cat
                })
            except Exception:
                continue
                
        res_df = pd.DataFrame(results)
        if not res_df.empty:
            # Sort by Scenario Score
            res_df = res_df.sort_values(by='scenario_score', ascending=False)
            
            # Final Formatting
            res_df['IV'] = (res_df['IV'] * 100).round(1).astype(str) + '%'
            res_df['profit_base'] = res_df['profit_base'].round(2)
            res_df['profit_max'] = res_df['profit_max'].round(2)
            res_df['ROI_base'] = (res_df['ROI_base'] * 100).round(1).astype(str) + '%'
            res_df['ROI_max'] = (res_df['ROI_max'] * 100).round(1).astype(str) + '%'
            res_df['expected_roi'] = (res_df['expected_roi'] * 100).round(1).astype(str) + '%'
            
        return res_df
