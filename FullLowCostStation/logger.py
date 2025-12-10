import serial
import os
import csv
import re
from datetime import datetime

# ================== CONFIGURAÇÕES ==================

SERIAL_PORT = "COM3"   # troque para a porta do CUBECELL RX (ex: COM5)
BAUDRATE = 115200
LOG_DIR = "logs_lora"   # pasta onde ficarão os CSVs
INTERVALO_S = 5       # 5 minutos = 300 segundos

# ===================================================

def garantir_pasta(path):
    if not os.path.exists(path):
        os.makedirs(path)

def caminho_csv_do_dia(data=None):
    """Retorna o caminho do CSV para a data dada (ou hoje)."""
    if data is None:
        data = datetime.now()
    nome_arquivo = f"medicoes_{data.strftime('%Y-%m-%d')}.csv"
    return os.path.join(LOG_DIR, nome_arquivo)

def garantir_cabecalho_csv(caminho_csv):
    """Cria o arquivo com cabeçalho se ainda não existir."""
    if not os.path.exists(caminho_csv):
        with open(caminho_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp_iso",
                "data",
                "hora",
                "temperatura_C",
                "uv_index",
                "linha_bruta"
            ])

# regex: captura algo tipo 203.6,0 ou 25,3 etc
PADRAO_TEMP_UV = re.compile(r'(-?\d+(?:\.\d+)?),\s*(-?\d+)')

def parse_linha(linha):
    """
    Procura um padrão "temp,uv" em qualquer lugar da linha.
    Exemplo de linha: "Bruto: 203.6,0"
    Retorna (temp_float, uv_int) ou levanta ValueError.
    """
    m = PADRAO_TEMP_UV.search(linha)
    if not m:
        raise ValueError("Nenhum padrão 'temp,uv' encontrado na linha.")
    temp = float(m.group(1))
    uv = int(m.group(2))
    return temp, uv

def main():
    garantir_pasta(LOG_DIR)

    print(f"Abrindo porta serial {SERIAL_PORT} @ {BAUDRATE}...")
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

    print("Lendo dados da porta serial. Pressione Ctrl+C para parar.")
    ultimo_registro = None  # datetime do último registro salvo

    try:
        while True:
            linha_bytes = ser.readline()
            if not linha_bytes:
                # nada recebido nesse instante
                continue

            try:
                linha = linha_bytes.decode("utf-8", errors="ignore").strip()
            except UnicodeDecodeError:
                # caso bizarro, ignora essa linha
                continue

            if not linha:
                continue  # linha vazia

            # debug opcional:
            # print(f"[SERIAL] {linha}")

            now = datetime.now()

            # Tenta fazer o parse da linha para extrair "temp,uv"
            try:
                temp, uv = parse_linha(linha)
            except ValueError as e:
                # aqui vão cair linhas tipo "====== PACOTE RECEBIDO ======"
                # ou "RSSI: ..." etc.
                # Se quiser menos ruído, pode comentar o print abaixo.
                print(f"[WARN] Linha ignorada (formato inválido): '{linha}' -> {e}")
                continue

            # Controle de intervalo de 5 min
            if ultimo_registro is not None:
                delta = (now - ultimo_registro).total_seconds()
                if delta < INTERVALO_S:
                    # já tenho um registro recente, não salvo outro agora
                    print(f"[INFO] Dado válido recebido, mas ainda não passaram 5 min. (Δ={delta:.0f}s)")
                    continue

            # Garante o CSV do dia com cabeçalho
            caminho_csv = caminho_csv_do_dia(now)
            garantir_cabecalho_csv(caminho_csv)

            data_str = now.strftime("%Y-%m-%d")
            hora_str = now.strftime("%H:%M:%S")
            timestamp_iso = now.isoformat()

            # Escreve uma nova linha no CSV
            with open(caminho_csv, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp_iso, data_str, hora_str, temp, uv, linha])

            ultimo_registro = now

            print(f"[LOG] {timestamp_iso} | T={temp:.1f} °C | UV={uv} → salvo em {caminho_csv}")

    except KeyboardInterrupt:
        print("\nFinalizando script...")
    finally:
        ser.close()
        print("Porta serial fechada.")

if __name__ == "__main__":
    main()
