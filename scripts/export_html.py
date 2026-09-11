#!/usr/bin/env python3
"""Roadbook JSON -> responsive AMap JS API 2.0 roadbook.

The output is a single-file app with an overview and hash-addressable daily detail
pages. It uses road geometry returned by the route provider when available. Rough
routes without geometry are calculated in the browser with AMap.Driving and are
clearly marked as needing motorcycle/highway verification.
"""

import argparse
import html
import json
import os
import sys

from roadbook_utils import estimate_fuel, load_roadbook, to_gcj02


def convert_coordinates(rb):
    source = rb["coordinate_system"]

    def convert_array(point):
        lng, lat = to_gcj02(point[0], point[1], source)
        return [lng, lat]

    def convert_object(point):
        if isinstance(point, dict) and isinstance(point.get("lng"), (int, float)) and isinstance(point.get("lat"), (int, float)):
            point["lng"], point["lat"] = to_gcj02(point["lng"], point["lat"], source)

    for day in rb["days"]:
        day["start_coords"] = convert_array(day["start_coords"])
        day["end_coords"] = convert_array(day["end_coords"])
        if day.get("route_geometry"):
            day["route_geometry"] = [convert_array(point) for point in day["route_geometry"]]
        for route in day.get("alternative_routes", []):
            if route.get("route_geometry"):
                route["route_geometry"] = [convert_array(point) for point in route["route_geometry"]]
        for collection in ("waypoints", "fuel_stops", "scenic_spots", "bailout_points"):
            for point in day.get(collection, []):
                convert_object(point)
        for scenic_route in day.get("scenic_routes", []):
            if scenic_route.get("route_geometry"):
                scenic_route["route_geometry"] = [convert_array(point) for point in scenic_route["route_geometry"]]
        convert_object(day.get("lodging"))
    rb["coordinate_system"] = "gcj02"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roadbook")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--amap-key", default=os.environ.get("AMAP_JS_KEY", ""), help="高德 Web端(JS API) Key；也可用 AMAP_JS_KEY")
    parser.add_argument("--amap-security-code", default=os.environ.get("AMAP_JS_SECURITY_CODE", ""), help="高德 JS API 安全密钥；也可用 AMAP_JS_SECURITY_CODE")
    args = parser.parse_args()
    try:
        rb = load_roadbook(args.roadbook)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))

    convert_coordinates(rb)
    consumption = rb.get("rider", {}).get("consumption_l_per_100km", 3.5)
    for day in rb["days"]:
        day["estimated_fuel_l"] = 0 if day.get("is_gap_day") else round(estimate_fuel(day, consumption), 1)

    out = args.output or "roadbook.html"
    days_js = json.dumps(rb["days"], ensure_ascii=False).replace("</", "<\\/")
    crowd_js = json.dumps(rb.get("crowd_avoidance", {}), ensure_ascii=False).replace("</", "<\\/")
    config_js = json.dumps({"key": args.amap_key, "securityCode": args.amap_security_code}, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(rb.get("title", "摩旅路书"), quote=True)

    template = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<title>__TITLE__</title>
<style>
:root{--asphalt:#16252d;--slate:#30444d;--paper:#f7f8f4;--route:#ec6a38;--ice:#6aaec4;--warning:#c7493a;--line:#d7dedb;--muted:#64757c;--white:#fff;--shadow:0 18px 45px rgba(18,35,43,.16)}
*{box-sizing:border-box}html,body{height:100%;margin:0}body{overflow:hidden;background:var(--paper);color:var(--asphalt);font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}button,input{font:inherit}button{cursor:pointer}.shell{display:grid;grid-template-columns:360px 1fr;height:100%}.rail{position:relative;z-index:5;display:flex;min-height:0;flex-direction:column;background:var(--paper);box-shadow:8px 0 35px rgba(18,35,43,.14)}
.mast{padding:28px 26px 20px;background:var(--asphalt);color:#fff}.eyebrow{font:700 11px/1 "DIN Alternate","Avenir Next",sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#a9c0c8}.mast h1{margin:10px 0 12px;font-size:27px;line-height:1.2;letter-spacing:-.02em}.mast-meta{display:flex;gap:14px;color:#c8d4d8;font-size:12px}.route-list{overflow:auto;padding:14px 14px 96px}.day-card{width:100%;display:grid;grid-template-columns:48px 1fr auto;gap:10px;align-items:center;margin:0 0 8px;padding:12px;border:1px solid transparent;border-radius:12px;background:transparent;color:inherit;text-align:left;transition:.2s ease}.day-card:hover,.day-card:focus-visible{background:#fff;border-color:var(--line);outline:none}.day-card.active{background:#fff;border-color:#bdc9c5;box-shadow:0 8px 20px rgba(18,35,43,.08)}.day-no{font:800 17px/1 "DIN Alternate","Avenir Next",sans-serif;color:var(--route)}.day-route{min-width:0}.day-route strong,.day-route small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.day-route strong{font-size:14px}.day-route small{margin-top:4px;color:var(--muted);font-size:11px}.open-label{font-size:11px;color:var(--muted)}
.map-wrap{position:relative;min-width:0}.map{height:100%;background:#dce5e3}.map-status{position:absolute;top:18px;left:18px;z-index:4;max-width:min(520px,calc(100% - 36px));padding:10px 13px;border-radius:9px;background:rgba(22,37,45,.88);color:#fff;font-size:12px;backdrop-filter:blur(8px)}.legend{position:absolute;right:18px;bottom:18px;z-index:4;padding:10px 12px;border:1px solid rgba(255,255,255,.55);border-radius:10px;background:rgba(247,248,244,.92);box-shadow:var(--shadow);font-size:11px}.swatch{display:inline-block;width:19px;height:4px;margin:0 5px 2px 10px;background:var(--route);vertical-align:middle}.swatch:first-child{margin-left:0}.swatch.alt{background:var(--ice)}
.detail{position:absolute;z-index:8;top:18px;right:18px;bottom:18px;width:min(470px,calc(100% - 36px));overflow:auto;padding:0 24px 28px;border:1px solid rgba(255,255,255,.7);border-radius:18px;background:rgba(247,248,244,.96);box-shadow:var(--shadow);backdrop-filter:blur(14px);transform:translateX(calc(100% + 40px));transition:transform .28s ease}.detail.open{transform:none}.detail-head{position:sticky;top:0;z-index:2;margin:0 -24px 20px;padding:22px 24px 16px;background:rgba(247,248,244,.97);border-bottom:1px solid var(--line)}.detail-head-top{display:flex;justify-content:space-between;gap:16px}.detail h2{margin:5px 0 0;font-size:24px;line-height:1.2}.close{width:36px;height:36px;border:1px solid var(--line);border-radius:50%;background:#fff;color:var(--asphalt);font-size:19px}.route-hero{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding:17px;border-radius:13px;background:var(--asphalt);color:#fff}.route-hero span{font-size:11px;color:#9db2ba}.route-hero strong{display:block;margin-top:3px}.route-arrow{color:var(--route);font-weight:900}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 22px}.metric{padding:12px 10px;border:1px solid var(--line);border-radius:10px;background:#fff}.metric span{display:block;color:var(--muted);font-size:10px}.metric strong{display:block;margin-top:4px;font:800 17px/1.1 "DIN Alternate","Avenir Next",sans-serif}.section{padding:17px 0;border-top:1px solid var(--line)}.section h3{margin:0 0 9px;font-size:13px;letter-spacing:.04em}.section p{margin:0;color:var(--slate);font-size:13px;line-height:1.65}.chips{display:flex;flex-wrap:wrap;gap:7px}.chip{padding:6px 9px;border-radius:999px;background:#fff;border:1px solid var(--line);font-size:11px}.risk-high{color:var(--warning);font-weight:700}.risk-medium{color:#a7651c;font-weight:700}.snow{border-left:4px solid var(--ice);padding-left:12px}.empty{color:var(--muted)!important}.key-dialog{position:fixed;inset:0;z-index:30;display:none;place-items:center;padding:20px;background:rgba(22,37,45,.72);backdrop-filter:blur(8px)}.key-dialog.open{display:grid}.key-box{width:min(480px,100%);padding:26px;border-radius:18px;background:var(--paper);box-shadow:var(--shadow)}.key-box h2{margin:0 0 8px}.key-box p{color:var(--muted);font-size:13px;line-height:1.6}.key-box label{display:block;margin-top:14px;font-size:12px;font-weight:700}.key-box input{width:100%;margin-top:6px;padding:11px 12px;border:1px solid #b9c5c1;border-radius:8px;background:#fff}.primary{width:100%;margin-top:18px;padding:12px;border:0;border-radius:9px;background:var(--route);color:#fff;font-weight:700}.key-error{min-height:18px;margin-top:8px;color:var(--warning);font-size:12px}.map-pin{width:28px;height:28px;display:grid;place-items:center;border:2px solid #fff;border-radius:50% 50% 50% 8px;transform:rotate(-45deg);background:var(--asphalt);box-shadow:0 3px 10px rgba(0,0,0,.28);color:#fff}.map-pin span{transform:rotate(45deg);font:800 11px/1 sans-serif}
@media(max-width:760px){.shell{grid-template-columns:1fr;grid-template-rows:44% 56%}.rail{grid-row:2;box-shadow:0 -8px 30px rgba(18,35,43,.13)}.mast{padding:14px 16px 12px}.mast h1{margin:5px 0 7px;font-size:19px}.eyebrow{font-size:9px}.route-list{display:flex;overflow:auto;padding:10px 12px 20px;gap:8px}.day-card{flex:0 0 240px;margin:0}.map-wrap{grid-row:1}.detail{position:fixed;top:auto;left:0;right:0;bottom:0;width:100%;max-height:82%;border-radius:18px 18px 0 0;transform:translateY(105%)}.detail.open{transform:none}.legend{display:none}.map-status{top:10px;left:10px;max-width:calc(100% - 20px)}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style></head><body>
<main class="shell"><aside class="rail"><header class="mast"><div class="eyebrow">Western Sichuan / Moto roadbook</div><h1>__TITLE__</h1><div class="mast-meta"><span id="trip-days"></span><span id="trip-distance"></span><span>风景公路优先</span></div></header><nav id="route-list" class="route-list" aria-label="每日路线"></nav></aside><section class="map-wrap"><div id="map" class="map"></div><div id="map-status" class="map-status">正在准备高德地图…</div><div class="legend"><span class="swatch"></span>主路线 <span class="swatch alt"></span>备选路线</div><article id="detail" class="detail" aria-live="polite"></article></section></main>
<div id="key-dialog" class="key-dialog" role="dialog" aria-modal="true" aria-labelledby="key-title"><div class="key-box"><h2 id="key-title">连接高德地图</h2><p>此路书使用高德地图 JS API 2.0。请输入“Web端(JS API)”Key 与安全密钥；仅保存在当前浏览器会话中。</p><label>Web 端 Key<input id="amap-key" autocomplete="off"></label><label>安全密钥<input id="amap-code" autocomplete="off"></label><button id="connect" class="primary">加载道路地图</button><div id="key-error" class="key-error"></div></div></div>
<script>
const days=__DAYS__;const crowdPolicy=__CROWD__;const embeddedConfig=__CONFIG__;const colors=['#ec6a38','#d45a34','#f08a45','#bf4b32','#e97936','#cd6540'];let map=null;let overlays=[];let currentDay=1;
const $=s=>document.querySelector(s);const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const validPoint=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);function riskClass(value){value=String(value||'');return value.startsWith('高')?'risk-high':value.startsWith('中')?'risk-medium':''}
function renderRail(){const total=days.reduce((n,d)=>n+(Number(d.distance_km)||0),0);$('#trip-days').textContent=`${days.length} 天`;$('#trip-distance').textContent=`${Math.round(total)} km`;$('#route-list').innerHTML=days.map(d=>`<button class="day-card ${d.day===currentDay?'active':''}" data-day="${d.day}" aria-label="查看第${d.day}天详情"><span class="day-no">D${d.day}</span><span class="day-route"><strong>${esc(d.is_gap_day?'机动缓冲日':`${d.start} → ${d.end}`)}</strong><small>${esc(d.date||'日期机动')} · ${esc(d.distance_km)} km</small></span><span class="open-label">详情 ›</span></button>`).join('');document.querySelectorAll('.day-card').forEach(b=>b.addEventListener('click',()=>openDay(Number(b.dataset.day))))}
function block(title,body,klass=''){return `<section class="section ${klass}"><h3>${title}</h3>${body}</section>`}
function detailHtml(d){if(d.is_gap_day)return `<header class="detail-head"><div class="detail-head-top"><div><div class="eyebrow">D${d.day} / GAP DAY</div><h2>机动缓冲日</h2></div><button class="close" aria-label="关闭详情">×</button></div></header>${block('如何使用',`<p>${esc(d.notes||'用于吸收天气、管制、疲劳或高原反应造成的延误。')}</p>`)}`;const scenic=(d.scenic_routes||[]).map(r=>`<span class="chip">${esc(r.name)}${r.distance_km?` · ${esc(r.distance_km)}km`:''}</span>`).join('');const fuels=(d.fuel_stops||[]).map(s=>`<span class="chip">⛽ ${esc(s.name)}${s.note?` · ${esc(s.note)}`:''}</span>`).join('');const alts=(d.alternative_routes||[]).map(r=>`<p><strong>${esc(r.name)}</strong>${r.distance_km?` · ${esc(r.distance_km)}km`:''}<br>${esc(r.trigger||r.note||'按当天路况启用')}</p>`).join('');const snow=d.snow_risk||{};const meals=d.meals||{};const crowd=d.crowd_avoidance||{};return `<header class="detail-head"><div class="detail-head-top"><div><div class="eyebrow">D${d.day} / ${esc(d.date)}</div><h2>${esc(d.start)} → ${esc(d.end)}</h2></div><button class="close" aria-label="关闭详情">×</button></div></header><div class="route-hero"><div><span>起点</span><strong>${esc(d.start)}</strong></div><div class="route-arrow">→</div><div><span>终点 / 住宿</span><strong>${esc(d.end)}</strong></div></div><div class="metrics"><div class="metric"><span>里程</span><strong>${esc(d.distance_km)} km</strong></div><div class="metric"><span>预估油耗</span><strong>${esc(d.estimated_fuel_l)} L</strong></div><div class="metric"><span>最高海拔</span><strong>${esc(d.max_elevation_m)} m</strong></div></div>${block('风景路线',scenic?`<div class="chips">${scenic}</div>`:'<p class="empty">尚未标出独立风景路段</p>')}${block('加油点',fuels?`<div class="chips">${fuels}</div>`:'<p class="empty">没有可靠加油点，出发前必须补齐</p>')}${block('备选路线',alts||`<p>${esc(d.plan_b||'未提供')}</p>`)}${block('顺路吃饭',`<p>午餐：${esc(meals.lunch||'待选')}<br>晚餐：${esc(meals.dinner||'待选')}</p>`)}${block('历史落雪风险',`<p><span class="${riskClass(snow.level)}">${esc(snow.level||'待核验')}</span>${snow.basis?` · ${esc(snow.basis)}`:''}<br>${esc(snow.action||'出发前按最新预报复核')}</p>`,'snow')}${block('避开人群与车流',`<p>${crowd.enabled===false?'用户未启用本日错峰':esc(crowd.plan||crowd.reason||'按用户指定的地点与时段执行；未指定则不擅自删减路线')}</p>`)}${block('路况与天气',`<p><span class="${riskClass(d.road_closure_risk)}">${esc(d.road_closure_risk)}</span><br>${esc(d.weather_typical)}<br>${esc(d.clothing)}</p>`)}`}
function openDay(dayNo){currentDay=dayNo;const d=days.find(x=>x.day===dayNo);if(!d)return;renderRail();$('#detail').innerHTML=detailHtml(d);$('#detail').classList.add('open');$('#detail .close').addEventListener('click',closeDetail);location.hash=`day-${dayNo}`;drawDay(d)}function closeDetail(){$('#detail').classList.remove('open');history.replaceState(null,'',location.pathname+location.search)}function clearMap(){if(map&&overlays.length)map.remove(overlays);overlays=[]}
function marker(AMap,point,label,color){if(!validPoint(point))return null;return new AMap.Marker({position:point,anchor:'bottom-center',content:`<div class="map-pin" style="background:${color}"><span>${esc(label)}</span></div>`})}function drawGeometry(AMap,path,color,dashed=false){if(!Array.isArray(path)||path.length<2)return null;return new AMap.Polyline({path,strokeColor:color,strokeWeight:6,strokeOpacity:.92,strokeStyle:dashed?'dashed':'solid',lineJoin:'round',showDir:true})}
function drawDay(d){if(!map)return;clearMap();const AMap=window.__AMap;if(d.is_gap_day){const m=marker(AMap,d.end_coords,'休','#64757c');if(m){overlays.push(m);map.add(m);map.setFitView(overlays)}return}const main=drawGeometry(AMap,d.route_geometry,colors[(d.day-1)%colors.length]);if(main){overlays.push(main);map.add(main);$('#map-status').textContent='主路线来自已核验道路轨迹'}else{drawAmapRoute(d)};(d.alternative_routes||[]).forEach(r=>{const line=drawGeometry(AMap,r.route_geometry,'#6aaec4',true);if(line){overlays.push(line);map.add(line)}});const s=marker(AMap,d.start_coords,'起','#16252d'),e=marker(AMap,d.end_coords,'终','#ec6a38');[s,e].filter(Boolean).forEach(m=>{overlays.push(m);map.add(m)});(d.fuel_stops||[]).forEach(f=>{const m=marker(AMap,[f.lng,f.lat],'油','#c7493a');if(m){overlays.push(m);map.add(m)}});if(overlays.length)map.setFitView(overlays,false,[70,70,70,70])}
function drawAmapRoute(d){const AMap=window.__AMap;$('#map-status').textContent='正在用高德道路网络临时算路；仍需复核禁摩与高速路段';const driving=new AMap.Driving({policy:AMap.DrivingPolicy.LEAST_FEE,ferry:1,extensions:'all'});const opts={waypoints:(d.waypoints||[]).map(p=>new AMap.LngLat(p.lng,p.lat))};driving.search(new AMap.LngLat(...d.start_coords),new AMap.LngLat(...d.end_coords),opts,(status,result)=>{if(status==='complete'&&result.routes?.length){const path=result.routes[0].steps.flatMap(step=>step.path);const line=drawGeometry(AMap,path,'#ec6a38',true);if(line){overlays.push(line);map.add(line);map.setFitView(overlays)}}else{$('#map-status').textContent='临时算路失败：请补充 route_geometry 或检查高德 Key'}})}
function loadLoader(){return new Promise((resolve,reject)=>{if(window.AMapLoader)return resolve();const s=document.createElement('script');s.src='https://webapi.amap.com/loader.js';s.onload=resolve;s.onerror=()=>reject(new Error('无法加载高德 JS API Loader'));document.head.appendChild(s)})}async function connect(config){try{$('#key-error').textContent='';window._AMapSecurityConfig={securityJsCode:config.securityCode};await loadLoader();const AMap=await AMapLoader.load({key:config.key,version:'2.0',plugins:['AMap.Driving','AMap.ToolBar','AMap.Scale']});window.__AMap=AMap;map=new AMap.Map('map',{viewMode:'2D',zoom:7,center:[101.9,30.6],mapStyle:'amap://styles/whitesmoke'});map.addControl(new AMap.ToolBar({position:{right:'18px',top:'70px'}}));map.addControl(new AMap.Scale());$('#key-dialog').classList.remove('open');sessionStorage.setItem('amap-roadbook-config',JSON.stringify(config));const hashDay=Number((location.hash.match(/day-(\d+)/)||[])[1]);openDay(hashDay||days[0].day)}catch(err){$('#key-dialog').classList.add('open');$('#key-error').textContent=`加载失败：${err.message||err}`;$('#map-status').textContent='高德地图尚未连接'}}
$('#connect').addEventListener('click',()=>{const config={key:$('#amap-key').value.trim(),securityCode:$('#amap-code').value.trim()};if(!config.key||!config.securityCode){$('#key-error').textContent='Key 和安全密钥都需要填写';return}connect(config)});renderRail();const saved=JSON.parse(sessionStorage.getItem('amap-roadbook-config')||'null');const initial=embeddedConfig.key&&embeddedConfig.securityCode?embeddedConfig:saved;if(initial)connect(initial);else{$('#key-dialog').classList.add('open');$('#map-status').textContent='输入高德 Web 端 Key 后显示道路地图'}
</script></body></html>'''
    page = template.replace("__TITLE__", safe_title).replace("__DAYS__", days_js).replace("__CROWD__", crowd_js).replace("__CONFIG__", config_js)
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(page)
    key_note = "已内置高德 JS 配置" if args.amap_key and args.amap_security_code else "打开页面后输入高德 Web 端 Key"
    print(f"已导出 {out} ({len(rb['days'])} 天，{key_note})")


if __name__ == "__main__":
    main()
