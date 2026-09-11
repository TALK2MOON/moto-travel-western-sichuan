#!/usr/bin/env python3
"""川西摩旅加油点规划器。

根据车型油箱容积与实测油耗,计算高原折减后的安全续航间隔,
并结合已知续航黑洞清单给出加油策略。

用法:
    python fuel_planner.py --tank 15 --consumption 3.5
    python fuel_planner.py --tank 15 --consumption 3.5 --reserve-km 30
"""
import argparse

# 保守规划系数,不是通用物理定律;应以本车在相似载重/路况的实测修正
ALTITUDE_FACTOR = 0.75
# 已知续航黑洞: (名称, 大致区间长度km, 说明)
FUEL_DESERTS = [
    ("理塘—稻城(G227)", 230, "中途基本无站,理塘出发前必加满;稻城桑堆/县城有站"),
    ("理塘—巴塘(G318)", 170, "途中无加油站,县城才有"),
    ("理塘—甘孜/新龙段", 260, "间隔远,见站就加;新龙县城中石油、吴亚乡民营站"),
    ("格聂南线等支线", 200, "支线加油站稀少,切勿侥幸,理塘必加满"),
]
# 县城必加节点
MUST_FILL_TOWNS = ["马尔康", "色达", "甘孜", "理塘", "新都桥", "康定", "稻城(香格里拉镇)"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tank", type=float, required=True, help="油箱容积(升)")
    p.add_argument("--consumption", type=float, required=True, help="实测油耗(升/100km)")
    p.add_argument("--reserve-km", type=float, default=30, help="保留冗余里程(km,默认30)")
    args = p.parse_args()

    if args.tank <= 0 or args.consumption <= 0:
        p.error("油箱容积和实测油耗必须大于 0")
    if args.reserve_km < 0:
        p.error("保留冗余里程不能小于 0")

    flat_range = args.tank / args.consumption * 100
    plateau_range = flat_range * ALTITUDE_FACTOR
    safe_range = plateau_range - args.reserve_km

    if safe_range <= 0:
        p.error("扣除冗余后的安全续航不大于 0,请检查输入或调整路线")

    print(f"=== 加油规划 ===")
    print(f"油箱 {args.tank}L / 油耗 {args.consumption}L/100km")
    print(f"平原理论续航: {flat_range:.0f} km")
    print(f"保守规划折减(x{ALTITUDE_FACTOR},需用本车实测校正): {plateau_range:.0f} km")
    print(f"扣除冗余 {args.reserve_km}km 后【最大安全加油间隔】: {safe_range:.0f} km")
    print()
    print("=== 续航黑洞核对(区间长度 vs 你的安全间隔) ===")
    for name, km, note in FUEL_DESERTS:
        flag = "⚠️ 超出安全间隔,需备油壶或中途补油" if km > safe_range else "✓ 可覆盖,但出发前加满"
        print(f"- {name} (~{km}km): {flag}。{note}")
    print()
    print("=== 策略 ===")
    print("1. 县城节点必加满: " + "、".join(MUST_FILL_TOWNS))
    print("2. 原则: 见站勤加、半箱开始评估下一站;优先正规大站,不要为品牌跳过必要补给")
    print("3. 92号沿线普遍有;95号仅县城大站有保障")
    print("4. 四川高速禁摩,全程国道,勿按高速油耗估算")


if __name__ == "__main__":
    main()
