"""兼容层：保留旧导入路径，实际实现已迁移到 pipeline.writing。"""

from poiesis.pipeline.writing.editor import ChapterEditor

__all__ = ["ChapterEditor"]
