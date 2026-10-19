#!/usr/bin/env python3
"""Car recap table from blurxt --all output: amax AmaxVehicle + its racingphysics RP_CarDynamics.

usage: carsummary.py XT_JSON_DIR OUT.csv      (';' separated, opens directly in French Excel)
"""
import csv, json, sys, os

d = sys.argv[1]
load = lambda n: json.load(open(os.path.join(d, n + ".json"), encoding="utf-8"))
cars = load("amax")["AmaxVehicle"]
phys = load("racingphysics")["RP_CarDynamics"]
tail = lambda ref: ref.rsplit("/", 1)[-1] if ref else ""

cols = ["car", "class", "manufacturer", "style", "use", "hidden", "gameplayTopSpeed_mph",
        "uiSpeed", "uiAccel", "uiGrip", "uiDrift", "uiStability", "uiStrength", "uiDifficulty",
        "carStyle", "weightClass", "health", "aiSteering",
        "mass_kg", "drive", "peakTorque", "limiterRPM", "gears", "topGearRatio", "finalRatio",
        "airFriction", "downforce", "brakeFront", "brakeRear", "physics"]
rows = []
for name, v in cars.items():
    p = phys.get(tail(v["dynamics"]), {})
    e, g = p.get("engine", {}), p.get("gears", {})
    tq = e.get("engineTorque_Rpm", {})
    ratios = g.get("gearRatios", [])
    rows.append([
        name, v["class"], tail(v["Manufacturer"]), tail(v["style"]), v["use"], v["DoNotShowInGame"],
        v["GameplayTopSpeed"], v["UiSpeed"], v["UiAcceleration"], v["UiGrip"], v["UiDrift"],
        v["UiStability"], v["UiStrength"], v["UiDifficulty"], v["UiCarStyle"], v["weightClass"],
        v["HealthGroup"], tail(v["aiSteering"]),
        p.get("mass", {}).get("mass"), p.get("transmission", {}).get("driveType"),
        round(tq.get("yScale", 0) * max(tq.get("dataPoints") or [0]), 1) if tq else None,
        e.get("limiterRPM"), len(ratios), ratios[-1] if ratios else None, g.get("finalRatio"),
        p.get("friction", {}).get("airFriction"), p.get("friction", {}).get("downforce"),
        p.get("brakes", {}).get("frontBrakeForce"), p.get("brakes", {}).get("rearBrakeForce"), tail(v["dynamics"])])

rows.sort(key=lambda r: (r[1], -(r[6] or 0), r[0]))
with open(sys.argv[2], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(cols)
    w.writerows([[str(x).replace(".", ",") if isinstance(x, float) else x for x in r] for r in rows])
print(len(rows), "cars ->", sys.argv[2])
