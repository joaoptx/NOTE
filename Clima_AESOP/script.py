import os
import time
import zipfile
from datetime import datetime, timedelta, timezone
import pandas as pd
import geopandas as gpd
import xarray as xr
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pytz import timezone as pytz_timezone
import logging

# ===================== CONFIGURAÇÕES =====================
PASTA_MONITORADA = r"C:/Users/admin/Documents/Joao/municipios/dados/ads"
PASTA_SAIDA = r"Z:/ObsTerra/Brasil"
SHAPE_MUNICIPIOS = r"C:/Users/admin/Documents/Joao/shapefiles/BR_Municipios_2024/BR_Municipios_2024.shp"

INICIO_SEMANA_UTC = (6, 12)  # Domingo 12h UTC (9h BRT)
FIM_SEMANA_UTC = (6, 2)      # Domingo 2h UTC (Sábado 23h BRT)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PASTA_SAIDA, "processamento.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carregar shapefile dos municípios uma única vez
logger.info("Carregando shapefile dos municípios...")
gdf_mun = gpd.read_file(SHAPE_MUNICIPIOS).to_crs(epsg=4326)
logger.info(f"{len(gdf_mun)} municípios carregados.")

# Dados semanais em memória
dados_semana = []

def processar_netcdfs(nc_paths):
    """Processa múltiplos arquivos NC identificando automaticamente a dimensão temporal"""
    global dados_semana
    logger.info(f"Processando {len(nc_paths)} arquivos NetCDF...")
    variaveis = {}

    for nc_path in nc_paths:
        try:
            with xr.open_dataset(nc_path, decode_timedelta=False) as ds:
                logger.debug(f"Dimensões disponíveis em {os.path.basename(nc_path)}: {list(ds.dims)}")
                
                # Identifica automaticamente a dimensão temporal
                time_dims = ['valid_time', 'time', 'forecast_reference_time', 'forecast_period']
                time_dim = None
                for dim in time_dims:
                    if dim in ds.dims:
                        time_dim = dim
                        break
                
                if time_dim is None:
                    raise ValueError(f"Nenhuma dimensão temporal encontrada em {nc_path}. Dimensões disponíveis: {list(ds.dims)}")
                
                logger.debug(f"Usando dimensão temporal: {time_dim}")
                
                file_name = os.path.basename(nc_path)

                if 'data_sfc.nc' in file_name:
                    logger.debug("Processando variáveis de superfície...")
                    variaveis.update({
                        't2m': ds["t2m"].mean(dim=time_dim).values,
                        'sp': ds["sp"].mean(dim=time_dim).values,
                        'tp': ds["tp"].sum(dim=time_dim).values,
                        'lat': ds["latitude"].values,
                        'lon': ds["longitude"].values
                    })
                elif 'data_plev.nc' in file_name:
                    logger.debug("Processando variáveis de pressão...")
                    # Verificar se a variável 'r' existe no dataset
                    if 'r' in ds.variables:
                        variaveis['r'] = ds["r"].mean(dim=time_dim).values
                    else:
                        logger.warning(f"Variável 'r' não encontrada em {file_name}")
        except Exception as e:
            logger.error(f"Erro ao processar {nc_path}: {str(e)}")
            raise

    # Verificar se todas as variáveis necessárias estão presentes
    required_vars = ['t2m', 'sp', 'tp', 'r', 'lat', 'lon']
    missing_vars = [var for var in required_vars if var not in variaveis]
    if missing_vars:
        raise ValueError(f"Variáveis essenciais faltando: {missing_vars}")

    # Criar DataFrame com os dados
    df_temp = pd.DataFrame({
        "lat": variaveis['lat'].repeat(len(variaveis['lon'])),
        "lon": list(variaveis['lon']) * len(variaveis['lat']),
        "temp": variaveis['t2m'].flatten(),
        "press": variaveis['sp'].flatten(),
        "ur": variaveis['r'].flatten(),
        "precip": variaveis['tp'].flatten()
    })

    # Converter para GeoDataFrame
    gdf_temp = gpd.GeoDataFrame(
        df_temp,
        geometry=gpd.points_from_xy(df_temp.lon, df_temp.lat),
        crs="EPSG:4326"
    )

    # Realizar join espacial com os municípios
    gdf_temp_proj = gdf_temp.to_crs(epsg=5880)
    gdf_mun_proj = gdf_mun.to_crs(epsg=5880)

    gdf_join_proj = gpd.sjoin_nearest(gdf_temp_proj, gdf_mun_proj, how="left", distance_col="distancia")

    gdf_join = gdf_join_proj.to_crs(epsg=4326)
    gdf_join = gdf_join.drop(columns=['distancia'], errors='ignore')

    # Agrupar por município
    df_grouped = gdf_join.groupby(["CD_MUN", "NM_MUN", "SIGLA_UF"]).agg({
        "temp": "mean",
        "press": "mean",
        "ur": "mean",
        "precip": "sum"
    }).reset_index()

    dados_semana.append(df_grouped)
    logger.info("Dados processados e adicionados ao buffer semanal.")

def salvar_semana_csv(df_semana, data_inicio, data_fim):
    """Salva dados semanais em estrutura de pastas por município"""
    semana_str = f"{data_inicio.strftime('%d/%m/%Y %Hh')} UTC - {data_fim.strftime('%d/%m/%Y %Hh')} UTC"
    num_semana = data_inicio.isocalendar()[1]
    ano = data_inicio.year

    brt = pytz_timezone('America/Sao_Paulo')
    inicio_brt = data_inicio.replace(tzinfo=timezone.utc).astimezone(brt)
    fim_brt = data_fim.replace(tzinfo=timezone.utc).astimezone(brt)
    logger.info(f"Período semanal convertido: {inicio_brt.strftime('%d/%m %Hh')} BRT a {fim_brt.strftime('%d/%m %Hh')} BRT")

    for _, row in df_semana.iterrows():
        try:
            uf = row["SIGLA_UF"]
            nm_mun = row["NM_MUN"].replace("/", "-")
            cd_mun = row["CD_MUN"]

            pasta_mun = os.path.join(PASTA_SAIDA, uf, nm_mun, str(ano))
            os.makedirs(pasta_mun, exist_ok=True)
            csv_path = os.path.join(pasta_mun, f"{ano}.csv")

            nova_linha = pd.DataFrame([{
                "Semana": semana_str,
                "Numero_Semana": num_semana,
                "NM_MUN": nm_mun,
                "CD_MUN": cd_mun,
                "Temp_Media": round(row["temp"] - 273.15, 2) if 'temp' in row else None,  # Converter Kelvin para Celsius
                "Pressao_Media": round(row["press"] / 100, 2) if 'press' in row else None,  # Converter Pa para hPa
                "Umidade_Media": round(row["ur"], 2) if 'ur' in row else None,
                "Precipitacao_Acumulada": round(row["precip"] * 1000, 2) if 'precip' in row else None  # Converter m para mm
            }])

            if os.path.exists(csv_path):
                df_existente = pd.read_csv(csv_path, sep=";")
                if semana_str not in df_existente["Semana"].values:
                    df_final = pd.concat([df_existente, nova_linha], ignore_index=True)
                    df_final.to_csv(csv_path, sep=";", index=False, encoding="utf-8")
                    logger.info(f"Dados atualizados para {nm_mun}/{uf}")
                else:
                    logger.info(f"Semana já registrada para {nm_mun}/{uf}")
            else:
                nova_linha.to_csv(csv_path, sep=";", index=False, encoding="utf-8")
                logger.info(f"Novo arquivo criado para {nm_mun}/{uf}")

        except Exception as e:
            logger.error(f"Erro ao salvar dados para município {row['NM_MUN']}: {str(e)}")

def calcular_medias_e_salvar():
    """Consolida e salva os dados semanais"""
    global dados_semana

    if not dados_semana:
        logger.warning("Nenhum dado para processar.")
        return

    logger.info("Iniciando cálculo das médias semanais...")
    try:
        df_total = pd.concat(dados_semana)
        df_semana = df_total.groupby(["CD_MUN", "NM_MUN", "SIGLA_UF"]).agg({
            "temp": "mean",
            "press": "mean",
            "ur": "mean",
            "precip": "sum"
        }).reset_index()

        # Calcular período semanal
        agora = datetime.now(timezone.utc)
        data_fim = agora.replace(
            hour=FIM_SEMANA_UTC[1], 
            minute=0, 
            second=0, 
            microsecond=0
        )
        
        # Ajustar se já passou do horário de fim desta semana
        if agora > data_fim:
            data_fim = data_fim + timedelta(days=7)
        
        data_inicio = data_fim - timedelta(days=7)
        data_inicio = data_inicio.replace(hour=INICIO_SEMANA_UTC[1])

        logger.info(f"Período calculado: {data_inicio.strftime('%A %d/%m %Hh UTC')} a {data_fim.strftime('%A %d/%m %Hh UTC')}")

        salvar_semana_csv(df_semana, data_inicio, data_fim)
        dados_semana = []  # Limpar buffer após processamento

        logger.info("Processamento semanal concluído com sucesso.")

    except Exception as e:
        logger.error(f"Erro no processamento semanal: {str(e)}")
        raise

def extrair_zip(zip_path):
    """Extrai e processa arquivos NC de um ZIP"""
    logger.info(f"Processando arquivo: {zip_path}")
    temp_files = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            nc_files = [f for f in zip_ref.namelist() if f.endswith('.nc')]
            logger.info(f"Arquivos NC encontrados no ZIP: {nc_files}")

            for file in nc_files:
                nc_path = os.path.join(PASTA_MONITORADA, file)
                zip_ref.extract(file, PASTA_MONITORADA)
                temp_files.append(nc_path)
                logger.info(f"Extraído: {file}")

            if len(nc_files) >= 2:
                processar_netcdfs(temp_files)
            else:
                logger.warning("ZIP não contém ambos os arquivos NC necessários (data_sfc.nc e data_plev.nc)")

    except Exception as e:
        logger.error(f"Erro ao extrair ZIP: {str(e)}")
    finally:
        # Limpeza de arquivos temporários
        for file in temp_files:
            try:
                os.remove(file)
                logger.info(f"Arquivo temporário removido: {file}")
            except Exception as e:
                logger.error(f"Erro ao remover {file}: {str(e)}")

        try:
            os.remove(zip_path)
            logger.info(f"Arquivo ZIP removido: {zip_path}")
        except Exception as e:
            logger.error(f"Erro ao remover ZIP: {str(e)}")

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.zip'):
            logger.info(f"Novo arquivo detectado: {event.src_path}")
            time.sleep(5)  # Espera para garantir que o arquivo está completamente escrito
            extrair_zip(event.src_path)

if __name__ == "__main__":
    logger.info(f"Iniciando monitoramento em: {PASTA_MONITORADA}")
    logger.info(f"Configuração do período semanal:")
    logger.info(f"- Início: Domingo {INICIO_SEMANA_UTC[1]}h UTC")
    logger.info(f"- Término: Domingo {FIM_SEMANA_UTC[1]}h UTC (Sábado 23h BRT)")

    brt = pytz_timezone('America/Sao_Paulo')
    utc_time = datetime.now(timezone.utc).replace(hour=FIM_SEMANA_UTC[1])
    logger.info(f"Domingo {FIM_SEMANA_UTC[1]}h UTC = {utc_time.astimezone(brt).strftime('%A %Hh BRT')}")

    observer = Observer()
    observer.schedule(Handler(), path=PASTA_MONITORADA, recursive=False)
    observer.start()

    # Variáveis para controlar a exibição das mensagens
    ultima_mensagem_aguardando = 0
    intervalo_mensagem = 300  # 5 minutos em segundos
    
    # Variável para controlar a semana atual
    semana_atual = datetime.now().isocalendar()[1]
    print(f"Semana {semana_atual} em andamento...")

    try:
        while True:
            agora_utc = datetime.now(timezone.utc)
            semana_agora = agora_utc.isocalendar()[1]

            # Verificar se começou uma nova semana
            if semana_agora != semana_atual:
                semana_atual = semana_agora
                print(f"Semana {semana_atual} se iniciando...")
                print("Aguardando a chegada dos dados...")
                ultima_mensagem_aguardando = time.time()  # Resetar o timer da mensagem

            # Verifica se é hora de processar a semana (Domingo 2h UTC)
            if (agora_utc.weekday() == FIM_SEMANA_UTC[0] and 
                agora_utc.hour == FIM_SEMANA_UTC[1] and 
                agora_utc.minute < 5):  # Executar apenas uma vez por hora
                calcular_medias_e_salvar()
                time.sleep(300)  # Esperar 5 minutos para evitar execuções múltiplas

            # Exibir mensagem a cada 5 minutos enquanto aguarda dados
            tempo_atual = time.time()
            if tempo_atual - ultima_mensagem_aguardando >= intervalo_mensagem:
                print("Aguardando a chegada dos dados...")
                ultima_mensagem_aguardando = tempo_atual

            time.sleep(60)  # Verifica a cada minuto

    except KeyboardInterrupt:
        logger.info("Interrompendo monitoramento...")
        observer.stop()

    observer.join()