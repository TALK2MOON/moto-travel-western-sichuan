# 路书构建流水线

Agent 负责询问用户、调用当前环境提供的 MCP/API，并把已经核验的道路轨迹、天气、住宿与 POI 汇总到 `roadbook.json`。本地脚本只负责确定性的采集辅助、计算、校验和导出；不要用脚本生成的默认值代替用户决定。

## 推荐入口

```bash
python scripts/build_roadbook.py roadbook.json \
  --output-dir roadbook-output \
  --name 川西摩旅路书
```

该命令先运行结构与安全规则校验，再从同一份 JSON 一次性生成 Markdown、HTML 和 Excel。只需要部分格式时使用：

```bash
python scripts/build_roadbook.py roadbook.json --formats md,html
```

高德 Web端(JS API) Key 与安全密钥优先通过本地环境变量提供：

```bash
AMAP_JS_KEY=... AMAP_JS_SECURITY_CODE=... \
  python scripts/build_roadbook.py roadbook.json
```

不要把 Key 写进 `roadbook.json`、仓库或聊天正文。未设置时，HTML 会在浏览器会话中提示用户临时输入。

## 住宿候选预采集

当环境没有飞猪 MCP、但本机已有 FlyAI CLI 时，可以从路书的逐日终点自动提取住宿节点：

```bash
python scripts/fetch_lodging.py roadbook.json \
  --budget-low 200 --budget-high 400 \
  -o lodging.json
```

首次执行前可用 `--dry-run` 检查节点和预计请求数。脚本按四种排序取并集，并增加一次无价格上限的查询；内置缓存、至少 25 秒请求间隔、风控退避、脱敏价格解析和经纬度距离复核。它不会修改原路书，Agent 必须复核结果后再写入 `lodging_options`。

`.roadbook-cache/`、API 原始响应、日志以及生成的路书文件都是运行产物，不应打包进 skill。
