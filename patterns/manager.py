"""
形态管理器 - 管理所有形态插件的注册和执行
"""
from typing import Dict, List, Any
import pandas as pd
from .base import PatternBase


class PatternManager:
    """
    形态管理器
    
    负责:
    1. 注册形态插件
    2. 批量执行形态识别和评分
    3. 汇总结果
    """
    
    def __init__(self):
        self._patterns: Dict[str, PatternBase] = {}
    
    def register(self, pattern_id: str, pattern: PatternBase):
        """
        注册形态插件
        
        Args:
            pattern_id: 形态标识符 (如 'triangle', 'double_dip')
            pattern: 形态实例
        """
        if not isinstance(pattern, PatternBase):
            raise TypeError(f"Pattern must inherit from PatternBase, got {type(pattern)}")
        self._patterns[pattern_id] = pattern
    
    def evaluate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        对股票数据执行所有已注册形态的识别和评分
        
        Args:
            df: 股票历史数据
            
        Returns:
            dict: 所有形态的评分结果
                {
                    'pattern_id': {
                        'score': score_result,
                        'pattern': pattern_data
                    },
                    ...
                }
        """
        results = {}
        
        for pattern_id, pattern in self._patterns.items():
            # 识别形态
            pattern_data = pattern.identify(df)
            
            # 评分
            score_result = pattern.score(df, pattern_data)
            
            results[pattern_id] = {
                'score': score_result,
                'pattern': pattern_data,
                'instance': pattern
            }
        
        return results
    
    def get_pattern(self, pattern_id: str) -> PatternBase:
        """
        获取已注册的形态实例
        
        Args:
            pattern_id: 形态标识符
            
        Returns:
            PatternBase: 形态实例
        """
        return self._patterns.get(pattern_id)
    
    def get_all_patterns(self) -> Dict[str, PatternBase]:
        """
        获取所有已注册的形态
        
        Returns:
            dict: 形态字典
        """
        return self._patterns.copy()
    
    def format_patterns_label(self, results: Dict[str, Any]) -> str:
        """
        格式化形态标签
        
        Args:
            results: evaluate()返回的结果
            
        Returns:
            str: 形态标签 (如 "收敛三角形(75)")
        """
        labels = []
        
        for pattern_id, result in results.items():
            pattern = result['instance']
            score = result['score']['total']
            label = pattern.format_pattern_name(score)
            if label:
                labels.append(label)
        
        return "; ".join(labels) if labels else "无"
    
    def generate_remark(self, results: Dict[str, Any]) -> str:
        """
        生成形态备注
        
        Args:
            results: evaluate()返回的结果
            
        Returns:
            str: 备注信息
        """
        remarks = []
        
        for pattern_id, result in results.items():
            pattern = result['instance']
            score_data = result['score']
            
            if score_data['total'] >= pattern.get_min_score():
                if 'details' in score_data:
                    for key, value in score_data['details'].items():
                        if value and isinstance(value, str):
                            remarks.append(f"{key}: {value}")
        
        return "; ".join(remarks) if remarks else ""
