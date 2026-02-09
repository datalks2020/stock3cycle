"""
陈凯收敛图 Debug 工具
用于分析单只股票的详细高低点信息
"""
import sys
import pandas as pd
from datetime import datetime
import config as config
import indicators as indicators
from patterns.chenkai_convergence import ChenKaiConvergencePattern
from db_manager import DBManager
def analyze_stock(ts_code: str, target_date: str = None):
    """
    分析单只股票的收敛图形态
    Args:
        ts_code: 股票代码
        target_date: 分析日期,默认今天
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y%m%d")
    print("=" * 100)
    print(f"🔍 陈凯收敛图 Debug 分析")
    print("=" * 100)
    print(f"股票代码: {ts_code}")
    print(f"分析日期: {target_date}")
    print("=" * 100)
    # 加载数据
    dm = DBManager()
    df_all = dm.load_data_for_strategy(target_date, lookback_days=500)
    if df_all.empty:
        print("❌ 无法加载数据")
        return
    # 筛选目标股票
    df = df_all[df_all['ts_code'] == ts_code].copy()
    if df.empty:
        print(f"❌ 未找到股票 {ts_code} 的数据")
        return
    # 修改点：处理日期索引，确保后续提取高低点信息时使用的是日期而非整数索引
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.sort_values('trade_date', inplace=True)
    df.set_index('trade_date', inplace=True)
    df = df[df.index <= pd.to_datetime(target_date)]
    print(f"✅ 数据加载成功: {len(df)} 条记录")
    # 获取股票基本信息
    curr_row = df.iloc[-1]
    print(f"\n📊 基本信息:")
    print(f"  名称: {curr_row['name']}")
    print(f"  价格: {curr_row['close']:.2f}")
    print(f"  流通市值: {curr_row['circ_mv']/10000:.2f}亿")
    # 执行形态识别
    pattern = ChenKaiConvergencePattern()
    pattern_data = pattern.identify(df)
    if not pattern_data['is_valid']:
        print(f"\n❌ 形态识别失败: {pattern_data.get('fail_reason', '未知原因')}")
        return
    # 执行评分
    score_result = pattern.score(df, pattern_data)
    print(f"\n💯 评分结果:")
    print(f"  总分: {score_result['total']:.1f}/100")
    print(f"  维度1(大周期): {score_result['dim1_score']:.0f}/40")
    print(f"  维度2(中周期): {score_result['dim2_score']:.0f}/50")
    print(f"  维度3(共振): {score_result['dim3_score']:.0f}/10")
    if score_result['total'] >= config.MIN_TOTAL_SCORE:
        print(f"  ✅ 达标 (≥{config.MIN_TOTAL_SCORE}分)")
    else:
        print(f"  ❌ 未达标 (<{config.MIN_TOTAL_SCORE}分)")
    # 显示维度1详情
    dim1_details = score_result.get('dim1_details', {})
    if dim1_details:
        print(f"\n📈 维度1: 大周期趋势详情")
        print(f"  均线多头: {dim1_details.get('ma_bull', 0)}分 - {dim1_details.get('details', {}).get('ma_bull_reason', '')}")
        print(f"  高低点结构: {dim1_details.get('structure', 0)}分 - {dim1_details.get('details', {}).get('structure_reason', '')}")
        print(f"  量能趋势: {dim1_details.get('volume', 0)}分 - {dim1_details.get('details', {}).get('volume_reason', '')}")
    # 显示维度2详情
    dim2_details = score_result.get('dim2_details', {})
    if dim2_details:
        print(f"\n📊 维度2: 中周期收敛详情")
        details = dim2_details.get('details', {})
        print(f"  高低点数量: {dim2_details.get('count', 0)}分 - {details.get('count_reason', '')}")
        print(f"  高点特征: {dim2_details.get('peak', 0)}分 - {details.get('peak_reason', '')}")
        print(f"  低点特征: {dim2_details.get('trough', 0)}分 - {details.get('trough_reason', '')}")
        print(f"  波动幅度: {dim2_details.get('amplitude', 0)}分 - {details.get('amplitude_reason', '')}")
        print(f"  时间跨度: {dim2_details.get('timespan', 0)}分 - {details.get('timespan_reason', '')}")
        print(f"  成交量萎缩: {dim2_details.get('volume', 0)}分 - {details.get('volume_reason', '')}")
    # 显示所有高低点
    debug_peaks = dim2_details.get('debug_peaks', {})
    debug_troughs = dim2_details.get('debug_troughs', {})
    if debug_peaks and debug_peaks.get('values'):
        print(f"\n🔺 所有高点 (共{len(debug_peaks['values'])}个):")
        print(f"{'序号':<6} {'日期':<12} {'价格':<10} {'说明':<30}")
        print("-" * 70)
        peak_values = debug_peaks['values']
        peak_dates = debug_peaks['dates']
        for i, (date, price) in enumerate(zip(peak_dates, peak_values), 1):
            # 标注最近3个高点
            if i >= len(peak_values) - 2:
                idx = len(peak_values) - i + 1
                if idx == 0:
                    label = "H3 (最新高点,用于评分)"
                elif idx == 1:
                    label = "H2 (次新高点,用于评分)"
                elif idx == 2:
                    label = "H1 (第三高点,用于评分)"
                else:
                    label = "早期高点"
            else:
                label = "早期高点"
            print(f"{i:<6} {date:<12} {price:<10.2f} {label:<30}")
    if debug_troughs and debug_troughs.get('values'):
        print(f"\n🔻 所有低点 (共{len(debug_troughs['values'])}个):")
        print(f"{'序号':<6} {'日期':<12} {'价格':<10} {'说明':<30}")
        print("-" * 70)
        trough_values = debug_troughs['values']
        trough_dates = debug_troughs['dates']
        for i, (date, price) in enumerate(zip(trough_dates, trough_values), 1):
            # 标注最近2个低点
            if i >= len(trough_values) - 1:
                idx = len(trough_values) - i + 1
                if idx == 0:
                    label = "L2 (最新低点,用于评分)"
                elif idx == 1:
                    label = "L1 (次新低点,用于评分)"
                else:
                    label = "早期低点"
            else:
                label = "早期低点"
            print(f"{i:<6} {date:<12} {price:<10.2f} {label:<30}")
    # 显示形态特征
    features = score_result.get('pattern_features', {})
    if features:
        print(f"\n📐 形态特征统计:")
        print(f"  高点总数: {features.get('peak_count', 0)}")
        print(f"  低点总数: {features.get('trough_count', 0)}")
        print(f"  收敛天数: {features.get('convergence_days', 0)}")
        if features.get('h1', 0) > 0:
            print(f"\n  最近3个高点:")
            print(f"    H1 = {features['h1']:.2f}")
            print(f"    H2 = {features['h2']:.2f}")
            print(f"    H3 = {features['h3']:.2f}")
            print(f"    H3/H2 = {(features['h3']/features['h2']-1)*100:+.2f}% (标准:±3%以内)")
        if features.get('l1', 0) > 0:
            print(f"\n  最近2个低点:")
            print(f"    L1 = {features['l1']:.2f}")
            print(f"    L2 = {features['l2']:.2f}")
            print(f"    L2/L1 = {(features['l2']/features['l1']-1)*100:+.2f}% (标准:>1%为强上移,>0.5%为弱上移)")
        if features.get('amplitude_ratio', 0) > 0:
            print(f"\n  振幅比:")
            print(f"    (H3-L2)/L2 = {features['amplitude_ratio']*100:.2f}% (标准:≤5%紧收敛,≤10%宽收敛)")
    print(f"\n{'='*100}")
    print("✅ 分析完成")
    print(f"{'='*100}\n")
def batch_analyze(csv_file: str):
    """
    批量分析CSV文件中的股票
    Args:
        csv_file: CSV文件路径(应包含ts_code列)
    """
    try:
        df = pd.read_csv(csv_file)
        if 'ts_code' not in df.columns:
            print("❌ CSV文件必须包含ts_code列")
            return
        stock_codes = df['ts_code'].unique()
        print(f"📋 准备分析 {len(stock_codes)} 只股票")
        for i, code in enumerate(stock_codes, 1):
            print(f"\n[{i}/{len(stock_codes)}]")
            analyze_stock(code)
            if i < len(stock_codes):
                input("\n按Enter继续下一只...")
    except Exception as e:
        print(f"❌ 批量分析出错: {e}")
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  分析单只股票: python debug_chenkai.py 600000.SH")
        print("  指定日期:     python debug_chenkai.py 600000.SH 20240115")
        print("  批量分析:     python debug_chenkai.py --batch 选股结果.csv")
    else:
        if sys.argv[1] == '--batch' and len(sys.argv) >= 3:
            batch_analyze(sys.argv[2])
        else:
            stock_code = sys.argv[1]
            date_arg = sys.argv[2] if len(sys.argv) > 2 else None
            analyze_stock(stock_code, date_arg)