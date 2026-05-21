
import os
import csv
import time
from datetime import datetime
from collections import defaultdict
from threading import Thread
import queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

INPUT_DIR = r"C:/Vaisala/observation_csv/ready_for_transfer"

STATIONS = {
    "AWS310_1": {
        "prefix": "observations_AWS310_1",
        "out_csv": r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_1_UFF\dados\serie_meteorologicas.csv",
    },
    "AWS310_2": {
        "prefix": "observations_AWS310_2",
        "out_csv": r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_2_LAMCE\dados\serie_meteorologicas.csv",
    },
}

MET_VAR_MAP = {
    "AIR_PRESSURE_HECTO_PASCALS_MEAN_PT1M_1":      "P_AR_HPA",
    "AIR_PRESSURE_QFE_HECTO_PASCALS_MEAN_PT1M_1":  "P_QFE_HPA",
    "AIR_PRESSURE_QFF_HECTO_PASCALS_MEAN_PT1M_1":  "P_QFF_HPA",
    "AIR_PRESSURE_QNH_HECTO_PASCALS_MEAN_PT1M_1":  "P_QNH_HPA",
    "AIR_TEMPERATURE_DEGREES_CELSIUS_MEAN_PT1M_1": "T_AR_C",
    "DEW_POINT_TEMPERATURE_DEGREES_CELSIUS_MEAN_PT1M_1": "T_ORVALHO_C",
    "RAIN_INTENSITY_MILLIMETRES_PER_HOUR_MEAN_PT1M_1":   "CHUVA_INT_MM_H",
    "RELATIVE_HUMIDITY_PERCENT_MEAN_PT1M_1": "UR_PCT",}

HEADER = ["DATA", "HORA"] + list(MET_VAR_MAP.values())

SETTLE_SECONDS = 6
QUEUES = {sid: queue.Queue(maxsize=200) for sid in STATIONS.keys()}

def ensure_parent_and_header(out_csv: str):
    parent = os.path.dirname(out_csv)
    os.makedirs(parent, exist_ok=True)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)

def try_lock(lock_path: str, retries: int = 20, wait_s: float = 0.25) -> bool:
    for _ in range(retries):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(wait_s)
    return False

def unlock(lock_path: str):
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass

def detect_station_id(basename: str):
    for sid, cfg in STATIONS.items():
        if basename.startswith(cfg["prefix"]):
            return sid
    return None

def parse_nm10_csv_meteo(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)

    buckets = defaultdict(list)

    for row in rows:
        if len(row) < 6:
            continue

        var_nm10 = row[2].strip()
        raw = row[5].strip()

        if var_nm10 in MET_VAR_MAP:
            try:
                v = float(raw)
                friendly = MET_VAR_MAP[var_nm10]
                buckets[friendly].append(v)
            except ValueError:
                continue
    out = {}
    for friendly, values in buckets.items():
        if values:
            out[friendly] = round(sum(values) / len(values), 2)
    return out

def append_meteo(out_csv: str, values: dict):
    ensure_parent_and_header(out_csv)
    now = datetime.now()
    row = [now.date().isoformat(), now.time().isoformat(timespec="seconds")]

    for friendly in MET_VAR_MAP.values():
        row.append(values.get(friendly, ""))
    lock_path = out_csv + ".lock"
    locked = try_lock(lock_path)
    try:
        with open(out_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    finally:
        if locked:
            unlock(lock_path)

def worker_loop(station_id: str):
    out_csv = STATIONS[station_id]["out_csv"]
    ensure_parent_and_header(out_csv)
    while True:
        path = QUEUES[station_id].get()
        try:
            time.sleep(SETTLE_SECONDS)
            values = parse_nm10_csv_meteo(path)
            append_meteo(out_csv, values)
            print(f"[{station_id}] METEO OK: {os.path.basename(path)} - {os.path.basename(out_csv)}")
        except Exception as e:
            print(f"[{station_id}] ERRO METEO em {path}: {e}")
        finally:
            QUEUES[station_id].task_done()

# ===== Watcher =====
class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        base = os.path.basename(event.src_path)
        sid = detect_station_id(base)
        if sid:
            try:
                QUEUES[sid].put_nowait(event.src_path)
                print(f"[{sid}] Arquivo METEO detectado: {base}")
            except queue.Full:
                print(f"[{sid}] Fila METEO cheia — descartando {base}")

def initial_scan():
    try:
        for base in os.listdir(INPUT_DIR):
            full = os.path.join(INPUT_DIR, base)
            if not os.path.isfile(full):
                continue
            sid = detect_station_id(base)
            if sid:
                QUEUES[sid].put(full)
    except FileNotFoundError:
        os.makedirs(INPUT_DIR, exist_ok=True)

def main():
    for sid in STATIONS.keys():
        Thread(target=worker_loop, args=(sid,), daemon=True).start()

    initial_scan()

    observer = Observer()
    observer.schedule(Handler(), INPUT_DIR, recursive=False)
    observer.start()
    print("Monitorando a chegada de arquivos do NM10 (variáveis meteorológicas)… (Ctrl+C para sair)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
