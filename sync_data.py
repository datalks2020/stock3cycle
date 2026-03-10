"""
数据同步脚本 - 用于增量同步股票数据
"""
from datetime import datetime, timedelta
import argparse
import config
from db_manager import DBManager


def main():
    """
    主程序 - 同步最近数据
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="数据同步脚本 - 用于增量同步股票数据")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="同步起始日期，格式: YYYYMMDD（例如: 20240101）。不指定则默认同步最近5天"
    )
    args = parser.parse_args()

    print("🚀 启动数据同步...")
    
    dm = DBManager()
    
    # 1. 更新股票列表
    print("\n>>> 更新股票列表")
    dm.update_stock_basic()
    
    # 2. 确定同步区间
    today = datetime.now().strftime("%Y%m%d")
    if args.start_date:
        start_date = args.start_date
    else:
        # 默认同步最近5天（覆盖节假日）
        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")

    print(f"\n>>> 同步日线数据: {start_date} -> {today}")
    
    # 3. 执行同步
    dm.sync_daily_data(start_date, today)
    
    print("\n✅ 数据同步完成！")
    print(f"   可以运行 python main.py 进行选股")


if __name__ == "__main__":
    main()
