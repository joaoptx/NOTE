import os
import sys
import time
import re
import glob
import logging
import multiprocessing as mp
from datetime import datetime, timezone

# --- CORREÇÃO DE PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- IMPORTAÇÕES DOS MÓDULOS DO PROJETO ---
from src import config
from src import aws_handler, visualization, file_manager, rgb_processor, utils

def setup_logging():
    """Configura o sistema de logs (Arquivo + Console)."""
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        filename=config.LOG_PATH,
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        filemode='a'
    )
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
                    
                    m = re.match(r'Band\s*0*([1-9]\d?)', band_folder, re.IGNORECASE)
                    if not m: continue
                    
                    band_num = int(m.group(1))
                    if band_num not in range(1, 17): continue

                    for nc_path in sorted(glob.glob(os.path.join(band_path, '*.nc'))):
                        args_list.append((band_num, band_folder, nc_path))

            if args_list:
                logging.info(f"Processando {len(args_list)} arquivos individuais...")
                num_processes = min(mp.cpu_count(), 12)
                
                with mp.Pool(processes=num_processes) as pool:
                    pool.starmap(visualization.process_nc_file, args_list)
            else:
                logging.info("Nenhum arquivo novo no INCOMING.")

        except Exception as e:
            logging.exception(f"Erro no loop principal de processamento: {e}")

        # ==============================================================================
        # ETAPA 2.5: GERAÇÃO DE TRUE COLOR (RGB)
        # ==============================================================================
        logging.info("Verificando disponibilidade para geração de True Color...")
        try:
            now_utc = datetime.now(timezone.utc)
            year, month, day = now_utc.strftime('%Y'), now_utc.strftime('%m'), now_utc.strftime('%d')
            
            files_by_ts = {} 

            for b in [1, 2, 3]:
                # Busca nas pastas organizadas (Note: get_band_folder_path acha a pasta raiz da banda)
                b_path = get_band_folder_path(config.ORGANIZED_DIR, b)
                if not b_path: continue
                
                # Procura dentro da nova estrutura: BandXX/Ano/Mes/Dia/NetCDF/*.nc
                netcdf_dir = os.path.join(b_path, year, month, day, "NetCDF")
                
                if os.path.exists(netcdf_dir):
                    for nc in glob.glob(os.path.join(netcdf_dir, '*.nc')):
                        fname = os.path.basename(nc)
                        match = re.search(r'recorte_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_UTC', fname)
                        
                        if match:
                            ts_key = match.group(1) 
                            
                            if ts_key not in files_by_ts: files_by_ts[ts_key] = {}
                            
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
                    # --- VERIFICAÇÃO ATUALIZADA COM UTILS ---
                    # Checa se a imagem Brasil TrueColor já existe para não refazer
                    try:
                        ts_obj_check = datetime.strptime(ts, '%Y-%m-%d_%H-%M')
                        
                        path_brasil_tc = utils.get_structure_path(ts_obj_check, "imagem", region="Brasil", banda="TrueColor")
                        expected_jpg = os.path.join(path_brasil_tc, f"{ts}_TrueColor_Brasil.jpg")
                        
                        if not os.path.exists(expected_jpg):
                            rgb_processor.process_true_color(ts, bands)
                            count_rgb += 1
                    except Exception as e:
                        logging.error(f"Erro ao verificar existência TC: {e}")
            
            if count_rgb > 0:
                logging.info(f"Gerados {count_rgb} novos mapas True Color.")

        except Exception as e:
            logging.exception(f"Erro na etapa True Color: {e}")

        # ==============================================================================
        # ETAPA 3: MANUTENÇÃO (Sync e Limpeza)
        # ==============================================================================
        file_manager.run_nas_sync(config.SCRIPT_SYNC_PATH)
        
        try:
            if datetime.now().minute == 0: 
                logging.info("Executando limpeza de arquivos antigos...")
                file_manager.limpar_arquivos_antigos(config.ORGANIZED_DIR, dias_para_manter=7)
                file_manager.limpar_arquivos_antigos(r"Z:\GOES_Organized", dias_para_manter=178)
        except Exception as e:
            logging.error(f"Erro durante rotina de limpeza: {e}")

        logging.info(f"Ciclo concluído. Aguardando {config.CHECK_INTERVAL} segundos...")
        time.sleep(config.CHECK_INTERVAL)