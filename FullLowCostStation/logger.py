import serial
import os
import csv
from datetime import datetime

# Configurações

SERIAL_PORT = ""   
BAUDRATE = 115200
LOG_DIR = "logs_lora"  # pasta onde ficarão os CSVs
INTERVALO_S = 300      # 5 minutos

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
            writer.writerow(["timestamp_iso", "data", "hora", "temperatura_C", "uv_index", "linha_bruta"])

def parse_linha(linha):
    """
    Espera linha no formato "temp,uv".
    Retorna (temp_float, uv_int) ou levanta ValueError.
    """
    partes = linha.split(",")
    if len(partes) != 2:
        raise ValueError("Linha não tem exatamente 2 campos separados por vírgula.")
    temp = float(partes[0])
    uv = int(partes[1])
    return temp, uv

def main():
    garantir_pasta(LOG_DIR)

    print(f"Abrindo porta serial {SERIAL_PORT} @ {BAUDRATE}...")
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

    print("Lendo dados do Heltec. Pressione Ctrl+C para parar.")
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
                # caso fora do padrão, ignora essa linha
                continue

            if not linha:
                continue  # linha vazia

            now = datetime.now()

            # Registra só a cada 5 min
            if ultimo_registro is not None:
                delta = (now - ultimo_registro).total_seconds()
                if delta < INTERVALO_S:
                    # Ainda não passou o tempo necessário, só ignora essa leitura
                    continue

            # Tenta fazer o parse da linha "temp,uv"
            try:
                temp, uv = parse_linha(linha)
            except ValueError as e:
                print(f"[WARN] Linha ignorada (formato inválido): '{linha}' -> {e}")
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
