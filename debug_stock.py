"""
股票调试工具 - 用于分析单只股票的技术指标和形态
"""
import pandas as pd
import config
from db_manager import DBManager
import indicators


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算技术指标
    
    Args:
        df: 股票数据DataFrame
        
    Returns:
        添加了指标的DataFrame
    """
    if df.empty:
        return df
    
    # 振幅
    df['amplitude'] = indicators.calc_amplitude(df)
    
    # 均线
    df['ma5'] = indicators.calc_ma(df['close'], 5)
    df['ma10'] = indicators.calc_ma(df['close'], 10)
    df['ma20'] = indicators.calc_ma(df['close'], 20)
    df['ma60'] = indicators.calc_ma(df['close'], 60)
    
    # 量能均量
    df['vol_ma5'] = df['vol'].rolling(5).mean()
    df['vol_ma10'] = df['vol'].rolling(10).mean()
    df['vol_ma20'] = df['vol'].rolling(20).mean()
    
    return df


def diagnose_triangle(df: pd.DataFrame):
    """
    诊断收敛三角形指标
    
    Args:
        df: 股票数据
    """
    print("\n" + "=" * 100)
    print("🔬 陈凯收敛三角形诊断 (最近10天)")
    print("=" * 100)
    
    last_10 = df.tail(10)
    
    # A. 趋势位置
    latest_close = last_10['close'].iloc[-1]
    latest_ma60 = last_10['ma60'].iloc[-1]
    trend_status = "📈 多头" if latest_close > latest_ma60 else "📉 空头/震荡"
    print(f"【趋势位置】: 价格 {latest_close:.2f} vs MA60 {latest_ma60:.2f} -> {trend_status}")
    
    # B. 振幅收敛
    amp_10_mean = last_10['amplitude'].mean()
    amp_prev_10 = df.iloc[-20:-10]['amplitude'].mean()
    
    if amp_prev_10 > 0:
        ratio = amp_10_mean / amp_prev_10
        print(f"【振幅收敛】: 近10日 {amp_10_mean:.2%} | 前10日 {amp_prev_10:.2%} | 比率 {ratio:.2%}")
    else:
        print(f"【振幅收敛】: 近10日 {amp_10_mean:.2%} | 数据不足")
    
    # C. 量能状态
    vol_3 = last_10['vol'].tail(3).mean()
    vol_20 = df['vol'].tail(20).mean()
    vol_ratio = vol_3 / vol_20 if vol_20 > 0 else 0
    print(f"【量能状态】: 近3日 {vol_3/10000:.0f}万手 | 20日均 {vol_20/10000:.0f}万手 | 比率 {vol_ratio:.2f}")
    
    # D. 高低点提示
    print(f"【高低点】: 请查看CSV中的high/low列，确认是否符合'低点上移、高点平移'")
    
    print("=" * 100 + "\n")


def main():
    """
    主程序 - 调试指定股票
    """
    # ========== 配置区域 ==========
    DEBUG_STOCK_CODE = "600114.SH"  # 设置要调试的股票代码
    LOOKBACK_DAYS = 500             # 回溯天数
    # ==============================
    
    dm = DBManager()
    
    print(f"🔍 正在获取 {DEBUG_STOCK_CODE} 的历史数据...")
    
    # 1. 获取数据
    df = dm.get_stock_history(DEBUG_STOCK_CODE, lookback_days=LOOKBACK_DAYS)
    
    if df.empty:
        print("❌ 未找到数据，请检查代码或先运行数据同步")
        return
    
    # 2. 计算指标
    df = calculate_indicators(df)
    
    # 3. 导出CSV
    output_file = f"debug_{DEBUG_STOCK_CODE}.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ 完整数据已导出至: {output_file}")
    
    # 4. 打印最近20天数据
    print("\n" + "=" * 100)
    print(f"📊 {DEBUG_STOCK_CODE} 最近30个交易日数据预览")
    print("=" * 100)
    
    display_cols = [
        'trade_date', 'close', 'pct_chg',
        'amplitude', 'ma20', 'ma60',
        'vol', 'vol_ma20'
    ]
    
    recent_df = df[display_cols].tail(30).copy()
    
    # 格式化显示
    for col in ['close', 'pct_chg', 'amplitude', 'ma20', 'ma60']:
        recent_df[col] = recent_df[col].apply(
            lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A"
        )
    
    recent_df['vol'] = recent_df['vol'].apply(
        lambda x: f"{int(x/10000)}万手" if pd.notnull(x) else "N/A"
    )
    recent_df['vol_ma20'] = recent_df['vol_ma20'].apply(
        lambda x: f"{int(x/10000)}万手" if pd.notnull(x) else "N/A"
    )
    
    print(recent_df.to_string(index=False))
    
    # 5. 核心指标诊断
    diagnose_triangle(df)


if __name__ == "__main__":
    main()
