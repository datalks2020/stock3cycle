"""
陈凯三周期选股系统 - 配置文件
基于可程序化股票收敛形态量化评分表
"""
import os
import logging
from dataclasses import dataclass

# ==================== 系统配置 ====================
try:
    from dotenv import load_dotenv
    load_dotenv()
    TS_TOKEN = os.getenv('TUSHARE_TOKEN')
except ImportError:
    TS_TOKEN = os.getenv('TUSHARE_TOKEN')

if not TS_TOKEN:
    raise ValueError("未找到Tushare Token配置!")

DB_PATH = f'sqlite:///{os.path.join(os.getcwd(), "stock_data.db")}'
OUTPUT_DIR = os.path.join(os.getcwd(), 'results')
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(OUTPUT_DIR, 'system.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ==================== 基础筛选配置 ====================
@dataclass
class BasicFilterConfig:
    """基础硬性筛选条件"""
    MIN_LIST_DAYS: int = 730        # 最少上市天数
    MIN_CIRC_MV: float = 50.0       # 最小流通市值(亿)
    MIN_TURNOVER_20: float = 3.0    # 最小20日平均换手率

# ==================== 陈凯三周期收敛图配置 ====================
@dataclass
class ChenKaiConvergenceConfig:
    """
    陈凯三周期收敛图形态参数
    基于新评分表标准
    """
    
    # 周期定义
    WEEKLY_DAYS: int = 7            # 周线周期定义(天)
    WEEKLY_MA_PERIOD: int = 20      # 周线均线周期
    DAILY_MA_PERIOD: int = 20       # 日线均线周期
    
    # 中周期收敛图时间范围
    MIN_CONVERGENCE_DAYS: int = 10  # 收敛期最少天数
    MAX_CONVERGENCE_DAYS: int = 25  # 收敛期最多天数
    
    # 高低点识别参数
    FRACTAL_WINDOW: int = 3         # 分型识别窗口(3根K线)
    
    # 评分项1: 收敛起点识别
    VOLATILITY_RATIO: float = 0.6   # 收敛期波动率 ≤ 趋势期的60%
    
    # 评分项3: 有序波动验证
    PEAK_DIFF_RATIO: float = 0.03   # 高点偏离阈值(±3%)
    TROUGH_RISE_RATIO: float = 0.01 # 低点抬高阈值(≥1%)
    TROUGH_RISE_MULT: float = 1.01  # 低点抬高倍数(>1.01)
    
    # 评分项4: 量能收缩验证
    VOL_SHRINK_RATIO: float = 0.5   # 量能收缩阈值(≤50%)
    TREND_PERIOD_DAYS: int = 20     # 趋势期天数(用于量能对比)
    
    # 评分项5: 技术指标确认
    MA_ENTANGLE_RATIO: float = 0.05 # 均线缠绕阈值(<5%)
    MACD_DULL_THRESHOLD: float = 0.5 # MACD钝化阈值(<0.5)
    
    # 评分项6: 提前识别机制
    EARLY_RECOGNITION_DAYS: int = 2  # L1后连续上涨天数

@dataclass
class ChenKaiScoringConfig:
    """
    陈凯三周期评分标准
    新评分体系(总分100分)
    """
    
    # === 评分项1: 收敛起点识别(15分) ===
    SCORE1_TOTAL: int = 15
    
    # === 评分项2: 交替高低点结构(25分) ===
    SCORE2_TOTAL: int = 25
    SCORE2_BASE: int = 20           # 顺序正确基础分
    SCORE2_TIMESPAN: int = 5        # 周期合规加分
    
    # === 评分项3: 有序波动验证(25分) ===
    SCORE3_TOTAL: int = 25
    SCORE3_PEAK_FLAT: int = 10      # 高点持平
    SCORE3_TROUGH_RISE: int = 15    # 低点抬高
    
    # === 评分项4: 量能收缩验证(20分) ===
    SCORE4_TOTAL: int = 20
    SCORE4_VOL_SHRINK: int = 10     # 收敛期量能收缩
    SCORE4_YANG_VOL: int = 10       # 阳线放量
    
    # === 评分项5: 技术指标确认(15分) ===
    SCORE5_TOTAL: int = 15
    SCORE5_MA_ENTANGLE: int = 8     # 均线缠绕
    SCORE5_MACD_DULL: int = 7       # MACD钝化
    
    # === 评分项6: 提前识别机制(10分) ===
    SCORE6_TOTAL: int = 10
    
    # === 兼容旧版字段(用于维度映射) ===
    # 维度1 = 评分项1 + 评分项2 (40分)
    DIM1_TOTAL: int = 40
    DIM1_MA_BULL: int = 15          # 保留，但在新体系中不使用
    DIM1_STRUCTURE: int = 15        # 保留，但在新体系中不使用
    DIM1_VOLUME: int = 10           # 保留，但在新体系中不使用
    
    # 维度2 = 评分项3 + 评分项4 (45分)
    DIM2_TOTAL: int = 45
    DIM2_COUNT: int = 8             # 保留，但在新体系中不使用
    DIM2_PEAK: int = 10             # 保留，但在新体系中不使用
    DIM2_TROUGH: int = 10           # 保留，但在新体系中不使用
    DIM2_AMPLITUDE: int = 8         # 保留，但在新体系中不使用
    DIM2_TIMESPAN: int = 6          # 保留，但在新体系中不使用
    DIM2_VOLUME: int = 8            # 保留，但在新体系中不使用
    
    # 维度3 = 评分项5 + 评分项6 (15分)
    DIM3_TOTAL: int = 15
    DIM3_TREND: int = 6             # 保留，但在新体系中不使用
    DIM3_VOLUME: int = 4            # 保留，但在新体系中不使用
    
    # 以下字段保留用于兼容
    WEEKLY_RECENT_WINDOW: int = 4
    WEEKLY_LONG_WINDOW: int = 12
    TROUGH_STRONG_SCORE: int = 10
    TROUGH_WEAK_SCORE: int = 5
    AMP_TIGHT_SCORE: int = 8
    AMP_LOOSE_SCORE: int = 4
    TIME_OPTIMAL_SCORE: int = 6
    TIME_ACCEPTABLE_SCORE: int = 3
    VOL_STRONG_SCORE: int = 8
    VOL_WEAK_SCORE: int = 4

# ==================== 输出配置 ====================
MIN_TOTAL_SCORE: float = 70         # 选股总分阈值

CSV_COLUMNS = [
    'ts_code', 'name', 'trade_date', 'price', 'industry',
    'circ_mv', 'turnover_avg', 'list_days',
    'total_score', 'dim1_score', 'dim2_score', 'dim3_score',
    'patterns', 'remark'
]

INCLUDE_SCORE_DETAILS: bool = True

if INCLUDE_SCORE_DETAILS:
    CSV_COLUMNS.extend([
        # 维度1细项(兼容字段)
        'dim1_ma_bull', 'dim1_structure', 'dim1_volume',
        # 维度2细项(兼容字段)
        'dim2_count', 'dim2_peak', 'dim2_trough',
        'dim2_amplitude', 'dim2_timespan', 'dim2_volume',
        # 维度3细项(兼容字段)
        'dim3_trend', 'dim3_volume_resonance',
        # 形态特征
        'peak_count', 'trough_count', 'convergence_days',
        'h1', 'h2', 'h3', 'l1', 'l2', 'amplitude_ratio'
    ])

BACKTRACK_DAYS_DAILY: int = 120
BACKTRACK_WEEKS: int = 70

# 实例化配置对象
BasicFilter = BasicFilterConfig()
CKConvergence = ChenKaiConvergenceConfig()
CKScoring = ChenKaiScoringConfig()
