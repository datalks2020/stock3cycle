"""
陈凯三周期收敛图形态插件
基于陈凯三周期收敛图标准的完整实现
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
import config as config
import indicators as indicators
from .base import PatternBase
class ChenKaiConvergencePattern(PatternBase):
    """陈凯三周期收敛图形态识别与评分"""
    def __init__(self):
        self.cfg = config.CKConvergence
        self.score_cfg = config.CKScoring
    def get_name(self) -> str:
        return "陈凯收敛图"
    def get_min_score(self) -> float:
        return config.MIN_TOTAL_SCORE
    def identify(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        识别陈凯三周期收敛图形态
        Args:
            df: 日线数据(必须包含至少50天数据)
        Returns:
            dict: 识别结果
        """
        n = len(df)
        # 数据量检查
        if n < 50:
            return {
                'is_valid': False, 
                'fail_reason': f'数据不足({n}<50天)',
                'weekly_data': None,
                'daily_data': None
            }
        # 准备周线数据
        weekly_data = indicators.prepare_weekly_data(
            df, 
            ma_period=self.cfg.WEEKLY_MA_PERIOD
        )
        # 准备日线数据
        daily_data = indicators.prepare_daily_data(
            df,
            ma_period=self.cfg.DAILY_MA_PERIOD
        )
        # 返回处理后的数据,识别逻辑在score中完成
        return {
            'is_valid': True,
            'weekly_data': weekly_data,
            'daily_data': daily_data,
            'fail_reason': None
        }
    def score(self, df: pd.DataFrame, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        陈凯三周期收敛图评分
        评分维度:
        1. 大周期趋势(40分): 周线多头确认
        2. 中周期收敛(50分): 日线收敛形态
        3. 周期共振(10分): 大中周期一致性
        Args:
            df: 原始日线数据
            pattern_data: identify()返回的数据
        Returns:
            dict: 评分结果
        """
        if not pattern_data['is_valid']:
            return self._get_zero_score(pattern_data['fail_reason'])
        weekly_data = pattern_data['weekly_data']
        daily_data = pattern_data['daily_data']
        # === 维度1: 大周期趋势评分(40分) ===
        dim1_result = self._score_weekly_trend(weekly_data)
        # === 维度2: 中周期收敛形态评分(50分) ===
        dim2_result = self._score_daily_convergence(daily_data)
        # === 维度3: 大中周期共振评分(10分) ===
        dim3_result = self._score_resonance(
            weekly_data, 
            daily_data,
            dim1_result,
            dim2_result
        )
        # === 计算总分 ===
        total_score = (
            dim1_result['total'] + 
            dim2_result['total'] + 
            dim3_result['total']
        )
        return {
            'total': round(total_score, 1),
            'dim1_score': dim1_result['total'],
            'dim2_score': dim2_result['total'],
            'dim3_score': dim3_result['total'],
            'dim1_details': dim1_result,
            'dim2_details': dim2_result,
            'dim3_details': dim3_result,
            'pattern_features': dim2_result.get('features', {})
        }
    def _score_weekly_trend(self, weekly: pd.DataFrame) -> Dict[str, Any]:
        """
        维度1: 大周期(周线)趋势评分(40分)
        细项:
        1. 均线多头(15分): 周线收盘价 > 20周均线
        2. 高低点结构(15分): L2 > L1 (最近两个周线低点上移)
        3. 量能趋势(10分): 近4周量 > 近12周量
        """
        score = 0
        details = {}
        if len(weekly) < self.cfg.WEEKLY_MA_PERIOD:
            return {
                'total': 0,
                'ma_bull': 0,
                'structure': 0,
                'volume': 0,
                'reason': '周线数据不足'
            }
        # 1. 均线多头(15分)
        latest_close = weekly['close'].iloc[-1]
        latest_ma20 = weekly['ma20'].iloc[-1]
        ma_bull_score = 0
        if not pd.isna(latest_ma20) and latest_close > latest_ma20:
            ma_bull_score = self.score_cfg.DIM1_MA_BULL
            details['ma_bull_reason'] = f'价{latest_close:.2f}>MA20{latest_ma20:.2f}'
        else:
            details['ma_bull_reason'] = f'价{latest_close:.2f}≤MA20{latest_ma20:.2f}'
        score += ma_bull_score
        # 2. 高低点结构(15分)
        structure_score = 0
        if len(weekly) >= 3:
            l1 = weekly['low'].iloc[-3]  # 前前周低点
            l2 = weekly['low'].iloc[-2]  # 上周低点
            if l2 > l1:
                structure_score = self.score_cfg.DIM1_STRUCTURE
                details['structure_reason'] = f'L2({l2:.2f})>L1({l1:.2f})'
            else:
                details['structure_reason'] = f'L2({l2:.2f})≤L1({l1:.2f})'
        else:
            details['structure_reason'] = '数据不足'
        score += structure_score
        # 3. 量能趋势(10分)
        volume_score = 0
        if len(weekly) >= self.score_cfg.WEEKLY_LONG_WINDOW:
            recent_4w = weekly['vol'].iloc[-self.score_cfg.WEEKLY_RECENT_WINDOW:].mean()
            recent_12w = weekly['vol'].iloc[-self.score_cfg.WEEKLY_LONG_WINDOW:].mean()
            if recent_4w > recent_12w:
                volume_score = self.score_cfg.DIM1_VOLUME
                details['volume_reason'] = f'近4周量({recent_4w:.0f})>近12周量({recent_12w:.0f})'
            else:
                details['volume_reason'] = f'近4周量({recent_4w:.0f})≤近12周量({recent_12w:.0f})'
        else:
            details['volume_reason'] = '数据不足'
        score += volume_score
        return {
            'total': score,
            'ma_bull': ma_bull_score,
            'structure': structure_score,
            'volume': volume_score,
            'details': details
        }
    def _score_daily_convergence(self, daily: pd.DataFrame) -> Dict[str, Any]:
        """
        维度2: 中周期(日线)收敛形态评分(50分)
        细项:
        1. 高低点数量(8分): 高点≥3, 低点≥2
        2. 高点特征(10分): H1(最新)在H2(次新)的±3%范围内
        3. 低点特征(10分): L1(最新)>L2(次新)*1.01=10分, >1.005=5分
        4. 波动幅度(8分): (H1-L1)/L1 ≤5%=8分, ≤10%=4分
        5. 时间跨度(6分): 15-25天=6分, 10-30天=3分 (从H3开始到现在的天数)
        6. 成交量萎缩(8分): 收敛期量<趋势期50%=8分, <60%=4分
        """
        score = 0
        features = {}
        details = {}
        # 取最近30天数据作为分析窗口
        if len(daily) < self.cfg.MAX_CONVERGENCE_DAYS:
            return {
                'total': 0,
                'count': 0,
                'peak': 0,
                'trough': 0,
                'amplitude': 0,
                'timespan': 0,
                'volume': 0,
                'features': {},
                'reason': '日线数据不足'
            }
        recent_30d = daily.iloc[-self.cfg.MAX_CONVERGENCE_DAYS:].copy()
        # 提取高低点(带日期信息)
        peaks_data = recent_30d[recent_30d['is_top'] == 1][['high']].copy()
        peaks_data['date'] = peaks_data.index
        peaks = peaks_data['high'].tolist()
        peak_dates = peaks_data['date'].tolist()
        troughs_data = recent_30d[recent_30d['is_bottom'] == 1][['low']].copy()
        troughs_data['date'] = troughs_data.index
        troughs = troughs_data['low'].tolist()
        trough_dates = troughs_data['date'].tolist()
        peak_count = len(peaks)
        trough_count = len(troughs)
        features['peak_count'] = peak_count
        features['trough_count'] = trough_count
        # 保存所有高低点信息(用于debug)
        features['all_peaks'] = peaks
        features['all_peak_dates'] = [str(d.date()) if hasattr(d, 'date') else str(d) for d in peak_dates]
        features['all_troughs'] = troughs
        features['all_trough_dates'] = [str(d.date()) if hasattr(d, 'date') else str(d) for d in trough_dates]
        # 1. 高低点数量(8分)
        count_score = 0
        if peak_count >= self.cfg.MIN_PEAK_COUNT and trough_count >= self.cfg.MIN_TROUGH_COUNT:
            count_score = self.score_cfg.DIM2_COUNT
            details['count_reason'] = f'高点{peak_count}≥3, 低点{trough_count}≥2'
        else:
            details['count_reason'] = f'高点{peak_count}<3或低点{trough_count}<2'
            # 数量不足,后续评分无意义,直接返回
            return {
                'total': count_score,
                'count': count_score,
                'peak': 0,
                'trough': 0,
                'amplitude': 0,
                'timespan': 0,
                'volume': 0,
                'features': features,
                'reason': details['count_reason']
            }
        score += count_score
        # 修正变量命名逻辑：确保 h1 是最新高点，l1 是最新低点
        if peak_count >= 3:
            h1, h2, h3 = peaks[-1], peaks[-2], peaks[-3]
        else:
            h1, h2, h3 = peaks[-1], peaks[-1], peaks[-1]
        if trough_count >= 2:
            l1, l2 = troughs[-1], troughs[-2]
        else:
            l1, l2 = troughs[-1], troughs[-1]
        features['h1'] = h1
        features['h2'] = h2
        features['h3'] = h3
        features['l1'] = l1
        features['l2'] = l2
        # === Bug修复: 检查收敛形态是否被破坏 ===
        # 如果最近低点(L1)已经高于或等于最近高点(H1)，说明股价已突破箱体上沿
        if l1 >= h1:
            return {
                'total': count_score, 
                'count': count_score,
                'peak': 0,
                'trough': 0,
                'amplitude': 0,
                'timespan': 0,
                'volume': 0,
                'features': features,
                'reason': f'低点({l1:.2f})突破高点({h1:.2f})，形态已破坏(非收敛图)'
            }
        # === 逻辑修正: 低点上升必须快于高点下降 ===
        # 计算价格变化的绝对幅度
        peak_drop_amount = h3 - h1   # 高点下降的金额 (正数)
        trough_rise_amount = l1 - l2 # 低点上升的金额 (正数)
        # 如果高点在下降 (h3 > h1)，则要求低点上升金额必须大于高点下降金额
        # 如果高点在上升 (h3 <= h1)，则没有额外要求（已通过低点上移的基本要求）
        if peak_drop_amount > 0 and trough_rise_amount <= peak_drop_amount:
            return {
                'total': count_score,
                'count': count_score,
                'peak': 0,
                'trough': 0,
                'amplitude': 0,
                'timespan': 0,
                'volume': 0,
                'features': features,
                'reason': f'高点下降({peak_drop_amount:.2f})但低点上升不够快({trough_rise_amount:.2f})'
            }
        # === 逻辑修正结束 ===
        # 2. 高点特征(10分): H1(最新)在H2(次新)的±3%范围内
        peak_score = 0
        if h1 <= h2 * self.cfg.PEAK_UPPER_RATIO and h1 >= h2 * self.cfg.PEAK_LOWER_RATIO:
            peak_score = self.score_cfg.DIM2_PEAK
            h1_h2_ratio = (h1 - h2) / h2 * 100
            details['peak_reason'] = f'H1({h1:.2f})在H2({h2:.2f})±3%内(偏离{h1_h2_ratio:.1f}%)'
        else:
            h1_h2_ratio = (h1 - h2) / h2 * 100
            details['peak_reason'] = f'H1({h1:.2f})超出H2({h2:.2f})±3%范围(偏离{h1_h2_ratio:.1f}%)'
        score += peak_score
        # 3. 低点特征(10分): L1(最新)>L2(次新)*1.01=10分, >1.005=5分
        trough_score = 0
        if l1 > l2 * self.cfg.TROUGH_STRONG_RATIO:
            trough_score = self.score_cfg.TROUGH_STRONG_SCORE
            l1_l2_ratio = (l1 - l2) / l2 * 100
            details['trough_reason'] = f'L1({l1:.2f})>L2({l2:.2f})*1.01(上移{l1_l2_ratio:.1f}%)'
        elif l1 > l2 * self.cfg.TROUGH_WEAK_RATIO:
            trough_score = self.score_cfg.TROUGH_WEAK_SCORE
            l1_l2_ratio = (l1 - l2) / l2 * 100
            details['trough_reason'] = f'L1({l1:.2f})>L2({l2:.2f})*1.005(弱上移{l1_l2_ratio:.1f}%)'
        else:
            l1_l2_ratio = (l1 - l2) / l2 * 100
            details['trough_reason'] = f'L1({l1:.2f})未有效上移L2({l2:.2f})(仅{l1_l2_ratio:.1f}%)'
        score += trough_score
        # 4. 波动幅度(8分): (H1-L1)/L1 ≤5%=8分, ≤10%=4分
        amplitude_score = 0
        amplitude_ratio = (h1 - l1) / l1
        features['amplitude_ratio'] = amplitude_ratio
        if amplitude_ratio <= self.cfg.AMPLITUDE_TIGHT:
            amplitude_score = self.score_cfg.AMP_TIGHT_SCORE
            details['amplitude_reason'] = f'振幅{amplitude_ratio*100:.1f}%≤5%(紧收敛)'
        elif amplitude_ratio <= self.cfg.AMPLITUDE_LOOSE:
            amplitude_score = self.score_cfg.AMP_LOOSE_SCORE
            details['amplitude_reason'] = f'振幅{amplitude_ratio*100:.1f}%≤10%(宽收敛)'
        else:
            details['amplitude_reason'] = f'振幅{amplitude_ratio*100:.1f}%>10%(未收敛)'
        score += amplitude_score
        # 5. 时间跨度(6分): 从第三个高点(H3)到现在的天数
        first_peak_idx = recent_30d[recent_30d['high'] == h3].index[0]
        convergence_days = len(recent_30d.loc[first_peak_idx:])
        features['convergence_days'] = convergence_days
        timespan_score = 0
        if self.cfg.OPTIMAL_MIN_DAYS <= convergence_days <= self.cfg.OPTIMAL_MAX_DAYS:
            timespan_score = self.score_cfg.TIME_OPTIMAL_SCORE
            details['timespan_reason'] = f'{convergence_days}天在最优范围[15-25]'
        elif self.cfg.MIN_CONVERGENCE_DAYS <= convergence_days <= self.cfg.MAX_CONVERGENCE_DAYS:
            timespan_score = self.score_cfg.TIME_ACCEPTABLE_SCORE
            details['timespan_reason'] = f'{convergence_days}天在可接受范围[10-30]'
        else:
            details['timespan_reason'] = f'{convergence_days}天超出范围[10-30]'
        score += timespan_score
        # 6. 成交量萎缩(8分): 收敛期量 < 趋势期50%=8分, <60%=4分
        volume_score = 0
        trend_start = -(self.cfg.MAX_CONVERGENCE_DAYS + self.cfg.TREND_PERIOD_DAYS)
        trend_end = -self.cfg.MAX_CONVERGENCE_DAYS
        if len(daily) >= abs(trend_start):
            trend_period = daily.iloc[trend_start:trend_end]
            trend_vol_mean = trend_period['vol'].mean()
            convergence_vol_mean = recent_30d['vol'].mean()
            vol_ratio = convergence_vol_mean / trend_vol_mean if trend_vol_mean > 0 else 1
            if vol_ratio < self.cfg.VOL_SHRINK_STRONG:
                volume_score = self.score_cfg.VOL_STRONG_SCORE
                details['volume_reason'] = f'收敛量{convergence_vol_mean:.0f}<趋势量50%(比例{vol_ratio*100:.1f}%)'
            elif vol_ratio < self.cfg.VOL_SHRINK_WEAK:
                volume_score = self.score_cfg.VOL_WEAK_SCORE
                details['volume_reason'] = f'收敛量{convergence_vol_mean:.0f}<趋势量60%(比例{vol_ratio*100:.1f}%)'
            else:
                details['volume_reason'] = f'收敛量{convergence_vol_mean:.0f}未萎缩(比例{vol_ratio*100:.1f}%)'
        else:
            details['volume_reason'] = '无足够趋势期数据'
        score += volume_score
        return {
            'total': score,
            'count': count_score,
            'peak': peak_score,
            'trough': trough_score,
            'amplitude': amplitude_score,
            'timespan': timespan_score,
            'volume': volume_score,
            'features': features,
             'details': details,
            'debug_peaks': {
                'values': features.get('all_peaks', []),
                'dates': features.get('all_peak_dates', [])
            },
            'debug_troughs': {
                'values': features.get('all_troughs', []),
                'dates': features.get('all_trough_dates', [])
            }
        }
    def _score_resonance(
        self, 
        weekly: pd.DataFrame, 
        daily: pd.DataFrame,
        dim1_result: Dict[str, Any],
        dim2_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        维度3: 大中周期共振评分(10分)
        细项:
        1. 趋势一致性(6分): 日线收盘价>20日均线
        2. 量能共振(4分): 大周期量能向上 + 中周期量缩
        """
        score = 0
        details = {}
        # 1. 趋势一致性(6分)
        trend_score = 0
        if len(daily) >= self.cfg.DAILY_MA_PERIOD:
            latest_close = daily['close'].iloc[-1]
            latest_ma20 = daily['ma20'].iloc[-1]
            if not pd.isna(latest_ma20) and latest_close > latest_ma20:
                trend_score = self.score_cfg.DIM3_TREND
                details['trend_reason'] = f'日价{latest_close:.2f}>日MA20{latest_ma20:.2f}'
            else:
                details['trend_reason'] = f'日价{latest_close:.2f}≤日MA20{latest_ma20:.2f}'
        else:
            details['trend_reason'] = '日线数据不足'
        score += trend_score
        # 2. 量能共振(4分): 大周期量能向上(dim1.volume=10) + 中周期量缩(dim2.volume≥4)
        volume_resonance_score = 0
        dim1_vol = dim1_result.get('volume', 0)
        dim2_vol = dim2_result.get('volume', 0)
        if dim1_vol == self.score_cfg.DIM1_VOLUME and dim2_vol >= self.score_cfg.VOL_WEAK_SCORE:
            volume_resonance_score = self.score_cfg.DIM3_VOLUME
            details['volume_resonance_reason'] = '大周期放量+中周期缩量'
        else:
            details['volume_resonance_reason'] = f'量能未共振(大{dim1_vol}分,中{dim2_vol}分)'
        score += volume_resonance_score
        return {
            'total': score,
            'trend': trend_score,
            'volume_resonance': volume_resonance_score,
            'details': details
        }
    def _get_zero_score(self, reason: str) -> Dict[str, Any]:
        """返回零分结果"""
        return {
            'total': 0,
            'dim1_score': 0,
            'dim2_score': 0,
            'dim3_score': 0,
            'dim1_details': {'total': 0, 'reason': reason},
            'dim2_details': {'total': 0, 'reason': reason},
            'dim3_details': {'total': 0, 'reason': reason},
            'pattern_features': {}
        }