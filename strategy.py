"""
策略引擎 - 陈凯三周期收敛图选股
"""
import pandas as pd
import numpy as np
from tqdm import tqdm
import logging
from typing import Tuple, Optional
import config as config
import indicators as indicators
from patterns import PatternManager, ChenKaiConvergencePattern
class ChenKaiStrategyEngine:
    """
    陈凯三周期收敛图选股策略引擎
    流程:
    1. 基础硬性筛选
    2. 陈凯收敛图识别与评分
    3. 结果汇总
    """
    def __init__(self, data_df: pd.DataFrame, target_date: str):
        """
        初始化策略引擎
        Args:
            data_df: 股票历史数据
            target_date: 选股日期
        """
        self.raw_data = data_df
        self.target_date = target_date
        self.results = []
        self.logger = logging.getLogger(__name__)
        # 初始化形态管理器并注册陈凯收敛图
        self.pattern_manager = PatternManager()
        self._register_patterns()
        # 统计信息
        self.stats = {
            'total': 0,
            'passed_basic': 0,
            'evaluated': 0,
            'fail_list_days': 0,
            'fail_circ_mv': 0,
            'fail_turnover': 0,
        }
        # 评分分布
        self.score_distribution = []
    def _register_patterns(self):
        """注册形态插件"""
        self.pattern_manager.register('chenkai', ChenKaiConvergencePattern())
    def run(self) -> pd.DataFrame:
        """
        执行完整选股流程
        Returns:
            pd.DataFrame: 选股结果
        """
        if self.raw_data.empty:
            return pd.DataFrame()
        self._preprocess_data()
        groups = list(self.raw_data.groupby('ts_code'))
        self.stats['total'] = len(groups)
        self.logger.info("=" * 60)
        self.logger.info(f"📊 陈凯三周期收敛图选股系统 - {self.target_date}")
        self.logger.info("=" * 60)
        self.logger.info(f"总样本池: {self.stats['total']} 只")
        # 阶段1: 基础硬性筛选
        self.logger.info("\n>>> 阶段1: 基础硬性筛选")
        candidates = self._basic_filter(groups)
        self.stats['passed_basic'] = len(candidates)
        self.logger.info(f"   ✅ 通过基础筛选: {self.stats['passed_basic']} 只")
        if self.stats['passed_basic'] == 0:
            self.logger.warning("   ⚠️  无股票通过筛选")
            self._log_stats()
            return pd.DataFrame()
        # 阶段2: 陈凯收敛图评分
        self.logger.info("\n>>> 阶段2: 陈凯收敛图识别与评分")
        self._evaluate_patterns(candidates)
        self.stats['evaluated'] = len(self.results)
        self._log_stats()
        if self.results:
            result_df = pd.DataFrame(self.results)
            # 按总分降序排序
            result_df = result_df.sort_values(by='total_score', ascending=False)
            return result_df
        else:
            return pd.DataFrame()
    def _preprocess_data(self):
        """数据预处理"""
        self.raw_data['trade_date'] = pd.to_datetime(self.raw_data['trade_date'])
        self.raw_data.sort_values(['ts_code', 'trade_date'], inplace=True)
        # 修改点：将日期设为索引，确保后续逻辑中使用的是日期索引而非整数索引
        self.raw_data.set_index('trade_date', inplace=True)
    def _basic_filter(self, groups: list) -> dict:
        """
        基础硬性筛选
        Args:
            groups: 按股票代码分组的数据
        Returns:
            dict: 通过筛选的股票 {ts_code: df}
        """
        candidates = {}
        for ts_code, df_stock in tqdm(groups, desc="基础筛选"):
            passed, fail_reason = self._check_basic_criteria(ts_code, df_stock)
            if passed:
                candidates[ts_code] = df_stock
        return candidates
    def _check_basic_criteria(
        self,
        ts_code: str,
        df: pd.DataFrame
    ) -> Tuple[bool, Optional[str]]:
        """
        检查单只股票的基础条件
        Args:
            ts_code: 股票代码
            df: 股票数据 (注意：此时 df.index 已为 trade_date)
        Returns:
            (是否通过, 失败原因)
        """
        # 修改点：使用 df.index 进行过滤，因为 trade_date 现在是索引
        df = df[df.index <= pd.to_datetime(self.target_date)]
        if df.empty:
            return False, "无数据"
        curr_row = df.iloc[-1]
        cfg = config.BasicFilter
        # 1. 上市时间
        list_date = pd.to_datetime(curr_row['list_date'])
        list_days = (pd.to_datetime(self.target_date) - list_date).days
        if list_days < cfg.MIN_LIST_DAYS:
            self.stats['fail_list_days'] += 1
            return False, f'上市天数{list_days}<{cfg.MIN_LIST_DAYS}'
        # 2. 流通市值
        circ_mv_yi = curr_row['circ_mv'] / 10000
        if circ_mv_yi < cfg.MIN_CIRC_MV:
            self.stats['fail_circ_mv'] += 1
            return False, f'流通市值{circ_mv_yi:.1f}<{cfg.MIN_CIRC_MV}'
        # 3. 换手率
        if len(df) < 20:
            self.stats['fail_turnover'] += 1
            return False, '数据不足20天'
        avg_turnover = df['turnover_rate'].iloc[-20:].mean()
        if avg_turnover < cfg.MIN_TURNOVER_20:
            self.stats['fail_turnover'] += 1
            return False, f'换手率{avg_turnover:.2f}<{cfg.MIN_TURNOVER_20}'
        return True, None
    def _evaluate_patterns(self, candidates: dict):
        """
        对候选股票进行形态评分
        Args:
            candidates: 通过基础筛选的股票
        """
        for ts_code, df in tqdm(candidates.items(), desc="陈凯收敛图评分"):
            self._evaluate_single_stock(ts_code, df)
    def _evaluate_single_stock(self, ts_code: str, df: pd.DataFrame):
        """
        评估单只股票
        Args:
            ts_code: 股票代码
            df: 股票数据 (注意：此时 df.index 已为 trade_date)
        """
        # 修改点：使用 df.index 进行过滤，因为 trade_date 现在是索引
        df = df[df.index <= pd.to_datetime(self.target_date)]
        curr_row = df.iloc[-1]
        # 计算基础统计信息
        list_date = pd.to_datetime(curr_row['list_date'])
        list_days = (pd.to_datetime(self.target_date) - list_date).days
        circ_mv_yi = curr_row['circ_mv'] / 10000
        avg_turnover = df['turnover_rate'].iloc[-20:].mean()
        # 使用形态管理器进行评分
        pattern_results = self.pattern_manager.evaluate(df)
        # 提取陈凯收敛图结果
        ck_result = pattern_results['chenkai']['score']
        # 记录分数分布
        self.score_distribution.append(ck_result['total'])
        # 格式化形态标签
        patterns = self.pattern_manager.format_patterns_label(pattern_results)
        # 提取详细得分
        dim1_details = ck_result.get('dim1_details', {})
        dim2_details = ck_result.get('dim2_details', {})
        dim3_details = ck_result.get('dim3_details', {})
        features = ck_result.get('pattern_features', {})        
        # 提取debug信息(高低点详情)
        debug_peaks = dim2_details.get('debug_peaks', {})
        debug_troughs = dim2_details.get('debug_troughs', {})
        # 生成备注
        remark_parts = []
        if dim1_details.get('details'):
            for k, v in dim1_details['details'].items():
                remark_parts.append(f"{k}: {v}")
        if dim2_details.get('details'):
            for k, v in dim2_details['details'].items():
                remark_parts.append(f"{k}: {v}")
        remark = "; ".join(remark_parts[:3])  # 只取前3条
        # 构建结果记录
        record = {
            'ts_code': ts_code,
            'name': curr_row['name'],
            'trade_date': self.target_date,
            'price': curr_row['close'],
            'industry': curr_row.get('industry', ''),
            'circ_mv': round(circ_mv_yi, 2),
            'turnover_avg': round(avg_turnover, 2),
            'list_days': list_days,
            'total_score': ck_result['total'],
            'dim1_score': ck_result['dim1_score'],
            'dim2_score': ck_result['dim2_score'],
            'dim3_score': ck_result['dim3_score'],
            'patterns': patterns,
            'remark': remark,
            # Debug信息
            'debug_info': {
                'peaks': debug_peaks,
                'troughs': debug_troughs
            }
        }
        # 添加详细分项
        if config.INCLUDE_SCORE_DETAILS:
            record.update({
                # 维度1细项
                'dim1_ma_bull': dim1_details.get('ma_bull', 0),
                'dim1_structure': dim1_details.get('structure', 0),
                'dim1_volume': dim1_details.get('volume', 0),
                # 维度2细项
                'dim2_count': dim2_details.get('count', 0),
                'dim2_peak': dim2_details.get('peak', 0),
                'dim2_trough': dim2_details.get('trough', 0),
                'dim2_amplitude': dim2_details.get('amplitude', 0),
                'dim2_timespan': dim2_details.get('timespan', 0),
                'dim2_volume': dim2_details.get('volume', 0),
                # 维度3细项
                'dim3_trend': dim3_details.get('trend', 0),
                'dim3_volume_resonance': dim3_details.get('volume_resonance', 0),
                # 形态特征
                'peak_count': features.get('peak_count', 0),
                'trough_count': features.get('trough_count', 0),
                'convergence_days': features.get('convergence_days', 0),
                'h1': features.get('h1', 0),
                'h2': features.get('h2', 0),
                'h3': features.get('h3', 0),
                'l1': features.get('l1', 0),
                'l2': features.get('l2', 0),
                'amplitude_ratio': features.get('amplitude_ratio', 0),
            })
        self.results.append(record)
    def _log_stats(self):
        """输出统计信息"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 选股统计汇总")
        self.logger.info("=" * 60)
        # 基础筛选统计
        self.logger.info("\n【阶段1: 基础筛选】")
        self.logger.info(f"  总样本池: {self.stats['total']} 只")
        self.logger.info(
            f"  ✅ 通过: {self.stats['passed_basic']} 只 "
            f"({self.stats['passed_basic']/self.stats['total']*100:.1f}%)"
        )
        if self.stats['total'] - self.stats['passed_basic'] > 0:
            self.logger.info(f"  ❌ 淘汰: {self.stats['total'] - self.stats['passed_basic']} 只")
            self.logger.info(f"     - 上市时间不足: {self.stats['fail_list_days']} 只")
            self.logger.info(f"     - 流通市值不足: {self.stats['fail_circ_mv']} 只")
            self.logger.info(f"     - 换手率不足: {self.stats['fail_turnover']} 只")
        # 形态评分统计
        if self.stats['passed_basic'] > 0:
            self.logger.info("\n【阶段2: 陈凯收敛图评分】")
            self.logger.info(f"  评分标的数: {self.stats['evaluated']} 只")
            # 分数分布
            if self.score_distribution:
                scores = np.array(self.score_distribution)
                self.logger.info(f"\n  评分分布:")
                self.logger.info(f"     - 平均分: {scores.mean():.1f}")
                self.logger.info(f"     - 中位数: {np.median(scores):.1f}")
                self.logger.info(f"     - 最高分: {scores.max():.1f}")
                excellent = (scores >= 90).sum()
                good = ((scores >= 80) & (scores < 90)).sum()
                acceptable = ((scores >= 70) & (scores < 80)).sum()
                self.logger.info(f"     - 优秀(≥90分): {excellent} 只")
                self.logger.info(f"     - 良好(80-90分): {good} 只")
                self.logger.info(f"     - 及格(70-80分): {acceptable} 只")
        self.logger.info("\n" + "=" * 60)