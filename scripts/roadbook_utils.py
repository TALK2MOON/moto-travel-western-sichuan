"""Shared validation, fuel estimation, and coordinate conversion helpers."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path


COORDINATE_SYSTEMS = {"gcj02", "bd09", "wgs84"}
REQUIRED_DAY_FIELDS = {
    "day",
    "date",
    "is_gap_day",
    "start",
    "end",
    "route_level",
    "start_coords",
    "end_coords",
    "distance_km",
    "max_elevation_m",
    "end_elevation_m",
    "scenic_spots",
    "fuel_stops",
    "road_closure_risk",
    "weather_typical",
    "clothing",
}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_coord(value, label, errors):
    if not isinstance(value, list) or len(value) != 2 or not all(_is_number(v) for v in value):
        errors.append(f"{label} 必须是 [lng, lat] 数字数组")
        return
    lng, lat = value
    if not -180 <= lng <= 180 or not -90 <= lat <= 90:
        errors.append(f"{label} 超出经纬度范围")


def _valid_iso_date(value):
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_roadbook(rb):
    """Return a list of human-readable validation errors."""
    errors = []
    if not isinstance(rb, dict):
        return ["路书顶层必须是对象"]
    if not isinstance(rb.get("title"), str) or not rb["title"].strip():
        errors.append("title 必须是非空字符串")
    if "仅供参考，请量力而行" not in str(rb.get("disclaimer", "")):
        errors.append("disclaimer 必须包含：仅供参考，请量力而行")
    if rb.get("coordinate_system") not in COORDINATE_SYSTEMS:
        errors.append("coordinate_system 必须是 gcj02、bd09 或 wgs84")
    rider = rb.get("rider")
    if not isinstance(rider, dict):
        errors.append("rider 必须记录与用户确认的骑行能力资料")
    else:
        rider_required = ("motorcycle_model", "experience_level", "plateau_experience", "offroad_experience", "preferred_pace")
        if not all(rider.get(key) for key in rider_required):
            errors.append("rider 必须包含 motorcycle_model/experience_level/plateau_experience/offroad_experience/preferred_pace")
    preflight = rb.get("service_preflight")
    services = preflight.get("services") if isinstance(preflight, dict) else None
    if not isinstance(preflight, dict) or not preflight.get("checked_at") or not isinstance(services, dict):
        errors.append("service_preflight 必须记录 checked_at 和 services")
    else:
        for service in ("amap", "weather", "lodging"):
            item = services.get(service)
            if not isinstance(item, dict) or item.get("status") not in {"available", "unavailable", "not_configured", "declined", "fallback"}:
                errors.append(f"service_preflight.services.{service} 必须记录有效 status")
    crowd_policy = rb.get("crowd_avoidance")
    if not isinstance(crowd_policy, dict) or crowd_policy.get("mode") not in {"avoid", "accept"}:
        errors.append("crowd_avoidance.mode 必须记录用户选择: avoid 或 accept")
    holiday = rb.get("holiday_strategy")
    if not isinstance(holiday, dict) or holiday.get("is_holiday_period") not in {True, False}:
        errors.append("holiday_strategy 必须记录是否处于假期")
    elif holiday.get("is_holiday_period"):
        if holiday.get("day1_extension_proposed") is not True:
            errors.append("假期路线必须先向用户提出首日延长赶路的隔离车流方案")
        if holiday.get("user_decision") not in {"accept", "reject"}:
            errors.append("假期路线必须记录用户对首日延长方案的 accept/reject 决定")
    days = rb.get("days")
    if not isinstance(days, list) or not days:
        errors.append("days 必须是非空数组")
        return errors

    expected_day = 1
    for index, day in enumerate(days):
        label = f"days[{index}]"
        if not isinstance(day, dict):
            errors.append(f"{label} 必须是对象")
            continue
        missing = sorted(REQUIRED_DAY_FIELDS - day.keys())
        if missing:
            errors.append(f"{label} 缺少字段: {', '.join(missing)}")
        if day.get("day") != expected_day:
            errors.append(f"{label}.day 应为 {expected_day}")
        expected_day += 1
        if day.get("route_level") not in {"rough", "detailed"}:
            errors.append(f"{label}.route_level 必须是 rough 或 detailed")
        if day.get("is_gap_day") is not True and day.get("is_gap_day") is not False:
            errors.append(f"{label}.is_gap_day 必须是布尔值")
        if day.get("date") is not None and not _valid_iso_date(day.get("date")):
            errors.append(f"{label}.date 必须是 YYYY-MM-DD 格式的有效日期或 null")
        if not day.get("is_gap_day") and not _valid_iso_date(day.get("date")):
            errors.append(f"{label}.date 骑行日必须提供有效日期")
        distance = day.get("distance_km")
        if not _is_number(distance) or distance < 0:
            errors.append(f"{label}.distance_km 必须是不小于 0 的数字")
        _validate_coord(day.get("start_coords"), f"{label}.start_coords", errors)
        _validate_coord(day.get("end_coords"), f"{label}.end_coords", errors)
        geometry = day.get("route_geometry")
        if geometry is not None:
            if not isinstance(geometry, list) or len(geometry) < 2:
                errors.append(f"{label}.route_geometry 至少需要两个坐标")
            else:
                for point_index, point in enumerate(geometry):
                    _validate_coord(point, f"{label}.route_geometry[{point_index}]", errors)
        difficulty = day.get("technical_difficulty")
        if difficulty is not None and (not isinstance(difficulty, int) or isinstance(difficulty, bool) or not 1 <= difficulty <= 5):
            errors.append(f"{label}.technical_difficulty 必须是 1–5 的整数")
        if difficulty in {4, 5}:
            if not isinstance(geometry, list) or len(geometry) < 2:
                errors.append(f"{label} 难度 4–5 必须提供真实 route_geometry")
            for field in ("route_evidence", "bailout_points", "no_go_conditions"):
                if not isinstance(day.get(field), list) or not day[field]:
                    errors.append(f"{label} 难度 4–5 必须提供非空 {field}")
        confidence = day.get("route_confidence")
        if confidence is not None and confidence not in {"verified", "recent-community-lead", "unverified"}:
            errors.append(f"{label}.route_confidence 值无效")
        if day.get("route_level") == "detailed" and not day.get("is_gap_day"):
            if day.get("route_phase") not in {"outbound", "return", "local"}:
                errors.append(f"{label}.route_phase 必须是 outbound/return/local")
            if not isinstance(day.get("waypoints"), list):
                errors.append(f"{label}.waypoints 详细路线必须是数组")
            schedule = day.get("schedule")
            if not isinstance(schedule, dict) or not all(key in schedule for key in ("am", "pm", "evening")):
                errors.append(f"{label}.schedule 详细路线必须包含 am/pm/evening")
            if not isinstance(day.get("plan_b"), str) or not day.get("plan_b", "").strip():
                errors.append(f"{label}.plan_b 详细骑行日不能为空")
            if not isinstance(geometry, list) or len(geometry) < 2:
                errors.append(f"{label}.route_geometry 详细路线必须提供地图服务道路轨迹")
            route_source = day.get("route_source")
            if not isinstance(route_source, dict) or not all(route_source.get(key) for key in ("provider", "strategy", "checked_at")):
                errors.append(f"{label}.route_source 必须记录 provider/strategy/checked_at")
            scenic_routes = day.get("scenic_routes")
            if not isinstance(scenic_routes, list) or not scenic_routes:
                errors.append(f"{label}.scenic_routes 详细路线至少需要一条风景公路/路段")
            alternatives = day.get("alternative_routes")
            if not isinstance(alternatives, list) or not alternatives:
                errors.append(f"{label}.alternative_routes 详细路线至少需要一个可执行备选")
            meals = day.get("meals")
            if not isinstance(meals, dict) or not all(meals.get(key) for key in ("lunch", "dinner")):
                errors.append(f"{label}.meals 必须包含 lunch/dinner")
            crowd = day.get("crowd_avoidance")
            if not isinstance(crowd, dict) or crowd.get("enabled") not in {True, False}:
                errors.append(f"{label}.crowd_avoidance 必须记录本日是否按用户选择错峰")
            elif crowd.get("enabled") and not crowd.get("plan"):
                errors.append(f"{label}.crowd_avoidance 启用时必须提供 plan")
            snow = day.get("snow_risk")
            if not isinstance(snow, dict) or snow.get("level") not in {"低", "中", "高", "未知"}:
                errors.append(f"{label}.snow_risk.level 必须是低/中/高/未知")
            elif not all(snow.get(key) for key in ("basis", "checked_at", "action")):
                errors.append(f"{label}.snow_risk 必须记录 basis/checked_at/action")
            elif snow.get("level") == "高":
                if not isinstance(day.get("no_go_conditions"), list) or not day["no_go_conditions"]:
                    errors.append(f"{label} 历史落雪高风险日必须提供 no_go_conditions")
            forecast = day.get("weather_forecast")
            if not isinstance(forecast, dict) or not all(forecast.get(key) for key in ("status", "summary", "updated_at")):
                errors.append(f"{label}.weather_forecast 必须记录 status/summary/updated_at")
            history = day.get("historical_weather")
            if not isinstance(history, dict) or not all(history.get(key) for key in ("probability_summary", "source", "checked_at", "sample_description")):
                errors.append(f"{label}.historical_weather 必须记录概率摘要、来源、查询时间和样本说明")
            elif not any(_is_number(history.get(key)) for key in ("precipitation_probability_pct", "snow_probability_pct")):
                errors.append(f"{label}.historical_weather 至少需要雨雪或降雪概率")
            lodging_options = day.get("lodging_options")
            if day.get("requires_lodging", True) and (not isinstance(lodging_options, list) or not lodging_options):
                errors.append(f"{label}.lodging_options 住宿日必须包含酒店/民宿建议或明确的不可用占位")
            context_pois = day.get("context_pois")
            if not isinstance(context_pois, list):
                errors.append(f"{label}.context_pois 必须是沿线地物与服务点数组")
    return errors


def load_roadbook(path):
    with Path(path).open(encoding="utf-8") as handle:
        rb = json.load(handle)
    errors = validate_roadbook(rb)
    if errors:
        raise ValueError("路书校验失败:\n- " + "\n- ".join(errors))
    return rb


def estimate_fuel(day, consumption):
    km = day.get("distance_km", 0)
    base = km * consumption / 100
    alt_factor = 1 + 0.02 * (day.get("end_elevation_m", 0) / 1000)
    gain = day.get("elevation_gain_m")
    if gain is None:
        gain = max(0, day.get("max_elevation_m", 0) - day.get("end_elevation_m", 0))
    return base * alt_factor * 1.08 + 0.15 * gain / 1000


def _out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng, lat):
    value = -100 + 2 * lng + 3 * lat + 0.2 * lat * lat + 0.1 * lng * lat
    value += 0.2 * math.sqrt(abs(lng))
    value += (20 * math.sin(6 * lng * math.pi) + 20 * math.sin(2 * lng * math.pi)) * 2 / 3
    value += (20 * math.sin(lat * math.pi) + 40 * math.sin(lat / 3 * math.pi)) * 2 / 3
    value += (160 * math.sin(lat / 12 * math.pi) + 320 * math.sin(lat * math.pi / 30)) * 2 / 3
    return value


def _transform_lng(lng, lat):
    value = 300 + lng + 2 * lat + 0.1 * lng * lng + 0.1 * lng * lat
    value += 0.1 * math.sqrt(abs(lng))
    value += (20 * math.sin(6 * lng * math.pi) + 20 * math.sin(2 * lng * math.pi)) * 2 / 3
    value += (20 * math.sin(lng * math.pi) + 40 * math.sin(lng / 3 * math.pi)) * 2 / 3
    value += (150 * math.sin(lng / 12 * math.pi) + 300 * math.sin(lng / 30 * math.pi)) * 2 / 3
    return value


def wgs84_to_gcj02(lng, lat):
    if _out_of_china(lng, lat):
        return lng, lat
    a = 6378245.0
    ee = 0.006693421622965943
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = 1 - ee * math.sin(radlat) ** 2
    sqrtmagic = math.sqrt(magic)
    dlat = dlat * 180.0 / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = dlng * 180.0 / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat


def bd09_to_gcj02(lng, lat):
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * math.pi * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * math.pi * 3000.0 / 180.0)
    return z * math.cos(theta), z * math.sin(theta)


def to_gcj02(lng, lat, coordinate_system):
    if coordinate_system == "gcj02":
        return lng, lat
    if coordinate_system == "bd09":
        return bd09_to_gcj02(lng, lat)
    if coordinate_system == "wgs84":
        return wgs84_to_gcj02(lng, lat)
    raise ValueError(f"不支持的坐标系: {coordinate_system}")
