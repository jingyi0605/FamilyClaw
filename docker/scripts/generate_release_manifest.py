from __future__ import annotations

import argparse
import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate release-manifest.json for the FamilyClaw container image.")
    parser.add_argument("--alembic-ini", required=True, help="Absolute path to alembic.ini")
    parser.add_argument("--output", required=True, help="Absolute path to the manifest output file")
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--build-channel", required=True)
    parser.add_argument("--build-time", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--git-tag", required=True)
    parser.add_argument("--release-url", default="")
    parser.add_argument("--docker-image", required=True)
    return parser.parse_args()


def load_schema_heads(alembic_ini: Path) -> list[str]:
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_ini.parent / "migrations"))
    script = ScriptDirectory.from_config(config)
    return sorted(script.get_heads())


def main() -> None:
    args = parse_args()
    schema_heads = load_schema_heads(Path(args.alembic_ini))

    manifest = {
        "app_version": args.app_version,
        "git_tag": args.git_tag,
        "git_sha": args.git_sha,
        "built_at": args.build_time,
        "release_url": args.release_url or None,
        "docker_image": args.docker_image,
        "schema_heads": schema_heads,
        "upgrade_policy": {
            "min_supported_app_version": args.app_version,
            "allowed_source_schema_heads": schema_heads,
            "requires_manual_migration": False,
            "manual_migration_doc": None,
        },
        "build_channel": args.build_channel,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
