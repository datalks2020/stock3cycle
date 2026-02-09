"""
技术指标模块 - 基于陈凯三周期标准
包含分型识别、均线计算等
"""
import numpy as np
import pandas as pd
from typing import List, Tuple

# ==================== 基础指标计算 ====================
def calc_ma(series: pd.Series, window: int) -> pd.Series:
    """计算移动平均线"""
    return series.rolling(window=window).mean()


def calc_macd(df: pd.DataFrame, close_col: str = 'close') -> pd.DataFrame:
    """计算MACD指标"""
    exp1 = df[close_col].ewm(span=12, adjust=False).mean()
    exp2 = df[close_col].ewm(span=26, adjust=False).mean()
    df['dif'] = exp1 - exp2
    df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
    df['macd'] = (df['dif'] - df['dea']) * 2
    return df


def calc_amplitude(df: pd.DataFrame) -> pd.Series:
    """计算振幅"""
    amplitude = (df['high'] - df['low']) / df['close'].shift(1)
    return amplitude.fillna(0)

# ==================== 分型识别(缠论风格) ====================
def identify_top_fractal(df: pd.DataFrame, window: int = 3) -> pd.Series:
    """
    识别顶分型(高点)
    
    定义: 中间K线的高点是前后K线高点中的最高点
    标准3K线分型: high[i] > high[i-1] and high[i] > high[i+1]
    
    Args:
        df: DataFrame包含high列
        window: 分型窗口大小(默认3)
    
    Returns:
        Series: 1表示顶分型,0表示非顶分型
    """
    top_fractal = pd.Series(0, index=df.index)
    
    if len(df) < window:
        return top_fractal
    
    highs = df['high'].values
    
    for i in range(1, len(df) - 1):
        # 标准顶分型: 中间K线高点最高
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            top_fractal.iloc[i] = 1
    
    return top_fractal


def identify_bottom_fractal(df: pd.DataFrame, window: int = 3) -> pd.Series:
    """
    识别底分型(低点)
    
    定义: 中间K线的低点是前后K线低点中的最低点
    标准3K线分型: low[i] < low[i-1] and low[i] < low[i+1]
    
    Args:
        df: DataFrame包含low列
        window: 分型窗口大小(默认3)
    
    Returns:
        Series: 1表示底分型,0表示非底分型
    """
    bottom_fractal = pd.Series(0, index=df.index)
    
    if len(df) < window:
        return bottom_fractal
    
    lows = df['low'].values
    
    for i in range(1, len(df) - 1):
        # 标准底分型: 中间K线低点最低
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            bottom_fractal.iloc[i] = 1
    
    return bottom_fractal


def get_peaks_and_troughs(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    获取所有的高点和低点
    
    Args:
        df: DataFrame包含high, low列
    
    Returns:
        (peaks_df, troughs_df): 高点和低点的DataFrame
    """
    # 识别分型
    df['is_top'] = identify_top_fractal(df)
    df['is_bottom'] = identify_bottom_fractal(df)
    
    # 提取高点
    peaks = df[df['is_top'] == 1][['high']].copy()
    peaks.rename(columns={'high': 'price'}, inplace=True)
    
    # 提取低点
    troughs = df[df['is_bottom'] == 1][['low']].copy()
    troughs.rename(columns={'low': 'price'}, inplace=True)
    
    return peaks, troughs


def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    将日线数据重采样为周线数据
    
    规则:
    - 每周最后一个交易日的收盘价作为周收盘价
    - 周最高价 = max(日最高价)
    - 周最低价 = min(日最低价)  
    - 周成交量 = sum(日成交量)
    
    Args:
        df_daily: 日线数据,需包含trade_date作为索引
    
    Returns:
        DataFrame: 周线数据
    """
    df = df_daily.copy()
    
    # 确保有trade_date列
    if 'trade_date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame必须包含trade_date列或DatetimeIndex")
    
    # 如果trade_date在列中,设置为索引
    if 'trade_date' in df.columns:
        df = df.set_index('trade_date')
    
    # 确保索引是DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # 重采样规则
    agg_dict = {}
    if 'open' in df.columns:
        agg_dict['open'] = 'first'
    if 'high' in df.columns:
        agg_dict['high'] = 'max'
    if 'low' in df.columns:
        agg_dict['low'] = 'min'
    if 'close' in df.columns:
        agg_dict['close'] = 'last'
    if 'vol' in df.columns:
        agg_dict['vol'] = 'sum'
    if 'amount' in df.columns:
        agg_dict['amount'] = 'sum'
    
    weekly = df.resample('W').agg(agg_dict)
       
    # 删除全为NaN的行(无交易周)
    weekly = weekly.dropna(subset=['close'])
    
    return weekly


# ==================== 周期数据准备 ====================
def prepare_weekly_data(df_daily: pd.DataFrame, ma_period: int = 20) -> pd.DataFrame:
    """
    准备周线数据(含均线)
    
    Args:
        df_daily: 日线数据
        ma_period: 均线周期
    
    Returns:
        DataFrame: 周线数据含ma列
    """
    weekly = resample_to_weekly(df_daily)
    weekly[f'ma{ma_period}'] = calc_ma(weekly['close'], ma_period)
    
    return weekly


def prepare_daily_data(df_daily: pd.DataFrame, ma_period: int = 20) -> pd.DataFrame:
    """
    准备日线数据(含均线和分型)
    
    Args:
        df_daily: 日线数据
        ma_period: 均线周期
    
    Returns:
        DataFrame: 日线数据含ma、is_top、is_bottom列
    """
    df = df_daily.copy()
    
    # 计算均线
    df[f'ma{ma_period}'] = calc_ma(df['close'], ma_period)
    
    # 识别分型
    df['is_top'] = identify_top_fractal(df)
    df['is_bottom'] = identify_bottom_fractal(df)
    
    return df
