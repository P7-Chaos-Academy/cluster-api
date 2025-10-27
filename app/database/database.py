import requests
import sqlite3
import time
from datetime import datetime

sql_statements = [ 
    """CREATE TABLE IF NOT EXISTS nanos (
            id INTEGER PRIMARY KEY, 
            name text NOT NULL
        );""",

    """CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY,
            in_voltage_mv INTEGER,
            in_current_ma INTEGER,
            in_watts REAL,
            gpu_voltage_mv INTEGER,
            gpu_current_ma INTEGER,
            gpu_watts REAL,
            cpu_voltage_mv INTEGER,
            cpu_current_ma INTEGER,
            cpu_watts REAL,
            cpu_temp REAL,
            gpu_temp REAL,
            collected_at INTEGER,
            fk_nano INTEGER,
            FOREIGN KEY(fk_nano) REFERENCES nanos(id)
        );"""
]

# create tables if they do not already exist
try:
    with sqlite3.connect('cluster.db') as con:
        cursor = con.cursor()

        # execute statements from above
        for statement in sql_statements:
            cursor.execute(statement)

        # commit the transaction (sqlite uses transactions!)
        con.commit()

        print("Tables created successfully.")
except sqlite3.OperationalError as e:
    print("Failed to create tables:", e)

PROM = "http://127.0.0.1:9090" # running on localhost in the Pi!

# map prometheus metrics to coloumn names in db
METRICS = [
    ("jetson_pom_5v_in_voltage_mv", "in_voltage_mv"),
    ("jetson_pom_5v_in_current_ma", "in_current_ma"),
    ("jetson_pom_5v_in_watts",      "in_watts"),
    ("jetson_pom_5v_gpu_voltage_mv","gpu_voltage_mv"),
    ("jetson_pom_5v_gpu_current_ma","gpu_current_ma"),
    ("jetson_pom_5v_gpu_watts",     "gpu_watts"),
    ("jetson_pom_5v_cpu_voltage_mv","cpu_voltage_mv"),
    ("jetson_pom_5v_cpu_current_ma","cpu_current_ma"),
    ("jetson_pom_5v_cpu_watts",     "cpu_watts"),
    ("jetson_cpu_temp",             "cpu_temp"),
    ("jetson_gpu_temp",             "gpu_temp"),
]

def prom_query_latest(metric_name: str) -> dict:
    # accept series that carry the 'nano' label
    query = f'{metric_name}{{job="jetson_nano",nano!=""}}'
    request = requests.get(f"{PROM}/api/v1/query", params={"query": query}, timeout=8)
    request.raise_for_status()
    json = request.json()
    out = {}
    for item in json.get("data", {}).get("result", []):
        nano = item["metric"].get("nano")
        if nano:
            out[nano] = float(item["value"][1])
    return out # {nano: value}

def collect_once():
    cols = [
        "in_voltage_mv","in_current_ma","in_watts",
        "gpu_voltage_mv","gpu_current_ma","gpu_watts",
        "cpu_voltage_mv","cpu_current_ma","cpu_watts",
        "cpu_temp","gpu_temp","collected_at"
    ]
    ts = int(time.time())

    # gather latest samples per metric, keyed by nano
    readings = {}  # nano -> {col: val}
    for metric, col in METRICS:
        latest = prom_query_latest(metric)
        for nano, val in latest.items():
            if nano not in readings:
                readings[nano] = {c: None for c in cols}
                readings[nano]["collected_at"] = ts
            readings[nano][col] = val

    if not readings:
        return  # nothing scraped this cycle

    with sqlite3.connect('cluster.db') as con:
        cur = con.cursor()
        for nano, row in readings.items():
            # upsert nano
            cur.execute("SELECT id FROM nanos WHERE name=?", (nano,))
            got = cur.fetchone()
            if got:
                nano_id = got[0]
            else:
                cur.execute("INSERT INTO nanos(name) VALUES(?)", (nano,))
                nano_id = cur.lastrowid

            values = [row.get(c) for c in cols]
            cur.execute(
                f"INSERT INTO metrics ({','.join(cols)}, fk_nano) "
                f"VALUES ({','.join('?' for _ in cols)}, ?)",
                values + [nano_id]
            )
        con.commit()


if __name__ == "__main__":
    collect_once()
    print("Prometheus → SQLite: done.")