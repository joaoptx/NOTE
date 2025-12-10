import os

# Diretórios
INCOMING_DIR  = r"Y:\incoming\GOES-R-CMI-Imagery"
ORGANIZED_DIR = r"Y:\GOES-Organized"

# Logos
LOGO_LEFT_PATH  = r"C:\Users\ire0349s\Downloads\assVisual_LAMCE_COR_SemTextoTransparente.png"
LOGO_RIGHT_PATH = r"C:\Users\ire0349s\Downloads\BaiaDigital-03.png"

# Domínios
DOMAIN         = [-73.9906, -26.5928, -33.7520, 6.2720]
DOMAIN_SUDESTE = [-54.0, -32.0, -27.5, -13.0]

# Configurações AWS
AWS_BUCKET = 'noaa-goes19'
AWS_PRODUCT = 'ABI-L2-CMIPF'
INTERVALO_ESPERADO_MINUTOS = 10
GRACE_PERIOD_MINUTES = 30

# Sistema
CHECK_INTERVAL = 60  # segundos entre varreduras
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "goes_loop.log")
SCRIPT_SYNC_PATH = r"C:\scripts\sync_goes_to_nas.ps1"