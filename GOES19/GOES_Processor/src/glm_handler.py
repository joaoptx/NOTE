import os
import shutil
import logging
import re
import numpy as np
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from datetime import datetime, timedelta, timezone # Adicionado timezone
from netCDF4 import Dataset

# --- CORREÇÃO DE IMPORTAÇÃO ---
from src import config

def download_glm_window(target_dt):
    """
    Baixa arquivos GLM da janela de tempo (target_dt - 10min até target_dt).
    Retorna lista de caminhos locais.
    """
    files_found = []
    
    # Garante que target_dt é UTC (aware)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    # Define janela de tempo
    end_dt = target_dt
    start_dt = target_dt - timedelta(minutes=config.GLM_WINDOW_MINUTES)
    
    try:
        s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        
        # O GLM pode estar dividido em duas pastas de horas diferentes
        hours_to_check = [start_dt]
        if start_dt.hour != end_dt.hour:
            hours_to_check.append(end_dt)
            
        for dt_check in hours_to_check:
            year = dt_check.strftime('%Y')
            julian_day = dt_check.strftime('%j')
            hour = dt_check.strftime('%H')
            
            prefix = f"{config.AWS_PRODUCT_GLM}/{year}/{julian_day}/{hour}/"
            
            resp = s3.list_objects_v2(Bucket=config.AWS_BUCKET, Prefix=prefix)
            
            if 'Contents' not in resp: continue
            
            for obj in resp['Contents']:
                key = obj['Key']
                fname = os.path.basename(key)
                
                # Extrai timestamp do arquivo GLM
                match = re.search(r'_s(\d{13})', fname)
                if match:
                    file_dt_str = match.group(1)
                    # --- CORREÇÃO DO ERRO DE TIMEZONE AQUI ---
                    # Convertemos a string para datetime e IMEDIATAMENTE definimos como UTC
                    file_dt = datetime.strptime(file_dt_str, '%Y%j%H%M%S').replace(tzinfo=timezone.utc)
                    
                    # Verifica se arquivo está DENTRO da janela
                    if start_dt <= file_dt <= end_dt:
                        local_dir = os.path.join(config.DIR_GLM_CACHE, year, julian_day, hour)
                        os.makedirs(local_dir, exist_ok=True)
                        local_path = os.path.join(local_dir, fname)
                        
                        if not os.path.exists(local_path):
                            try:
                                s3.download_file(config.AWS_BUCKET, key, local_path)
                            except Exception:
                                continue
                        
                        files_found.append(local_path)
                        
    except Exception as e:
        logging.error(f"Erro ao baixar GLM: {e}")
        
    return files_found

def get_glm_data(timestamp_utc):
    """
    Orquestra o download e a leitura dos dados.
    Retorna (lats, lons) acumulados ou (None, None).
    """
    try:
        glm_files = download_glm_window(timestamp_utc)
        
        if not glm_files:
            return None, None
            
        all_lats = []
        all_lons = []
        
        for nc_path in glm_files:
            try:
                # Usa netCDF4 pois é muito mais rápido
                with Dataset(nc_path, 'r') as nc:
                    if 'flash_lat' in nc.variables and 'flash_lon' in nc.variables:
                        lats = nc.variables['flash_lat'][:]
                        lons = nc.variables['flash_lon'][:]
                        
                        if len(lats) > 0:
                            all_lats.append(lats)
                            all_lons.append(lons)
            except Exception:
                continue
                
        if not all_lats:
            return None, None
            
        final_lats = np.concatenate(all_lats)
        final_lons = np.concatenate(all_lons)
        
        return final_lats, final_lons

    except Exception as e:
        logging.warning(f"Erro ao processar dados GLM: {e}")
        return None, None

def clear_glm_cache():
    """Limpa a pasta de cache do GLM para não encher o disco."""
    try:
        if os.path.exists(config.DIR_GLM_CACHE):
            shutil.rmtree(config.DIR_GLM_CACHE)
    except Exception:
        pass