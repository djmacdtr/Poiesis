"""兼容层：保留旧导入路径，实际实现已迁移到 pipeline.merge。"""

from poiesis.pipeline.merge.merger import WorldMerger

__all__ = ["WorldMerger"]
