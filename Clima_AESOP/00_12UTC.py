import cdsapi
from datetime import datetime
import os

today = datetime.today()
data_str = today.strftime('%Y-%m-%d')

# Garante que a pasta de saída existe
path_saida = 'C:/Users/admin/Documents/Joao/municipios/dados/ads'
os.makedirs(path_saida, exist_ok=True)

# Nome completo do arquivo de saída (incluindo nome do arquivo)
output_file = os.path.join(path_saida, f'dados_cams_2025-08-30.zip')

dataset = "cams-global-atmospheric-composition-forecasts"
request = {
    "variable": [
        "2m_temperature",
        "surface_pressure",
        "total_precipitation",
        "relative_humidity"],
    "pressure_level": ["1000"],
    "date": ["2025-08-30/2025-08-30"],  # Modificado para formato simples
    "time": ["00:00", "12:00"],
    "leadtime_hour": ["0"],
    "type": "forecast",  # Removido colchetes
    "format": "netcdf_zip",  # Alterado de data_format para format
    "area": [5, -75, -55, -20]  # Brasil aproximadamente
}

print(f"Baixando dados de {data_str} 00:00 UTC...")
try:
    client = cdsapi.Client()
    client.retrieve(dataset, request, output_file)  # Usando o caminho completo do arquivo
    print(f"Download concluído: {output_file}")
except Exception as e:
    print(f"Erro durante o download: {str(e)}")