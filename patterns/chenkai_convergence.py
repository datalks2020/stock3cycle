"""
陈凯三周期收敛图形态插件 - 新评分体系
基于可程序化股票收敛形态量化评分表
总分100分，6个评分维度

时间顺序定义：H1(最早) → L1 → H2 → L2 → H3(最新)
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
import config as config
import indicators as indicators
from .base import PatternBase


class ChenKaiConvergencePattern(PatternBase):
    """
    陈凯三周期收敛图形态识别与评分
    
    时间顺序: H1 → L1 → H2 → L2 → H3
    - H1: 第一个高点(最早)
    - L1: 第一个低点
    - H2: 第二个高点
    - L2: 第二个低点
    - H3: 第三个高点(最新)
    
    新评分体系(100分):
    1. 收敛起点识别(15分)
    2. 交替高低点结构(25分)
    3. 有序波动验证(25分)
    4. 量能收缩验证(20分)
    5. 技术指标确认(15分)
    6. 提前识别机制(10分)
    
    关键约束: 
    - H3必须出现在最近N个交易日内，确保时效性
    - 周线趋势必须向上，走平或向下趋势硬性排除
    """
    
    # ============================================================
    # H3时效性控制参数
    # ============================================================
    H3_MAX_AGE_DAYS = 3          # H3距离最新交易日不超过3个交易日
    H3_FRESHNESS_BONUS = 5       # H3为当日/前一日时额外加分（从评分项2中分配）
    
    # ============================================================
    # 周线趋势过滤参数（★★★ 要求向上趋势 ★★★）
    # ============================================================
    WEEKLY_MA_SLOPE_LOOKBACK = 5     # 看最近5根周线MA的斜率
    WEEKLY_MA_UP_THRESHOLD = 0.002   # ★要求向上: 周线MA斜率必须高于此值（+0.2%/周）
    WEEKLY_CLOSE_UP_THRESHOLD = 0.02 # ★要求向上: 最近N周收盘价回归斜率必须高于此值
    WEEKLY_TREND_LOOKBACK = 10       # 周线趋势观察窗口（周数）
    WEEKLY_SHORT_MA = 5              # 周线短期均线周期
    WEEKLY_LONG_MA = 20              # 周线长期均线周期
    WEEKLY_PRICE_FROM_HIGH_THRESHOLD = 0.10  # ★收紧: 当前价距离近期高点超过10%视为弱势
    WEEKLY_ABOVE_MA_TOLERANCE = 0.01 # ★要求向上: 收盘价必须在MA之上（容忍度1%）
    
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
        """
        n = len(df)
        
        if n < 50:
            return {
                'is_valid': False,
                'fail_reason': f'数据不足({n}<50天)',
                'weekly_data': None,
                'daily_data': None,
                'weekly_trend_ok': False,
                'weekly_trend_info': '数据不足'
            }
        
        weekly_data = indicators.prepare_weekly_data(
            df, ma_period=self.cfg.WEEKLY_MA_PERIOD
        )
        daily_data = indicators.prepare_daily_data(
            df, ma_period=self.cfg.DAILY_MA_PERIOD
        )
        daily_data['ma5'] = indicators.calc_ma(daily_data['close'], 5)
        daily_data['ma10'] = indicators.calc_ma(daily_data['close'], 10)
        daily_data = indicators.calc_macd(daily_data)
        
        # ============================================================
        # ★★★ 周线趋势硬性检查（要求向上） ★★★
        # ============================================================
        weekly_trend_ok, weekly_trend_info = self._check_weekly_trend(weekly_data)
        
        return {
            'is_valid': True,
            'weekly_data': weekly_data,
            'daily_data': daily_data,
            'fail_reason': None,
            'weekly_trend_ok': weekly_trend_ok,
            'weekly_trend_info': weekly_trend_info
        }
    
    def _check_weekly_trend(self, weekly: pd.DataFrame) -> Tuple[bool, str]:
        """
        ★★★ 要求向上趋势: 周线趋势硬性检查 ★★★
        
        核心原则: 收敛图要求周线趋势明确向上，走平或下降均排除。
        
        检查维度（6项，任一不通过即排除）:
        1. 周线MA方向（MA斜率必须为正且达到阈值）—— 硬性
        2. 周线收盘价线性回归斜率（必须为正）
        3. 最近周线收盘价必须在MA之上
        4. 近期周线高低点走势（低点必须抬升）
        5. 周线均线排列（短期MA必须 > 长期MA，多头排列）—— 硬性
        6. 当前价格相对近期高点的位置 —— 硬性
        
        判定规则（★★★ 要求向上: 更严格 ★★★）:
        - 单项硬性排除: 检查1/5/6 任一不通过直接排除
        - 组合排除: 检查2/3/4 中任意一项不通过即排除
        
        Returns:
            (是否通过, 描述信息)
        """
        if len(weekly) < self.WEEKLY_TREND_LOOKBACK:
            return False, f'周线数据不足{self.WEEKLY_TREND_LOOKBACK}根，无法确认上升趋势'
        
        recent_weekly = weekly.iloc[-self.WEEKLY_TREND_LOOKBACK:]
        
        # ============================================================
        # 检查1: 周线均线(MA)方向 — ★硬性检查，必须向上★
        # ============================================================
        ma_col = f'ma{self.cfg.WEEKLY_MA_PERIOD}' if hasattr(self.cfg, 'WEEKLY_MA_PERIOD') else 'ma20'
        
        # 尝试获取周线MA，如果没有则手动计算
        if ma_col in recent_weekly.columns:
            ma_values = recent_weekly[ma_col].dropna()
        else:
            # 手动计算周线MA
            ma_period = getattr(self.cfg, 'WEEKLY_MA_PERIOD', 20)
            if len(weekly) >= ma_period:
                weekly_ma = weekly['close'].rolling(ma_period).mean()
                ma_values = weekly_ma.iloc[-self.WEEKLY_TREND_LOOKBACK:].dropna()
            else:
                ma_values = pd.Series(dtype=float)
        
        ma_slope_ok = False
        ma_slope_info = ''
        ma_slope_per_week = 0.0
        
        if len(ma_values) >= self.WEEKLY_MA_SLOPE_LOOKBACK:
            recent_ma = ma_values.iloc[-self.WEEKLY_MA_SLOPE_LOOKBACK:]
            ma_start = recent_ma.iloc[0]
            ma_end = recent_ma.iloc[-1]
            
            if ma_start > 0:
                ma_change_rate = (ma_end - ma_start) / ma_start
                ma_slope_per_week = ma_change_rate / len(recent_ma)
                
                if ma_slope_per_week >= self.WEEKLY_MA_UP_THRESHOLD:
                    ma_slope_ok = True
                    ma_slope_info = (
                        f'周线MA上升: 斜率{ma_slope_per_week*100:.3f}%/周 '
                        f'≥ 阈值{self.WEEKLY_MA_UP_THRESHOLD*100:.2f}%/周'
                    )
                else:
                    ma_slope_ok = False
                    if ma_slope_per_week >= 0:
                        ma_slope_info = (
                            f'周线MA走平(未达上升标准): 斜率{ma_slope_per_week*100:.3f}%/周 '
                            f'< 阈值{self.WEEKLY_MA_UP_THRESHOLD*100:.2f}%/周'
                        )
                    else:
                        ma_slope_info = (
                            f'周线MA下降: 斜率{ma_slope_per_week*100:.3f}%/周 '
                            f'< 阈值{self.WEEKLY_MA_UP_THRESHOLD*100:.2f}%/周'
                        )
        else:
            ma_slope_ok = False
            ma_slope_info = f'MA数据不足{self.WEEKLY_MA_SLOPE_LOOKBACK}根'
        
        # ★ 检查1为硬性条件：MA未明确上升直接排除
        if not ma_slope_ok:
            return False, f'★硬性排除-周线MA未上升: {ma_slope_info}'
        
        # ============================================================
        # 检查2: 周线收盘价线性回归斜率（必须为正）
        # ============================================================
        close_values = recent_weekly['close'].values
        n_weeks = len(close_values)
        
        close_slope_ok = False
        close_slope_info = ''
        close_slope_pct = 0.0
        
        if n_weeks >= 3:
            x = np.arange(n_weeks)
            mean_price = np.mean(close_values)
            if mean_price > 0:
                slope, intercept = np.polyfit(x, close_values, 1)
                close_slope_pct = slope / mean_price
                
                close_slope_ok = close_slope_pct >= self.WEEKLY_CLOSE_UP_THRESHOLD / n_weeks
                if close_slope_ok:
                    close_slope_info = (
                        f'周线收盘价回归斜率向上: {close_slope_pct*100:.3f}%/周, '
                        f'累计{close_slope_pct*n_weeks*100:.2f}%/{n_weeks}周'
                    )
                else:
                    close_slope_info = (
                        f'周线收盘价回归斜率不足: {close_slope_pct*100:.3f}%/周, '
                        f'累计{close_slope_pct*n_weeks*100:.2f}%/{n_weeks}周, '
                        f'需≥{self.WEEKLY_CLOSE_UP_THRESHOLD/n_weeks*100:.3f}%/周'
                    )
            else:
                close_slope_ok = False
                close_slope_info = '价格异常'
        else:
            close_slope_ok = False
            close_slope_info = '数据不足'
        
        # ============================================================
        # 检查3: 近期周线必须收在MA之上
        # ============================================================
        above_ma_ok = True
        above_ma_info = ''
        
        if len(ma_values) >= 4:
            recent_close_4 = recent_weekly['close'].iloc[-4:].values
            recent_ma_4 = ma_values.iloc[-4:].values
            
            min_len = min(len(recent_close_4), len(recent_ma_4))
            if min_len >= 4:
                # ★要求向上: 至少3周收盘价在MA之上（容忍度1%）
                above_count = sum(
                    1 for i in range(min_len)
                    if recent_close_4[i] >= recent_ma_4[i] * (1 - self.WEEKLY_ABOVE_MA_TOLERANCE)
                )
                below_count = min_len - above_count
                if above_count >= 3:
                    above_ma_ok = True
                    above_ma_info = (
                        f'收盘价在MA之上({above_count}/{min_len}周)'
                    )
                else:
                    above_ma_ok = False
                    above_ma_info = (
                        f'收盘价未能持续站在MA之上'
                        f'(仅{above_count}/{min_len}周在MA上方，需≥3周)'
                    )
        
        # ============================================================
        # 检查4: 周线高低点走势（低点必须抬升，高点不能持续下移）
        # ============================================================
        hl_ok = True
        hl_info = ''
        
        if len(recent_weekly) >= 5:
            recent_5 = recent_weekly.iloc[-5:]
            lows_5 = recent_5['low'].values
            highs_5 = recent_5['high'].values
            
            low_rises = sum(
                1 for i in range(1, len(lows_5))
                if lows_5[i] >= lows_5[i-1]
            )
            high_rises = sum(
                1 for i in range(1, len(highs_5))
                if highs_5[i] >= highs_5[i-1]
            )
            
            low_drops = (len(lows_5) - 1) - low_rises
            high_drops = (len(highs_5) - 1) - high_rises
            
            # ★要求向上: 低点抬升≥2次，且高点下移不超过1次
            if low_rises >= 2 and high_drops <= 1:
                hl_ok = True
                hl_info = (
                    f'周线高低点向上: '
                    f'低点抬升{low_rises}次, 高点抬升{high_rises}次(共{len(lows_5)-1}周)'
                )
            else:
                hl_ok = False
                hl_info = (
                    f'周线高低点未持续向上: '
                    f'低点抬升{low_rises}次(需≥2), 高点下移{high_drops}次(需≤1)'
                )
        
        # ============================================================
        # ★检查5: 周线均线排列（必须多头排列: 短期MA > 长期MA）
        # ============================================================
        ma_arrangement_ok = False
        ma_arrangement_info = ''
        
        short_ma_period = self.WEEKLY_SHORT_MA
        long_ma_period = self.WEEKLY_LONG_MA
        
        if len(weekly) >= long_ma_period:
            weekly_short_ma = weekly['close'].rolling(short_ma_period).mean()
            weekly_long_ma = weekly['close'].rolling(long_ma_period).mean()
            
            # 取最近3根周线的短期MA和长期MA
            recent_short = weekly_short_ma.iloc[-3:].dropna()
            recent_long = weekly_long_ma.iloc[-3:].dropna()
            
            if len(recent_short) >= 3 and len(recent_long) >= 3:
                # ★要求向上: 最近3周短期MA必须全部高于长期MA（多头排列）
                above_count = sum(
                    1 for i in range(len(recent_short))
                    if recent_short.iloc[i] > recent_long.iloc[i] * (1 - 0.005)  # 0.5%容忍度
                )
                
                latest_short = recent_short.iloc[-1]
                latest_long = recent_long.iloc[-1]
                gap_pct = (latest_short - latest_long) / latest_long * 100 if latest_long > 0 else 0
                
                if above_count >= 3:
                    ma_arrangement_ok = True
                    ma_arrangement_info = (
                        f'周线多头排列: MA{short_ma_period}连续{above_count}周高于MA{long_ma_period}'
                        f'(当前差距+{gap_pct:.2f}%)'
                    )
                elif above_count >= 2:
                    # 2周满足，给予有条件通过（但仍需其他条件配合）
                    ma_arrangement_ok = False
                    ma_arrangement_info = (
                        f'周线均线排列偏弱: MA{short_ma_period}仅{above_count}周高于MA{long_ma_period}'
                        f'(需3周全部满足，当前差距{gap_pct:+.2f}%)'
                    )
                else:
                    ma_arrangement_ok = False
                    ma_arrangement_info = (
                        f'周线空头排列: MA{short_ma_period}仅{above_count}周高于MA{long_ma_period}'
                        f'(当前差距{gap_pct:+.2f}%)'
                    )
        else:
            ma_arrangement_ok = False
            ma_arrangement_info = f'周线数据不足{long_ma_period}根，无法确认多头排列'
        
        # ★ 检查5为硬性条件：非多头排列直接排除
        if not ma_arrangement_ok:
            combined_info = (
                f'★硬性排除-{ma_arrangement_info} | '
                f'{ma_slope_info} | {close_slope_info} | {above_ma_info} | {hl_info}'
            )
            return False, combined_info
        
        # ============================================================
        # ★检查6: 当前价格相对近期高点的位置
        # ============================================================
        price_position_ok = True
        price_position_info = ''
        
        if len(weekly) >= 20:
            recent_20w = weekly.iloc[-20:]
            highest_high = recent_20w['high'].max()
            latest_close = weekly.iloc[-1]['close']
            
            if highest_high > 0:
                drawdown = (highest_high - latest_close) / highest_high
                
                if drawdown > self.WEEKLY_PRICE_FROM_HIGH_THRESHOLD:
                    price_position_ok = False
                    price_position_info = (
                        f'价格偏离高点: 当前{latest_close:.2f}距20周高点{highest_high:.2f}'
                        f'下跌{drawdown*100:.1f}%>{self.WEEKLY_PRICE_FROM_HIGH_THRESHOLD*100:.0f}%'
                    )
                else:
                    price_position_info = (
                        f'价格位置正常: 距20周高点回落{drawdown*100:.1f}%'
                        f'≤{self.WEEKLY_PRICE_FROM_HIGH_THRESHOLD*100:.0f}%'
                    )
        
        # ★ 检查6为硬性条件：价格距高点过远直接排除
        if not price_position_ok:
            combined_info = (
                f'★硬性排除-{price_position_info} | '
                f'{ma_slope_info} | {close_slope_info} | '
                f'{above_ma_info} | {hl_info} | {ma_arrangement_info}'
            )
            return False, combined_info
        
        # ============================================================
        # 综合判断（检查2/3/4: 要求向上，任意一项不通过即排除）
        # ============================================================
        soft_checks = {
            'close_slope': close_slope_ok,
            'above_ma': above_ma_ok,
            'hl_trend': hl_ok,
        }
        
        soft_fail_count = sum(1 for v in soft_checks.values() if not v)
        soft_fail_names = [k for k, v in soft_checks.items() if not v]
        
        is_not_uptrend = False
        fail_reasons = []
        
        # ★★★ 要求向上: 任意一项软性检查不通过即排除 ★★★
        if soft_fail_count >= 1:
            is_not_uptrend = True
            fail_reasons.append(
                f'软性检查{soft_fail_count}/3项不通过: {", ".join(soft_fail_names)}'
            )
        
        if is_not_uptrend:
            combined_info = (
                f'★周线未达上升趋势标准(已排除): {"; ".join(fail_reasons)} | '
                f'{ma_slope_info} | {close_slope_info} | '
                f'{above_ma_info} | {hl_info} | '
                f'{ma_arrangement_info} | {price_position_info}'
            )
            return False, combined_info
        else:
            combined_info = (
                f'周线上升趋势确认OK: {ma_slope_info} | {close_slope_info} | '
                f'{above_ma_info} | {hl_info} | '
                f'{ma_arrangement_info} | {price_position_info}'
            )
            return True, combined_info
    
    def score(self, df: pd.DataFrame, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        陈凯三周期收敛图评分
        """
        if not pattern_data['is_valid']:
            return self._get_zero_score(pattern_data['fail_reason'])
        
        # ============================================================
        # ★★★ 周线趋势硬性排除 ★★★
        # ============================================================
        weekly_trend_ok = pattern_data.get('weekly_trend_ok', True)
        weekly_trend_info = pattern_data.get('weekly_trend_info', '')
        
        if not weekly_trend_ok:
            return self._get_zero_score(
                f'周线非上升趋势排除: {weekly_trend_info}',
                weekly_downtrend=True
            )
        
        weekly_data = pattern_data['weekly_data']
        daily_data = pattern_data['daily_data']
        
        # === 评分项1: 收敛起点识别(15分) ===
        score1_result = self._score_convergence_start(weekly_data, daily_data)
        
        # === 评分项2: 交替高低点结构(25分) ===
        score2_result = self._score_alternating_structure(daily_data)
        
        if not score2_result.get('is_valid', False):
            return {
                'total': score1_result['score'],
                'dim1_score': score1_result['score'],
                'dim2_score': 0,
                'dim3_score': 0,
                'dim1_details': score1_result,
                'dim2_details': score2_result,
                'dim3_details': {'score': 0},
                'pattern_features': score2_result.get('features', {}),
                'weekly_trend_info': weekly_trend_info
            }
        
        # ============================================================
        # ★★★ 关键过滤: 检查H3时效性 ★★★
        # ============================================================
        h3_age = score2_result.get('features', {}).get('h3_age_days', 999)
        if h3_age > self.H3_MAX_AGE_DAYS:
            fail_reason = (
                f'H3不够新鲜: 距最新交易日{h3_age}天 > 阈值{self.H3_MAX_AGE_DAYS}天，'
                f'已过最佳介入窗口'
            )
            return {
                'total': score1_result['score'] + score2_result['score'],
                'dim1_score': score1_result['score'] + score2_result['score'],
                'dim2_score': 0,
                'dim3_score': 0,
                'dim1_details': {
                    'total': score1_result['score'] + score2_result['score'],
                    'convergence_start': score1_result['score'],
                    'structure': score2_result['score'],
                    'details': {
                        **score1_result.get('details', {}),
                        **score2_result.get('details', {}),
                        'h3_freshness': fail_reason
                    }
                },
                'dim2_details': {'total': 0, 'reason': fail_reason},
                'dim3_details': {'total': 0, 'reason': fail_reason},
                'pattern_features': score2_result.get('features', {}),
                'h3_too_old': True,
                'weekly_trend_info': weekly_trend_info
            }
        
        # === 评分项3: 有序波动验证(25分) ===
        score3_result = self._score_ordered_fluctuation(score2_result)
        
        # === 评分项4: 量能收缩验证(20分) ===
        score4_result = self._score_volume_contraction(daily_data, score2_result)
        
        # === 评分项5: 技术指标确认(15分) ===
        score5_result = self._score_technical_indicators(daily_data)
        
        # === 评分项6: 提前识别机制(10分) ===
        score6_result = self._score_early_recognition(daily_data, score2_result)
        
        # === 计算总分 ===
        total_score = (
            score1_result['score'] +
            score2_result['score'] +
            score3_result['score'] +
            score4_result['score'] +
            score5_result['score'] +
            score6_result['score']
        )
        
        all_details = {
            **score1_result.get('details', {}),
            **score2_result.get('details', {}),
            **score3_result.get('details', {}),
            **score4_result.get('details', {}),
            **score5_result.get('details', {}),
            **score6_result.get('details', {})
        }
        #print(all_details)
        return {
            'total': round(total_score, 1),
            'dim1_score': score1_result['score'] + score2_result['score'],
            'dim2_score': score3_result['score'] + score4_result['score'],
            'dim3_score': score5_result['score'] + score6_result['score'],
            'dim1_details': {
                'total': score1_result['score'] + score2_result['score'],
                'convergence_start': score1_result['score'],
                'structure': score2_result['score'],
                'details': all_details
            },
            'dim2_details': {
                'total': score3_result['score'] + score4_result['score'],
                'fluctuation': score3_result['score'],
                'volume': score4_result['score'],
                'details': all_details,
                'debug_peaks': score2_result.get('debug_peaks', {}),
                'debug_troughs': score2_result.get('debug_troughs', {})
            },
            'dim3_details': {
                'total': score5_result['score'] + score6_result['score'],
                'technical': score5_result['score'],
                'early_recognition': score6_result['score'],
                'details': all_details
            },
            'pattern_features': score2_result.get('features', {}),
            'h3_too_old': False,
            'weekly_trend_info': weekly_trend_info
        }
    
    def _score_convergence_start(self, weekly, daily):
        """
        评分项1: 收敛起点识别(15分)
        
        核心逻辑:
        1. 在周线上找到一个显著高点（顶分型）
        2. 验证该高点之前存在一段明确的上涨趋势
        3. 验证该高点之后进入收敛（波动收窄、价格横盘）
        """
        score = 0
        details = {}

        if len(weekly) < 20 or len(daily) < 60:
            return {'score': 0, 'details': {'convergence_start': '数据不足'}}

        # === Step 1: 找候选高点（周线顶分型）===
        weekly = weekly.copy()
        weekly['is_top'] = indicators.identify_top_fractal(weekly)
        top_weeks = weekly[weekly['is_top'] == 1]

        if len(top_weeks) == 0:
            return {'score': 0, 'details': {'convergence_start': '无周线顶分型'}}

        # 取最近的几个顶分型，逐一检验
        candidates = top_weeks.iloc[-3:]  # 最多检查最近3个

        best_score = 0
        best_details = {}
        best_peak_date = None

        for peak_date in reversed(candidates.index):
            peak_price = weekly.loc[peak_date, 'high']
            peak_pos = weekly.index.get_loc(peak_date)

            # === Step 2: 验证高点之前存在上涨趋势 ===
            # 取高点之前的一段周线（比如8~15周）
            lookback = min(peak_pos, 12)
            if lookback < 6:
                continue

            pre_trend = weekly.iloc[peak_pos - lookback: peak_pos + 1]
            
            # 上涨趋势判定：
            # (a) 起点到终点有明显涨幅
            trend_start_price = pre_trend['low'].iloc[:3].min()
            trend_end_price = peak_price
            if trend_start_price <= 0:
                continue
            trend_gain = (trend_end_price - trend_start_price) / trend_start_price

            # (b) 用线性回归斜率确认趋势方向
            closes = pre_trend['close'].values
            x = np.arange(len(closes))
            slope = np.polyfit(x, closes, 1)[0]
            normalized_slope = slope / np.mean(closes)

            # 要求：涨幅 >= 10% 且 斜率为正
            if trend_gain < 0.10 or normalized_slope <= 0:
                continue  # 不是上涨趋势，跳过这个候选

            # === Step 3: 验证高点之后进入收敛 ===
            post_data_weekly = weekly.iloc[peak_pos:]
            if len(post_data_weekly) < 3:
                continue

            # 收敛判定：高点之后的价格不再创新高，且波动收窄
            post_high = post_data_weekly['high'].max()
            # 允许微幅突破（2%以内）
            if post_high > peak_price * 1.02:
                continue  # 还在涨，不是收敛起点

            # 波动率对比
            pre_vol = pre_trend['close'].std() / pre_trend['close'].mean()
            post_vol = post_data_weekly['close'].std() / post_data_weekly['close'].mean()

            if post_vol > pre_vol * 0.9:
                # 波动没有明显收窄
                vol_score = 0
            elif post_vol > pre_vol * 0.7:
                vol_score = 8
            else:
                vol_score = 15

            if vol_score > best_score:
                best_score = vol_score
                best_peak_date = peak_date
                best_details = {
                    'convergence_start': (
                        f'上涨趋势+{trend_gain*100:.1f}% → '
                        f'高点{peak_date.strftime("%Y-%m-%d")} → '
                        f'波动率降至{post_vol/pre_vol*100:.0f}%'
                    )
                }

        if best_score == 0 and not best_details:
            best_details = {'convergence_start': '未找到"上涨趋势结束高点+收敛"的组合'}

        return {'score': best_score, 'details': best_details}
    
    def _score_alternating_structure(self, daily: pd.DataFrame) -> Dict[str, Any]:
        """
        评分项2: 交替高低点结构(25分)
        
        时间顺序: H1(最早) → L1 → H2 → L2 → H3(最新)
        
        核心验证:
        1. 数量: 至少3高2低
        2. 交替: H-L-H-L-H 严格交替
        3. 错落有致:
            - 高点收敛: H1 >= H2 >= H3
            - 低点抬升: L2 >= L1
            - 振幅收窄: 后段振幅 < 前段振幅
            - 每段波动有意义（排除噪音）
        """
        score = 0
        details = {}
        features = {}

        if len(daily) < 35:
            return {
                'score': 0, 'is_valid': False,
                'details': {'structure': '数据不足'}, 'features': {}
            }

        recent = daily.iloc[-35:].copy()
        latest_date = daily.index[-1]

        peaks_data = recent[recent['is_top'] == 1][['high']].copy()
        peaks_data['date'] = peaks_data.index

        troughs_data = recent[recent['is_bottom'] == 1][['low']].copy()
        troughs_data['date'] = troughs_data.index

        peak_count = len(peaks_data)
        trough_count = len(troughs_data)

        features['peak_count'] = peak_count
        features['trough_count'] = trough_count
        features['latest_date'] = (
            str(latest_date.date()) if hasattr(latest_date, 'date') else str(latest_date)
        )

        features['all_peaks'] = peaks_data['high'].tolist()
        features['all_peak_dates'] = [
            str(d.date()) if hasattr(d, 'date') else str(d)
            for d in peaks_data['date']
        ]
        features['all_troughs'] = troughs_data['low'].tolist()
        features['all_trough_dates'] = [
            str(d.date()) if hasattr(d, 'date') else str(d)
            for d in troughs_data['date']
        ]

        if peak_count < 3 or trough_count < 2:
            return {
                'score': 0, 'is_valid': False,
                'details': {
                    'structure': (
                        f'高低点不足(需3高2低，当前H{peak_count}L{trough_count})'
                    )
                },
                'features': features
            }

        # === 合并所有高低点 ===
        all_points = []
        for i in range(peak_count):
            all_points.append({
                'type': 'H',
                'value': peaks_data['high'].iloc[i],
                'date': peaks_data['date'].iloc[i],
            })
        for i in range(trough_count):
            all_points.append({
                'type': 'L',
                'value': troughs_data['low'].iloc[i],
                'date': troughs_data['date'].iloc[i],
            })
        all_points.sort(key=lambda x: x['date'])

        # === 构建严格交替序列 ===
        alternating_points = self._build_alternating_sequence(all_points)

        # === 优先选择H3最新的序列 ===
        best_sequence = self._find_best_hlhlh_in_alternating(
            alternating_points, latest_date
        )

        if best_sequence is None:
            # 补充逻辑: 检查准H3
            proto_result = self._check_proto_h3(alternating_points, daily, latest_date)
            if proto_result is not None:
                return proto_result

            return {
                'score': 0, 'is_valid': False,
                'details': {'structure': '未找到H1→L1→H2→L2→H3严格交替序列'},
                'features': features
            }

        h1_point, l1_point, h2_point, l2_point, h3_point = best_sequence

        h1, h1_date = h1_point['value'], h1_point['date']
        l1, l1_date = l1_point['value'], l1_point['date']
        h2, h2_date = h2_point['value'], h2_point['date']
        l2, l2_date = l2_point['value'], l2_point['date']
        h3, h3_date = h3_point['value'], h3_point['date']

        # === 时间顺序验证 ===
        if not (h1_date < l1_date < h2_date < l2_date < h3_date):
            return {
                'score': 0, 'is_valid': False,
                'details': {'structure': '时间顺序验证失败'},
                'features': features
            }

        # === 计算H3的"年龄" ===
        h3_age_days = (latest_date - h3_date).days
        h3_idx = daily.index.get_loc(h3_date) if h3_date in daily.index else None
        latest_idx = len(daily) - 1
        if h3_idx is not None:
            h3_age_trading_days = latest_idx - h3_idx
        else:
            h3_age_trading_days = h3_age_days

        # === 填充features ===
        features['h1'] = h1
        features['h2'] = h2
        features['h3'] = h3
        features['l1'] = l1
        features['l2'] = l2
        features['h1_date'] = str(h1_date.date()) if hasattr(h1_date, 'date') else str(h1_date)
        features['h2_date'] = str(h2_date.date()) if hasattr(h2_date, 'date') else str(h2_date)
        features['h3_date'] = str(h3_date.date()) if hasattr(h3_date, 'date') else str(h3_date)
        features['l1_date'] = str(l1_date.date()) if hasattr(l1_date, 'date') else str(l1_date)
        features['l2_date'] = str(l2_date.date()) if hasattr(l2_date, 'date') else str(l2_date)
        features['h3_age_days'] = h3_age_days
        features['h3_age_trading_days'] = h3_age_trading_days
        features['is_proto_h3'] = False

        features['selected_sequence'] = [
            {'type': 'H1', 'date': features['h1_date'], 'value': h1},
            {'type': 'L1', 'date': features['l1_date'], 'value': l1},
            {'type': 'H2', 'date': features['h2_date'], 'value': h2},
            {'type': 'L2', 'date': features['l2_date'], 'value': l2},
            {'type': 'H3', 'date': features['h3_date'], 'value': h3},
        ]

        # ================================================================
        # ★★★ 核心: "错落有致"价格结构验证 ★★★
        # ================================================================

        tolerance = 0.02  # 允许2%的微幅偏差

        # --- 1. 高点收敛: H1 >= H2 >= H3 ---
        h_converging = (
            h1 * (1 + tolerance) >= h2
            and h2 * (1 + tolerance) >= h3
        )

        features['h_converging'] = h_converging
        features['h1_vs_h2_pct'] = ((h2 - h1) / h1 * 100) if h1 > 0 else 0
        features['h2_vs_h3_pct'] = ((h3 - h2) / h2 * 100) if h2 > 0 else 0

        # --- 2. 低点抬升: L2 >= L1 ---
        l_rising = l2 >= l1 * (1 - tolerance)

        features['l_rising'] = l_rising
        features['l1_vs_l2_pct'] = ((l2 - l1) / l1 * 100) if l1 > 0 else 0

        # --- 3. 振幅收窄 ---
        # 第一个波段振幅: H1到L1、L1到H2 中取较大的作为前段代表
        # 第二个波段振幅: H2到L2、L2到H3 中取较大的作为后段代表
        ref_price = h1 if h1 > 0 else 1  # 归一化基准

        amp_h1_l1 = abs(h1 - l1) / ref_price
        amp_l1_h2 = abs(h2 - l1) / ref_price
        amp_h2_l2 = abs(h2 - l2) / ref_price
        amp_l2_h3 = abs(h3 - l2) / ref_price

        range_first = max(amp_h1_l1, amp_l1_h2)   # 前半段最大振幅
        range_second = max(amp_h2_l2, amp_l2_h3)  # 后半段最大振幅

        narrowing = range_second < range_first

        features['range_first_pct'] = round(range_first * 100, 2)
        features['range_second_pct'] = round(range_second * 100, 2)
        features['narrowing'] = narrowing

        # 也计算整体收敛区间宽度
        overall_range_1 = (max(h1, h2) - min(l1, l2)) / ref_price  # 前段区间
        overall_range_2 = (max(h2, h3) - min(l1, l2)) / ref_price  # 后段区间（包含重叠）
        # 更直接: H到L的带宽
        bandwidth_first = (h1 - l1) / ref_price
        bandwidth_second = (h3 - l2) / ref_price
        bandwidth_narrowing = bandwidth_second < bandwidth_first

        features['bandwidth_first_pct'] = round(bandwidth_first * 100, 2)
        features['bandwidth_second_pct'] = round(bandwidth_second * 100, 2)
        features['bandwidth_narrowing'] = bandwidth_narrowing

        # --- 4. 最小波动阈值（排除噪音）---
        min_swing_threshold = 0.015  # 每段至少1.5%的波动

        swing_h1_l1 = (h1 - l1) / h1 if h1 > 0 else 0
        swing_l1_h2 = (h2 - l1) / l1 if l1 > 0 else 0
        swing_h2_l2 = (h2 - l2) / h2 if h2 > 0 else 0
        swing_l2_h3 = (h3 - l2) / l2 if l2 > 0 else 0

        all_swings = [swing_h1_l1, swing_l1_h2, swing_h2_l2, swing_l2_h3]
        meaningful_swings = all(s >= min_swing_threshold for s in all_swings)
        min_swing_actual = min(all_swings)

        features['swings'] = {
            'H1→L1': round(swing_h1_l1 * 100, 2),
            'L1→H2': round(swing_l1_h2 * 100, 2),
            'H2→L2': round(swing_h2_l2 * 100, 2),
            'L2→H3': round(swing_l2_h3 * 100, 2),
        }
        features['meaningful_swings'] = meaningful_swings
        features['min_swing_pct'] = round(min_swing_actual * 100, 2)

        # ================================================================
        # ★★★ 综合评分 ★★★
        # ================================================================

        # 先检查噪音
        if not meaningful_swings:
            details['structure'] = (
                f'高低点波动幅度过小(最小{min_swing_actual*100:.1f}%<{min_swing_threshold*100:.1f}%)，'
                f'可能是噪音而非有序结构'
            )
            return {
                'score': 0, 'is_valid': False,
                'details': details, 'features': features,
                'debug_peaks': {
                    'values': features['all_peaks'],
                    'dates': features['all_peak_dates']
                },
                'debug_troughs': {
                    'values': features['all_troughs'],
                    'dates': features['all_trough_dates']
                }
            }

        # 结构评分（最高25分）
        structure_score = 0
        structure_notes = []

        # (A) 交替序列基础分: 找到H-L-H-L-H = 10分
        structure_score += 10
        structure_notes.append('H-L-H-L-H交替序列✓')

        # (B) 高点收敛: +5分
        if h_converging:
            structure_score += 5
            structure_notes.append(
                f'高点收敛✓(H1={h1:.2f}≥H2={h2:.2f}≥H3={h3:.2f})'
            )
        else:
            structure_notes.append(
                f'高点未收敛✗(H1={h1:.2f},H2={h2:.2f},H3={h3:.2f})'
            )

        # (C) 低点抬升: +4分
        if l_rising:
            structure_score += 4
            structure_notes.append(
                f'低点抬升✓(L1={l1:.2f}≤L2={l2:.2f})'
            )
        else:
            structure_notes.append(
                f'低点未抬升✗(L1={l1:.2f},L2={l2:.2f})'
            )

        # (D) 振幅收窄: +3分
        if narrowing or bandwidth_narrowing:
            structure_score += 3
            structure_notes.append(
                f'振幅收窄✓({features["range_first_pct"]}%→{features["range_second_pct"]}%)'
            )
        else:
            structure_notes.append(
                f'振幅未收窄✗({features["range_first_pct"]}%→{features["range_second_pct"]}%)'
            )

        # (E) 时间间隔合理性: +3分
        h1_l1_days = (l1_date - h1_date).days
        l1_h2_days = (h2_date - l1_date).days
        h2_l2_days = (l2_date - h2_date).days
        l2_h3_days = (h3_date - l2_date).days

        features['h1_l1_days'] = h1_l1_days
        features['l1_h2_days'] = l1_h2_days
        features['h2_l2_days'] = h2_l2_days
        features['l2_h3_days'] = l2_h3_days

        min_interval = min(h1_l1_days, l1_h2_days, h2_l2_days, l2_h3_days)
        convergence_days = (h3_date - h1_date).days
        features['convergence_days'] = convergence_days

        if min_interval >= 2 and 10 <= convergence_days <= 45:
            structure_score += 3
            structure_notes.append(
                f'周期合理✓(总{convergence_days}天,最短间隔{min_interval}天)'
            )
        elif min_interval >= 1:
            structure_score += 1
            structure_notes.append(
                f'周期偏离✗(总{convergence_days}天,最短间隔{min_interval}天)'
            )
        else:
            structure_notes.append(
                f'间隔不足✗(最短间隔{min_interval}天)'
            )

        # 封顶25分
        score = min(structure_score, 25)

        # 判定是否为有效结构（至少满足交替+高点收敛或低点抬升之一）
        is_valid = (score >= 14) and (h_converging or l_rising)

        # 构建详情字符串
        details['structure'] = (
            f'{" | ".join(structure_notes)} | '
            f'H3距今{h3_age_trading_days}个交易日'
        )

        # 额外: 如果高点完全不收敛且低点也不抬升，标记为杂乱波动
        if not h_converging and not l_rising:
            details['structure'] = (
                f'高低点无序(高点不收敛且低点不抬升)，不构成收敛结构 | '
                f'H1={h1:.2f},H2={h2:.2f},H3={h3:.2f} | '
                f'L1={l1:.2f},L2={l2:.2f}'
            )
            is_valid = False
            score = min(score, 10)  # 最多只给交替基础分

        return {
            'score': score, 'is_valid': is_valid,
            'details': details, 'features': features,
            'debug_peaks': {
                'values': features['all_peaks'],
                'dates': features['all_peak_dates']
            },
            'debug_troughs': {
                'values': features['all_troughs'],
                'dates': features['all_trough_dates']
            }
        }
    
    def _check_proto_h3(
        self,
        alternating: List[Dict],
        daily: pd.DataFrame,
        latest_date
    ) -> Optional[Dict[str, Any]]:
        """
        检查"准H3"模式
        """
        n = len(alternating)
        if n < 4:
            return None
        
        # 从后往前找 H-L-H-L 序列
        for i in range(n - 4, -1, -1):
            window = alternating[i:i+4]
            types = [p['type'] for p in window]
            
            if types != ['H', 'L', 'H', 'L']:
                continue
            
            h1_p, l1_p, h2_p, l2_p = window
            
            if not (h1_p['date'] < l1_p['date'] < h2_p['date'] < l2_p['date']):
                continue
            
            # 检查L2之后的价格走势
            l2_date = l2_p['date']
            if l2_date not in daily.index:
                continue
            
            l2_idx = daily.index.get_loc(l2_date)
            latest_idx = len(daily) - 1
            
            if latest_idx - l2_idx < 2:
                continue
            
            latest_close = daily.iloc[-1]['close']
            latest_high = daily.iloc[-1]['high']
            l2_val = l2_p['value']
            h1_val = h1_p['value']
            h2_val = h2_p['value']
            
            if latest_close <= l2_val:
                continue
            
            h_avg = (h1_val + h2_val) / 2
            h_min = min(h1_val, h2_val)
            l_avg = (l2_val + l1_p['value']) / 2
            price_range = h_avg - l_avg
            
            if price_range <= 0:
                continue
            
            current_position = (latest_high - l_avg) / price_range
            if current_position < 0.6:
                continue
            
            features = {
                'h1': h1_val,
                'h2': h2_val,
                'h3': latest_high,
                'l1': l1_p['value'],
                'l2': l2_val,
                'h1_date': str(h1_p['date'].date()) if hasattr(h1_p['date'], 'date') else str(h1_p['date']),
                'h2_date': str(h2_p['date'].date()) if hasattr(h2_p['date'], 'date') else str(h2_p['date']),
                'h3_date': str(latest_date.date()) if hasattr(latest_date, 'date') else str(latest_date),
                'l1_date': str(l1_p['date'].date()) if hasattr(l1_p['date'], 'date') else str(l1_p['date']),
                'l2_date': str(l2_p['date'].date()) if hasattr(l2_p['date'], 'date') else str(l2_p['date']),
                'h3_age_days': 0,
                'h3_age_trading_days': 0,
                'is_proto_h3': True,
                'proto_h3_position': round(current_position, 2),
                'convergence_days': (latest_date - h1_p['date']).days,
                'peak_count': 2,
                'trough_count': 2,
                'all_peaks': [],
                'all_peak_dates': [],
                'all_troughs': [],
                'all_trough_dates': [],
            }
            
            convergence_days = features['convergence_days']
            
            score = 15
            
            if 10 <= convergence_days <= 30:
                score += 3
            
            details = {
                'structure': (
                    f'★准H3模式: H1→L1→H2→L2已确认，'
                    f'当前价格从L2反弹至{current_position*100:.0f}%位置，'
                    f'疑似正在形成H3，周期{convergence_days}天'
                )
            }
            
            features['selected_sequence'] = [
                {'type': 'H1', 'date': features['h1_date'], 'value': h1_val},
                {'type': 'L1', 'date': features['l1_date'], 'value': l1_p['value']},
                {'type': 'H2', 'date': features['h2_date'], 'value': h2_val},
                {'type': 'L2', 'date': features['l2_date'], 'value': l2_val},
                {'type': 'H3(准)', 'date': features['h3_date'], 'value': latest_high},
            ]
            
            features['h1_l1_days'] = (l1_p['date'] - h1_p['date']).days
            features['l1_h2_days'] = (h2_p['date'] - l1_p['date']).days
            features['h2_l2_days'] = (l2_p['date'] - h2_p['date']).days
            features['l2_h3_days'] = (latest_date - l2_p['date']).days
            
            return {
                'score': score, 'is_valid': True,
                'details': details, 'features': features,
                'debug_peaks': {}, 'debug_troughs': {}
            }
        
        return None
    
    def _build_alternating_sequence(self, all_points: List[Dict]) -> List[Dict]:
        """
        将按时间排序的高低点序列转换为严格交替序列。
        """
        if not all_points:
            return []
        
        alternating = []
        buffer = [all_points[0]]
        
        for i in range(1, len(all_points)):
            current = all_points[i]
            if current['type'] == buffer[0]['type']:
                buffer.append(current)
            else:
                representative = self._select_representative(buffer)
                alternating.append(representative)
                buffer = [current]
        
        if buffer:
            representative = self._select_representative(buffer)
            alternating.append(representative)
        
        return alternating
    
    def _select_representative(self, points: List[Dict]) -> Dict:
        """
        从一组同类型的点中选出代表点。
        """
        if not points:
            return None
        
        point_type = points[0]['type']
        if point_type == 'H':
            return max(points, key=lambda x: x['value'])
        else:
            return min(points, key=lambda x: x['value'])
    
    def _find_best_hlhlh_in_alternating(
        self, alternating: List[Dict], latest_date=None
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, Dict]]:
        """
        在严格交替的序列中搜索最佳的 H-L-H-L-H 子序列。
        优先选择H3尽可能接近最新交易日。
        """
        n = len(alternating)
        if n < 5:
            return None
        
        best_sequence = None
        best_quality = -999
        
        for i in range(n - 5, -1, -1):
            window = alternating[i:i+5]
            
            expected_types = ['H', 'L', 'H', 'L', 'H']
            actual_types = [p['type'] for p in window]
            
            if actual_types != expected_types:
                continue
            
            h1, l1, h2, l2, h3 = window
            
            if not (h1['date'] < l1['date'] < h2['date'] < l2['date'] < h3['date']):
                continue
            
            quality = 0
            
            # H3时效性权重
            if latest_date is not None:
                h3_age = (latest_date - h3['date']).days
                if h3_age == 0:
                    quality += 50
                elif h3_age == 1:
                    quality += 40
                elif h3_age == 2:
                    quality += 30
                elif h3_age == 3:
                    quality += 20
                elif h3_age <= 5:
                    quality += 5
                else:
                    quality -= 20
            
            # 高点收敛
            if h1['value'] >= h2['value'] >= h3['value']:
                quality += 3
            elif h1['value'] >= h2['value'] or h2['value'] >= h3['value']:
                quality += 2
            elif abs(h1['value'] - h3['value']) / max(h1['value'], 1e-10) <= 0.03:
                quality += 2
            else:
                quality += 1
            
            # 低点抬升
            if l2['value'] > l1['value']:
                quality += 3
            elif abs(l2['value'] - l1['value']) / max(l1['value'], 1e-10) <= 0.02:
                quality += 2
            else:
                quality += 1
            
            if quality > best_quality:
                best_quality = quality
                best_sequence = (h1, l1, h2, l2, h3)
        
        return best_sequence
    
    def _score_ordered_fluctuation(
        self, structure_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评分项3: 有序波动验证(25分)
        - 高点收敛(10分): H1/H2/H3基本持平
        - 低点持续抬高(10分): L1 < L2 (< L3)
        - 高低点有序交替(5分): 排除无序波动
        """
        score = 0
        details = {}

        if not structure_result.get('is_valid', False):
            return {'score': 0, 'details': {'fluctuation': '无有效结构'}}

        features = structure_result.get('features', {})
        h1 = features.get('h1', 0)
        h2 = features.get('h2', 0)
        h3 = features.get('h3', 0)
        l1 = features.get('l1', 0)
        l2 = features.get('l2', 0)
        l3 = features.get('l3', 0)

        is_proto = features.get('is_proto_h3', False)

        # --- 1. 高点收敛(10分) ---
        if h1 > 0 and h2 > 0 and h3 > 0:
            h12_diff = abs(h1 - h2) / h1
            h23_diff = abs(h2 - h3) / h2
            max_h_diff = max(h12_diff, h23_diff)

            threshold = 0.05 if is_proto else 0.03

            if max_h_diff <= threshold:
                score += 10
                details['peak_convergence'] = (
                    f'高点收敛(H1→H2偏离{h12_diff * 100:.1f}%, '
                    f'H2→H3偏离{h23_diff * 100:.1f}%, 均≤{threshold * 100:.0f}%)'
                )
            else:
                details['peak_convergence'] = (
                    f'高点偏离过大(最大{max_h_diff * 100:.1f}%>{threshold * 100:.0f}%)'
                )
        elif h1 > 0 and h2 > 0:
            # 只有两个高点时也做初步判断
            h12_diff = abs(h1 - h2) / h1
            threshold = 0.05 if is_proto else 0.03
            if h12_diff <= threshold:
                score += 5
                details['peak_convergence'] = (
                    f'仅两高点,初步收敛(H1→H2偏离{h12_diff * 100:.1f}%≤{threshold * 100:.0f}%)'
                )
            else:
                details['peak_convergence'] = (
                    f'仅两高点,偏离过大({h12_diff * 100:.1f}%>{threshold * 100:.0f}%)'
                )
        else:
            details['peak_convergence'] = '无有效高点'

        # --- 2. 低点持续抬高(10分) ---
        if l1 > 0 and l2 > 0:
            l12_rise = (l2 - l1) / l1

            if l3 > 0:
                # 存在L3时: L3只需 > L2 即可(反身向上)
                l23_rise = (l3 - l2) / l2
                if l2 > l1 * 1.01 and l3 > l2:
                    score += 10
                    details['trough_rise'] = (
                        f'低点持续抬高(L1→L2+{l12_rise * 100:.1f}%, '
                        f'L2→L3+{l23_rise * 100:.1f}%, L3反身向上确认)'
                    )
                elif l2 > l1 * 1.01 and l3 <= l2:
                    score += 5
                    details['trough_rise'] = (
                        f'L1→L2抬高但L3未反身向上'
                        f'(L1→L2+{l12_rise * 100:.1f}%, L2→L3{l23_rise * 100:+.1f}%)'
                    )
                else:
                    details['trough_rise'] = (
                        f'低点未有效抬高(L1→L2变化{l12_rise * 100:.1f}%)'
                    )
            else:
                # 只有L1/L2
                if l2 > l1 * 1.01:
                    score += 10
                    details['trough_rise'] = (
                        f'低点抬高(L2/L1上升{l12_rise * 100:.1f}%≥1%)'
                    )
                else:
                    details['trough_rise'] = (
                        f'低点未有效抬高(L2/L1变化{l12_rise * 100:.1f}%<1%)'
                    )
        else:
            details['trough_rise'] = '无有效低点'

        # --- 3. 高低点有序交替验证(5分) ---
        # 检查时间顺序: H1 → L1 → H2 → L2 → (H3) → (L3) 交替出现
        date_keys = ['h1_date', 'l1_date', 'h2_date', 'l2_date', 'h3_date', 'l3_date']
        date_values = []
        for key in date_keys:
            d = features.get(key, '')
            if d:
                date_values.append((key, pd.to_datetime(d)))

        if len(date_values) >= 4:
            is_ordered = True
            for i in range(1, len(date_values)):
                if date_values[i][1] <= date_values[i - 1][1]:
                    is_ordered = False
                    break

            # 还要验证高低交替: H→L→H→L→...
            is_alternating = True
            for i, (key, _) in enumerate(date_values):
                expected_type = 'h' if i % 2 == 0 else 'l'
                if not key.startswith(expected_type):
                    is_alternating = False
                    break

            if is_ordered and is_alternating:
                score += 5
                details['order_check'] = (
                    f'高低点有序交替(共{len(date_values)}个点,时序正确)'
                )
            elif is_ordered:
                score += 2
                details['order_check'] = '时序正确但未严格交替'
            else:
                details['order_check'] = '高低点时序无序,不符合收敛特征'
        else:
            details['order_check'] = f'有效高低点不足(仅{len(date_values)}个)'

        return {'score': score, 'details': details}
    
    def _score_volume_contraction(
        self, daily: pd.DataFrame, structure_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评分项4: 量能收缩验证(20分)
        - 收敛区间量能总体较大,不低于长期均量(5分)
        - 收敛区间内部成交量逐渐递减(8分)
        - 阳线成交量 > 阴线成交量(7分)
        """
        score = 0
        details = {}

        if not structure_result.get('is_valid', False):
            return {'score': 0, 'details': {'volume': '无有效结构'}}

        features = structure_result.get('features', {})
        convergence_days = features.get('convergence_days', 0)

        if convergence_days == 0 or len(daily) < convergence_days + 20:
            return {'score': 0, 'details': {'volume': '数据不足'}}

        convergence_period = daily.iloc[-convergence_days:]
        trend_period = daily.iloc[-(convergence_days + 20):-convergence_days]

        convergence_vol_mean = convergence_period['vol'].mean()
        trend_vol_mean = trend_period['vol'].mean()

        # --- 1. 收敛区间量能总体较大(5分) ---
        # 与长期均量(近250日或可用最长周期)对比,不低于60%说明有交投活跃度
        long_lookback = min(250, len(daily))
        long_term_vol_mean = daily.iloc[-long_lookback:]['vol'].mean()

        if long_term_vol_mean > 0:
            vol_vs_longterm = convergence_vol_mean / long_term_vol_mean
            if vol_vs_longterm >= 0.6:
                score += 5
                details['volume_level'] = (
                    f'区间量能活跃(收敛期/长期均量={vol_vs_longterm * 100:.1f}%≥60%)'
                )
            else:
                details['volume_level'] = (
                    f'区间量能偏低(收敛期/长期均量={vol_vs_longterm * 100:.1f}%<60%)'
                )
        else:
            details['volume_level'] = '长期均量数据无效'

        # --- 2. 收敛区间内部成交量逐渐递减(8分) ---
        if len(convergence_period) >= 6:
            half = len(convergence_period) // 2
            first_half_vol = convergence_period.iloc[:half]['vol'].mean()
            second_half_vol = convergence_period.iloc[half:]['vol'].mean()

            if first_half_vol > 0:
                shrink_ratio = second_half_vol / first_half_vol
                if shrink_ratio < 0.85:
                    score += 8
                    details['volume_trend'] = (
                        f'区间内逐渐缩量(后半段/前半段={shrink_ratio * 100:.1f}%<85%)'
                    )
                elif shrink_ratio < 1.0:
                    score += 4
                    details['volume_trend'] = (
                        f'区间内轻微缩量(后半段/前半段={shrink_ratio * 100:.1f}%)'
                    )
                else:
                    details['volume_trend'] = (
                        f'区间内未缩量(后半段/前半段={shrink_ratio * 100:.1f}%≥100%)'
                    )
            else:
                details['volume_trend'] = '前半段无成交量'
        else:
            details['volume_trend'] = f'收敛区间过短({len(convergence_period)}日),无法判断趋势'

        # --- 3. 阳线成交量 > 阴线成交量(7分) ---
        convergence_period_copy = convergence_period.copy()
        convergence_period_copy['is_up'] = (
            convergence_period_copy['close'] > convergence_period_copy['open']
        )

        up_days = convergence_period_copy[convergence_period_copy['is_up']]
        down_days = convergence_period_copy[~convergence_period_copy['is_up']]

        if len(up_days) > 0 and len(down_days) > 0:
            up_vol_mean = up_days['vol'].mean()
            down_vol_mean = down_days['vol'].mean()

            if down_vol_mean > 0:
                yang_yin_ratio = up_vol_mean / down_vol_mean
                if yang_yin_ratio > 1.0:
                    score += 7
                    details['yang_volume'] = (
                        f'阳线放量(阳/阴={yang_yin_ratio:.2f}>1.0)'
                    )
                else:
                    details['yang_volume'] = (
                        f'阳线未放量(阳/阴={yang_yin_ratio:.2f}≤1.0)'
                    )
            else:
                details['yang_volume'] = '阴线无成交量'
        else:
            details['yang_volume'] = '阳阴线数据不足'

        return {'score': score, 'details': details}
    
    def _score_technical_indicators(self, daily: pd.DataFrame) -> Dict[str, Any]:
        """
        评分项5: 技术指标确认(15分)
        - 收敛区间内均线缠绕且方向趋于一致(8分)
        - 收敛区间内MACD绝对值趋近于0(7分)
        """
        score = 0
        details = {}

        if len(daily) < 20:
            return {'score': 0, 'details': {'technical': '数据不足'}}

        # 取近N日作为收敛区间参考(使用最近20日)
        lookback = min(20, len(daily))
        convergence_window = daily.iloc[-lookback:]

        # --- 1. 均线缠绕 + 方向趋于一致(8分) ---
        ma_cols = ['ma5', 'ma10', 'ma20']
        has_ma = all(col in convergence_window.columns for col in ma_cols)

        if has_ma:
            entangle_scores_list = []
            for _, row in convergence_window.iterrows():
                ma5 = row.get('ma5', 0)
                ma10 = row.get('ma10', 0)
                ma20 = row.get('ma20', 0)
                if ma5 > 0 and ma10 > 0 and ma20 > 0:
                    avg_ma = (ma5 + ma10 + ma20) / 3
                    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / avg_ma
                    entangle_scores_list.append(spread)

            if entangle_scores_list:
                avg_spread = sum(entangle_scores_list) / len(entangle_scores_list)

                # 检查均线方向(斜率)是否趋于一致
                direction_consistent = False
                if len(convergence_window) >= 5:
                    last5 = convergence_window.iloc[-5:]
                    first5 = convergence_window.iloc[:5]

                    slopes = {}
                    for col in ma_cols:
                        end_val = last5[col].mean()
                        start_val = first5[col].mean()
                        if start_val > 0:
                            slopes[col] = (end_val - start_val) / start_val

                    if slopes:
                        slope_values = list(slopes.values())
                        slope_range = max(slope_values) - min(slope_values)
                        # 斜率差异小于2%视为方向一致
                        direction_consistent = slope_range < 0.02

                if avg_spread < 0.03:
                    score += 5
                    details['ma_entangle'] = (
                        f'均线缠绕(区间平均偏离{avg_spread * 100:.2f}%<3%)'
                    )
                elif avg_spread < 0.05:
                    score += 3
                    details['ma_entangle'] = (
                        f'均线初步缠绕(区间平均偏离{avg_spread * 100:.2f}%<5%)'
                    )
                else:
                    details['ma_entangle'] = (
                        f'均线未缠绕(区间平均偏离{avg_spread * 100:.2f}%≥5%)'
                    )

                if direction_consistent:
                    score += 3
                    details['ma_direction'] = (
                        f'均线方向趋于一致(斜率差{slope_range * 100:.2f}%<2%)'
                    )
                else:
                    slope_range_val = slope_range if 'slope_range' in dir() else -1
                    if slope_range_val >= 0:
                        details['ma_direction'] = (
                            f'均线方向未一致(斜率差{slope_range_val * 100:.2f}%≥2%)'
                        )
                    else:
                        details['ma_direction'] = '均线方向数据不足'
            else:
                details['ma_entangle'] = '均线数据无效'
                details['ma_direction'] = '均线数据无效'
        else:
            details['ma_entangle'] = '缺少均线列'
            details['ma_direction'] = '缺少均线列'

        # --- 2. MACD绝对值趋近于0(7分) ---
        has_macd = 'dif' in convergence_window.columns and 'dea' in convergence_window.columns

        if has_macd:
            macd_values = []
            close_values = []
            for _, row in convergence_window.iterrows():
                dif = row.get('dif', None)
                dea = row.get('dea', None)
                close = row.get('close', None)
                if pd.notna(dif) and pd.notna(dea) and pd.notna(close) and close > 0:
                    # 用相对值: (|DIF| + |DEA|) / close
                    relative_macd = (abs(dif) + abs(dea)) / close
                    macd_values.append(relative_macd)
                    close_values.append(close)

            if macd_values:
                avg_relative_macd = sum(macd_values) / len(macd_values)

                # 阈值: 相对值 < 1% 认为钝化, < 2% 初步钝化
                if avg_relative_macd < 0.01:
                    score += 7
                    details['macd_dull'] = (
                        f'MACD充分钝化(区间相对均值{avg_relative_macd * 100:.3f}%<1%)'
                    )
                elif avg_relative_macd < 0.02:
                    score += 4
                    details['macd_dull'] = (
                        f'MACD初步钝化(区间相对均值{avg_relative_macd * 100:.3f}%<2%)'
                    )
                else:
                    details['macd_dull'] = (
                        f'MACD未钝化(区间相对均值{avg_relative_macd * 100:.3f}%≥2%)'
                    )
            else:
                details['macd_dull'] = 'MACD数据无效'
        else:
            details['macd_dull'] = '缺少MACD列'

        return {'score': score, 'details': details}
    
    def _score_early_recognition(
        self, daily: pd.DataFrame, structure_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评分项6: 提前识别机制(10分)
        """
        score = 0
        details = {}

        if not structure_result.get('is_valid', False):
            return {'score': 0, 'details': {'early_recognition': '无有效结构'}}

        features = structure_result.get('features', {})
        is_proto = features.get('is_proto_h3', False)

        if features.get('peak_count', 0) < 2 or features.get('trough_count', 0) < 2:
            if not is_proto:
                return {
                    'score': 0,
                    'details': {'early_recognition': '高低点数量不足'}
                }

        l2_date_str = features.get('l2_date', '')
        if not l2_date_str:
            return {'score': 0, 'details': {'early_recognition': '无法定位L2日期'}}

        try:
            l2_date = pd.to_datetime(l2_date_str)

            if l2_date not in daily.index:
                idx = daily.index.searchsorted(l2_date)
                if idx >= len(daily):
                    return {
                        'score': 0,
                        'details': {'early_recognition': 'L2是最新数据点'}
                    }
            else:
                idx = daily.index.get_loc(l2_date)

            if idx + 2 >= len(daily):
                return {
                    'score': 0,
                    'details': {'early_recognition': 'L2后数据不足2日'}
                }

            l2_close = daily.iloc[idx]['close']
            day1_close = daily.iloc[idx + 1]['close']
            day2_close = daily.iloc[idx + 2]['close']

            if day1_close > l2_close and day2_close > l2_close:
                score = 10
                if is_proto:
                    details['early_recognition'] = (
                        f'★准H3: L2后连续反弹确认'
                        f'(L2:{l2_close:.2f}, D+1:{day1_close:.2f}, D+2:{day2_close:.2f})'
                    )
                else:
                    details['early_recognition'] = (
                        f'L2后连续2日上涨确认'
                        f'(L2:{l2_close:.2f}, D+1:{day1_close:.2f}, D+2:{day2_close:.2f})'
                    )
            else:
                details['early_recognition'] = (
                    f'L2后未连续上涨'
                    f'(L2:{l2_close:.2f}, D+1:{day1_close:.2f}, D+2:{day2_close:.2f})'
                )

        except Exception as e:
            details['early_recognition'] = f'处理异常: {str(e)}'

        return {'score': score, 'details': details}
    
    def _get_zero_score(self, reason: str, weekly_downtrend: bool = False) -> Dict[str, Any]:
        """返回零分结果"""
        return {
            'total': 0,
            'dim1_score': 0,
            'dim2_score': 0,
            'dim3_score': 0,
            'dim1_details': {'total': 0, 'reason': reason},
            'dim2_details': {'total': 0, 'reason': reason},
            'dim3_details': {'total': 0, 'reason': reason},
            'pattern_features': {},
            'h3_too_old': True,
            'weekly_downtrend': weekly_downtrend,
            'weekly_trend_info': reason if weekly_downtrend else ''
        }