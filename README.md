# 陈凯三周期选股系统 - 重构版

## 📋 项目简介

本项目是陈凯三周期选股系统的重构版本，采用模块化插件架构，便于扩展新的形态识别策略。

当前版本只包含**收敛三角形**形态识别，已移除二踩图相关代码。

## 🏗️ 项目结构

```
.
├── config.py              # 配置文件
├── indicators.py          # 技术指标计算
├── strategy.py           # 策略引擎
├── main.py               # 主程序入口
├── db_manager.py         # 数据库管理 (需自行实现)
├── patterns/             # 形态插件包
│   ├── __init__.py
│   ├── base.py          # 形态基类
│   ├── manager.py       # 形态管理器
│   └── triangle.py      # 收敛三角形插件
└── results/             # 输出目录
```

## 🔌 插件化架构

### 核心设计

1. **PatternBase**: 形态基类，定义统一接口
2. **PatternManager**: 形态管理器，负责注册和调度
3. **具体形态插件**: 如 TrianglePattern

### 添加新形态的步骤

假设要添加"箱体突破"形态:

#### 1. 创建形态插件 `patterns/box_break.py`

```python
from patterns.base import PatternBase
import config

class BoxBreakPattern(PatternBase):
    
    def __init__(self):
        # 初始化配置
        pass
    
    def get_name(self) -> str:
        return "箱体突破"
    
    def get_min_score(self) -> float:
        return 60  # 最低分数线
    
    def identify(self, df: pd.DataFrame) -> Dict[str, Any]:
        """识别箱体突破形态"""
        # 实现识别逻辑
        return {
            'is_valid': True/False,
            'fail_reason': '...',
            # 其他形态数据...
        }
    
    def score(self, df: pd.DataFrame, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """评分"""
        # 实现评分逻辑
        return {
            'total': 75,
            'dimension1': 20,
            'dimension2': 30,
            'details': {...}
        }
```

#### 2. 在 `patterns/__init__.py` 中导出

```python
from patterns.box_break import BoxBreakPattern

__all__ = [
    'PatternBase',
    'PatternManager',
    'TrianglePattern',
    'BoxBreakPattern',  # 新增
]
```

#### 3. 在 `strategy.py` 中注册

```python
def _register_patterns(self):
    """注册形态插件"""
    self.pattern_manager.register('triangle', TrianglePattern())
    self.pattern_manager.register('box_break', BoxBreakPattern())  # 新增
```

#### 4. 在 `config.py` 中添加配置(可选)

```python
@dataclass
class BoxBreakPatternConfig:
    """箱体突破形态参数"""
    MIN_DAYS: int = 20
    # 其他参数...

BoxBreakPattern = BoxBreakPatternConfig()
```

#### 5. 更新输出字段(可选)

在 `config.py` 的 `CSV_COLUMNS` 中添加:

```python
CSV_COLUMNS = [
    # ...
    'box_break_score',  # 新增
    # ...
]
```

## 📦 当前包含的形态

### 收敛三角形 (TrianglePattern)

**识别条件:**
- 至少25天数据
- 高点数量≥2, 低点数量≥2
- 完整形态: 3高2低 (30分)
- 准形态: 2高2低 (20分)

**评分维度 (满分100):**
- 结构 (30分): 形态完整性
- 高低点 (25分): 高点变化 + 低点上移
- 振幅 (20分): 振幅收窄程度
- 量能 (15分): 量能缩减趋势
- 收敛末端 (10分): 收敛度

**最低分数线:** 60分

## 🚀 使用方法

### 基本使用

```bash
# 今天选股
python main.py

# 指定日期选股
python main.py 20240115
```

### 编程接口

```python
from strategy import StrategyEngine
import pandas as pd

# 加载数据
df_data = load_your_data()

# 执行选股
engine = StrategyEngine(df_data, '20240115')
result_df = engine.run()

# 查看结果
print(result_df.head())
```

## 📊 输出文件

选股完成后会在 `results/` 目录生成:

- `选股结果_YYYYMMDD.csv`: 完整结果
- `选股结果_YYYYMMDD.xlsx`: Excel格式
- `system.log`: 运行日志

## ⚙️ 配置说明

### 基础筛选条件 (BasicFilterConfig)

```python
MIN_LIST_DAYS = 730        # 最少上市天数
MIN_CIRC_MV = 50.0         # 最小流通市值(亿)
MIN_TURNOVER_20 = 3.0      # 最小20日平均换手率
NEED_ABOVE_MA20 = True     # 需要在MA20附近
NEED_ABOVE_MA60_WEEKLY = True  # 周线需要在MA60附近
```

### 收敛三角形配置 (TrianglePatternConfig)

```python
MIN_DAYS = 25              # 最少天数
PEAK_TROUGH_WINDOW = 5     # 高低点识别窗口
ALLOW_QUASI_PATTERN = True # 允许准形态
```

## 🔍 扩展示例

### 添加二踩图形态

```python
# patterns/double_dip.py
class DoubleDipPattern(PatternBase):
    def get_name(self) -> str:
        return "二踩图"
    
    def identify(self, df: pd.DataFrame) -> Dict[str, Any]:
        # 识别逻辑
        pass
    
    def score(self, df: pd.DataFrame, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        # 评分逻辑
        pass
```

## 📝 注意事项

1. **数据库依赖**: 需要实现 `db_manager.py` 的 `DBManager` 类
2. **数据格式**: DataFrame需包含以下字段:
   - ts_code, name, trade_date, open, high, low, close, vol
   - turnover_rate, circ_mv, list_date, industry
3. **环境变量**: 需设置 `TUSHARE_TOKEN` 环境变量

## 🛠️ 依赖包

```bash
pip install pandas numpy tqdm python-dotenv openpyxl
```

## 📄 许可证

MIT License

## 👥 贡献

欢迎提交 Issue 和 Pull Request!
