# 川西摩旅路书规划 · moto-travel-western-sichuan

一个把「川西骑摩托怎么走」从模糊想法变成**可执行、可复核、可导出**的路书工具包。

它不接受"把景点串起来"的做法，而是反过来：**先选值得骑的连续风景公路，再用少量景点补充**；把节假日避堵、历史落雪风险、海拔适应节奏、加油续航当成硬约束而不是备注；最后输出带真实道路轨迹的 Markdown 路书、Excel 表和高德地图网页。

> 适用范围：四川阿坝州与甘孜州的摩托车（非汽车）旅行规划。
> **不适用**：汽车自驾、川西以外地区、实时应急指挥，也不能把本工具当作医疗、交通执法或道路开放状态的权威结论。

---

## 目录

- [它解决什么问题](#它解决什么问题)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [工作流](#工作流)
- [脚本参考](#脚本参考)
- [路书 JSON 数据模型](#路书-json-数据模型)
- [数据源与回退链](#数据源与回退链)
- [输出物](#输出物)
- [已知限制与免责声明](#已知限制与免责声明)

---

## 它解决什么问题

规划川西摩旅时最容易踩的坑，恰好都是"看着没问题"的：

| 坑 | 后果 | 本 skill 的做法 |
|---|---|---|
| 用驾车算路直接当摩托路线 | 算出来的最短路径往往上高速，而**四川高速禁摩**（《四川省高速公路条例》第四十一条） | 算路一律设 `strategy=6`（不走高速），导出后再扫一遍道路构成，发现高速段就返回修正 |
| 把景区当主线 | 一天耗在停车场和接驳车上，风景全在路上没看到 | 主路线必须是**连续风景公路**；每个骑行日至少写一条 `scenic_routes` 并说明为什么值得骑、最佳光线 |
| 直接开到 4000m 睡 | 高原反应 | 首晚 ≤2600m；进入 3000m 以上后住宿海拔原则上每日 +≤500m；理塘（4014m）只过境不过夜 |
| 用温度而不是海拔判断落雪 | 漏掉垭口暗冰 | 按**日期 + 垭口海拔 + 历史同期资料**逐日评级，写入 `snow_risk`，高风险必须配 `no_go_conditions` |
| 续航按平原油耗算 | 高原断油 | `fuel_planner.py` 给最大安全加油间隔；续航黑洞单独列（金小路、格聂、理塘—雅江…） |
| 替用户决定要不要错峰 | 丢掉用户最想骑的路 | 避堵必须由用户选择，写入顶层 `crowd_avoidance`，不启用也要记录 `mode: accept` |

还有一条工程上的硬要求：**详细路书的主路线必须是地图服务返回的真实道路轨迹**（`route_geometry`），不允许用起终点坐标直线连一条假路线蒙混过去——`validate_roadbook.py` 会把这种路书拦下来。

---

## 快速开始

### 1. 依赖

```bash
pip install -r requirements.txt      # openpyxl>=3.1,<4（仅 Excel 导出需要）
```

Python 3.9+。核心校验、燃料、预算与 HTML 导出只用标准库，`openpyxl` 只有 Excel 导出用得上。

### 2. 作为 Skill 加载

把这个目录放进你的 skills 目录（Claude Code / Kimi Code 等），或链接到项目作用域：

```bash
# 例：本项目作用域
mkdir -p <项目根>/.kimi-code/skills
ln -s "$PWD" <项目根>/.kimi-code/skills/moto-travel-western-sichuan
```

加载后，提到"川西摩旅 / 格聂 / 金小路 / S434 / 折多山 / 稻城亚丁 / 四姑娘山 路书"会触发它。

### 3. 需要的外部能力

这个 skill **不绑定某一个 MCP**，执行前会先探测当前环境实际有什么，缺什么就走回退方案。

| 用途 | 首选 | 回退 |
|---|---|---|
| 算路 / 里程 / 道路轨迹 / POI | 高德地图（Web 服务 Key + REST 或 MCP） | 百度地图 MCP |
| 天气 / 往年同期 / 预警 | 和风天气 | Open-Meteo（免 Key，含历史与预报） |
| 住宿房态 | 飞猪 FlyAI | 给节点策略与价格区间，由用户自订 |
| 沿途情报 | 小红书 | 联网检索 |
| 临时交通管控 | **无单一 API 可靠**，见 `references/road-conditions.md` | 官方渠道 + 现场核实 |

配置细节见 [`references/mcp-setup.md`](references/mcp-setup.md)。

> **密钥纪律**：API Key 不写进路书 JSON、skill 文件、仓库或聊天正文。请通过环境变量或客户端本地 MCP 配置提供。
> 高德 JS API 的**安全密钥**建议按官方文档用服务端代理；直接内嵌在导出 HTML 里只适合本地自用，**不要公开分享或提交到仓库**。

### 4. 跑一次

```bash
python3 scripts/fuel_planner.py --tank 22 --consumption 7.0
python3 scripts/validate_roadbook.py roadbook.json
python3 scripts/budget_estimator.py roadbook.json --tier comfort
python3 scripts/export_excel.py roadbook.json -o 路书.xlsx
AMAP_JS_KEY=... AMAP_JS_SECURITY_CODE=... \
  python3 scripts/export_html.py roadbook.json -o 路书.html
```

---

## 目录结构

```
moto-travel-western-sichuan/
├── SKILL.md                        技能主体：核心原则、依赖预检、7 步工作流
├── requirements.txt                Excel 导出依赖
├── references/                     领域知识 + 规则 + schema（按需读取，见下）
│   ├── western-sichuan-knowledge.md  经典环线模板、垭口海拔表、加油黑洞、景区预约、季节景色、装备与高反
│   ├── roadbook-schema.md            路书 JSON 数据模型的字段规则
│   ├── roadbook.schema.json          可机器校验的 JSON Schema（2020-12）
│   ├── planning-policy.md            节假日用户可控避堵、风景公路评分、历史落雪风险决策规则
│   ├── road-conditions.md            临时交通管控的官方查询渠道 + 检索模板
│   ├── mcp-setup.md                  各 MCP 的接入配置说明
│   └── niche-routes.md               20 条小众/穿越路线候选及其核验状态
├── scripts/
│   ├── roadbook_utils.py           共用：校验、油耗估算、WGS-84/BD-09 → GCJ-02 坐标转换
│   ├── validate_roadbook.py        路书校验（导出前必跑）
│   ├── fuel_planner.py             按车型算最大安全加油间隔 + 续航黑洞核对
│   ├── budget_estimator.py         分类预算（油/住/餐/票/机动）
│   ├── export_excel.py             逐日路书 Excel（高风险标色、gap day 灰底、汇总总耗油）
│   └── export_html.py              单文件高德 JS API 2.0 地图路书
└── tests/
    └── test_core.py                9 个单测：校验规则、坐标转换、HTML/Excel 安全
```

**references 是按需读取的**，不要一次性全读——只在进入对应阶段时读（例如进入输出阶段才读 `roadbook-schema.md`）。

---

## 工作流

`SKILL.md` 定义的 7 步：

1. **收集需求** —— 出发地/天数/日期、车型（排量·油箱·实测油耗→续航）、骑手经验与同行人、节奏档位（轻松 ≤200km / 正常 200–300km / 特种兵 300km+）、**节假日避堵选择（必须问用户）**、风景偏好、落雪风险容忍度、铺装/非铺装取向、预算档位。
   问不全就**合理假设并声明**，不要默默替用户决定。
2. **线路规划（分两级）** —— 先出**粗略路线**（逐日 起终点+里程+住宿点+当日最高海拔）供用户决策；确认后再出**详细路线**（补道路轨迹、连续风景路段、途经点、垭口、路况、加油、备选）。
   候选路线评分顺序：连续风景质量 > 摩托通行与路面可信度 > 历史落雪/地灾风险 > 用户避堵约束 > 补给与住宿 > 景点数量。
3. **加油点规划** —— `fuel_planner.py` + 续航黑洞清单，县城节点优先加满。
4. **天气与装备** —— 历史同期（按海拔选代表点，不能拿县城低海拔代表高垭口）+ 预报 + 预警，逐日写 `snow_risk`；给分层衣物、车辆整备、工具、药品与血氧纪律。
5. **住宿推荐** —— 每晚 2–3 个选项（价格、海拔、供氧/地暖）；大假提前 1–2 个月订。
6. **预约、动态核验与合规** —— 每个收费景区核验票价/开放时间/预约要求并**记录来源与查询日期**；查不到就标"待复核"。含证件清单、检查站、无人机禁飞区。
7. **输出路书** —— 生成 JSON → 校验 → 导出 Markdown / Excel / HTML。

另外两个贯穿性机制：

- **gapDays（机动缓冲日）**：参考基线为每 4–5 个骑行日 1 个；雨雪季、非铺装、新手同行、连续高海拔住宿时增加。`总天数 = 骑行日 + gap ≤ 假期`，安全缓冲放不下时**缩短线路并说明原因**，不靠压缩休息或超长骑行硬凑。
- **每日 plan B**：每个骑行日都要给恶劣天气/管制/闭馆/高反时的替换安排。
- **小众路线漏斗**：路线名称/起终点/轨迹不完整的一律标 `unverified`，只能进候选清单，不得进逐日正式路线；技术难度 4–5 必须先满足近期路况证据、真实轨迹、补给续航核对、撤退点、禁行核验、天气窗口与 no-go 条件。

---

## 脚本参考

### `fuel_planner.py` —— 加油规划

```bash
python scripts/fuel_planner.py --tank 22 --consumption 7.0 [--reserve-km 30]
```

按"平原理论续航 × 保守折减系数（默认 0.75）− 冗余"给出**最大安全加油间隔**，并逐条核对已知续航黑洞区间是否超限。

> 折减系数只是保守的**规划参数**，不是物理定律；必须以本车在相似载重/路况的实测修正。

### `validate_roadbook.py` —— 导出前必跑

```bash
python scripts/validate_roadbook.py roadbook.json
```

机器校验规则见 `references/roadbook.schema.json`。会拦下这些情况：

- 详细路线缺少 `route_geometry`（真实道路轨迹）或 `route_source`
- 详细骑行日缺少 `scenic_routes` / `alternative_routes` / `schedule` / `meals` / `crowd_avoidance` / `snow_risk` / `plan_b`
- `technical_difficulty` 为 4–5 却缺 `route_evidence` / `bailout_points` / `no_go_conditions`
- `snow_risk.level = 高` 却没有 `no_go_conditions`
- 坐标系缺失或混用

### `budget_estimator.py` —— 分类预算

```bash
python scripts/budget_estimator.py roadbook.json --tier comfort [--fuel-price 8.2]
```

档位：`economy` / `comfort` / `premium`。输出油费、住宿、餐饮、门票、机动费（默认 12%）与每日分布。油耗口径与 Excel 导出一致。

### `export_excel.py` —— 逐日路书表

```bash
python scripts/export_excel.py roadbook.json -o 路书.xlsx
```

字段：日期、天气/穿衣、海拔、起终点、路面/难度/可信度、风景点、封路可能性、加油站、餐饮、备用方案、预估耗油。高/中风险标色，gap day 灰底，末尾汇总总耗油。

耗油口径：`里程 × 油耗/100 × (1 + 2%/1000m 终点海拔) × 1.08 + 0.15L/1000m 累计爬升`。

### `export_html.py` —— 高德地图路书

```bash
AMAP_JS_KEY=... AMAP_JS_SECURITY_CODE=... \
  python scripts/export_html.py roadbook.json -o 路书.html
```

单文件应用，高德 JS API 2.0。左侧每日列表，右侧地图，每个「详情」进入 `#day-N` 每日详情（起终点、风景路线、里程、预估油耗、加油点、备选路线、吃饭点、避堵安排、历史落雪风险、路况）。

- 未配置 Key 时页面会引导在浏览器中临时输入（仅存 sessionStorage）。
- 主路线用 `route_geometry` 贴路绘制；只有粗略路线（无几何）时才会调 `AMap.Driving` 临时算路，**并用虚线标为"需复核禁摩/高速"**。
- 导出时把 JSON 里的坐标统一转换为高德所需的 GCJ-02。

### 测试

```bash
cd moto-travel-western-sichuan && python -m unittest discover -s tests
```

9 个用例覆盖：校验规则的正反例、WGS-84→GCJ-02 转换、Excel 公式注入防护、HTML 的 `</script>` 逃逸防护与内嵌 JS 语法。

---

## 路书 JSON 数据模型

顶层：

```json
{
  "title": "川西大环线13天摩旅",
  "coordinate_system": "gcj02",
  "crowd_avoidance": { "mode": "avoid", "locations": ["折多山垭口"], "date_ranges": ["2026-10-01/2026-10-03"] },
  "rider": { "tank_l": 22, "consumption_l_per_100km": 7.0 },
  "days": [ /* ... */ ]
}
```

`coordinate_system` 必填且**同一文件内不得混用**（高德 GCJ-02 / 百度 BD-09 / GPS·OSM WGS-84）。
`crowd_avoidance.mode` 必须是 `avoid` 或 `accept`，且必须反映**用户的选择**。

`days[]` 中每个骑行日的关键字段：

| 字段 | 说明 |
|---|---|
| `route_geometry` | 地图服务返回的真实道路轨迹 `[[lng,lat],...]` |
| `route_source` | `{provider, strategy, checked_at}` |
| `scenic_routes` | 连续风景公路/路段（不是景点列表），含选择理由与最佳光线 |
| `alternative_routes` | 可执行备选 + 触发条件 |
| `surface` / `technical_difficulty` / `route_confidence` | 路面组成 / 技术难度 1–5 / `verified`·`recent-community-lead`·`unverified` |
| `bailout_points` / `no_go_conditions` | 撤退点 / 必须放弃或掉头的条件（难度 4–5 与落雪高风险时强制） |
| `snow_risk` | `{level: 低/中/高/未知, basis, checked_at, action}`，不得无证据伪造百分比 |
| `road_closure_risk` | 与落雪**分开评级**：这里只描述道路管制/地灾 |
| `schedule` / `meals` / `crowd_avoidance` / `plan_b` | 分时段安排（垭口与长线徒步放上午）/ 顺路餐饮 / 本日错峰落实 / 当日备用方案 |

三条容易忽略的规则：

1. **gap day 的 `date` 用 `null`**，未绑定日期时不要把"机动"伪装成一个日期。
2. `route_geometry` 只有在地图服务返回道路轨迹时才填；人工连接景点坐标**不算**道路轨迹。
3. 隧道路段用 DEM 采样会把隧道上方的山体当成路面海拔——已知垭口要用权威值覆盖并注明口径。

---

## 数据源与回退链

这个 skill 的原则是：**每次执行先探测当前环境实际有什么能力，不假设某个 MCP 存在。**

| 环节 | 实际用到的 | 备注 |
|---|---|---|
| 道路轨迹 | 高德 Web 服务 REST `/v3/direction/driving`，`strategy=6`（不走高速）+ `extensions=all` | 逐 step 取 `polyline` 拼接，再 Douglas-Peucker 抽稀；导出前扫描道路名里是否出现"高速" |
| 海拔 | Open-Meteo Elevation API（Copernicus DEM GLO-90），沿真实轨迹等距采样 | 隧道处会高估（采到上方山体），需覆盖 |
| 历史同期气候 | Open-Meteo Archive API（ERA5），1995–2025 年窗口 | 模型格点约 9–25km，**不能替代垭口实测**，必须写明这条局限 |
| 预报 | 和风天气 `/v7/weather/30d`；Open-Meteo Forecast API | 见下方「关于和风天气」 |
| 气象预警 | 和风天气 `/weatheralert/v1/current/{lat}/{lon}` | 旧的 `/v7/warning/now` 已弃用（2026-10-01 停服），必须用 v1 端点 |
| 管制/封路 | 阿坝州政府「阿坝路况」专栏、甘孜州交通运输局、四川省交通运输厅、甘孜/康定/阿坝交警微博 | 无 API，只能查官方公告 + 现场核实 |

### 关于和风天气（几个实测坑）

- **凭据 ID ≠ API Host。** API Host 由系统随机分配、每个账号唯一，形如 `xxxxxxxxxx.re.qweatherapi.com`，要在控制台**设置**里复制。用错 Host 会得到 `403 Invalid Host`——这个报错与 Key 无关，别去换 Key。
- API Host 本身是**身份认证的一部分**，因此不要把它写进任何交付物；放环境变量。
- **30 天产品是格点级的**：同一格点的多个坐标会返回**完全相同**的数值（实测：巴朗山隧道 == 四姑娘山镇、万里城梁子 == 金川县城、新都桥 == 塔公 == 雅拉山口 == 折多山 == 康定）。**它分辨不出 4500m 级垭口**，会把金川河谷的气温报成万里城梁子的气温。
- 所以结论是：**判断垭口暗冰/降雪看按海拔建模的格点值（如 Open-Meteo）；判断大尺度天气形势（哪天连续降雨、何时转晴）用和风。** 两个源都查，交叉验证。

---

## 输出物

一次完整规划产出四个文件：

| 文件 | 内容 |
|---|---|
| `roadbook.json` | 数据源。所有导出都由它生成，也由 `validate_roadbook.py` 校验 |
| `路书.md` | 主路书：逐日行程表（节点/里程/海拔/住宿/加油/景点/分时段安排/备选/no-go）、出发倒排清单、装备清单、加油表、分类预算、风险应对表、通行合规、路况复核清单、数据来源与已知限制 |
| `路书.xlsx` | 逐日表格，适合打印或发给同行的人 |
| `路书.html` | 高德地图版，适合在手机上对着走 |

---

## 已知限制与免责声明

- **不是实时权威。** 路况、管制、票价、预约、房态、开放状态全部需要按「出发前复核清单」在出发前 1 周、48 小时、当日清晨复核。超过 72 小时的管制信息默认需要重新确认。
- **管制信息没有可靠的单一 API。** 地图事件图层和社区帖子只是线索，**不能证明道路开放**；最终以官方公告和现场交通标志为准。
- **长周期预报只是趋势。** 出发前 14 天看到的任何预报都不能当决策依据；真正调整路线顺序要在出发前 7 天用 7 天预报做。
- **历史气候资料的局限必须随结论一起给出。** 用低海拔县城站代表高垭口是不允许的；数据不足时写"未知"并按中等风险处理。
- **医疗内容只提供风险识别与就医/下撤原则**，不构成医疗建议。有高反症状时不继续升高住宿海拔；同海拔休息后加重，或出现静息呼吸困难、步态不稳、意识异常时立即下撤并求医。血氧读数必须结合海拔、趋势、症状与设备误差判断，不能用单一阈值替代诊断。小罐便携氧不能替代下撤或医疗救治。
- **`niche-routes.md` 里的路线只是线索。** 它们来自用户提供的档案（转自短视频标题与简介），难度与风景评分不是官方数据也不是本 skill 实测，**点赞量不参与安全判断**。
- **静态模板会过期。** `western-sichuan-knowledge.md` 里的金额、里程、开放政策与风险点超过 90 天未核验时，不得作为实时结论。

---

## 许可

未指定。若要公开发布，请自行补充 LICENSE；注意 `references/niche-routes.md` 中引用的第三方视频与笔记链接仅作为线索来源。
