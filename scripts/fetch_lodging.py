#!/usr/bin/env python3
"""从路书住宿节点批量查询 FlyAI，并输出可合并的住宿候选数据。

脚本不修改原路书。查询有缓存、频率限制、风控识别、地名坐标复核和预算分档。
"""

import argparse
import json
import math
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path


SORTS = ("distance_asc", "price_asc", "rate_desc", "no_rank")
STAR_RANK = {"豪华型": 4, "高档型": 3, "舒适型": 2, "经济型": 1}


def parse_price_range(value):
    """把 FlyAI 脱敏起价 ¥2xx/¥7x/¥1xxx 转为 200/70/1000。"""
    match = re.match(r"^\s*[¥￥]?\s*(\d+)\s*(x+)\s*$", str(value or ""), re.I)
    return int(match.group(1)) * 10 ** len(match.group(2)) if match else None


def haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def extract_json(value):
    value = value.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(value[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def slug(value):
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", str(value or "")).strip("_")


def lodging_nodes(roadbook, default_radius):
    nodes = []
    seen = set()
    for day in roadbook.get("days") or []:
        if day.get("is_gap_day") or day.get("requires_lodging", True) is False or not day.get("date"):
            continue
        coords = day.get("end_coords") or []
        if len(coords) != 2:
            continue
        destination = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", str(day.get("end") or "")).strip()
        key = (destination, day["date"])
        if key in seen:
            continue
        seen.add(key)
        nodes.append({
            "key": f"D{day['day']}:{destination}",
            "dest": destination,
            "check_in": day["date"],
            "check_out": (date.fromisoformat(day["date"]) + timedelta(days=1)).isoformat(),
            "lng": float(coords[0]),
            "lat": float(coords[1]),
            "elevation_m": day.get("end_elevation_m"),
            "radius_km": default_radius,
        })
    return nodes


def normalize(node, item, hard_max_km):
    try:
        lat, lng = float(item.get("latitude")), float(item.get("longitude"))
    except (TypeError, ValueError):
        return None
    distance = haversine_km(node["lat"], node["lng"], lat, lng)
    if distance > hard_max_km or not str(item.get("name") or "").strip():
        return None
    price_range = str(item.get("price") or "").strip()
    return {
        "name": str(item["name"]).strip(),
        "price_range": price_range,
        "price_low": parse_price_range(price_range),
        "star": str(item.get("star") or "未知").strip(),
        "distance_km": round(distance, 1),
        "address": str(item.get("address") or "").strip(),
        "lat": lat,
        "lng": lng,
        "detail_url": item.get("detailUrl") or "",
    }


def select_hotels(hotels, budget_low, budget_high, limit):
    def rank(item):
        return (int(item["distance_km"] // 10), -STAR_RANK.get(item["star"], 0), item["distance_km"])

    priced = [item for item in hotels if item["price_low"] is not None]
    in_budget = sorted(
        [item for item in priced if budget_low <= item["price_low"] <= budget_high], key=rank
    )
    cheaper = sorted(
        [item for item in priced if item["price_low"] < budget_low],
        key=lambda item: (rank(item), -(item["price_low"] or 0)),
    )
    over_budget = sorted(
        [item for item in priced if item["price_low"] > budget_high],
        key=lambda item: (rank(item), item["price_low"]),
    )
    return {
        "in_budget": in_budget[:limit],
        "cheaper": cheaper[:limit],
        "over_budget": over_budget[:limit],
    }


class FlyAICollector:
    def __init__(self, executable, cache_dir, wait_seconds, risk_backoff, attempts, timeout):
        self.executable = executable
        self.cache_dir = cache_dir
        self.wait_seconds = wait_seconds
        self.risk_backoff = risk_backoff
        self.attempts = attempts
        self.timeout = timeout
        self.calls = 0

    def query(self, node, sort, max_price):
        suffix = str(max_price) if max_price is not None else "nomax"
        cache = self.cache_dir / f"{slug(node['key'])}__{node['check_in']}__{sort}__{suffix}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        if self.calls:
            time.sleep(random.uniform(*self.wait_seconds))
        self.calls += 1
        command = [
            self.executable,
            "search-hotel",
            "--dest-name", node["dest"],
            "--check-in-date", node["check_in"],
            "--check-out-date", node["check_out"],
            "--sort", sort,
        ]
        if max_price is not None:
            command += ["--max-price", str(max_price)]
        result = {"status": "unknown", "items": []}
        for attempt in range(1, self.attempts + 1):
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout)
                raw = process.stdout + "\n" + process.stderr
            except subprocess.TimeoutExpired:
                result = {"status": "timeout", "items": []}
                break
            if "risk control" in raw.lower():
                result = {"status": "risk_control", "items": []}
                if attempt < self.attempts:
                    time.sleep(self.risk_backoff)
                    continue
                break
            document = extract_json(raw)
            items = document.get("data", {}).get("itemList", []) if isinstance(document, dict) else []
            result = {"status": "ok" if items else "empty", "items": items}
            break
        cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


def main():
    parser = argparse.ArgumentParser(description="按 roadbook.json 的住宿节点查询 FlyAI")
    parser.add_argument("roadbook")
    parser.add_argument("-o", "--output", default="lodging.json")
    parser.add_argument("--cache-dir", default=".roadbook-cache/flyai")
    parser.add_argument("--budget-low", type=int, required=True)
    parser.add_argument("--budget-high", type=int, required=True)
    parser.add_argument("--radius-km", type=float, default=20)
    parser.add_argument("--hard-max-km", type=float, default=40)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--wait-min", type=float, default=25)
    parser.add_argument("--wait-max", type=float, default=30)
    parser.add_argument("--risk-backoff", type=float, default=120)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=150)
    parser.add_argument("--dry-run", action="store_true", help="只列出住宿节点，不调用 FlyAI")
    args = parser.parse_args()
    if args.budget_low > args.budget_high:
        parser.error("--budget-low 不能大于 --budget-high")

    source = Path(args.roadbook)
    roadbook = json.loads(source.read_text(encoding="utf-8"))
    nodes = lodging_nodes(roadbook, args.radius_km)
    if args.dry_run:
        print(json.dumps({"nodes": nodes, "estimated_queries": len(nodes) * 5}, ensure_ascii=False, indent=2))
        return

    executable = shutil.which("flyai")
    if not executable:
        sys.exit("未找到 flyai。请先按 references/mcp-setup.md 在受信任的本地环境完成安装。")
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    collector = FlyAICollector(
        executable, cache_dir, (args.wait_min, args.wait_max), args.risk_backoff, args.attempts, args.timeout
    )
    output_nodes = {}
    for node in nodes:
        found, statuses = {}, []
        for sort in SORTS:
            result = collector.query(node, sort, args.budget_high)
            statuses.append(result["status"])
            for item in result["items"]:
                normalized = normalize(node, item, args.hard_max_km)
                if normalized and normalized["distance_km"] <= node["radius_km"]:
                    found[normalized["name"]] = normalized
        extra = collector.query(node, "rate_desc", None)
        statuses.append(extra["status"])
        for item in extra["items"]:
            normalized = normalize(node, item, args.hard_max_km)
            if normalized and normalized["distance_km"] <= node["radius_km"]:
                found[normalized["name"]] = normalized
        selected = select_hotels(list(found.values()), args.budget_low, args.budget_high, args.limit)
        output_nodes[node["key"]] = {
            "destination": node["dest"],
            "check_in": node["check_in"],
            "check_out": node["check_out"],
            "elevation_m": node["elevation_m"],
            "query_status": "ok" if "ok" in statuses else ("risk_control" if "risk_control" in statuses else "unavailable"),
            "search_radius_km": node["radius_km"],
            "distinct_hotels_found": len(found),
            **selected,
        }
    document = {
        "checked_at": date.today().isoformat(),
        "provider": "飞猪 FlyAI CLI",
        "budget": {"low": args.budget_low, "high": args.budget_high},
        "price_caveat": "价格为脱敏区间起价，不是精确报价，也不等于实时房态",
        "nodes": output_nodes,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {target}: {len(output_nodes)} 个住宿节点")


if __name__ == "__main__":
    main()
