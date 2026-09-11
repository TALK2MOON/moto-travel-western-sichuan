# 路书 JSON 数据模型(Schema)

Excel/HTML 导出脚本共用同一份路书 JSON。规划完成、用户确认后生成该文件,再调用 scripts/export_excel.py 与 scripts/export_html.py 导出。

## 顶层结构

```json
{
  "title": "川西大环线13天摩旅",
  "disclaimer": "仅供参考，请量力而行。出发前复核天气、路况、禁限摩及临时管制。",
  "coordinate_system": "gcj02",
  "crowd_avoidance": {
    "mode": "avoid",
    "locations": ["折多山观景台", "新都桥镇区"],
    "date_ranges": ["2026-10-01/2026-10-03"],
    "time_windows": ["09:00-16:00"]
  },
  "rider": {
    "motorcycle_model": "ADV 500",
    "experience_level": "intermediate",
    "plateau_experience": "some",
    "offroad_experience": "basic",
    "preferred_pace": "normal",
    "tank_l": 15,
    "consumption_l_per_100km": 3.5
  },
  "service_preflight": {
    "checked_at": "2026-09-11",
    "services": {
      "amap": {"status": "available", "provider": "高德 MCP"},
      "weather": {"status": "available", "provider": "和风天气"},
      "lodging": {"status": "available", "provider": "飞猪"}
    }
  },
  "holiday_strategy": {
    "is_holiday_period": true,
    "day1_extension_proposed": true,
    "user_decision": "accept",
    "plan": "首日早出并延长到低海拔住宿点"
  },
  "days": [ ... ]
}
```

`rider` 必填,其经验字段必须来自用户回答,不得代填。油耗缺失时可以明确使用估算值,但车型、骑行/高原/非铺装经验和节奏不可省略。

`service_preflight` 必填,证明路线规划前检查了高德、天气与住宿服务。`holiday_strategy` 必填;若覆盖法定节假日,必须记录已经提出首日延长赶路方案及用户接受/拒绝的决定。

`coordinate_system` 必填,枚举为 `gcj02`、`bd09`、`wgs84`,且同一文件中所有坐标必须一致。高德来源通常为 GCJ-02,百度来源通常为 BD-09,GPS/OSM 常用 WGS-84。HTML 导出时统一转换为 GCJ-02。

`disclaimer` 必填并包含“仅供参考，请量力而行”。

`crowd_avoidance` 必填,必须记录用户的选择。`mode` 为 `avoid` 或 `accept`;不得由规划者擅自替用户选择。启用避堵时补 `locations`、`date_ranges`、`time_windows` 和可接受的绕行代价。

## days[] 每日对象字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| day | int | ✅ | 第几天(1起) |
| date | string/null | ✅ | 骑行日用 ISO 日期 `"2026-09-25"`;未绑定日期的 gap day 用 `null`,不要把“机动”伪装成日期 |
| is_gap_day | bool | ✅ | 是否机动缓冲日(封路/绕路/高反延误用) |
| start / end | string | ✅ | 起点/终点地名 |
| route_level | string | ✅ | "rough"(粗略:仅节点)或 "detailed"(详细:含途经点/路况/玩法) |
| waypoints | array | detailed 必填 | 途经点 [{name, lat, lng, note}],粗略级可为空 |
| route_geometry | array | detailed 必填 | 地图服务返回的真实道路轨迹 `[[lng,lat], ...]`;粗略路线缺少时 HTML 可用高德临时算路并标为待核验 |
| route_source | object | detailed 必填 | `{provider, strategy, checked_at}`;记录地图服务、避高速/避拥堵策略和查询日期 |
| route_phase | string | detailed 必填 | `outbound`/`return`/`local`;用于地图固定区分去程、回程和驻地环线 |
| scenic_routes | array | detailed 必填且非空 | `[{name, reason, distance_km, best_time, route_geometry}]`;连续风景公路/路段,不是景点列表 |
| alternative_routes | array | detailed 必填且非空 | `[{name, trigger, distance_km, route_geometry}]`;可执行备选及启用条件,重要备选也应有真实轨迹 |
| surface | string | detailed 建议 | 路面组成,如“铺装90%＋碎石10%”;无近期依据时写“待核验” |
| technical_difficulty | int 1–5 | 穿越路线必填 | 技术难度,只描述骑行技术与路况,不代表景观评分 |
| route_confidence | string | detailed 建议 | `verified` / `recent-community-lead` / `unverified` |
| route_evidence | array | detailed 建议 | [{source, url, published_at, checked_at, claim}];社交平台单一来源不能升级为 verified |
| bailout_points | array | 难度4–5必填 | 撤退点 [{name, lat, lng, note}] |
| no_go_conditions | array | 难度4–5必填 | 必须放弃/掉头的条件,如降雪预警、无近期轨迹、超过最晚折返点 |
| start_coords / end_coords | [lng, lat] | ✅ | 起终点坐标(高德 MCP 地理编码获取;无 MCP 用已知坐标表或检索) |
| distance_km | number | ✅ | 当日里程 |
| max_elevation_m | int | ✅ | 当日最高点(垭口)海拔 |
| end_elevation_m | int | ✅ | 住宿点海拔 |
| elevation_gain_m | int | 建议 | 累计爬升(估算耗油用,缺省按 max-起点海拔粗算) |
| scenic_spots | array | ✅ | [{name, type, lat, lng, note, level}];type ∈ "景区"/"非景区"/"穿越路线"/"铺装景观段";level ∈ "必去"/"推荐"/"可选"(用户"一定想去"→必去) |
| fuel_stops | array | ✅ | [{name, lat, lng, brand, note}];brand 建议只填中石油/中石化;标注"必加满"节点 |
| road_closure_risk | string | ✅ | "低"/"中"/"高" + 原因(如"高:折多山降雪管制,备选G350") |
| weather_typical | string | ✅ | 往年同期天气描述(和风 MCP 历史数据或检索) |
| snow_risk | object | detailed 必填 | `{level,basis,checked_at,action}`;level=低/中/高/未知,不得无证据伪造百分比 |
| weather_forecast | object | detailed 必填 | `{status,summary,updated_at,high_c,low_c,precipitation_probability_pct}`;超出预报范围要明确标注 |
| historical_weather | object | detailed 必填 | `{probability_summary,precipitation_probability_pct,snow_probability_pct,source,checked_at,sample_description}`;概率必须可追溯 |
| clothing | string | ✅ | 穿衣推荐(按当日最高海拔与天气) |
| lodging | object | 建议 | {name, lat, lng, price_range, note}(飞猪 MCP 查得;无则给策略) |
| lodging_options | array | 住宿日必填 | 2–3 个飞猪酒店/民宿建议;含状态、来源、查询时间、价格区间、海拔、供氧/地暖/停车。接口不可用时用明确的不可用占位,不得伪造 |
| context_pois | array | detailed 必填 | 沿线草原、山峰/垭口、县城、餐饮、住宿、加油、维修和医院等带坐标标注 |
| requires_lodging | bool | 建议 | 当晚是否产生住宿成本;最终返回家中通常为 false,缺省为 true |
| schedule | object | detailed 必填 | {am, pm, evening}:分时段安排;垭口/长线徒步放上午 |
| meals | object | 建议 | {lunch, dinner, note}:顺路午餐节点+当地特色+晚餐区域 |
| crowd_avoidance | object | detailed 必填 | `{enabled, plan/reason}`;落实用户顶层避堵选择,不启用也要记录 |
| plan_b | string | ✅(骑行日) | 当日备用方案:雨天/管制/闭馆/高反时的替换安排 |
| tickets | array | 可选 | [{name, price, note}]:当日门票/观光车/摆渡车费用 |
| verification | array | 建议 | [{claim, source, date}]:动态核验记录(门票/开放时间/预约要求+来源与查询日期) |
| notes | string | 可选 | 其他备注(高反提示/检查站等) |

## 规则

1. **gapDays 编排原则**:每 4–5 个骑行日 1 个是参考基线,结合季节、非铺装、新手、连续高海拔住宿和绕行条件增减;高风险段之后优先紧邻安排。总天数不得超出用户假期;安全缓冲放不下时缩短线路并说明原因。
2. **封路与降雪分开评级**:`road_closure_risk` 描述道路管制/地灾;`snow_risk` 描述历史同期落雪/结冰风险。高落雪风险默认改期或换低海拔线;条件保留时必须有非空 `no_go_conditions` 和已核验备选。
3. 坐标优先用地图服务实时获取;获取失败时可检索估算,并在 notes 标注"坐标估算"。不得在同一文件中混用 GCJ-02、BD-09 与 WGS-84。
4. `route_geometry` 只有在地图服务返回道路轨迹时填写;人工连接景点坐标不属于道路轨迹。详细路线没有真实道路轨迹不能通过校验。
5. 每次导出前运行 `python scripts/validate_roadbook.py roadbook.json`;机器校验规则见 `references/roadbook.schema.json`。
6. `technical_difficulty` 为 4–5 时,必须同时提供真实 `route_geometry`、非空 `route_evidence`、`bailout_points` 和 `no_go_conditions`;否则只允许保留为候选,不得进入正式详细路书。
