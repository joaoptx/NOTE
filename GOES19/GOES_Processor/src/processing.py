import os
import logging
import gc
import numpy as np
import xarray as xr
import GOES

# --- CORREÇÃO DE IMPORTAÇÃO ---
from src import config

def recortar_e_salvar_netcdf(nc_path, destino_dir, timestamp_utc):
    try:
        actual_path = nc_path
        if not os.path.exists(actual_path):
            candidate = os.path.join(destino_dir, os.path.basename(nc_path))
            if os.path.exists(candidate):
                actual_path = candidate
            else:
                logging.warning(f"Arquivo não encontrado para recorte: {nc_path}")
                return None

        # Obter Lon/Lat (grade)
        ds_goes = None
        try:
            ds_goes = GOES.open_dataset(actual_path)
            result = ds_goes.image('CMI', lonlat='corner')
            if result is None or any(r is None for r in result):
                raise ValueError("Falha ao obter CMI/Lon/Lat via GOES.")
            CMI_img, Lon_img, Lat_img = result
            lon2d = np.array(Lon_img.data, copy=True)
            lat2d = np.array(Lat_img.data, copy=True)
        except Exception as e:
            raise ValueError(f"Erro extrair Lon/Lat: {e}")
        finally:
            if ds_goes and hasattr(ds_goes, "close"):
                ds_goes.close()

        # Normalizar longitudes
        lon_max = np.nanmax(lon2d)
        uses_360 = lon_max > 180.0
        
        def to_360(l): return l + 360.0 if l < 0 else l
        
        if uses_360:
            dom_lon_min = to_360(config.DOMAIN[0])
            dom_lon_max = to_360(config.DOMAIN[1])
            lon_data = lon2d
        else:
            dom_lon_min = config.DOMAIN[0]
            dom_lon_max = config.DOMAIN[1]
            lon_data = np.where(lon2d > 180.0, lon2d - 360.0, lon2d)

        # Máscara
        if uses_360 and dom_lon_min > dom_lon_max:
            lon_mask = (lon_data >= dom_lon_min) | (lon_data <= dom_lon_max)
        else:
            lon_mask = (lon_data >= dom_lon_min) & (lon_data <= dom_lon_max)
            
        lat_mask = (lat2d >= config.DOMAIN[2]) & (lat2d <= config.DOMAIN[3])
        mask = lon_mask & lat_mask
        
        if not np.any(mask):
            raise ValueError("Recorte vazio - nenhum dado no domínio.")

        ys, xs = np.where(mask)
        y_min, y_max = int(ys.min()), int(ys.max())
        x_min, x_max = int(xs.min()), int(xs.max())

        # Recortar com Xarray
        ds = xr.open_dataset(actual_path)
        try:
            ds_recorte = ds.isel(y=slice(y_min, y_max + 1), x=slice(x_min, x_max + 1))
            os.makedirs(destino_dir, exist_ok=True)
            nome_recorte = f"recorte_{timestamp_utc.strftime('%Y-%m-%d_%H-%M')}_UTC_{os.path.basename(actual_path)}"
            caminho_final = os.path.join(destino_dir, nome_recorte)
            ds_recorte.to_netcdf(caminho_final)
            ds_recorte.close()
        finally:
            ds.close()
            del ds
            gc.collect()
            
        return caminho_final
    except Exception as e:
        logging.warning(f"Erro ao recortar NetCDF: {nc_path} -> {e}")
        return None