"""
陈凯三周期选股系统 - 配置文件
基于陈凯三周期收敛图标准
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
    """陈凯三周期收敛图形态参数"""
    
    # 周期定义
    WEEKLY_DAYS: int = 7            # 周线周期定义(天)
    WEEKLY_MA_PERIOD: int = 20      # 周线均线周期
    DAILY_MA_PERIOD: int = 20       # 日线均线周期
    
    # 中周期收敛图时间范围
    MIN_CONVERGENCE_DAYS: int = 10  # 收敛期最少天数
    MAX_CONVERGENCE_DAYS: int = 30  # 收敛期最多天数
    OPTIMAL_MIN_DAYS: int = 15      # 最优收敛天数下限
    OPTIMAL_MAX_DAYS: int = 25      # 最优收敛天数上限
    
    # 高低点识别参数
    FRACTAL_WINDOW: int = 3         # 分型识别窗口(3根K线)
    MIN_PEAK_COUNT: int = 3         # 最少高点数量
    MIN_TROUGH_COUNT: int = 2       # 最少低点数量
    
    # 高点特征阈值
    PEAK_UPPER_RATIO: float = 1.03  # 高点上限(H3 ≤ H2 * 1.03)
    PEAK_LOWER_RATIO: float = 0.97  # 高点下限(H3 ≥ H2 * 0.97)
    
    # 低点特征阈值  
    TROUGH_STRONG_RATIO: float = 1.01   # 低点强上移(L2 > L1 * 1.01)
    TROUGH_WEAK_RATIO: float = 1.005    # 低点弱上移(L2 > L1 * 1.005)
    
    # 波动幅度阈值
    AMPLITUDE_TIGHT: float = 0.05   # 紧收敛(<5%)
    AMPLITUDE_LOOSE: float = 0.10   # 宽收敛(<10%)
    
    # 量能萎缩阈值
    VOL_SHRINK_STRONG: float = 0.5  # 强萎缩(<50%)
    VOL_SHRINK_WEAK: float = 0.6    # 弱萎缩(<60%)
    
    # 趋势期参数(用于计算量能对比)
    TREND_PERIOD_DAYS: int = 20     # 趋势期天数(收敛前)

@dataclass
class ChenKaiScoringConfig:
    """陈凯三周期评分标准(总分100分)"""
    
    # === 维度1: 大周期趋势评分(40分) ===
    DIM1_TOTAL: int = 40
    DIM1_MA_BULL: int = 15          # 均线多头
    DIM1_STRUCTURE: int = 15        # 高低点结构
    DIM1_VOLUME: int = 10           # 量能趋势
    
    # 大周期量能计算窗口
    WEEKLY_RECENT_WINDOW: int = 4   # 最近4周
    WEEKLY_LONG_WINDOW: int = 12    # 最近12周
    
    # === 维度2: 中周期收敛形态评分(50分) ===
    DIM2_TOTAL: int = 50
    DIM2_COUNT: int = 8             # 高低点数量
    DIM2_PEAK: int = 10             # 高点特征
    DIM2_TROUGH: int = 10           # 低点特征
    DIM2_AMPLITUDE: int = 8         # 波动幅度
    DIM2_TIMESPAN: int = 6          # 时间跨度
    DIM2_VOLUME: int = 8            # 成交量萎缩
    
    # 低点特征分档
    TROUGH_STRONG_SCORE: int = 10   # 强上移得分
    TROUGH_WEAK_SCORE: int = 5      # 弱上移得分
    
    # 波动幅度分档
    AMP_TIGHT_SCORE: int = 8        # 紧收敛得分
    AMP_LOOSE_SCORE: int = 4        # 宽收敛得分
    
    # 时间跨度分档
    TIME_OPTIMAL_SCORE: int = 6     # 最优时长得分
    TIME_ACCEPTABLE_SCORE: int = 3  # 可接受时长得分
    
    # 量能萎缩分档
    VOL_STRONG_SCORE: int = 8       # 强萎缩得分
    VOL_WEAK_SCORE: int = 4         # 弱萎缩得分
    
    # === 维度3: 大中周期共振评分(10分) ===
    DIM3_TOTAL: int = 10
    DIM3_TREND: int = 6             # 趋势一致性
    DIM3_VOLUME: int = 4            # 量能共振

# ==================== 输出配置 ====================
MIN_TOTAL_SCORE: float = 80         # 选股总分阈值

CSV_COLUMNS = [
    'ts_code', 'name', 'trade_date', 'price', 'industry',
    'circ_mv', 'turnover_avg', 'list_days',
    'total_score', 'dim1_score', 'dim2_score', 'dim3_score',
    'patterns', 'remark'
]

INCLUDE_SCORE_DETAILS: bool = True

if INCLUDE_SCORE_DETAILS:
    CSV_COLUMNS.extend([
        # 维度1细项
        'dim1_ma_bull', 'dim1_structure', 'dim1_volume',
        # 维度2细项
        'dim2_count', 'dim2_peak', 'dim2_trough', 
        'dim2_amplitude', 'dim2_timespan', 'dim2_volume',
        # 维度3细项
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
