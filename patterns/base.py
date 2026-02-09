"""
形态基类 - 定义形态识别与评分的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class PatternBase(ABC):
    """
    形态基类 - 所有形态插件必须继承此类
    
    形态插件需要实现:
    1. identify() - 形态识别
    2. score() - 形态评分
    3. get_min_score() - 最低分数线
    4. get_name() - 形态名称
    """
    
    @abstractmethod
    def identify(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        识别形态
        
        Args:
            df: 股票历史数据
            
        Returns:
            dict: 识别结果
                - is_valid: bool, 是否识别到有效形态
                - fail_reason: str, 失败原因 (可选)
                - 其他形态特征数据...
        """
        pass
    
    @abstractmethod
    def score(self, df: pd.DataFrame, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        对识别的形态进行评分
        
        Args:
            df: 股票历史数据
            pattern_data: identify()返回的形态数据
            
        Returns:
            dict: 评分结果
                - total: float, 总分
                - details: dict, 各维度得分和说明
                - 其他评分维度...
        """
        pass
    
    @abstractmethod
    def get_min_score(self) -> float:
        """
        获取形态的最低分数线
        
        Returns:
            float: 最低分数
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        获取形态名称
        
        Returns:
            str: 形态名称
        """
        pass
    
    def format_pattern_name(self, score: float) -> str:
        """
        根据分数格式化形态标签
        
        Args:
            score: 形态得分
            
        Returns:
            str: 格式化后的形态名称
        """
        if score >= self.get_min_score():
            return f"{self.get_name()}({score:.0f})"
        return ""
