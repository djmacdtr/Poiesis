"""兼容层：保留旧导入路径，实际实现已迁移到 pipeline.summary。"""

from poiesis.pipeline.summary.summarizer import ChapterSummarizer

__all__ = ["ChapterSummarizer"]
