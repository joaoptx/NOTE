import os
import shutil
import logging
import time
import gc
import subprocess
from datetime import datetime, timedelta

def check_nas_space(path, min_gb_free=10):
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)
        if free_gb < min_gb_free:
            logging.warning(f"NAS com pouco espaço: {free_gb:.2f} GB disponíveis.")
            return False
        return True
    except Exception as e:
        logging.error(f"Erro verificação espaço NAS ({path}): {e}")
        return False

def safe_remove(path, retries=10, delay=1.0):
    """
    Remove um arquivo com múltiplas tentativas e delay progressivo.
    Ideal para Windows com multiprocessing.
    """
    for i in range(retries):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            # O arquivo está travado. Espera um pouco.
            # Aumenta o tempo de espera a cada tentativa (Exponential Backoff)
            wait_time = delay * (i + 1)
            # logging.warning(f"Arquivo em uso, aguardando {wait_time}s para remover: {path}") # Comentado para não poluir
            gc.collect() # Força o Python a limpar referências soltas
            time.sleep(wait_time)
        except Exception as e:
            logging.warning(f"Erro genérico ao remover '{path}': {e}")
            time.sleep(delay)
            
    # Se chegou aqui, falhou todas as tentativas
    logging.error(f"Falha definitiva ao remover arquivo após {retries} tentativas: {path}")
    return False

def limpar_arquivos_antigos(base_dir, dias_para_manter):
    hoje = datetime.utcnow().date()
    limite = hoje - timedelta(days=dias_para_manter)
    
    if not os.path.exists(base_dir):
        return

    for banda in os.listdir(base_dir):
        banda_path = os.path.join(base_dir, banda)
        if not os.path.isdir(banda_path): continue
        
        for ano in os.listdir(banda_path):
            ano_path = os.path.join(banda_path, ano)
            if not ano.isdigit(): continue
            
            for mes in os.listdir(ano_path):
                mes_path = os.path.join(ano_path, mes)
                if not mes.isdigit(): continue
                
                for dia in os.listdir(mes_path):
                    dia_path = os.path.join(mes_path, dia)
                    try:
                        data_pasta = datetime.strptime(f"{ano}-{mes}-{dia}", "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    
                    if data_pasta < limite:
                        try:
                            shutil.rmtree(dia_path)
                            logging.info(f"Pasta antiga removida: {dia_path}")
                        except Exception as e:
                            logging.warning(f"Erro apagar {dia_path}: {e}")

def run_nas_sync(script_path):
    """Executa o script de sincronização PowerShell."""
    try:
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
            check=True, timeout=60
        )
        logging.info("Sincronização com NAS concluída.")
    except FileNotFoundError:
        logging.warning(f"Script sync não encontrado: {script_path}")
    except subprocess.TimeoutExpired:
        logging.warning("Sync com NAS expirou por timeout.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Falha no PowerShell: código {e.returncode}")
    except Exception as e:
        logging.exception(f"Erro inesperado no sync: {e}")