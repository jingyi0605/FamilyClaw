from pathlib import Path

API_SERVER_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = API_SERVER_DIR.parents[1]
VERSION_FILE = PROJECT_ROOT / "VERSION"
DEVELOPMENT_FALLBACK_APP_VERSION = "0.0.0-dev"


def load_repo_app_version(*, version_file: Path | None = None) -> str:
    """从仓库根目录 VERSION 读取应用版本。

    正式构建会通过环境变量或 release manifest 覆盖这里的默认值，
    本地开发环境则直接回落到仓库里的 VERSION，避免后端再维护一份手写版本号。
    """

    target_file = version_file or VERSION_FILE
    try:
        version = target_file.read_text(encoding="utf-8").strip()
    except OSError:
        return DEVELOPMENT_FALLBACK_APP_VERSION

    return version or DEVELOPMENT_FALLBACK_APP_VERSION
