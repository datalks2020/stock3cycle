"""
测试脚本 - 验证debug功能和数据处理
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 测试数据生成
def generate_test_data(ts_code='600000.SH', days=120):
    """生成测试数据"""
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(days)]
    
    # 生成模拟价格数据
    base_price = 10.0
    np.random.seed(42)
    
    prices = []
    for i in range(days):
        # 模拟收敛图: 高点平移, 低点抬升
        if i < 30:
            price = base_price + np.random.uniform(-0.5, 0.5)
        elif i < 60:
            # 第一波上涨
            price = base_price + (i-30) * 0.02 + np.random.uniform(-0.2, 0.2)
        elif i < 80:
            # 回调
            price = base_price + 0.6 - (i-60) * 0.01 + np.random.uniform(-0.1, 0.1)
        elif i < 100:
            # 第二波上涨
            price = base_price + 0.4 + (i-80) * 0.01 + np.random.uniform(-0.1, 0.1)
        else:
            # 收敛整理
            price = base_price + 0.6 + np.random.uniform(-0.05, 0.05)
        
        prices.append(price)
    
    df = pd.DataFrame({
        'ts_code': ts_code,
        'trade_date': dates,
        'name': '测试股票',
        'open': prices,
        'high': [p + np.random.uniform(0, 0.1) for p in prices],
        'low': [p - np.random.uniform(0, 0.1) for p in prices],
        'close': prices,
        'vol': [1000000 + np.random.randint(-200000, 200000) for _ in range(days)],
        'amount': [10000000 + np.random.randint(-2000000, 2000000) for _ in range(days)],
        'turnover_rate': [np.random.uniform(1, 5) for _ in range(days)],
        'circ_mv': [300000000] * days,  # 3000亿
        'list_date': ['2020-01-01'] * days,
        'industry': ['银行'] * days
    })
    
    return df


def test_indicators():
    """测试指标计算"""
    print("=" * 80)
    print("测试1: 指标计算")
    print("=" * 80)
    
    try:
        import indicators as indicators
        
        df = generate_test_data()
        print(f"✅ 生成测试数据: {len(df)} 条")
        
        # 测试日线数据准备
        daily = indicators.prepare_daily_data(df, ma_period=20)
        print(f"✅ 日线数据准备成功")
        print(f"   - MA20列存在: {'ma20' in daily.columns}")
        print(f"   - 分型列存在: {all(c in daily.columns for c in ['is_top', 'is_bottom'])}")
        
        # 统计分型
        peak_count = daily['is_top'].sum()
        trough_count = daily['is_bottom'].sum()
        print(f"   - 识别高点: {peak_count} 个")
        print(f"   - 识别低点: {trough_count} 个")
        
        # 测试周线数据准备
        weekly = indicators.prepare_weekly_data(df, ma_period=20)
        print(f"✅ 周线数据准备成功: {len(weekly)} 周")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pattern():
    """测试形态识别"""
    print("\n" + "=" * 80)
    print("测试2: 形态识别")
    print("=" * 80)
    
    try:
        from patterns.chenkai_convergence import ChenKaiConvergencePattern
        
        df = generate_test_data()
        pattern = ChenKaiConvergencePattern()
        
        # 识别形态
        pattern_data = pattern.identify(df)
        print(f"✅ 形态识别: {'成功' if pattern_data['is_valid'] else '失败'}")
        
        if not pattern_data['is_valid']:
            print(f"   失败原因: {pattern_data.get('fail_reason', '未知')}")
            return False
        
        # 评分
        score_result = pattern.score(df, pattern_data)
        print(f"✅ 评分完成")
        print(f"   - 总分: {score_result['total']:.1f}")
        print(f"   - 维度1: {score_result['dim1_score']:.0f}")
        print(f"   - 维度2: {score_result['dim2_score']:.0f}")
        print(f"   - 维度3: {score_result['dim3_score']:.0f}")
        
        # 检查debug信息
        dim2 = score_result.get('dim2_details', {})
        debug_peaks = dim2.get('debug_peaks', {})
        debug_troughs = dim2.get('debug_troughs', {})
        
        print(f"✅ Debug信息")
        print(f"   - 高点数据: {len(debug_peaks.get('values', []))} 个")
        print(f"   - 低点数据: {len(debug_troughs.get('values', []))} 个")
        
        if debug_peaks.get('values'):
            print(f"   - 最新高点: {debug_peaks['values'][-1]:.2f}")
        if debug_troughs.get('values'):
            print(f"   - 最新低点: {debug_troughs['values'][-1]:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_debug_tool():
    """测试debug工具"""
    print("\n" + "=" * 80)
    print("测试3: Debug工具")
    print("=" * 80)
    
    print("⚠️  此测试需要实际数据库,跳过")
    print("   使用方法: python debug_chenkai.py 600000.SH")
    
    return True


if __name__ == "__main__":
    print("\n🧪 陈凯收敛图系统测试\n")
    
    results = []
    
    # 运行测试
    results.append(("指标计算", test_indicators()))
    results.append(("形态识别", test_pattern()))
    results.append(("Debug工具", test_debug_tool()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📊 测试结果汇总")
    print("=" * 80)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️  部分测试失败,请检查错误信息")
    
    print("=" * 80 + "\n")
