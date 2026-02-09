"""
陈凯三周期收敛图选股系统 - 主程序
"""
import sys
from datetime import datetime
import pandas as pd
import config as config
from db_manager import DBManager
from strategy import ChenKaiStrategyEngine
# Debug模式开关
DEBUG_MODE = False  # 设置为True开启详细debug输出
def main(target_date: str = None, debug: bool = False):
    """
    主程序入口
    Args:
        target_date: 选股日期 YYYYMMDD, 默认为今天
        debug: 是否开启debug模式,输出详细高低点信息
    """
    global DEBUG_MODE
    DEBUG_MODE = debug
    if target_date is None:
        target_date = datetime.now().strftime("%Y%m%d")
    logger = config.logging.getLogger(__name__)
    logger.info("🤖 陈凯三周期收敛图选股系统启动")
    logger.info(f"📅 选股日期: {target_date}")
    # 初始化数据库管理器
    dm = DBManager()
    # Step 1: 市场环境风控
    logger.info("\n>>> 市场环境风控")
    logger.info("暂时跳过，后续需要用akshare 替换")
    # Step 2: 加载数据
    logger.info("\n>>> 读取本地数据")
    df_data = dm.load_data_for_strategy(target_date, lookback_days=500)
    if df_data.empty:
        logger.error("❌ 未找到本地数据，请先运行 sync_data.py")
        return
    stock_count = df_data['ts_code'].nunique()
    row_count = len(df_data)
    logger.info(f"   ✅ 加载成功: {stock_count} 只股票, {row_count} 条记录")
    # Step 3: 执行陈凯收敛图选股
    engine = ChenKaiStrategyEngine(df_data, target_date)
    result_df = engine.run()
    # Step 4: 输出结果
    if not result_df.empty:
        output_results(result_df, target_date)
    else:
        logger.info("\n今天没有符合条件的股票")
        print("\n" + "=" * 80)
        print("⚠️  今天没有符合条件的股票")
        print("=" * 80)
def output_results(result_df: pd.DataFrame, target_date: str):
    """
    输出选股结果
    Args:
        result_df: 结果DataFrame
        target_date: 选股日期
    """
    global DEBUG_MODE
    # 标记符合条件的股票
    result_df['qualified'] = result_df['total_score'] >= config.MIN_TOTAL_SCORE
    # 统计数量
    qualified_count = result_df['qualified'].sum()
    # === Debug模式: 输出详细高低点信息 ===
    if DEBUG_MODE and qualified_count > 0:
        print("\n" + "=" * 100)
        print("🔍 DEBUG模式: 详细高低点信息")
        print("=" * 100)
        qualified_stocks = result_df[result_df['qualified']].copy()
        for idx, row in qualified_stocks.iterrows():
            print(f"\n{'='*100}")
            print(f"📊 {row['ts_code']} - {row['name']}")
            print(f"{'='*100}")
            print(f"总分: {row['total_score']:.1f} | 大周期: {row['dim1_score']:.0f} | 中周期: {row['dim2_score']:.0f} | 共振: {row['dim3_score']:.0f}")
            print(f"价格: {row['price']:.2f} | 市值: {row['circ_mv']:.2f}亿")
            # 提取debug信息
            if 'debug_info' in row and row['debug_info']:
                debug_info = row['debug_info']
                # 显示所有高点
                if 'peaks' in debug_info and debug_info['peaks']['values']:
                    peaks_vals = debug_info['peaks']['values']
                    peaks_dates = debug_info['peaks']['dates']
                    total_peaks = len(peaks_vals)
                    print(f"\n🔺 高点信息 (共{total_peaks}个):")
                    print(f"{'序号':<6} {'日期':<12} {'价格':<10} {'说明':<20}")
                    print("-" * 60)
                    for i, (date, price) in enumerate(zip(peaks_dates, peaks_vals), 1):
                        # 修复逻辑：判断是否为最近的3个高点
                        # i 是从1开始的序号，total_peaks 是总数
                        # 最后一个点是 i == total_peaks
                        if i > total_peaks - 3:
                            offset = total_peaks - i
                            if offset == 0: label = "H1 (最新)"
                            elif offset == 1: label = "H2 (次新)"
                            else: label = "H3 (第三)"
                        else:
                            label = "早期高点"
                        print(f"{i:<6} {date:<12} {price:<10.2f} {label:<20}")
                # 显示所有低点
                if 'troughs' in debug_info and debug_info['troughs']['values']:
                    troughs_vals = debug_info['troughs']['values']
                    troughs_dates = debug_info['troughs']['dates']
                    total_troughs = len(troughs_vals)
                    print(f"\n🔻 低点信息 (共{total_troughs}个):")
                    print(f"{'序号':<6} {'日期':<12} {'价格':<10} {'说明':<20}")
                    print("-" * 60)
                    for i, (date, price) in enumerate(zip(troughs_dates, troughs_vals), 1):
                        # 修复逻辑：判断是否为最近的2个低点
                        if i > total_troughs - 2:
                            offset = total_troughs - i
                            if offset == 0: label = "L1 (最新)"
                            else: label = "L2 (次新)"
                        else:
                            label = "早期低点"
                        print(f"{i:<6} {date:<12} {price:<10.2f} {label:<20}")
                # 显示关键形态特征
                print(f"\n📐 形态特征:")
                print(f"  收敛天数: {row.get('convergence_days', 'N/A')} 天")
                # 注意：此处 h1/h2/h3 对应 chenkai_convergence.py 修正后的定义
                if row.get('h1', 0) > 0:
                    print(f"  最近3高点: H1={row['h1']:.2f}, H2={row['h2']:.2f}, H3={row['h3']:.2f}")
                    # H1是最新，H2是次新
                    if row.get('h2', 0) > 0:
                        print(f"  高点变化: H1/H2 = {(row['h1']/row['h2']-1)*100:+.2f}%")
                if row.get('l1', 0) > 0:
                    print(f"  最近2低点: L1={row['l1']:.2f}, L2={row['l2']:.2f}")
                    if row.get('l2', 0) > 0:
                        print(f"  低点变化: L1/L2 = {(row['l1']/row['l2']-1)*100:+.2f}%")
                if row.get('amplitude_ratio', 0) > 0:
                    print(f"  振幅比: {row['amplitude_ratio']*100:.2f}%")
        print(f"\n{'='*100}")
        print("🔍 Debug信息输出完成")
        print(f"{'='*100}\n")
    # 保存完整CSV
    csv_filename = f"陈凯收敛图_{target_date}.csv"
    csv_path = f"{config.OUTPUT_DIR}/{csv_filename}"
    output_cols = [col for col in config.CSV_COLUMNS if col in result_df.columns]
    result_df[output_cols].to_csv(csv_path, index=False, encoding='utf-8-sig')
    # 保存Excel
    excel_filename = f"陈凯收敛图_{target_date}.xlsx"
    excel_path = f"{config.OUTPUT_DIR}/{excel_filename}"
    result_df[output_cols].to_excel(excel_path, index=False)
    # 如果有高分股票,额外保存
    if qualified_count > 0:
        high_score_df = result_df[result_df['qualified']].copy()
        hs_csv_path = f"{config.OUTPUT_DIR}/陈凯收敛图_高分_{target_date}.csv"
        high_score_df[output_cols].to_csv(hs_csv_path, index=False, encoding='utf-8-sig')
    # 控制台输出
    print("\n" + "=" * 80)
    print(f"🎉 陈凯三周期收敛图选股完成!")
    print("=" * 80)
    print(f"\n📊 结果统计:")
    print(f"  评分标的: {len(result_df)} 只")
    print(f"  达标股票(≥{config.MIN_TOTAL_SCORE}分): {qualified_count} 只")
    # 分数段分布
    print(f"\n【分数分布】")
    scores = result_df['total_score']
    print(f"  优秀(≥90分): {(scores >= 90).sum()} 只")
    print(f"  良好(80-90分): {((scores >= 80) & (scores < 90)).sum()} 只")
    print(f"  及格(70-80分): {((scores >= 70) & (scores < 80)).sum()} 只")
    print(f"  不及格(<70分): {(scores < 70).sum()} 只")
    # TOP 10展示
    if len(result_df) > 0:
        print("\n【TOP 20 陈凯收敛图】")
        display_cols = ['ts_code', 'name', 'total_score', 'dim1_score', 
                       'dim2_score', 'dim3_score', 'price', 'circ_mv']
        top10 = result_df.nlargest(min(20, len(result_df)), 'total_score')
        print(top10[display_cols].to_string(index=False))
    # 维度得分统计
    if qualified_count > 0:
        qualified_df = result_df[result_df['qualified']]
        print(f"\n【达标股票维度分析】(共{qualified_count}只)")
        print(f"  维度1(大周期)平均分: {qualified_df['dim1_score'].mean():.1f}/40")
        print(f"  维度2(中周期)平均分: {qualified_df['dim2_score'].mean():.1f}/50")
        print(f"  维度3(共振)平均分: {qualified_df['dim3_score'].mean():.1f}/10")
        # 形态特征统计
        if 'peak_count' in qualified_df.columns:
            print(f"\n【形态特征】")
            print(f"  平均高点数: {qualified_df['peak_count'].mean():.1f}")
            print(f"  平均低点数: {qualified_df['trough_count'].mean():.1f}")
            print(f"  平均收敛天数: {qualified_df['convergence_days'].mean():.1f}")
            print(f"  平均振幅比: {qualified_df['amplitude_ratio'].mean()*100:.1f}%")
    # 文件路径
    print(f"\n📄 文件已保存:")
    print(f"   完整结果: {csv_path}")
    print(f"   Excel: {excel_path}")
    if qualified_count > 0:
        print(f"   高分专用: {hs_csv_path}")
    print("=" * 80 + "\n")
if __name__ == "__main__":
    # 支持命令行传参: 
    # python main_chenkai.py 20231027
    # python main_chenkai.py 20231027 --debug  (开启debug模式)
    # python main_chenkai.py --debug           (今天+debug模式)
    date_arg = None
    debug_mode = False
    for arg in sys.argv[1:]:
        if arg == '--debug' or arg == '-d':
            debug_mode = True
        elif not arg.startswith('-'):
            date_arg = arg
    main(date_arg, debug_mode)