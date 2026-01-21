import pandas as pd
import os

TIME_STEP_HOURS = 0.25

def load_latest_csv(folder="data/live"):
    files = sorted(
        [f for f in os.listdir(folder) if f.endswith(".csv")],
        reverse=True
    )
    if not files:
        return None
    return pd.read_csv(f"{folder}/{files[0]}")

def preprocess(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["occupancy"] = df["occupancy"].astype(int)
    df["ahu_status"] = df["ahu_status"].map({"ON": 1, "OFF": 0})
    return df

def compute_analytics(df, cfg):
    # ---- ZONE ----
    zones = df.dropna(subset=["zone_temp","zone_setpoint","occupancy","zone_id"]).copy()
    zones["overcooled"] = (
        (zones["zone_temp"] < zones["zone_setpoint"] - cfg["ZONE_OVERCOOL_TOL"]) &
        (zones["occupancy"] == 0)
    )
    zones["est_cost"] = (
        (zones["zone_setpoint"] - zones["zone_temp"])
        .clip(lower=0) * 0.3 * cfg["COST_PER_KWH"]
    )
    zone_flags = zones[zones["overcooled"]]

    # ---- AHU ----
    zones_ahu = df.dropna(subset=["zone_temp","zone_setpoint","occupancy","ahu_id","zone_id"])
    zones_ahu["zone_satisfied"] = (
        (zones_ahu["zone_temp"] <= zones_ahu["zone_setpoint"] + cfg["ZONE_SAT_TOL"]) |
        (zones_ahu["occupancy"] == 0)
    )

    ahu_zone_stats = zones_ahu.groupby(["timestamp","ahu_id"]).agg(
        total_zones=("zone_id","count"),
        satisfied_zones=("zone_satisfied","sum")
    ).reset_index()

    ahu_zone_stats["satisfied_ratio"] = (
        ahu_zone_stats["satisfied_zones"] /
        ahu_zone_stats["total_zones"]
    )

    ahu_data = pd.merge(
        ahu_zone_stats,
        df[["timestamp","ahu_id","airflow_pct","ahu_status"]],
        on=["timestamp","ahu_id"]
    )

    ahu_data["ahu_no_demand"] = (
        (ahu_data["ahu_status"] == 1) &
        (ahu_data["airflow_pct"] >= cfg["AHU_AIRFLOW_HIGH"]) &
        (ahu_data["satisfied_ratio"] >= cfg["AHU_ZONE_SAT_RATIO"])
    )

    ahu_data["est_cost"] = (
        ((ahu_data["airflow_pct"] / 100) ** 3 * 10)
        * TIME_STEP_HOURS * cfg["COST_PER_KWH"]
    )

    ahu_flags = ahu_data[ahu_data["ahu_no_demand"]]

    # ---- CHILLER ----
    chillers = df.dropna(subset=["chiller_id","chw_supply_temp","chw_return_temp"])
    chillers["delta_t"] = (
        chillers["chw_return_temp"] - chillers["chw_supply_temp"]
    )

    chillers["low_delta_t"] = chillers["delta_t"] < cfg["CHILLER_LOW_DT"]
    chillers["est_cost"] = (
        (cfg["CHILLER_LOW_DT"] - chillers["delta_t"])
        .clip(lower=0) * 0.05 * 500 * TIME_STEP_HOURS * cfg["COST_PER_KWH"]
    )

    chiller_flags = chillers[chillers["low_delta_t"]]

    return zone_flags, ahu_flags, chiller_flags