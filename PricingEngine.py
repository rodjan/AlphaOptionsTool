import numpy as np
from scipy.stats import norm

class BlackScholes:
    def __init__(self, risk_free_rate=0.04):
        self.r = risk_free_rate

    def _d1(self, S, K, T, sigma):
        return (np.log(S / K) + (self.r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    def _d2(self, d1, T, sigma):
        return d1 - sigma * np.sqrt(T)

    def price(self, S, K, T, sigma, option_type='put'):
        """Calculate the theoretical Black-Scholes price."""
        if T <= 0:
            return max(0.0, K - S) if option_type == 'put' else max(0.0, S - K)
        
        d1 = self._d1(S, K, T, sigma)
        d2 = self._d2(d1, T, sigma)
        
        if option_type == 'put':
            return K * np.exp(-self.r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            return S * norm.cdf(d1) - K * np.exp(-self.r * T) * norm.cdf(d2)

    def delta(self, S, K, T, sigma, option_type='put'):
        if T <= 0:
            return -1.0 if option_type == 'put' else 1.0
        d1 = self._d1(S, K, T, sigma)
        if option_type == 'put':
            return norm.cdf(d1) - 1
        else:
            return norm.cdf(d1)

    def calc_profit_at_target(self, current_cost, S_current, S_target, K, T_total_days, days_to_target, sigma, option_type='put'):
            """
            Calculates expected profit with a Volatility Kick (IV Expansion).
            """
            # 1. Calculate the percentage change in the underlying
            price_change_pct = (S_target - S_current) / S_current
            
            # 2. Apply Volatility Kick logic
            # Heuristic: If price drops, IV expands. If price rises, IV often contracts (for Puts).
            # A factor of 1.5 is a common "shock" multiplier for equity downside.
            # from 1.5 down to 1.1 or 1.2. This would simulate a "Vol Plateau" where the market is already so stressed that it can't get much more panicked.
            vol_stickiness = 1.2 
            
            # Only apply expansion on price drops for Puts (the 'Crash' scenario)
            if option_type == 'put' and price_change_pct < 0:
                # Formula: Adjusted Sigma = Original Sigma * (1 + |% Drop| * Stickiness)
                adjusted_sigma = sigma * (1 + abs(price_change_pct) * vol_stickiness)
            else:
                adjusted_sigma = sigma
                
            # Sanity Check: Cap the IV at 250% to prevent unrealistic mathematical outliers
            adjusted_sigma = min(adjusted_sigma, 2.5)

            T_future_years = max(0.0, (T_total_days - days_to_target) / 365.0)
            future_price = self.price(S_target, K, T_future_years, adjusted_sigma, option_type)
            
            return future_price - current_cost
