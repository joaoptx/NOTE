import os
import csv
import time
from datetime import datetime
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

entrada_csv = "C:/Vaisala/observation_csv/ready_for_transfer"
saida_csv = r"\\IRE0341\Dados_NOT\ObsTerra\estacao_lamce\dados\serie_iqar.csv"
nome_prefixo = "observations_AWS310_2"

MOLAR_MASS_NO2 = 46.0055  # g/mol
MOLAR_MASS_O3 = 48.00     # g/mol
VOLUME_MOLAR = 24.45      # L/mol

o3_history = deque(maxlen=8)
co_history = deque(maxlen=8)

def ppb_to_ugm3(ppb, molar_mass):
    return (ppb * molar_mass) / VOLUME_MOLAR

def ppb_to_ppm(ppb):
    return ppb / 1000

faixas_iqa = {
    'NO2': [(0, 200, 0, 40), (200, 240, 41, 80), (240, 320, 81, 120), (320, 1130, 121, 200), (1130, 3750, 201, 400)],
    'O3':  [(0, 100, 0, 40), (100, 130, 41, 80), (130, 160, 81, 120), (160, 200, 121, 200), (200, 800, 201, 400)],
    'CO':  [(0, 9, 0, 40), (9, 11, 41, 80), (11, 13, 81, 120), (13, 15, 121, 200), (15, 50, 201, 400)]}

qualidade_ar = [
    (0, 40, "Boa"),
    (41, 80, "Moderada"),
    (81, 120, "Ruim"),
    (121, 200, "Muito Ruim"),
    (201, float('inf'), "Péssima")]

def calcular_iqa(concentracao, poluente):
    for c_ini, c_fin, i_ini, i_fin in faixas_iqa[poluente]:
        if c_ini <= concentracao <= c_fin:
            return round(i_ini + ((i_fin - i_ini) / (c_fin - c_ini)) * (concentracao - c_ini))
    return None

def classificar_qualidade(iqar):
    if iqar is None:
        return "Indefinida"
    for ini, fim, classificacao in qualidade_ar:
        if ini <= iqar <= fim:
            return classificacao
    return "Indefinida"

def formatar_iqar(iqar):
    """Retorna 'Faixa – índice' (ex.: 'Boa – 37') ou '' se None."""
    if iqar is None:
        return ""
    return f"{classificar_qualidade(iqar)} – {iqar}"

os.makedirs(os.path.dirname(saida_csv), exist_ok=True)
if not os.path.exists(saida_csv):
    with open(saida_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'DATA', 'HORA',
            'IQAR_CO', 'IQAR_O3', 'IQAR_NO2',
            'QUALIDADE_GERAL'])

def processar_csv(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        linhas = list(csv.reader(f, delimiter=';'))

    co_vals, o3_vals, no2_vals = [], [], []

    for linha in linhas:
        if len(linha) < 6:
            continue
        var = linha[2].strip()
        val_str = linha[5].strip()
        try:
            val = float(val_str)
        except ValueError:
            continue

        if var == "CARBON_MONOXIDE_PARTS_PER_BILLION_MEAN_PT10M_1":
            co_vals.append(val)
        elif var == "OZONE_PARTS_PER_BILLION_MEAN_PT10M_3":
            o3_vals.append(val)
        elif var == "NITROGEN_DIOXIDE_PARTS_PER_BILLION_MEAN_PT1H_2":
            no2_vals.append(val)

    co_media_ppb = sum(co_vals) / len(co_vals) if co_vals else None
    co_ppm = ppb_to_ppm(co_media_ppb) if co_media_ppb is not None else None
    if co_ppm is not None:
        co_history.append(co_ppm)

    o3_media_ppb = (sum(o3_vals) / len(o3_vals)) if o3_vals else None
    o3_media_ugm3 = ppb_to_ugm3(o3_media_ppb, MOLAR_MASS_O3) if o3_media_ppb is not None else None
    if o3_media_ugm3 is not None:
        o3_history.append(o3_media_ugm3)

    no2_media_ppb = (sum(no2_vals) / len(no2_vals)) if no2_vals else None
    no2_media_ugm3 = ppb_to_ugm3(no2_media_ppb, MOLAR_MASS_NO2) if no2_media_ppb is not None else None

    iqar_co  = calcular_iqa(sum(co_history) / 8, 'CO') if len(co_history) == 8 else None
    iqar_o3  = calcular_iqa(sum(o3_history) / 8, 'O3') if len(o3_history) == 8 else None
    iqar_no2 = calcular_iqa(no2_media_ugm3, 'NO2') if no2_media_ugm3 is not None else None

    iqar_disponiveis = [i for i in (iqar_co, iqar_o3, iqar_no2) if i is not None]
    qualidade_geral = classificar_qualidade(max(iqar_disponiveis)) if iqar_disponiveis else "Indefinida"

    data = datetime.now().date().isoformat()
    hora = datetime.now().time().isoformat(timespec='seconds')

    with open(saida_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            data, hora,
            formatar_iqar(iqar_co),
            formatar_iqar(iqar_o3),
            formatar_iqar(iqar_no2),
            qualidade_geral
        ])

class NovoCSVHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and os.path.basename(event.src_path).startswith(nome_prefixo):
            print(f"Arquivo novo detectado: {event.src_path}")
            time.sleep(2)  # dá tempo do arquivo terminar de ser gravado
            processar_csv(event.src_path)

observer = Observer()
evento_handler = NovoCSVHandler()
observer.schedule(evento_handler, entrada_csv, recursive=False)
observer.start()

print("Monitorando novos arquivos para cálculo do IQAR...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
