#!/usr/bin/env python3
"""路书 JSON -> 分类预算估算。

用法:
    python budget_estimator.py roadbook.json [--tier economy|comfort|premium] [--fuel-price 8.2]

分类:油费(由预估耗油推算) | 住宿 | 餐饮 | 门票 | 机动费用(默认12%)。
耗油口径与 export_excel.py 一致:海拔修正+2%/1000m、爬升+0.15L/1000m、高原综合x1.08。
"""
import argparse
import sys

from roadbook_utils import estimate_fuel, load_roadbook

TIERS = {
    "economy":  {"lodging": 150, "meals": 60},
    "comfort":  {"lodging": 300, "meals": 100},
    "premium":  {"lodging": 600, "meals": 160},
}
BUFFER_RATE = 0.12

def main():
    p = argparse.ArgumentParser()
    p.add_argument("roadbook")
    p.add_argument("--tier", choices=TIERS.keys(), default="comfort")
    p.add_argument("--fuel-price", type=float, default=8.2, help="油价 元/升")
    args = p.parse_args()

    if args.fuel_price <= 0:
        p.error("油价必须大于 0")

    try:
        rb = load_roadbook(args.roadbook)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    consumption = rb.get("rider", {}).get("consumption_l_per_100km", 3.5)
    if consumption <= 0:
        p.error("油耗必须大于 0")
    tier = TIERS[args.tier]

    fuel_l = lodging_cost = tickets = 0.0
    lodging_nights = 0
    daily = []
    for d in rb["days"]:
        day_fuel = 0.0 if d.get("is_gap_day") else estimate_fuel(d, consumption)
        fuel_l += day_fuel
        day_lodging = tier["lodging"] if d.get("requires_lodging", True) else 0
        if day_lodging:
            lodging_nights += 1
        lodging_cost += day_lodging
        day_tickets = 0.0
        for t in d.get("tickets", []):
            day_tickets += float(t.get("price", 0))
        tickets += day_tickets
        daily.append((d["day"], day_fuel * args.fuel_price, day_lodging, tier["meals"], day_tickets))

    fuel_cost = fuel_l * args.fuel_price
    meals_cost = len(rb["days"]) * tier["meals"]
    subtotal = fuel_cost + lodging_cost + meals_cost + tickets
    buffer = subtotal * BUFFER_RATE

    print(f"=== 分类预算({args.tier}档)===")
    print(f"油费:   {fuel_cost:8.0f} 元  ({fuel_l:.1f}L × {args.fuel_price}元/L)")
    print(f"住宿:   {lodging_cost:8.0f} 元  ({lodging_nights}晚 × {tier['lodging']}元)")
    print(f"餐饮:   {meals_cost:8.0f} 元  ({len(rb['days'])}天 × {tier['meals']}元)")
    print(f"门票:   {tickets:8.0f} 元")
    print(f"机动费: {buffer:8.0f} 元  ({int(BUFFER_RATE*100)}%:维修/救援/临时变更)")
    print(f"--------------------------------")
    print(f"全程预估: {subtotal + buffer:8.0f} 元(不含大交通与装备)")
    print("\n=== 每日分布(不含按比例分摊的机动费) ===")
    for day, day_fuel_cost, day_lodging, day_meals, day_tickets in daily:
        day_total = day_fuel_cost + day_lodging + day_meals + day_tickets
        print(f"D{day}: {day_total:.0f} 元 (油{day_fuel_cost:.0f}/住{day_lodging:.0f}/餐{day_meals:.0f}/票{day_tickets:.0f})")

if __name__ == "__main__":
    main()
