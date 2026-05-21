import os
import time
import pandas as pd
from datetime import datetime, date, timedelta

arquivo_bruto = r"C:\Users\lamce\Desktop\Lidar\dados_modbuspoll\principais_variaveis.csv"
saida_dir = r"\Users\lamce\Desktop\Lidar\dados_modbuspoll"
saida_base = "dados_tratados"
alturas = [40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300]

COMEÇAR_DO_INÍCIO = False

conversoes = {
    "u": (0.01, -100),
    "v": (0.01, -100),
    "w": (0.01, -100),
    "radial": (0.01, -100),
    "cnr": (0.01, -100),
    "id_valid": (1.0, 0),
    "vel_horiz": (0.01, -100),
    "direcao": (0.01, 0),
}

def caminho_saida_para(d: date) -> str:
    os.makedirs(saida_dir, exist_ok=True)
    return os.path.join(saida_dir, f"{saida_base}_{d.isoformat()}.csv")

def garantir_cabecalho(caminho_csv: str):
    if not os.path.exists(caminho_csv):
        pd.DataFrame(columns=[
            "datetime","altura","u","v","w","radial","cnr",
            "id_valid","vel_horiz","direcao"
        ]).to_csv(caminho_csv, index=False)

def aplicar_conversao(x, a, b):
    try:
        return a * float(x) + b
    except Exception:
        return None

def processar_linha(linha, data_base_iso):
    partes = linha.strip().split(",")
    if len(partes) < 1 + 112:
        return None

    hora = partes[0].strip()
    try:
        datetime.strptime(hora, "%H:%M:%S")
    except ValueError:
        return None

    timestamp = f"{data_base_iso} {hora}"

    try:
        valores = list(map(float, partes[1:1+112]))
    except Exception:
        return None

    u_blk      = valores[0:14]
    v_blk      = valores[14:28]
    w_blk      = valores[28:42]
    radial_blk = valores[42:56]
    cnr_blk    = valores[56:70]
    id_blk     = valores[70:84]
    vel_blk    = valores[84:98]
    dir_blk    = valores[98:112]

    dados = []
    for i, altura in enumerate(alturas):
        u  = aplicar_conversao(u_blk[i],      *conversoes["u"])
        v  = aplicar_conversao(v_blk[i],      *conversoes["v"])
        w  = aplicar_conversao(w_blk[i],      *conversoes["w"])
        rs = aplicar_conversao(radial_blk[i], *conversoes["radial"])
        cn = aplicar_conversao(cnr_blk[i],    *conversoes["cnr"])
        iv = aplicar_conversao(id_blk[i],     *conversoes["id_valid"])
        vh = aplicar_conversao(vel_blk[i],    *conversoes["vel_horiz"])
        dr = aplicar_conversao(dir_blk[i],    *conversoes["direcao"])

        dados.append({
            "datetime": timestamp,
            "altura": altura,
            "u": u,
            "v": v,
            "w": w,
            "radial": rs,
            "cnr": cn,
            "id_valid": iv,
            "vel_horiz": vh,
            "direcao": dr
        })
    return dados, hora

def tail_f(caminho, start_from_beginning=False):
    f = open(caminho, "r", encoding="utf-8", errors="ignore")
    try:
        f.seek(0, os.SEEK_SET if start_from_beginning else os.SEEK_END)
        while True:
            linha = f.readline()
            if not linha:
                time.sleep(0.5)
                continue
            yield linha
    finally:
        f.close()

if __name__ == "__main__":
    print("Monitorando em tempo real:", arquivo_bruto)

    data_base = date.today()
    ultimo_hms = None

    arquivo_saida_atual = caminho_saida_para(data_base)
    garantir_cabecalho(arquivo_saida_atual)
    print("Gravando em:", arquivo_saida_atual)

    for linha in tail_f(arquivo_bruto, start_from_beginning=COMEÇAR_DO_INÍCIO):
        try:
            hms_atual = linha.split(",")[0].strip()
            if ultimo_hms is not None and hms_atual < ultimo_hms:
                data_base += timedelta(days=1)
                arquivo_saida_atual = caminho_saida_para(data_base)
                garantir_cabecalho(arquivo_saida_atual)
                print("Virou o dia. Novo CSV:", arquivo_saida_atual)
            ultimo_hms = hms_atual
        except Exception:
            pass

        resultado = processar_linha(linha, data_base.isoformat())
        if resultado is None:
            continue
        dados, _ = resultado

        df = pd.DataFrame(dados)
        df.to_csv(arquivo_saida_atual, mode="a", header=False, index=False)

        ts = df["datetime"].iloc[0]
        print(f"\n⏱ {ts}  →  saída: {os.path.basename(arquivo_saida_atual)}")
        for _, row in df.iterrows():
            vh = row["vel_horiz"]; dr = row["direcao"]
            if vh is None or dr is None:
                print(f"{row['altura']}m → (inválido)")
            else:
                print(f"{row['altura']}m → {vh:.2f} m/s | {dr:.1f}°")
