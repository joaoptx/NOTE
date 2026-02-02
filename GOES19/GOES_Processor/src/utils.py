import os
from src import config

def get_structure_path(date_obj, data_type, region=None, banda="13"):
    """
    Gera o caminho dinâmico:
    ROOT / Band{XX} / Ano / Mês / Dia / [Pasta Específica]
    """
    
    # 1. Define a Raiz dinâmica
    # Se for número (int ou str numérico), formata como "BandXX" (com zero à esquerda)
    # Se for texto (ex: "TrueColor"), usa o texto direto.
    if isinstance(banda, int):
        root_band = f"Band{banda:02d}"
    elif str(banda).isdigit():
        root_band = f"Band{int(banda):02d}"
    else:
        # Caso especial para TrueColor ou outros nomes
        root_band = banda 
    
    # 2. Base temporal: Ano/Mês/Dia
    date_path = date_obj.strftime("%Y/%m/%d")
    
    # 3. Define a subpasta final
    folder_name = ""
    
    if data_type == "netcdf":
        folder_name = "NetCDF"
        
    elif data_type == "glm":
        # Ex: "GLM Brasil"
        folder_name = f"GLM {region}" if region else "GLM_Full"
            
    elif data_type == "imagem":
        # Ex: "Brasil" ou "Sudeste"
        folder_name = region if region else "FullDisk"

    # 4. Monta o caminho completo usando o ORGANIZED_DIR do config
    # Ex: Y:\GOES-Organized \ Band13 \ 2026 \ 02 \ 02 \ GLM Brasil
    full_path = os.path.join(config.ORGANIZED_DIR, root_band, date_path, folder_name)
    
    # Cria os diretórios automaticamente se não existirem
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)
    
    return full_path