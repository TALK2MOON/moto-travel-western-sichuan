# MCP/API 接入配置指引

本 skill 不依赖某一个固定 MCP 才能触发,但详细路线优先接入官方高德地图 MCP。执行时先查看当前环境实际提供的地图、天气、住宿和检索工具;缺少关键能力时主动说明收益并请求用户安装/连接。第三方项目、安装命令、免费额度和认证方式都可能变化,使用前必须访问其官方仓库或文档复核。

## 能力预检

1. 列出当前可调用工具,按“路线与坐标 / 天气与预警 / 住宿 / 联网检索”归类。
2. 对候选工具做只读能力探测,确认是否真的支持历史天气、避开高速、路线轨迹、房态等所需字段。
3. 不存在对应能力时使用公开网页检索或明确标为估算;不得因为本文列过某个 MCP 就假设它已安装。
4. 社区 MCP 视为可选依赖,不得要求用户提供 Cookie、令牌或账号给模型;凭据只能由用户在受信任客户端本地配置。
5. API Key 不写进路书 JSON、skill 文件、仓库或聊天正文。请用户通过客户端 MCP 配置或本地环境变量设置,配置后只做最小的只读连通性测试。

## 目录
- 高德地图 MCP(首选:算路/POI/导航)
- 百度地图 MCP(备选)
- 飞猪 FlyAI(住宿/票务)
- 和风天气 MCP(社区)
- 12306 MCP(社区)
- 小红书 MCP(社区,有风险)

---

## 高德地图 MCP(官方,首选且优先请求安装)

- 先询问用户是否愿意连接官方高德 MCP;当前客户端能代装时,在用户授权后安装,否则给出官方配置入口。
- 申请:高德开放平台创建应用并添加 **Web 服务** Key。此 Key 用于 MCP,不是 HTML 地图的 Web 端 JS Key。
- 官方 Streamable HTTP:`https://mcp.amap.com/mcp?key=本地配置的Key`。
- 官方 Node.js I/O:`npx -y @amap/amap-maps-mcp-server`,环境变量 `AMAP_MAPS_API_KEY`。版本与最低 Node 要求以高德官方文档为准。
- 配好后探测:地理编码、驾车路线(避开高速)、道路几何、沿途加油/餐饮 POI。详细路书逐段保存返回的道路轨迹和查询时间。
- 摩托车通行规则不由驾车算路自动保证;对高速、城市禁限摩和临时管制另行复核。

## 高德 JS API 2.0(HTML 地图,与 MCP 分开)

- 在高德控制台创建 **Web端(JS API)** Key,并取得安全密钥。2021-12-02 之后申请的 Key 需配合安全密钥。
- 本地导出可设置 `AMAP_JS_KEY` 与 `AMAP_JS_SECURITY_CODE`;缺少时,导出的 HTML 会在浏览器中请求临时输入并仅保存在会话中。
- 生产发布不要把安全密钥长期明文写入 HTML;优先按高德官方“JS API 安全密钥使用”文档配置服务端代理。
- HTML 必须用 `AMap.Map`、`AMap.Polyline` 和必要时的 `AMap.Driving`,不得再用 Leaflet 加载高德瓦片冒充高德 JS 地图。

## 百度地图 MCP(官方,备选)

- 申请:百度地图开放平台注册→创建服务端 AK
- 接入:支持 HTTP/SSE/stdio;`pip install mcp-server-baidu-maps` 或 `npx @baidumap/mcp-server-baidu-maps`
- 能力:地点检索、路线规划、地理编码、天气、"马克地图"(生成可分享旅行地图)

## 飞猪 FlyAI(官方,免 Key)

- 飞猪相关旅行工具若在当前环境可用,可用于查询住宿与票务;“免 Key”“即插即用”等状态必须以使用时的官方文档为准
- 接入:ClawHub/GitHub 安装 flyai skill;或 CLI:`npm i -g @fly-ai/flyai-cli`
- 能力:酒店/民宿搜索与报价、机票、火车票、景点门票
- 摩旅用法:按每晚住宿节点查 2–3 个酒店/民宿选项(价格、海拔、供氧/地暖);大假提示提前 1–2 个月订

### CLI 实测要点(2026-09 验证,`@fly-ai/flyai-cli` 1.0.16)

**先探测再回退。** 该 CLI 目前**可用且免 Key**,不需要 MCP 也能用。缺少 MCP 时不要直接跳到“给价格区间由用户自订”的回退方案,先 `which flyai`,没有就 `npm i -g @fly-ai/flyai-cli`,再不行才回退。

```bash
flyai search-hotel \
  --dest-name "康定" \
  --check-in-date 2026-10-04 --check-out-date 2026-10-05 \
  --sort rate_desc
```

- 其他子命令:`search-poi`(景点)、`search-flight`(机票)、`search-train`(火车票)、`keyword-search`、`ai-search`
- 可用参数:`--dest-name`(目的地)、`--key-words`、`--poi-name`、`--hotel-types hotel|homestay|inn`、`--sort distance_asc|rate_desc|price_asc|price_desc|no_rank`、`--check-in-date`/`--check-out-date`、`--hotel-stars`、`--hotel-bed-types`、`--max-price`
- 返回:JSON(`data.itemList[]`),字段含 `name`/`star`(经济型·舒适型·高档型·豪华型)/`price`/`address`/`latitude`/`longitude`/`decorationTime`/`interestsPoi`/`detailUrl`

**四个必须注意的坑:**

1. **价格是脱敏区间,不是精确报价。** 返回形如 `¥2xx`(= 200–299 元)、`¥7x`、`¥1xxx`、`¥2xxx`。可以据此分档,但**不能写成具体房价**,也不能当实时房态用。
2. **目的地名有歧义,必须按坐标复核。** `--dest-name 卧龙` 会匹配到**河南南阳卧龙区**(离目标 900km);实测查"卧龙"无结果,改用 `--dest-name 汶川` 再按经纬度距离过滤才对。**拿到结果后一定要用返回的 `latitude`/`longitude` 与节点坐标算距离并排序**,不要直接取第一条。
3. **偏远节点覆盖薄。** 格聂镇实测只有 2 家(其中一家是"理塘格聂云庭富氧酒店(格聂之眼景区店)",距镇中心 4.6km)。这类节点要在路书里明确写"房源少、务必提前电话订房",并给出低海拔替代住宿。
4. `--poi-name` / `--key-words` 可能返回非 JSON(用法或服务端限制);以 `--dest-name` + 自行距离过滤为主。

**用法建议:** 逐晚节点各查一次,取 25–30km 内按距离排序的前 2–3 家,连同档次、价格区间、距离、地址、建成年份写进路书;并按过夜海拔补一句选房建议(≥3000m 优先供氧/地暖,格聂镇这类高海拔点必须确认供氧、热水与停车)。

## 和风天气 MCP(社区开源,需免费 Key)

- 申请:和风天气(dev.qweather.com)注册,免费额度
- 项目示例:`hefeng-mcp-weather` 等社区实现;不同实现能力不一致,先探测它是否支持实时天气、预报、历史数据和气象预警
- 摩旅用法:历史同期数据只用于季节参考;出发前使用最新预报和预警调整路线,并记录数据时间

## 12306 MCP(社区开源,免登录)

- `npx -y 12306-mcp` 一条命令运行;查余票、经停站、中转方案
- 摩旅用法:摩托托运/人车分流的备用方案查询

## 小红书 MCP(社区开源,⚠️ 风险)

- 主流项目:`xpzouying/xiaohongshu-mcp`(Go,预编译二进制,扫码登录,Cookie 持久化;支持搜索笔记/详情/评论);RedNote-MCP(Playwright)等
- **风险:非官方逆向,违反平台协议,有封号风险——必须提示用户用小号**
- 部署:本地跑服务(如 :18060)后客户端配置
- 摩旅用法:搜"折多山 管制""新龙 塌方"等关键词按最新排序,获取摩友实时路况情报;住宿/餐馆口碑
