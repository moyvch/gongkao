#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志模块
替代项目中散落的 print() 输出，提供带时间戳、级别、颜色的日志。

用法:
    from scripts.logger import get_logger
    log = get_logger(__name__)
    log.info("开始收藏...")
    log.ok("保存成功")
    log.warn("session 可能已过期")
    log.error("抓取失败: ...")
    log.step("Step 1/3: 抓取页面")
"""
import logging
import sys
import os
from datetime import datetime

# ── ANSI 颜色（Windows Terminal / macOS / Linux 均支持）
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_BLUE   = "\033[34m"
_GRAY   = "\033[90m"

# 是否启用彩色（非 TTY 时关闭）
_USE_COLOR = sys.stdout.isatty() or os.environ.get("FORCE_COLOR", "")


def _c(text: str, *codes: str) -> str:
    """给文本加 ANSI 颜色码，非彩色模式返回原文"""
    if not _USE_COLOR:
        return text
    return "".join(codes) + text + _RESET


class GongkaoLogger:
    """
    轻量级 logger，对 logging.Logger 做薄封装，
    增加 ok / step / section 等语义化方法。
    """

    def __init__(self, name: str, level: int = logging.DEBUG):
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            self._setup(level)

    def _setup(self, level: int):
        self._logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(_ColorFormatter())
        self._logger.addHandler(handler)
        self._logger.propagate = False

    # ── 基础级别 ──────────────────────────────────────────────────
    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warn(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)

    # ── 语义化方法 ────────────────────────────────────────────────
    def ok(self, msg: str):
        """操作成功，绿色 [OK]"""
        self._logger.info(_c("[OK] ", _GREEN, _BOLD) + msg)

    def step(self, msg: str):
        """流程步骤提示，蓝色 [STEP]"""
        self._logger.info(_c("[>>] ", _BLUE, _BOLD) + msg)

    def section(self, title: str, width: int = 50):
        """打印分隔标题行"""
        bar = "=" * width
        self._logger.info(_c(bar, _CYAN))
        self._logger.info(_c(f"  {title}", _CYAN, _BOLD))
        self._logger.info(_c(bar, _CYAN))

    def skip(self, msg: str):
        """跳过项，灰色 [SKIP]"""
        self._logger.info(_c("[SKIP] " + msg, _GRAY))

    def fail(self, msg: str):
        """失败，红色 [FAIL]"""
        self._logger.error(_c("[FAIL] ", _RED, _BOLD) + msg)

    def summary(self, total: int, success: int, fail: int):
        """批量操作汇总"""
        self._logger.info(
            _c("汇总: ", _BOLD)
            + _c(f"成功 {success}", _GREEN)
            + " / "
            + _c(f"失败 {fail}", _RED if fail > 0 else _GRAY)
            + " / "
            + f"共 {total}"
        )


class _ColorFormatter(logging.Formatter):
    """带颜色的日志格式器"""

    _LEVEL_COLORS = {
        logging.DEBUG:    (_GRAY,   "DEBUG"),
        logging.INFO:     (_CYAN,   "INFO "),
        logging.WARNING:  (_YELLOW, "WARN "),
        logging.ERROR:    (_RED,    "ERROR"),
        logging.CRITICAL: (_RED,    "CRIT "),
    }

    def format(self, record: logging.LogRecord) -> str:
        color, label = self._LEVEL_COLORS.get(record.levelno, (_RESET, "?????"))
        ts = _c(datetime.now().strftime("%H:%M:%S"), _DIM)
        lv = _c(label, color)

        # 如果消息已经包含 [OK] / [FAIL] 等前缀，不再加 level label
        msg = record.getMessage()
        if msg.startswith("["):
            return f"{ts}  {msg}"
        return f"{ts}  {lv}  {msg}"


# ── 模块级便捷函数 ────────────────────────────────────────────────

_loggers: dict[str, GongkaoLogger] = {}


def get_logger(name: str = "gongkao", level: int = logging.DEBUG) -> GongkaoLogger:
    """获取或创建命名 logger（同名复用）"""
    if name not in _loggers:
        _loggers[name] = GongkaoLogger(name, level)
    return _loggers[name]


# ── 模块自测 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    log = get_logger("test")
    log.section("日志模块自测")
    log.debug("这是 debug 信息（开发用）")
    log.info("这是 info 信息")
    log.step("Step 1/3: 抓取页面")
    log.ok("页面抓取成功，内容长度: 1234 字符")
    log.warn("session 可能即将过期，建议刷新")
    log.fail("LLM 解析失败: JSONDecodeError")
    log.error("Excel 写入失败: 文件被占用")
    log.skip("该链接已存在，跳过重复收藏")
    log.summary(total=5, success=4, fail=1)
