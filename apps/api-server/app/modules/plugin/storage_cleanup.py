from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

def iter_household_plugin_storage_paths(household_id: str) -> tuple[Path, ...]:
    """返回 household 级插件落盘目录，供清理和诊断复用。"""
    storage_root = Path(settings.plugin_storage_root).resolve()
    install_root = Path(settings.plugin_marketplace_install_root).resolve()
    paths: set[Path] = {
        (storage_root / "third_party" / "local" / household_id).resolve(),
        (install_root / household_id).resolve(),
    }
    return tuple(sorted(paths))


def cleanup_household_plugin_storage(household_id: str) -> int:
    """删除 household 级插件目录。

    这里只处理磁盘残留，不碰数据库。函数本身吞掉文件删除异常，
    避免事务已经提交成功后又因为清理日志把调用方炸掉。
    """
    removed_count = 0
    for target_root in iter_household_plugin_storage_paths(household_id):
        if not target_root.exists():
            continue
        try:
            shutil.rmtree(target_root)
        except FileNotFoundError:
            continue
        except OSError:
            logger.exception(
                "删除 household 插件目录失败 household_id=%s path=%s",
                household_id,
                target_root,
            )
            continue
        removed_count += 1
    if removed_count > 0:
        logger.info(
            "已清理 household 插件目录 household_id=%s removed_count=%s",
            household_id,
            removed_count,
        )
    return removed_count
