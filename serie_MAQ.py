import os
import csv
import time
from datetime import datetime
from collections import defaultdict
from threading import Thread
import queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
0
INPUT_DIR = r"C:/Vaisala/observation_csv/ready_for_transfer"

STATIONS = {
    "AWS310_1": {
        "prefix": "observations_AWS310_1",
        "out_conc":  r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_1_UFF\poluentes\serie_concentracoes.csv",
        "out_meteo": r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_1_UFF\meteorologia\serie_meteoro.csv",
    },
    "AWS310_2": {
        "prefix": "observations_AWS310_2",
        "out_conc":  r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_2_LAMCE\poluentes\serie_concentracoes.csv",
        "out_meteo": r"\\IRE0341\Dados_NOT\ObsTerra\estacoes\aws310_2_LAMCE\meteorologia\serie_meteoro.csv",
    },
}

VAR_MAP_CONC = {
    "CARBON_MONOXIDE_PARTS_PER_BILLION_MEAN_PT10M_1": "MONOXIDO_DE_CARBONO_PPB",
    "CARBON_DIOXIDE_PARTS_PER_MILLION_MEAN_PT10M_1":   "DIOXIDO_DE_CARBONO_PPM",
    "HYDROGEN_SULFIDE_PARTS_PER_MILLION_MEAN_PT10M_1": "SULFETO_DE_HIDROGENIO_PPM",
    "NITROGEN_DIOXIDE_PARTS_PER_BILLION_MEAN_PT10M_2": "DIOXIDO_DE_NITROGENIO_PPB",
    "NITROGEN_MONOXIDE_PARTS_PER_BILLION_MEAN_PT10M_1":"MONOXIDO_DE_NITROGENIO_PPB",
    "OZONE_PARTS_PER_BILLION_MEAN_PT10M_3":            "OZONIO_PPB",
}

VAR_MAP_METEO = {
    "AIR_PRESSURE_HECTO_PASCALS_MEAN_PT1M_1":                "P_AR_HPA",
    "AIR_PRESSURE_QFE_HECTO_PASCALS_MEAN_PT1M_1":            "P_QFE_HPA",
    "AIR_PRESSURE_QFF_HECTO_PASCALS_MEAN_PT1M_1":            "P_QFF_HPA",
    "AIR_PRESSURE_QNH_HECTO_PASCALS_MEAN_PT1M_1":            "P_QNH_HPA",
    "AIR_TEMPERATURE_DEGREES_CELSIUS_MEAN_PT1M_1":           "T_AR_C",
    "DEW_POINT_TEMPERATURE_DEGREES_CELSIUS_MEAN_PT1M_1":     "T_ORVALHO_C",
    "RAIN_INTENSITY_MILLIMETRES_PER_HOUR_MEAN_PT1M_1":       "CHUVA_INT_MM_H",
    "RELATIVE_HUMIDITY_PERCENT_MEAN_PT1M_1":                 "UR_PCT",
}

HEADER_CONC  = ["DATA", "HORA"] + list(VAR_MAP_CONC.values())
HEADER_METEO = ["DATA", "HORA"] + list(VAR_MAP_METEO.values())

SETTLE_SECONDS = 6
QUEUES = {sid: queue.Queue(maxsize=200) for sid in STATIONS.keys()}

def ensure_parent_and_header(out_csv: str, header: list):
    parent = os.path.dirname(out_csv)
    os.makedirs(parent, exist_ok=True)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

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

def parse_nm10_csv_both(path: str):
    """
    Lê o CSV bruto do NM10 e calcula:
      - média dos 10 valores (ou quantos tiver) das variáveis de poluentes
      - média dos 10 valores (ou quantos tiver) das variáveis meteorológicas
    Retorna dois dicionários: (conc_dict, meteo_dict)
    """
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)

    buckets_conc  = defaultdict(list)
    buckets_meteo = defaultdict(list)

    for row in rows:
        if len(row) < 6:
            continue

        var_nm10 = row[2].strip()
        raw = row[5].strip()

        try:
            v = float(raw)
        except ValueError:
            continue

        if var_nm10 in VAR_MAP_CONC:
            friendly = VAR_MAP_CONC[var_nm10]
            buckets_conc[friendly].append(v)

        if var_nm10 in VAR_MAP_METEO:
            friendly = VAR_MAP_METEO[var_nm10]
            buckets_meteo[friendly].append(v)

    conc_out  = {}
    meteo_out = {}

    for friendly, values in buckets_conc.items():
        if values:
            conc_out[friendly] = round(sum(values) / len(values), 2)

    for friendly, values in buckets_meteo.items():
        if values:
            meteo_out[friendly] = round(sum(values) / len(values), 2)

    return conc_out, meteo_out

def append_concentrations(out_csv: str, values: dict):
    ensure_parent_and_header(out_csv, HEADER_CONC)
    now = datetime.now()
    row = [now.date().isoformat(), now.time().isoformat(timespec="seconds")]
    for friendly in VAR_MAP_CONC.values():
        row.append(values.get(friendly, ""))

    lock_path = out_csv + ".lock"
    locked = try_lock(lock_path)
    try:
        with open(out_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    finally:
        if locked:
            unlock(lock_path)

def append_meteo(out_csv: str, values: dict):
    ensure_parent_and_header(out_csv, HEADER_METEO)
    now = datetime.now()
    row = [now.date().isoformat(), now.time().isoformat(timespec="seconds")]
    for friendly in VAR_MAP_METEO.values():
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
    cfg = STATIONS[station_id]
    out_conc  = cfg["out_conc"]
    out_meteo = cfg["out_meteo"]

    ensure_parent_and_header(out_conc,  HEADER_CONC)
    ensure_parent_and_header(out_meteo, HEADER_METEO)

    while True:
        path = QUEUES[station_id].get()
        try:
            time.sleep(SETTLE_SECONDS)  # espera o NM10 terminar de escrever
            conc_vals, meteo_vals = parse_nm10_csv_both(path)

            if conc_vals:
                append_concentrations(out_conc, conc_vals)
            if meteo_vals:
                append_meteo(out_meteo, meteo_vals)

            print(
                f"[{station_id}] OK: {os.path.basename(path)} - "
                f"{os.path.basename(out_conc)}, {os.path.basename(out_meteo)}"
            )
        except Exception as e:
            print(f"[{station_id}] ERRO em {path}: {e}")
        finally:
            QUEUES[station_id].task_done()

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        base = os.path.basename(event.src_path)
        sid = detect_station_id(base)
        if sid:
            try:
                QUEUES[sid].put_nowait(event.src_path)
                print(f"[{sid}] Arquivo detectado: {base}")
            except queue.Full:
                print(f"[{sid}] Fila cheia — descartando {base}")

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
    # Uma thread worker para cada estação
    for sid in STATIONS.keys():
        Thread(target=worker_loop, args=(sid,), daemon=True).start()

    initial_scan()

    observer = Observer()
    observer.schedule(Handler(), INPUT_DIR, recursive=False)
    observer.start()
    print("Monitorando a chegada de arquivos... — Ctrl+C para sair")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
