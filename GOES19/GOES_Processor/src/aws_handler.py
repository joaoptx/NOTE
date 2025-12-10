import os
import re
import glob
import logging
from datetime import datetime, timezone, timedelta
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import config  # Importa constantes

def verificar_e_preencher_lacunas_aws():
    logging.info("Iniciando verificação de lacunas AWS (últimas 24h)...")
    try:
        s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        now_utc = datetime.now(timezone.utc)
        
        end_scan = now_utc - timedelta(minutes=config.GRACE_PERIOD_MINUTES)
        start_scan = now_utc - timedelta(hours=24)

        expected_timestamps = set()
        current_ts = start_scan.replace(minute=(start_scan.minute // 10) * 10, second=0, microsecond=0)
        while current_ts <= end_scan:
            expected_timestamps.add(current_ts.strftime('%Y-%m-%d_%H-%M'))
            current_ts += timedelta(minutes=config.INTERVALO_ESPERADO_MINUTOS)

        if not expected_timestamps:
            return

        for band_num in range(1, 17):
            try:
                processed_timestamps = set()
                # Encontrar nome da pasta (com ou sem espaço)
                dirs = os.listdir(config.ORGANIZED_DIR)
                band_folder_name = next((d for d in dirs if f"band{band_num:02d}" in d.lower().replace(" ", "")), f"Band {band_num:02d}")
                
                # Check hoje e ontem
                for i in range(2):
                    check_date = now_utc - timedelta(days=i)
                    path = os.path.join(config.ORGANIZED_DIR, band_folder_name, check_date.strftime('%Y'), check_date.strftime('%m'), check_date.strftime('%d'), 'Brasil', '*.jpg')
                    for f in glob.glob(path):
                        match = re.match(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})', os.path.basename(f))
                        if match: processed_timestamps.add(match.group(1))
                
                missing = sorted(list(expected_timestamps - processed_timestamps))
                if not missing: continue
                
                logging.warning(f"Banda {band_num:02d}: {len(missing)} lacunas. Preenchendo...")

                for ts_str in missing:
                    ts_obj = datetime.strptime(ts_str, '%Y-%m-%d_%H-%M')
                    ano, dj, hora, mn = ts_obj.strftime('%Y'), ts_obj.strftime('%j'), ts_obj.strftime('%H'), ts_obj.minute
                    
                    prefix = f"{config.AWS_PRODUCT}/{ano}/{dj}/{hora}/"
                    resp = s3.list_objects_v2(Bucket=config.AWS_BUCKET, Prefix=prefix)
                    
                    if 'Contents' not in resp: continue
                    
                    for obj in resp['Contents']:
                        fname = os.path.basename(obj['Key'])
                        match = re.search(r'_s(\d{4}\d{3}\d{2}\d{2})', fname)
                        if match and f"C{band_num:02d}_G19_" in fname and match.group(1) == f"{ano}{dj}{hora}{mn:02d}":
                            incoming_dirs = os.listdir(config.INCOMING_DIR)
                            incoming_band = next((d for d in incoming_dirs if f"band{band_num:02d}" in d.lower().replace(" ", "")), f"Band {band_num:02d}")
                            dest_path = os.path.join(config.INCOMING_DIR, incoming_band, fname)
                            
                            if not os.path.exists(dest_path):
                                logging.info(f"Baixando lacuna {ts_str} B{band_num:02d}: {fname}")
                                s3.download_file(config.AWS_BUCKET, obj['Key'], dest_path)
                            break
            except Exception as e:
                logging.exception(f"Erro processar Banda {band_num:02d} AWS: {e}")

    except Exception as e:
        logging.exception(f"Erro fatal AWS handler: {e}")