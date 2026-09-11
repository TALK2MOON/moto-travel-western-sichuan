#!/usr/bin/env python3
"""将经过校验的 roadbook.json 导出为可阅读、可复核的 Markdown 路书。"""

import argparse
import sys
from pathlib import Path

from roadbook_utils import estimate_fuel, load_roadbook


def text(value, fallback="待复核"):
    return str(value) if value not in (None, "") else fallback


def bullet_lines(items, formatter, empty="- 待补充"):
    return [f"- {formatter(item)}" for item in items] or [empty]


def render_day(day, consumption):
    number = day["day"]
    if day.get("is_gap_day"):
        return [
            f"## D{number} · 机动缓冲日",
            "",
            text(day.get("notes"), "用于吸收天气、管制、疲劳或高原反应造成的延误。"),
            "",
        ]

    fuel = estimate_fuel(day, consumption)
    snow = day.get("snow_risk") or {}
    forecast = day.get("weather_forecast") or {}
    history = day.get("historical_weather") or {}
    meals = day.get("meals") or {}
    crowd = day.get("crowd_avoidance") or {}
    route_source = day.get("route_source") or {}
    lines = [
        f"## D{number} · {text(day.get('date'), '日期待定')} · {text(day.get('start'))} → {text(day.get('end'))}",
        "",
        f"- 里程：{text(day.get('distance_km'))} km；预计耗油：{fuel:.1f} L",
        f"- 最高海拔：{text(day.get('max_elevation_m'))} m；住宿海拔：{text(day.get('end_elevation_m'))} m",
        f"- 路面/难度：{text(day.get('surface'))}；{text(day.get('technical_difficulty'), '未分级')}/5；可信度：{text(day.get('route_confidence'))}",
        f"- 轨迹来源：{text(route_source.get('provider'))}；策略：{text(route_source.get('strategy'))}；核验：{text(route_source.get('checked_at'))}",
        "",
        "### 分时段安排",
        "",
    ]
    schedule = day.get("schedule") or {}
    lines.extend([
        f"- 上午：{text(schedule.get('am'))}",
        f"- 下午：{text(schedule.get('pm'))}",
        f"- 晚间：{text(schedule.get('evening'))}",
        "",
        "### 连续风景路线",
        "",
    ])
    lines.extend(bullet_lines(
        day.get("scenic_routes") or [],
        lambda item: f"**{text(item.get('name'))}** — {text(item.get('reason'))}"
        + (f"（约 {item['distance_km']} km）" if item.get("distance_km") is not None else ""),
    ))
    lines.extend(["", "### 加油、吃饭与住宿", ""])
    lines.extend(bullet_lines(
        day.get("fuel_stops") or [],
        lambda item: f"加油：{text(item.get('name'))}；{text(item.get('note'), '')}",
        "- 加油点待补充",
    ))
    lines.extend([
        f"- 午餐：{text(meals.get('lunch'))}",
        f"- 晚餐：{text(meals.get('dinner'))}",
    ])
    lines.extend(bullet_lines(
        day.get("lodging_options") or [],
        lambda item: "住宿："
        f"{text(item.get('name'))}；{text(item.get('price_range'), '价格待复核')}；"
        f"供氧 {text(item.get('oxygen'), '待问')}；地暖 {text(item.get('heating'), '待问')}；"
        f"停车 {text(item.get('parking'), '待问')}；来源 {text(item.get('source'))}",
        "- 住宿候选待补充",
    ))
    lines.extend([
        "",
        "### 天气、落雪与避堵",
        "",
        f"- 预报：{text(forecast.get('summary'))}；更新时间 {text(forecast.get('updated_at'))}",
        f"- 历史同期：{text(history.get('probability_summary'), text(day.get('weather_typical')))}；来源 {text(history.get('source'))}",
        f"- 落雪风险：**{text(snow.get('level'), '未知')}**；{text(snow.get('basis'))}；处置：{text(snow.get('action'))}",
        f"- 避堵：{text(crowd.get('plan'), text(crowd.get('reason'), '按用户决定执行'))}",
        f"- 路况风险：{text(day.get('road_closure_risk'))}",
        f"- 穿衣：{text(day.get('clothing'))}",
        "",
        "### 备选与放弃条件",
        "",
    ])
    lines.extend(bullet_lines(
        day.get("alternative_routes") or [],
        lambda item: f"**{text(item.get('name'))}** — 触发：{text(item.get('trigger'), text(item.get('note')))}"
        + (f"；约 {item['distance_km']} km" if item.get("distance_km") is not None else ""),
        "- 备选路线待补充",
    ))
    lines.append(f"- 当日 Plan B：{text(day.get('plan_b'))}")
    for condition in day.get("no_go_conditions") or []:
        lines.append(f"- 必须放弃/掉头：{condition}")
    lines.append("")
    return lines


def render_markdown(roadbook):
    rider = roadbook.get("rider") or {}
    consumption = rider.get("consumption_l_per_100km", 3.5)
    days = roadbook.get("days") or []
    total_distance = sum(float(day.get("distance_km") or 0) for day in days)
    total_fuel = sum(
        estimate_fuel(day, consumption)
        for day in days
        if not day.get("is_gap_day")
    )
    lines = [
        f"# {text(roadbook.get('title'), '川西摩旅路书')}",
        "",
        f"> {text(roadbook.get('disclaimer'), '仅供参考，请量力而行。')}",
        "",
        "## 路线总览",
        "",
        f"- 共 {len(days)} 天，约 {total_distance:.0f} km，预计耗油 {total_fuel:.1f} L。",
        f"- 车型：{text(rider.get('motorcycle_model'))}；节奏：{text(rider.get('preferred_pace'))}。",
        "",
        "| Day | 日期 | 路线 | 里程 | 最高/住宿海拔 | 落雪风险 |",
        "|---|---|---|---:|---:|---|",
    ]
    for day in days:
        route = "机动缓冲日" if day.get("is_gap_day") else f"{text(day.get('start'))} → {text(day.get('end'))}"
        snow = (day.get("snow_risk") or {}).get("level", "未知")
        lines.append(
            f"| D{day['day']} | {text(day.get('date'), '机动')} | {route} | "
            f"{text(day.get('distance_km'), '0')} km | {text(day.get('max_elevation_m'), '—')} / "
            f"{text(day.get('end_elevation_m'), '—')} m | {snow} |"
        )
    lines.append("")
    for day in days:
        lines.extend(render_day(day, consumption))
    lines.extend([
        "---",
        "",
        f"> {text(roadbook.get('disclaimer'), '仅供参考，请量力而行。')}",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="路书 JSON -> Markdown")
    parser.add_argument("roadbook", help="路书 JSON 文件")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()
    try:
        roadbook = load_roadbook(args.roadbook)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    output = Path(args.output or "roadbook.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(roadbook), encoding="utf-8")
    print(f"已导出 {output}: {len(roadbook['days'])} 天")


if __name__ == "__main__":
    main()
