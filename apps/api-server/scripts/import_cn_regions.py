import argparse
from pathlib import Path

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.modules.region.models import RegionNode
from app.modules.region.schemas import RegionCatalogImportItem
from app.modules.region.service import (
    BUILTIN_CN_MAINLAND_COUNTRY,
    BUILTIN_CN_MAINLAND_PROVIDER,
    import_region_catalog,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入中国省市区县目录到 region_nodes")
    parser.add_argument(
        "--data-file",
        default=str(Path(__file__).resolve().parents[1] / "app" / "modules" / "region" / "data" / "cn_regions.json"),
        help="地区数据文件路径",
    )
    parser.add_argument(
        "--source-version",
        default="modood-mainland-plus-china-division-hk-mo-tw",
        help="数据源版本标识",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="单批导入数量",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="导入前先清空当前中国大陆目录",
    )
    return parser.parse_args()


def load_items(data_file: Path) -> list[RegionCatalogImportItem]:
    import json

    raw_items = json.loads(data_file.read_text(encoding="utf-8"))
    return [RegionCatalogImportItem.model_validate(item) for item in raw_items]


def main() -> None:
    args = parse_args()
    data_file = Path(args.data_file)
    if not data_file.exists():
        raise SystemExit(f"地区数据文件不存在: {data_file}")

    items = load_items(data_file)
    db = SessionLocal()
    try:
        if args.replace:
            db.execute(
                delete(RegionNode).where(
                    RegionNode.provider_code == BUILTIN_CN_MAINLAND_PROVIDER,
                    RegionNode.country_code == BUILTIN_CN_MAINLAND_COUNTRY,
                )
            )
            db.commit()

        for offset in range(0, len(items), args.batch_size):
            chunk = items[offset : offset + args.batch_size]
            import_region_catalog(
                db,
                items=chunk,
                provider_code=BUILTIN_CN_MAINLAND_PROVIDER,
                country_code=BUILTIN_CN_MAINLAND_COUNTRY,
                source_version=args.source_version,
            )
            db.commit()

        print(f"已导入 {len(items)} 条中国地区目录")
    finally:
        db.close()


if __name__ == "__main__":
    main()
