"""
陈凯三周期收敛图选股系统 - 主程序（完全修复版）
配合修复版 strategy.py 使用
"""
import sys
from datetime import datetime
import pandas as pd
import json
import config as config
from db_manager import DBManager
from strategy import ChenKaiStrategyEngine

# Debug模式开关
DEBUG_MODE = False


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
    """
    global DEBUG_MODE

    # 标记符合条件的股票
    result_df['qualified'] = result_df['total_score'] >= config.MIN_TOTAL_SCORE
    qualified_count = result_df['qualified'].sum()

    # === Debug模式: 输出详细高低点信息 ===
    if DEBUG_MODE and qualified_count > 0:
        print("\n" + "=" * 100)
        print("🔍 DEBUG模式: 详细高低点信息")
        print("  时间顺序定义: H1(最早) → L1 → H2 → L2 → H3(最新)")
        print("=" * 100)

        qualified_stocks = result_df[result_df['qualified']].copy()

        for idx, row in qualified_stocks.iterrows():
            print(f"\n{'='*100}")
            print(f"📊 {row['ts_code']} - {row['name']}")
            print(f"{'='*100}")
            print(f"总分: {row['total_score']:.1f} | 大周期: {row['dim1_score']:.0f} | 中周期: {row['dim2_score']:.0f} | 共振: {row['dim3_score']:.0f}")
            print(f"价格: {row['price']:.2f} | 市值: {row['circ_mv']:.2f}亿")

            # 从展开的列中提取 debug 信息
            debug_info = extract_debug_info(row)

            if not debug_info or (not debug_info.get('peaks') and not debug_info.get('troughs')):
                print(f"\n⚠️  无法提取 debug 信息")
                continue

            # 构建选中点的日期→角色映射
            selected_map = {}

            h1_date = str(row.get('h1_date', ''))
            h2_date = str(row.get('h2_date', ''))
            h3_date = str(row.get('h3_date', ''))
            l1_date = str(row.get('l1_date', ''))
            l2_date = str(row.get('l2_date', ''))

            if h1_date and h1_date != 'nan':
                selected_map[h1_date] = 'H1(最早高点)'
            if h2_date and h2_date != 'nan':
                selected_map[h2_date] = 'H2(中间高点)'
            if h3_date and h3_date != 'nan':
                selected_map[h3_date] = 'H3(最新潜在高点)'
            if l1_date and l1_date != 'nan':
                selected_map[l1_date] = 'L1(第一低点)'
            if l2_date and l2_date != 'nan':
                selected_map[l2_date] = 'L2(第二低点)'

            # 合并所有高点和低点，按日期统一排列
            all_points = []

            if 'peaks' in debug_info and debug_info['peaks'].get('values'):
                for date, price in zip(debug_info['peaks']['dates'], debug_info['peaks']['values']):
                    all_points.append((str(date), price, '🔺高点'))

            if 'troughs' in debug_info and debug_info['troughs'].get('values'):
                for date, price in zip(debug_info['troughs']['dates'], debug_info['troughs']['values']):
                    all_points.append((str(date), price, '🔻低点'))

            # 按日期排序
            all_points.sort(key=lambda x: x[0])

            total_points = len(all_points)
            print(f"\n📍 所有高低点 (共{total_points}个, 按日期从早到晚):")
            print(f"{'序号':<6} {'日期':<12} {'类型':<10} {'价格':<10} {'角色标注':<20}")
            print("-" * 70)

            for i, (date, price, ptype) in enumerate(all_points, 1):
                role = selected_map.get(date, '')
                marker = f"  ◀ {role}" if role else ''
                print(f"{i:<6} {date:<12} {ptype:<10} {price:<10.2f}{marker}")

            # 显示算法选中的 H1→L1→H2→L2→H3 序列
            print(f"\n✅ 算法选中的收敛序列 (严格时间顺序 H1→L1→H2→L2→H3):")
            print(f"{'角色':<8} {'日期':<12} {'价格':<10} {'说明':<20}")
            print("-" * 60)

            selected_points = [
                ('H1', row.get('h1_date', ''), row.get('h1', 0), 'H1(最早高点)'),
                ('L1', row.get('l1_date', ''), row.get('l1', 0), 'L1(第一低点)'),
                ('H2', row.get('h2_date', ''), row.get('h2', 0), 'H2(中间高点)'),
                ('L2', row.get('l2_date', ''), row.get('l2', 0), 'L2(第二低点)'),
                ('H3', row.get('h3_date', ''), row.get('h3', 0), 'H3(最新潜在高点)'),
            ]

            for role, date, price, desc in selected_points:
                if price > 0 and str(date) != 'nan':
                    print(f"{role:<8} {str(date):<12} {price:<10.2f} {desc:<20}")
                else:
                    print(f"{role:<8} {'N/A':<12} {'N/A':<10} {desc:<20}")

            # 显示关键形态特征
            print(f"\n📐 形态特征:")
            conv_days = row.get('convergence_days', 'N/A')
            print(f"  收敛天数: {conv_days} 天")

            if row.get('h1', 0) > 0 and row.get('h2', 0) > 0 and row.get('h3', 0) > 0:
                print(f"  高点序列: H1={row['h1']:.2f}({row.get('h1_date','')}) → H2={row['h2']:.2f}({row.get('h2_date','')}) → H3={row['h3']:.2f}({row.get('h3_date','')})")
                print(f"  高点变化: H1→H2 = {(row['h2']/row['h1']-1)*100:+.2f}%, H2→H3 = {(row['h3']/row['h2']-1)*100:+.2f}%")

            if row.get('l1', 0) > 0 and row.get('l2', 0) > 0:
                print(f"  低点序列: L1={row['l1']:.2f}({row.get('l1_date','')}) → L2={row['l2']:.2f}({row.get('l2_date','')})")
                print(f"  低点变化: L1→L2 = {(row['l2']/row['l1']-1)*100:+.2f}%")

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

    excel_filename = f"陈凯收敛图_{target_date}.xlsx"
    excel_path = f"{config.OUTPUT_DIR}/{excel_filename}"
    result_df[output_cols].to_excel(excel_path, index=False)

    if qualified_count > 0:
        high_score_df = result_df[result_df['qualified']].copy()
        hs_csv_path = f"{config.OUTPUT_DIR}/陈凯收敛图_高分_{target_date}.csv"
        high_score_df[output_cols].to_csv(hs_csv_path, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 80)
    print(f"🎉 陈凯三周期收敛图选股完成!")
    print("=" * 80)
    print(f"\n📊 结果统计:")
    print(f"  评分标的: {len(result_df)} 只")
    print(f"  达标股票(≥{config.MIN_TOTAL_SCORE}分): {qualified_count} 只")

    print(f"\n【分数分布】")
    scores = result_df['total_score']
    print(f"  优秀(≥90分): {(scores >= 90).sum()} 只")
    print(f"  良好(80-90分): {((scores >= 80) & (scores < 90)).sum()} 只")
    print(f"  及格(70-80分): {((scores >= 70) & (scores < 80)).sum()} 只")
    print(f"  不及格(<70分): {(scores < 70).sum()} 只")

    if len(result_df) > 0:
        print("\n【TOP 20 陈凯收敛图】")
        display_cols = ['ts_code', 'name', 'total_score', 'dim1_score',
                       'dim2_score', 'dim3_score', 'price', 'circ_mv']
        top10 = result_df.nlargest(min(20, len(result_df)), 'total_score')
        print(top10[display_cols].to_string(index=False))

    if qualified_count > 0:
        qualified_df = result_df[result_df['qualified']]
        print(f"\n【达标股票维度分析】(共{qualified_count}只)")
        print(f"  维度1(大周期)平均分: {qualified_df['dim1_score'].mean():.1f}/40")
        print(f"  维度2(中周期)平均分: {qualified_df['dim2_score'].mean():.1f}/50")
        print(f"  维度3(共振)平均分: {qualified_df['dim3_score'].mean():.1f}/10")

        if 'peak_count' in qualified_df.columns:
            print(f"\n【形态特征】")
            print(f"  平均高点数: {qualified_df['peak_count'].mean():.1f}")
            print(f"  平均低点数: {qualified_df['trough_count'].mean():.1f}")
            print(f"  平均收敛天数: {qualified_df['convergence_days'].mean():.1f}")
            print(f"  平均振幅比: {qualified_df['amplitude_ratio'].mean()*100:.1f}%")

    print(f"\n📄 文件已保存:")
    print(f"   完整结果: {csv_path}")
    print(f"   Excel: {excel_path}")
    if qualified_count > 0:
        print(f"   高分专用: {hs_csv_path}")
    print("=" * 80 + "\n")


def extract_debug_info(row):
    """
    从 DataFrame 行中提取 debug 信息
    支持多种数据格式
    """
    debug_info = {'peaks': {}, 'troughs': {}}

    # 方法1: 尝试从展开的列中提取
    if 'debug_peaks_values' in row.index and 'debug_peaks_dates' in row.index:
        peaks_values = row['debug_peaks_values']
        peaks_dates = row['debug_peaks_dates']

        # 处理列表类型
        if isinstance(peaks_values, list) and isinstance(peaks_dates, list):
            debug_info['peaks'] = {'values': peaks_values, 'dates': peaks_dates}
        # 处理字符串类型（可能是序列化的列表）
        elif isinstance(peaks_values, str) and isinstance(peaks_dates, str):
            try:
                import ast
                debug_info['peaks'] = {
                    'values': ast.literal_eval(peaks_values),
                    'dates': ast.literal_eval(peaks_dates)
                }
            except:
                pass

    if 'debug_troughs_values' in row.index and 'debug_troughs_dates' in row.index:
        troughs_values = row['debug_troughs_values']
        troughs_dates = row['debug_troughs_dates']

        if isinstance(troughs_values, list) and isinstance(troughs_dates, list):
            debug_info['troughs'] = {'values': troughs_values, 'dates': troughs_dates}
        elif isinstance(troughs_values, str) and isinstance(troughs_dates, str):
            try:
                import ast
                debug_info['troughs'] = {
                    'values': ast.literal_eval(troughs_values),
                    'dates': ast.literal_eval(troughs_dates)
                }
            except:
                pass

    # 方法2: 尝试从 JSON 字符串中提取（备用方案）
    if not debug_info['peaks'] and 'debug_peaks_json' in row.index:
        try:
            peaks_json = row['debug_peaks_json']
            if peaks_json and peaks_json != 'nan':
                debug_info['peaks'] = json.loads(peaks_json)
        except:
            pass

    if not debug_info['troughs'] and 'debug_troughs_json' in row.index:
        try:
            troughs_json = row['debug_troughs_json']
            if troughs_json and troughs_json != 'nan':
                debug_info['troughs'] = json.loads(troughs_json)
        except:
            pass

    return debug_info


if __name__ == "__main__":
    # 支持命令行传参:
    # python main.py 20231027
    # python main.py 20231027 --debug  (开启debug模式)
    # python main.py --debug           (今天+debug模式)
    date_arg = None
    debug_mode = False
    for arg in sys.argv[1:]:
        if arg == '--debug' or arg == '-d':
            debug_mode = True
        elif not arg.startswith('-'):
            date_arg = arg
    main(date_arg, debug_mode)