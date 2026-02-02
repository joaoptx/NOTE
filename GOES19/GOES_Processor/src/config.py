import os

# Diretórios
INCOMING_DIR  = r"Y:\incoming\GOES-R-CMI-Imagery"
ORGANIZED_DIR = r"Y:\GOES-Organized"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Logos
LOGO_LEFT_PATH  = r"C:\Users\ire0349s\Downloads\assVisual_LAMCE_COR_SemTextoTransparente.png"
LOGO_RIGHT_PATH = r"C:\Users\ire0349s\Downloads\BaiaDigital-03.png"

# Domínios
DOMAIN         = [-73.9906, -26.5928, -33.7520, 6.2720]
DOMAIN_SUDESTE = [-54.0, -32.0, -27.5, -13.0]

# Configurações AWS (Imagem ABI)
AWS_BUCKET = 'noaa-goes19'
AWS_PRODUCT = 'ABI-L2-CMIPF'
INTERVALO_ESPERADO_MINUTOS = 10
GRACE_PERIOD_MINUTES = 30

# --- NOVO: Configurações GLM (Raios) ---
AWS_PRODUCT_GLM = 'GLM-L2-LCFA'   # Produto de raios
GLM_WINDOW_MINUTES = 10           # Acumular raios dos últimos 10 minutos
DIR_GLM_CACHE = os.path.join(BASE_DIR, "glm_cache") # Pasta temporária para baixar GLM

# Sistema
CHECK_INTERVAL = 60  # segundos entre varreduras
LOG_PATH = os.path.join(BASE_DIR, "..", "goes_loop.log") # Salva log na raiz do projeto
SCRIPT_SYNC_PATH = r"C:\scripts\sync_goes_to_nas.ps1"