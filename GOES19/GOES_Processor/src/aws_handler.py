import os
import re
import glob
import logging
from datetime import datetime, timezone, timedelta
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from boto3.s3.transfer import TransferConfig
import concurrent.futures

# --- IMPORTAÇÃO DO PROJETO ---
from src import config

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE PARA DOWNLOAD ---
# Ajuste Fino: Reduzimos max_concurrency para 10 para não estourar sockets
# quando multiplicado pelas 16 threads de arquivos.
TRANSFER_CONFIG = TransferConfig(
    max_concurrency=10,      # 10 threads por arquivo x 16 arquivos = 160 conexões (gerenciável)
    multipart_threshold=8 * 1024 * 1024, 
    multipart_chunksize=8 * 1024 * 1024, 
    use_threads=True
)

def processar_banda_para_timestamp(s3_client, band_num, ts_str, now_utc):
    """
    Função auxiliar que roda em paralelo para verificar e baixar uma banda específica.
    """
    try:
        # Encontrar nome da pasta (com ou sem espaço)
        dirs = os.listdir(config.ORGANIZED_DIR)
        band_folder_name = next((d for d in dirs if f"band{band_num:02d}" in d.lower().replace(" ", "")), f"Band {band_num:02d}")
        
        # Caminho onde os arquivos processados (JPG) deveriam estar
        ts_obj = datetime.strptime(ts_str, '%Y-%m-%d_%H-%M')
        path_check = os.path.join(
            config.ORGANIZED_DIR, 
            band_folder_name, 
            ts_obj.strftime('%Y'), 
            ts_obj.strftime('%m'), 
            ts_obj.strftime('%d'), 
            'Brasil', 
            f"{ts_str}*.jpg"
        )
        
        # Se já existe JPG processado, pulamos o download
        if glob.glob(path_check):
            return

        # Se não existe, precisamos verificar se temos o NetCDF bruto ou baixar
        ano, dj, hora, mn = ts_obj.strftime('%Y'), ts_obj.strftime('%j'), ts_obj.strftime('%H'), ts_obj.minute
        
        prefix = f"{config.AWS_PRODUCT}/{ano}/{dj}/{hora}/"
        
        # Listar objetos na AWS
        resp = s3_client.list_objects_v2(Bucket=config.AWS_BUCKET, Prefix=prefix)
        
        if 'Contents' not in resp: return
        
        for obj in resp['Contents']:
            fname = os.path.basename(obj['Key'])
            
            match = re.search(r'_s(\d{4}\d{3}\d{2}\d{2})', fname)
            
            # Verifica se é a banda certa e o horário certo
            if match and f"C{band_num:02d}_G19_" in fname and match.group(1) == f"{ano}{dj}{hora}{mn:02d}":
                
                # Define onde salvar no INCOMING
                incoming_dirs = os.listdir(config.INCOMING_DIR)
                incoming_band = next((d for d in incoming_dirs if f"band{band_num:02d}" in d.lower().replace(" ", "")), f"Band {band_num:02d}")
                dest_path = os.path.join(config.INCOMING_DIR, incoming_band, fname)
                
                # Se o arquivo NetCDF já existe localmente, não baixa de novo
                if os.path.exists(dest_path):
                    return

                logging.info(f"Baixando [THREAD] {ts_str} B{band_num:02d}...")
                
                # Download Otimizado
                s3_client.download_file(
                    config.AWS_BUCKET, 
                    obj['Key'], 
                    dest_path,
                    Config=TRANSFER_CONFIG
                )
                return # Arquivo encontrado e baixado, encerra essa banda

    except Exception as e:
        logging.error(f"Erro thread Banda {band_num:02d}: {e}")

def verificar_e_preencher_lacunas_aws():
    logging.info("Iniciando verificação de lacunas AWS (Pool Otimizado)...")
    try:
        # --- CORREÇÃO DO POOL FULL ---
        # Aumentamos max_pool_connections para 300 para comportar o pico de threads.
        s3 = boto3.client('s3', config=Config(
            signature_version=UNSIGNED, 
            max_pool_connections=300, # Aumentado de 50 para 300
            retries={'max_attempts': 3, 'mode': 'standard'}
        ))
        
        now_utc = datetime.now(timezone.utc)
        
        # Janela de verificação
        end_scan = now_utc - timedelta(minutes=config.GRACE_PERIOD_MINUTES)
        start_scan = now_utc - timedelta(minutes=60)

        expected_timestamps = []
        current_ts = start_scan.replace(minute=(start_scan.minute // 10) * 10, second=0, microsecond=0)
        
        while current_ts <= end_scan:
            expected_timestamps.append(current_ts.strftime('%Y-%m-%d_%H-%M'))
            current_ts += timedelta(minutes=config.INTERVALO_ESPERADO_MINUTOS)

        if not expected_timestamps:
            return

        # Max Workers = 16 garante que processamos todas as bandas simultaneamente
        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            for ts_str in expected_timestamps:
                for band_num in range(1, 17):
                    tasks.append(
                        executor.submit(processar_banda_para_timestamp, s3, band_num, ts_str, now_utc)
                    )
            
            concurrent.futures.wait(tasks)

    except Exception as e:
        logging.exception(f"Erro fatal AWS handler: {e}")