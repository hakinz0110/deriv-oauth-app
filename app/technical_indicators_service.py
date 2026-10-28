"""
Technical Indicators Service
Calculates trading indicators using pandas-ta library
"""
import pandas as pd
import pandas_ta as ta
from typing import List, Dict, Any, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicatorsService:
    """Service for calculating technical indicators from price data"""
    
    @staticmethod
    def prepare_dataframe(ticks: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert tick/candle data to pandas DataFrame
        
        Args:
            ticks: List of tick/candle dictionaries with 'epoch', 'quote'/'close', 'high', 'low', 'open'
        
        Returns:
            pandas DataFrame with OHLCV data
        """
        if not ticks:
            raise ValueError("No tick data provided")
        
        # Check if we have candle data (OHLC) or just ticks
        has_ohlc = 'open' in ticks[0] and 'high' in ticks[0] and 'low' in ticks[0] and 'close' in ticks[0]
        
        if has_ohlc:
            df = pd.DataFrame(ticks)
            df = df.rename(columns={
                'epoch': 'time',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close'
            })
        else:
            # Convert ticks to OHLC format (each tick becomes its own candle)
            df = pd.DataFrame(ticks)
            df = df.rename(columns={'epoch': 'time', 'quote': 'close'})
            df['open'] = df['close']
            df['high'] = df['close']
            df['low'] = df['close']
        
        # Ensure numeric types
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        
        # Sort by time
        df = df.sort_values('time')
        df = df.reset_index(drop=True)
        
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            df: DataFrame with 'close' column
            period: RSI period (default: 14)
        
        Returns:
            pandas Series with RSI values
        """
        return ta.rsi(df['close'], length=period)
    
    @staticmethod
    def calculate_macd(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> pd.DataFrame:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            df: DataFrame with 'close' column
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)
        
        Returns:
            DataFrame with MACD, signal, and histogram columns
        """
        macd_df = ta.macd(df['close'], fast=fast, slow=slow, signal=signal)
        return macd_df
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA)
        
        Args:
            df: DataFrame with 'close' column
            period: EMA period (default: 20)
        
        Returns:
            pandas Series with EMA values
        """
        return ta.ema(df['close'], length=period)
    
    @staticmethod
    def calculate_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calculate Simple Moving Average (SMA)
        
        Args:
            df: DataFrame with 'close' column
            period: SMA period (default: 20)
        
        Returns:
            pandas Series with SMA values
        """
        return ta.sma(df['close'], length=period)
    
    @staticmethod
    def calculate_bollinger_bands(
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands
        
        Args:
            df: DataFrame with 'close' column
            period: Period for moving average (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
        
        Returns:
            DataFrame with lower, middle, upper bands
        """
        bb_df = ta.bbands(df['close'], length=period, std=std_dev)
        return bb_df
    
    @staticmethod
    def evaluate_rsi_condition(
        df: pd.DataFrame,
        period: int,
        condition: str,
        value: float
    ) -> bool:
        """
        Evaluate RSI condition
        
        Args:
            df: Price data DataFrame
            period: RSI period
            condition: 'above', 'below', 'crosses_above', 'crosses_below'
            value: Threshold value (e.g., 30 for oversold, 70 for overbought)
        
        Returns:
            True if condition is met
        """
        rsi = TechnicalIndicatorsService.calculate_rsi(df, period)
        
        if rsi is None or len(rsi) < 2:
            return False
        
        current_rsi = rsi.iloc[-1]
        previous_rsi = rsi.iloc[-2] if len(rsi) >= 2 else None
        
        if pd.isna(current_rsi):
            return False
        
        if condition == 'below':
            return current_rsi < value
        elif condition == 'above':
            return current_rsi > value
        elif condition == 'crosses_above' and previous_rsi is not None:
            return previous_rsi <= value and current_rsi > value
        elif condition == 'crosses_below' and previous_rsi is not None:
            return previous_rsi >= value and current_rsi < value
        
        return False
    
    @staticmethod
    def evaluate_macd_condition(
        df: pd.DataFrame,
        fast: int,
        slow: int,
        signal: int,
        condition: str
    ) -> bool:
        """
        Evaluate MACD condition
        
        Args:
            df: Price data DataFrame
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            condition: 'bullish_cross', 'bearish_cross', 'macd_above_signal', 'macd_below_signal'
        
        Returns:
            True if condition is met
        """
        macd_df = TechnicalIndicatorsService.calculate_macd(df, fast, slow, signal)
        
        if macd_df is None or len(macd_df) < 2:
            return False
        
        # Get column names (pandas-ta uses specific naming)
        macd_col = f'MACD_{fast}_{slow}_{signal}'
        signal_col = f'MACDs_{fast}_{slow}_{signal}'
        
        if macd_col not in macd_df.columns or signal_col not in macd_df.columns:
            return False
        
        current_macd = macd_df[macd_col].iloc[-1]
        current_signal = macd_df[signal_col].iloc[-1]
        previous_macd = macd_df[macd_col].iloc[-2] if len(macd_df) >= 2 else None
        previous_signal = macd_df[signal_col].iloc[-2] if len(macd_df) >= 2 else None
        
        if pd.isna(current_macd) or pd.isna(current_signal):
            return False
        
        if condition == 'bullish_cross' and previous_macd is not None and previous_signal is not None:
            return previous_macd <= previous_signal and current_macd > current_signal
        elif condition == 'bearish_cross' and previous_macd is not None and previous_signal is not None:
            return previous_macd >= previous_signal and current_macd < current_signal
        elif condition == 'macd_above_signal':
            return current_macd > current_signal
        elif condition == 'macd_below_signal':
            return current_macd < current_signal
        
        return False
    
    @staticmethod
    def evaluate_ema_cross_condition(
        df: pd.DataFrame,
        fast_period: int,
        slow_period: int,
        condition: str
    ) -> bool:
        """
        Evaluate EMA crossover condition
        
        Args:
            df: Price data DataFrame
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            condition: 'fast_above_slow', 'fast_below_slow', 'bullish_cross', 'bearish_cross'
        
        Returns:
            True if condition is met
        """
        fast_ema = TechnicalIndicatorsService.calculate_ema(df, fast_period)
        slow_ema = TechnicalIndicatorsService.calculate_ema(df, slow_period)
        
        if fast_ema is None or slow_ema is None or len(fast_ema) < 2 or len(slow_ema) < 2:
            return False
        
        current_fast = fast_ema.iloc[-1]
        current_slow = slow_ema.iloc[-1]
        previous_fast = fast_ema.iloc[-2]
        previous_slow = slow_ema.iloc[-2]
        
        if pd.isna(current_fast) or pd.isna(current_slow):
            return False
        
        if condition == 'fast_above_slow':
            return current_fast > current_slow
        elif condition == 'fast_below_slow':
            return current_fast < current_slow
        elif condition == 'bullish_cross':
            return previous_fast <= previous_slow and current_fast > current_slow
        elif condition == 'bearish_cross':
            return previous_fast >= previous_slow and current_fast < current_slow
        
        return False
    
    @staticmethod
    def evaluate_bb_condition(
        df: pd.DataFrame,
        period: int,
        std_dev: float,
        condition: str
    ) -> bool:
        """
        Evaluate Bollinger Bands condition
        
        Args:
            df: Price data DataFrame
            period: BB period
            std_dev: Standard deviation multiplier
            condition: 'below_lower_band', 'above_upper_band', 'crosses_below_lower', 'crosses_above_upper'
        
        Returns:
            True if condition is met
        """
        bb_df = TechnicalIndicatorsService.calculate_bollinger_bands(df, period, std_dev)
        
        if bb_df is None or len(bb_df) < 2:
            return False
        
        # Get column names
        lower_col = f'BBL_{period}_{std_dev}'
        upper_col = f'BBU_{period}_{std_dev}'
        
        if lower_col not in bb_df.columns or upper_col not in bb_df.columns:
            return False
        
        current_price = df['close'].iloc[-1]
        previous_price = df['close'].iloc[-2] if len(df) >= 2 else None
        current_lower = bb_df[lower_col].iloc[-1]
        current_upper = bb_df[upper_col].iloc[-1]
        previous_lower = bb_df[lower_col].iloc[-2] if len(bb_df) >= 2 else None
        previous_upper = bb_df[upper_col].iloc[-2] if len(bb_df) >= 2 else None
        
        if pd.isna(current_lower) or pd.isna(current_upper):
            return False
        
        if condition == 'below_lower_band':
            return current_price < current_lower
        elif condition == 'above_upper_band':
            return current_price > current_upper
        elif condition == 'crosses_below_lower' and previous_price is not None and previous_lower is not None:
            return previous_price >= previous_lower and current_price < current_lower
        elif condition == 'crosses_above_upper' and previous_price is not None and previous_upper is not None:
            return previous_price <= previous_upper and current_price > current_upper
        
        return False
    
    @staticmethod
    def evaluate_sma_condition(
        df: pd.DataFrame,
        period: int,
        condition: str
    ) -> bool:
        """
        Evaluate SMA condition
        
        Args:
            df: Price data DataFrame
            period: SMA period
            condition: 'price_above_sma', 'price_below_sma', 'price_crosses_above', 'price_crosses_below'
        
        Returns:
            True if condition is met
        """
        sma = TechnicalIndicatorsService.calculate_sma(df, period)
        
        if sma is None or len(sma) < 2:
            return False
        
        current_price = df['close'].iloc[-1]
        previous_price = df['close'].iloc[-2] if len(df) >= 2 else None
        current_sma = sma.iloc[-1]
        previous_sma = sma.iloc[-2] if len(sma) >= 2 else None
        
        if pd.isna(current_sma):
            return False
        
        if condition == 'price_above_sma':
            return current_price > current_sma
        elif condition == 'price_below_sma':
            return current_price < current_sma
        elif condition == 'price_crosses_above' and previous_price is not None and previous_sma is not None:
            return previous_price <= previous_sma and current_price > current_sma
        elif condition == 'price_crosses_below' and previous_price is not None and previous_sma is not None:
            return previous_price >= previous_sma and current_price < current_sma
        
        return False
    
    @staticmethod
    def get_current_values(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get current values for all common indicators
        
        Returns:
            Dictionary with current indicator values
        """
        if df is None or len(df) == 0:
            return {}
        
        current_price = float(df['close'].iloc[-1])
        
        result = {
            'price': current_price,
            'rsi_14': None,
            'macd': {},
            'ema_20': None,
            'ema_50': None,
            'sma_20': None,
            'bb': {}
        }
        
        try:
            rsi = TechnicalIndicatorsService.calculate_rsi(df, 14)
            if rsi is not None and not pd.isna(rsi.iloc[-1]):
                result['rsi_14'] = float(rsi.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
        
        try:
            macd_df = TechnicalIndicatorsService.calculate_macd(df)
            if macd_df is not None:
                macd_col = 'MACD_12_26_9'
                signal_col = 'MACDs_12_26_9'
                hist_col = 'MACDh_12_26_9'
                if macd_col in macd_df.columns:
                    result['macd'] = {
                        'macd': float(macd_df[macd_col].iloc[-1]) if not pd.isna(macd_df[macd_col].iloc[-1]) else None,
                        'signal': float(macd_df[signal_col].iloc[-1]) if signal_col in macd_df.columns and not pd.isna(macd_df[signal_col].iloc[-1]) else None,
                        'histogram': float(macd_df[hist_col].iloc[-1]) if hist_col in macd_df.columns and not pd.isna(macd_df[hist_col].iloc[-1]) else None
                    }
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
        
        try:
            ema_20 = TechnicalIndicatorsService.calculate_ema(df, 20)
            if ema_20 is not None and not pd.isna(ema_20.iloc[-1]):
                result['ema_20'] = float(ema_20.iloc[-1])
            
            ema_50 = TechnicalIndicatorsService.calculate_ema(df, 50)
            if ema_50 is not None and not pd.isna(ema_50.iloc[-1]):
                result['ema_50'] = float(ema_50.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
        
        try:
            sma_20 = TechnicalIndicatorsService.calculate_sma(df, 20)
            if sma_20 is not None and not pd.isna(sma_20.iloc[-1]):
                result['sma_20'] = float(sma_20.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
        
        try:
            bb_df = TechnicalIndicatorsService.calculate_bollinger_bands(df, 20, 2.0)
            if bb_df is not None:
                lower_col = 'BBL_20_2.0'
                middle_col = 'BBM_20_2.0'
                upper_col = 'BBU_20_2.0'
                if lower_col in bb_df.columns:
                    result['bb'] = {
                        'lower': float(bb_df[lower_col].iloc[-1]) if not pd.isna(bb_df[lower_col].iloc[-1]) else None,
                        'middle': float(bb_df[middle_col].iloc[-1]) if middle_col in bb_df.columns and not pd.isna(bb_df[middle_col].iloc[-1]) else None,
                        'upper': float(bb_df[upper_col].iloc[-1]) if upper_col in bb_df.columns and not pd.isna(bb_df[upper_col].iloc[-1]) else None
                    }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
        
        return result
