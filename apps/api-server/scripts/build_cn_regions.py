import json
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from urllib.request import urlopen


MODood_PCAS_URL = "https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist/pcas-code.json"
CHINA_DIVISION_META_URL = "https://registry.npmjs.org/china-division"
OUTPUT_FILE = Path(__file__).resolve().parents[1] / "app" / "modules" / "region" / "data" / "cn_regions.json"
SOURCE_VERSION = "modood-mainland-plus-china-division-taiwan"
DIRECT_PROVINCES = {"11", "12", "31", "50"}
DIRECT_CITY_NAMES = {"市辖区", "县"}
TAIWAN_CITY_CODE_MAP = {
    "台北市": "710100",
    "高雄市": "710200",
    "基隆市": "710300",
    "台中市": "710400",
    "台南市": "710500",
    "新竹市": "710600",
    "嘉义市": "710700",
    "新北市": "710800",
    "宜兰县": "710900",
    "桃园市": "711000",
    "新竹县": "711100",
    "苗栗县": "711200",
    "彰化县": "711300",
    "南投县": "711400",
    "云林县": "711500",
    "嘉义县": "711600",
    "屏东县": "711700",
    "台东县": "711800",
    "花莲县": "711900",
    "澎湖县": "712000",
    "金门县": "712100",
    "连江县": "712200",
}
TAIWAN_EXTRA_TOWNS = {
    "金门县": ["金城镇", "金湖镇", "金沙镇", "金宁乡", "烈屿乡", "乌丘乡"],
    "连江县": ["南竿乡", "北竿乡", "莒光乡", "东引乡"],
}


def fetch_json(url: str) -> Any:
    with urlopen(url) as response:
        return json.load(response)


def fetch_china_division_taiwan() -> dict[str, list[str]]:
    meta = cast(dict[str, Any], fetch_json(CHINA_DIVISION_META_URL))
    latest = meta["dist-tags"]["latest"]
    tarball_url = meta["versions"][latest]["dist"]["tarball"]
    with urlopen(tarball_url) as response:
        raw = response.read()
    with tarfile.open(fileobj=BytesIO(raw), mode="r:gz") as tar:
        file_obj = tar.extractfile("package/dist/HK-MO-TW.json")
        if file_obj is None:
            raise RuntimeError("无法从 china-division 包中读取台湾地区数据")
        with file_obj:
            payload = cast(dict[str, dict[str, list[str]]], json.load(file_obj))
    taiwan = dict(payload.get("台湾省", {}))
    for city_name, towns in TAIWAN_EXTRA_TOWNS.items():
        taiwan[city_name] = towns
    return taiwan


def build_mainland_nodes() -> list[dict[str, object]]:
    data = cast(list[dict[str, Any]], fetch_json(MODood_PCAS_URL))
    nodes: list[dict[str, object]] = []
    seen: set[str] = set()
    for province in data:
        province_prefix = f"{int(province['code']):02d}"
        province_code = f"{province_prefix}0000"
        province_name = province["name"]
        province_node = {
            "provider_code": "builtin.cn-mainland",
            "country_code": "CN",
            "region_code": province_code,
            "parent_region_code": None,
            "admin_level": "province",
            "name": province_name,
            "full_name": province_name,
            "path_codes": [province_code],
            "path_names": [province_name],
            "timezone": "Asia/Shanghai",
            "source_version": SOURCE_VERSION,
        }
        if province_code not in seen:
            nodes.append(province_node)
            seen.add(province_code)

        for city in province.get("children", []):
            city_code = f"{int(city['code']):04d}00"
            raw_city_name = city["name"]
            city_name = province_name if province_prefix in DIRECT_PROVINCES and raw_city_name in DIRECT_CITY_NAMES else raw_city_name
            city_node = {
                "provider_code": "builtin.cn-mainland",
                "country_code": "CN",
                "region_code": city_code,
                "parent_region_code": province_code,
                "admin_level": "city",
                "name": city_name,
                "full_name": f"{province_name} / {city_name}",
                "path_codes": [province_code, city_code],
                "path_names": [province_name, city_name],
                "timezone": "Asia/Shanghai",
                "source_version": SOURCE_VERSION,
            }
            if city_code not in seen:
                nodes.append(city_node)
                seen.add(city_code)

            for district in city.get("children", []):
                district_code = f"{int(district['code']):06d}"
                district_name = district["name"]
                district_node = {
                    "provider_code": "builtin.cn-mainland",
                    "country_code": "CN",
                    "region_code": district_code,
                    "parent_region_code": city_code,
                    "admin_level": "district",
                    "name": district_name,
                    "full_name": f"{province_name} / {city_name} / {district_name}",
                    "path_codes": [province_code, city_code, district_code],
                    "path_names": [province_name, city_name, district_name],
                    "timezone": "Asia/Shanghai",
                    "source_version": SOURCE_VERSION,
                }
                if district_code not in seen:
                    nodes.append(district_node)
                    seen.add(district_code)
    return nodes


def build_taiwan_nodes() -> list[dict[str, object]]:
    area_data = fetch_china_division_taiwan()
    province_code = "710000"
    province_name = "台湾省"
    nodes: list[dict[str, object]] = [
        {
            "provider_code": "builtin.cn-mainland",
            "country_code": "CN",
            "region_code": province_code,
            "parent_region_code": None,
            "admin_level": "province",
            "name": province_name,
            "full_name": province_name,
            "path_codes": [province_code],
            "path_names": [province_name],
            "timezone": "Asia/Taipei",
            "source_version": SOURCE_VERSION,
        }
    ]
    for city_name, city_code in TAIWAN_CITY_CODE_MAP.items():
        district_names = area_data.get(city_name, [])
        nodes.append(
            {
                "provider_code": "builtin.cn-mainland",
                "country_code": "CN",
                "region_code": city_code,
                "parent_region_code": province_code,
                "admin_level": "city",
                "name": city_name,
                "full_name": f"{province_name} / {city_name}",
                "path_codes": [province_code, city_code],
                "path_names": [province_name, city_name],
                "timezone": "Asia/Taipei",
                "source_version": SOURCE_VERSION,
            }
        )

        for index, district_name in enumerate(district_names, start=1):
            district_code = f"{city_code[:4]}{index:02d}"
            nodes.append(
                {
                    "provider_code": "builtin.cn-mainland",
                    "country_code": "CN",
                    "region_code": district_code,
                    "parent_region_code": city_code,
                    "admin_level": "district",
                    "name": district_name,
                    "full_name": f"{province_name} / {city_name} / {district_name}",
                    "path_codes": [province_code, city_code, district_code],
                    "path_names": [province_name, city_name, district_name],
                    "timezone": "Asia/Taipei",
                    "source_version": SOURCE_VERSION,
                }
            )
    return nodes


def main() -> None:
    mainland_nodes = build_mainland_nodes()
    taiwan_nodes = build_taiwan_nodes()
    all_nodes = sorted(mainland_nodes + taiwan_nodes, key=lambda item: str(item["region_code"]))
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(all_nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {len(all_nodes)} 条中国地区目录数据")


if __name__ == "__main__":
    main()
