"""
数据库管理模块 - 负责数据存储和查询
"""
import tushare as ts
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import Optional, Tuple
import time
from tqdm import tqdm
import logging

import config


class DBManager:
    """数据库管理类 - 封装所有数据库操作"""
    
    def __init__(self):
        """初始化数据库连接和Tushare接口"""
        self.pro = ts.pro_api(config.TS_TOKEN)
        self.engine = create_engine(config.DB_PATH)
        self.logger = logging.getLogger(__name__)
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表结构"""
        with self.engine.connect() as conn:
            # 股票基础信息表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stock_basic (
                    ts_code TEXT PRIMARY KEY,
                    symbol TEXT,
                    name TEXT,
                    industry TEXT,
                    list_date TEXT
                )
            """))
            
            # 日线行情表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stock_daily (
                    ts_code TEXT,
                    trade_date TEXT,
                    open REAL, 
                    high REAL, 
                    low REAL, 
                    close REAL,
                    pre_close REAL, 
                    change REAL, 
                    pct_chg REAL,
                    vol REAL, 
                    amount REAL,
                    turnover_rate REAL, 
                    circ_mv REAL,
                    PRIMARY KEY (ts_code, trade_date)
                )
            """))
            
            conn.commit()
    
    # ==================== 股票列表管理 ====================
    
    def update_stock_basic(self):
        """更新股票列表"""
        self.logger.info("正在更新股票列表...")
        
        df = self.pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,industry,list_date'
        )
        
        df.to_sql('stock_basic', self.engine, if_exists='replace', index=False)
        self.logger.info(f"股票列表更新完成，共 {len(df)} 只")
    
    # ==================== 交易日历 ====================
    
    def get_trade_cal(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            交易日历DataFrame
        """
        return self.pro.trade_cal(
            exchange='',
            start_date=start_date,
            end_date=end_date,
            is_open='1'
        )
    
    # ==================== 日线数据同步 ====================
    
    def sync_daily_data(self, start_date: str, end_date: str):
        """
        同步日线数据(按日期循环,节省积分)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        """
        # 获取交易日历
        cal = self.get_trade_cal(start_date, end_date)
        trade_dates = cal['cal_date'].tolist()
        
        if not trade_dates:
            self.logger.info("指定区间无交易日")
            return
        
        self.logger.info(f"开始同步日线数据: {start_date} -> {end_date} (共{len(trade_dates)}个交易日)")
        
        # 按日期循环下载
        for date in tqdm(trade_dates, desc="同步日线"):
            try:
                # 下载行情
                df_daily = self.pro.daily(trade_date=date)
                
                # 下载每日指标
                df_basic = self.pro.daily_basic(
                    trade_date=date,
                    fields='ts_code,turnover_rate,circ_mv'
                )
                
                if df_daily.empty or df_basic.empty:
                    continue
                
                # 合并数据
                df_merge = pd.merge(df_daily, df_basic, on='ts_code', how='inner')
                df_merge['trade_date'] = date
                
                # 删除当日旧数据后插入
                with self.engine.connect() as conn:
                    conn.execute(text(f"DELETE FROM stock_daily WHERE trade_date = '{date}'"))
                    conn.commit()
                
                df_merge.to_sql('stock_daily', self.engine, if_exists='append', index=False)
                
            except Exception as e:
                self.logger.error(f"日期 {date} 同步失败: {str(e)}")
                time.sleep(1)
            
            time.sleep(0.3)  # 限制频率
    
    # ==================== 数据查询 ====================
    
    def load_data_for_strategy(
        self,
        date: str,
        lookback_days: int = 120
    ) -> pd.DataFrame:
        """
        加载策略所需数据
        
        Args:
            date: 目标日期 YYYYMMDD
            lookback_days: 回溯天数
            
        Returns:
            包含历史数据的DataFrame
        """
        start_date = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=lookback_days)
        ).strftime("%Y%m%d")
        
        query = f"""
        SELECT a.*, b.name, b.industry, b.list_date 
        FROM stock_daily a 
        JOIN stock_basic b ON a.ts_code = b.ts_code
        WHERE a.trade_date >= '{start_date}' 
        AND a.trade_date <= '{date}'
        ORDER BY a.ts_code, a.trade_date
        """
        
        return pd.read_sql(query, self.engine)
    
    def get_stock_history(
        self,
        ts_code: str,
        end_date: Optional[str] = None,
        lookback_days: int = 500
    ) -> pd.DataFrame:
        """
        获取单只股票历史数据
        
        Args:
            ts_code: 股票代码
            end_date: 截止日期 YYYYMMDD
            lookback_days: 回溯天数
            
        Returns:
            历史行情DataFrame
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        start_date = (
            datetime.strptime(end_date, "%Y%m%d") - timedelta(days=lookback_days)
        ).strftime("%Y%m%d")
        
        query = f"""
        SELECT * 
        FROM stock_daily 
        WHERE ts_code = '{ts_code}' 
        AND trade_date >= '{start_date}' 
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            self.logger.error(f"查询股票历史失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_metadata(self, ts_code: str) -> Optional[dict]:
        """
        获取股票元数据(基本信息+最新行情)
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票元数据字典,未找到返回None
        """
        try:
            # 查询基本信息
            query_basic = f"SELECT * FROM stock_basic WHERE ts_code = '{ts_code}'"
            df_basic = pd.read_sql(query_basic, self.engine)
            
            if df_basic.empty:
                return None
            
            meta = df_basic.iloc[0].to_dict()
            
            # 查询最新行情
            query_daily = f"""
                SELECT trade_date, close, vol, amount, circ_mv, pct_chg, turnover_rate
                FROM stock_daily 
                WHERE ts_code = '{ts_code}' 
                ORDER BY trade_date DESC 
                LIMIT 1
            """
            df_daily = pd.read_sql(query_daily, self.engine)
            
            if not df_daily.empty:
                latest = df_daily.iloc[0]
                meta.update({
                    'price': latest['close'],
                    'trade_date': str(latest['trade_date']),
                    'vol': latest['vol'],
                    'amount': latest['amount'],
                    'pct_chg': latest['pct_chg'],
                    'turnover_rate': latest['turnover_rate'],
                    'circ_mv': latest.get('circ_mv', meta.get('circ_mv'))
                })
            
            return meta
        
        except Exception as e:
            self.logger.error(f"提取股票元数据失败: {str(e)}")
            return None
    
    # ==================== 市场情绪 ====================
    
    def get_market_sentiment(self, date: str) -> Tuple[int, int]:
        """
        获取涨跌停家数
        
        Args:
            date: 交易日期 YYYYMMDD或Timestamp
            
        Returns:
            (涨停数, 跌停数)
        """
        try:
            # 标准化日期格式
            if isinstance(date, pd.Timestamp):
                date_str = date.strftime("%Y%m%d")
            elif isinstance(date, datetime):
                date_str = date.strftime("%Y%m%d")
            else:
                date_str = str(date)
            
            # 调用接口
            df = self.pro.limit_list_d(trade_date=date_str)
            
            if df is None or df.empty:
                self.logger.warning(f"日期 {date_str} 涨跌停数据为空")
                return 0, 0
            
            # 统计
            up = len(df[df['limit'] == 'U'])
            down = len(df[df['limit'] == 'D'])
            
            self.logger.info(f"📅 {date_str} -> 涨停: {up}, 跌停: {down}")
            return up, down
        
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"获取涨跌停数据失败 ({date}): {error_msg}")
            
            if "权限" in error_msg or "积分" in error_msg:
                self.logger.error("提示: Tushare账户积分不足")
            
            return 100, 10  # 返回默认值防止阻断流程
