import os
import sys
import time
import re
import glob
import logging
import multiprocessing as mp
from datetime import datetime, timezone

# --- CORREÇÃO DE PATH (Essencial para o Python encontrar a pasta src) ---
# Pega o diretório onde o main.py está e adiciona ao path do sistema
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Importações dos módulos do projeto
import config
from src import aws_handler, visualization, file_manager, rgb_processor

def setup_logging():
    """Configura o sistema de logs (Arquivo + Console)."""
    # Remove handlers antigos para evitar duplicação
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        filename=config.LOG_PATH,
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        filemode='a'
    )
    # Adiciona saída no console para você acompanhar em tempo real
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    logging.info("Sistema GOES Processor Iniciado (Estrutura Modular Completa).")

def get_band_folder_path(base_dir, band_num):
    """
    Encontra a pasta correta da banda (ex: 'Band 01' ou 'Band01') 
    dentro do diretório organizado, lidando com espaços no nome.
    """
    if not os.path.exists(base_dir): return None
    for d in os.listdir(base_dir):
        # Remove espaços e converte para minusculo para comparar
        if f"band{band_num:02d}" in d.lower().replace(" ", ""):
            return os.path.join(base_dir, d)
    return None

if __name__ == "__main__":
    mp.freeze_support() # Necessário para Windows
    setup_logging()
    
    while True:
        # ==============================================================================
        # ETAPA 1: VERIFICAÇÃO E DOWNLOAD AWS
        # ==============================================================================
        # Baixa arquivos que faltam nas últimas 24h
        aws_handler.verificar_e_preencher_lacunas_aws()

        # ==============================================================================
        # ETAPA 2: PROCESSAMENTO INDIVIDUAL (Banda por Banda)
        # ==============================================================================
        logging.info("Verificando arquivos novos na pasta INCOMING...")
        try:
            args_list = []
            
            if os.path.exists(config.INCOMING_DIR):
                for band_folder in sorted(os.listdir(config.INCOMING_DIR)):
                    band_path = os.path.join(config.INCOMING_DIR, band_folder)
                    if not os.path.isdir(band_path): continue
                    
                    # Regex para garantir que é uma pasta de banda (Band XX)
                    m = re.match(r'Band\s*0*([1-9]\d?)', band_folder, re.IGNORECASE)
                    if not m: continue
                    
                    band_num = int(m.group(1))
                    if band_num not in range(1, 17): continue

                    # Lista todos os .nc para processar
                    for nc_path in sorted(glob.glob(os.path.join(band_path, '*.nc'))):
                        args_list.append((band_num, band_folder, nc_path))

            if args_list:
                logging.info(f"Processando {len(args_list)} arquivos individuais...")
                # Define número de processos (CPU count - um pouco de folga)
                num_processes = min(mp.cpu_count(), 12)
                
                # Executa o processamento em paralelo
                with mp.Pool(processes=num_processes) as pool:
                    pool.starmap(visualization.process_nc_file, args_list)
            else:
                logging.info("Nenhum arquivo novo no INCOMING.")

        except Exception as e:
            logging.exception(f"Erro no loop principal de processamento: {e}")

        # ==============================================================================
        # ETAPA 2.5: GERAÇÃO DE TRUE COLOR (RGB)
        # ==============================================================================
        # Agora que os arquivos foram movidos para o ORGANIZED e recortados,
        # vamos buscar os trios (Band 1, 2, 3) lá dentro.
        
        logging.info("Verificando disponibilidade para geração de True Color...")
        try:
            # Foca apenas no dia de hoje (UTC) para otimizar a busca
            now_utc = datetime.now(timezone.utc)
            year, month, day = now_utc.strftime('%Y'), now_utc.strftime('%m'), now_utc.strftime('%d')
            
            # Estrutura para agrupar arquivos: { '2025-10-12_14-30': {1: path, 2: path, 3: path} }
            files_by_ts = {} 

            for b in [1, 2, 3]:
                # 1. Acha a pasta da banda (Ex: Y:\GOES-Organized\Band 01)
                b_path = get_band_folder_path(config.ORGANIZED_DIR, b)
                if not b_path: continue
                
                # 2. Caminho dos recortes: .../BandXX/YYYY/MM/DD/NetCDF/*.nc
                netcdf_dir = os.path.join(b_path, year, month, day, "NetCDF")
                
                if os.path.exists(netcdf_dir):
                    for nc in glob.glob(os.path.join(netcdf_dir, '*.nc')):
                        # Extrai timestamp do nome do arquivo RECORTADO
                        # Exemplo de nome: recorte_2025-10-12_14-30_UTC_....nc
                        fname = os.path.basename(nc)
                        match = re.search(r'recorte_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_UTC', fname)
                        
                        if match:
                            ts_key = match.group(1) # Chave: '2025-10-12_14-30'
                            
                            if ts_key not in files_by_ts: files_by_ts[ts_key] = {}
                            
                            # --- LÓGICA DE ALTA RESOLUÇÃO ---
                            # Se for Banda 2 e já tivermos um arquivo, mantemos o maior (0.5km)
                            if b == 2 and 2 in files_by_ts[ts_key]:
                                size_existing = os.path.getsize(files_by_ts[ts_key][2])
                                size_new = os.path.getsize(nc)
                                if size_new > size_existing:
                                    files_by_ts[ts_key][2] = nc
                            else:
                                files_by_ts[ts_key][b] = nc

            # 3. Processa os trios completos
            count_rgb = 0
            for ts, bands in files_by_ts.items():
                if len(bands) == 3:
                    # Verifica se o arquivo final já existe na pasta Brasil para evitar refazer
                    # Caminho: GOES-Organized/TrueColor/YYYY/MM/DD/Brasil/TS_TrueColor_Brasil.jpg
                    true_color_base = os.path.join(config.ORGANIZED_DIR, "TrueColor", year, month, day)
                    expected_jpg = os.path.join(true_color_base, "Brasil", f"{ts}_TrueColor_Brasil.jpg")
                    
                    if not os.path.exists(expected_jpg):
                        # Chama o processador True Color (que gera Brasil e Sudeste)
                        rgb_processor.process_true_color(ts, bands)
                        count_rgb += 1
            
            if count_rgb > 0:
                logging.info(f"Gerados {count_rgb} novos mapas True Color (Brasil + Sudeste).")

        except Exception as e:
            logging.exception(f"Erro na etapa True Color: {e}")

        # ==============================================================================
        # ETAPA 3: MANUTENÇÃO (Sync e Limpeza)
        # ==============================================================================
        file_manager.run_nas_sync(config.SCRIPT_SYNC_PATH)
        
        try:
            # Executa limpeza periodicamente (ex: minuto 0 de cada hora) para não sobrecarregar disco
            # Se quiser limpar a cada loop, remova o if.
            if datetime.now().minute == 0: 
                logging.info("Executando limpeza de arquivos antigos...")
                # Limpa pasta local (incluindo TrueColor pois está dentro de ORGANIZED_DIR)
                file_manager.limpar_arquivos_antigos(config.ORGANIZED_DIR, dias_para_manter=7)
                # Limpa pasta remota (Backup Z:)
                file_manager.limpar_arquivos_antigos(r"Z:\GOES_Organized", dias_para_manter=178)
        except Exception as e:
            logging.error(f"Erro durante rotina de limpeza: {e}")

        logging.info(f"Ciclo concluído. Aguardando {config.CHECK_INTERVAL} segundos...")
        time.sleep(config.CHECK_INTERVAL)