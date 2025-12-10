import os
import logging
import gc
import shutil
from datetime import datetime, timezone
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
import GOES

# Importações internas do projeto
import config
from src import colormaps, processing, file_manager

# Tenta carregar os logos uma única vez ao iniciar o módulo
try:
    logo_left_img = plt.imread(config.LOGO_LEFT_PATH)
    logo_right_img = plt.imread(config.LOGO_RIGHT_PATH)
except Exception as e:
    logging.warning(f"Visualização: Erro ao carregar logos: {e}")
    logo_left_img = None
    logo_right_img = None

def add_logo_on_map(ax, logo_img, lon, lat, width_deg=5, anchor='bottom-left'):
    """Posiciona o logo no mapa."""
    if logo_img is None: return
    try:
        aspect = logo_img.shape[1] / logo_img.shape[0]
        height_deg = width_deg / aspect
        left, right = lon, lon + width_deg
        bottom, top = lat, lat + height_deg
        
        if anchor == 'top-right':
            left = lon - width_deg
            bottom = lat - height_deg
            top = lat
            right = lon
            
        ax.imshow(logo_img, extent=(left, right, bottom, top),
                  transform=ccrs.PlateCarree(),
                  alpha=logo_img[:, :, 3] if logo_img.shape[2] == 4 else 1,
                  origin='upper', zorder=10)
    except Exception as e:
        logging.warning(f"Erro ao posicionar logo: {e}")

def process_nc_file(band_num, band_folder, nc_path):
    """
    Função principal que:
    1. Abre o NetCDF
    2. Gera o Plot Brasil
    3. Gera o Plot Sudeste
    4. Chama o recorte do NetCDF
    5. Gerencia a limpeza do arquivo original
    """
    try:
        # --- 1. Abertura e Extração de Dados ---
        ds = GOES.open_dataset(nc_path)
        try:
            result = ds.image('CMI', lonlat='corner', domain=config.DOMAIN)
            if not result or any(r is None for r in result):
                logging.warning(f"Dados inválidos ou CMI vazio em {nc_path}")
                return
            
            CMI, Lon, Lat = result
            if CMI.data is None or np.all(np.isnan(CMI.data)):
                return
            
            # Copia para memória e desacopla do arquivo
            data = np.array(CMI.data, dtype=float, copy=True)
            Lon_data = np.array(Lon.data, copy=True)
            Lat_data = np.array(Lat.data, copy=True)
            
            # Metadados
            band_id = ds.variable('band_id').data[0]
            wl = ds.variable('band_wavelength').data[0]
            platform = ds.attribute("platform_ID")
            utc_dt = CMI.time_bounds.data[0]
            
            # Tratamento de timestamp
            if isinstance(utc_dt, np.datetime64):
                utc_dt = datetime.strptime(str(utc_dt)[:19], '%Y-%m-%dT%H:%M:%S')
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                
        except Exception as e:
            logging.warning(f"Erro extração dados {nc_path}: {e}")
            return
        finally:
            if hasattr(ds, "close"): ds.close()
            ds = None
            gc.collect()

        # Conversão de Unidades (Igual ao original)
        if band_num >= 7:
            data -= 273.15 # Kelvin para Celsius
        else:
            data *= 100    # Reflectância para %
        
        # Definições de Cores
        cmap = colormaps.cmap_lookup.get(band_num)
        vmin, vmax = colormaps.vmin_vmax.get(band_num)
        product_name = colormaps.colormaps_names.get(band_num, "Unknown")
        
        # Diretório de saída
        out_dir = os.path.join(config.ORGANIZED_DIR, band_folder, f"{utc_dt.year:04d}", f"{utc_dt.month:02d}", f"{utc_dt.day:02d}")
        ts_str = utc_dt.strftime('%Y-%m-%d_%H-%M')

        # ==========================================
        # 2. PLOT BRASIL
        # ==========================================
        fig = plt.figure(figsize=(12, 9), dpi=200)
        gs = fig.add_gridspec(nrows=20, ncols=24)
        ax = fig.add_subplot(gs[1:17, 2:22], projection=ccrs.PlateCarree())
        ax.set_extent([config.DOMAIN[0]+360, config.DOMAIN[1]+360, config.DOMAIN[2], config.DOMAIN[3]])
        
        mesh = ax.pcolormesh(Lon_data, Lat_data, data, cmap=cmap, norm=mcolors.Normalize(vmin=vmin, vmax=vmax))
        cbar_ax = fig.add_subplot(gs[18, 2:22])
        cb = plt.colorbar(mesh, cax=cbar_ax, orientation='horizontal', extend='both')
        cb.set_label('Brightness Temperature (°C)' if band_num >= 7 else 'Reflectance (%)', size=9)
        cb.ax.tick_params(labelsize=8)
        
        fig.suptitle(f'{platform} - Band {band_id:02d}: {product_name}\n{utc_dt.strftime("%Y-%m-%d %H:%M UTC")}\n{wl:.1f} µm', y=0.98, fontsize=8, linespacing=1.5)
        ax.add_feature(cfeature.NaturalEarthFeature('cultural', 'admin_0_countries', '50m', facecolor='none'), edgecolor='white', linewidth=0.8)
        ax.gridlines(draw_labels=False, linestyle='--', alpha=0.7)
        ax.xaxis.set_major_formatter(LongitudeFormatter(number_format='.0f°'))
        ax.yaxis.set_major_formatter(LatitudeFormatter(number_format='.0f°'))
        
        # Logos BRASIL (Tamanhos grandes: 13.5 e 14.5)
        add_logo_on_map(ax, logo_left_img, config.DOMAIN[0] + 1.0, config.DOMAIN[2] + 1.5, 13.5)
        add_logo_on_map(ax, logo_right_img, config.DOMAIN[1] - 1.0, config.DOMAIN[3] - 0.5, 14.5, 'top-right')
        
        jpg_name = f'{ts_str}_Band{band_num:02d}_Brasil_{os.path.basename(nc_path).replace(".nc", "")}.jpg'
        jpg_path = os.path.join(out_dir, 'Brasil', jpg_name)
        os.makedirs(os.path.dirname(jpg_path), exist_ok=True)
        fig.savefig(jpg_path, format='jpeg', bbox_inches='tight')
        plt.close(fig)
        gc.collect()

        # ==========================================
        # 3. PLOT SUDESTE
        # ==========================================
        fig = plt.figure(figsize=(12, 9), dpi=200)
        gs = fig.add_gridspec(nrows=20, ncols=24)
        ax = fig.add_subplot(gs[1:17, 2:22], projection=ccrs.PlateCarree())
        ax.set_extent([config.DOMAIN_SUDESTE[0]+360, config.DOMAIN_SUDESTE[1]+360, config.DOMAIN_SUDESTE[2], config.DOMAIN_SUDESTE[3]])
        
        mesh = ax.pcolormesh(Lon_data, Lat_data, data, cmap=cmap, norm=mcolors.Normalize(vmin=vmin, vmax=vmax))
        cbar_ax = fig.add_subplot(gs[18, 2:22])
        cb = plt.colorbar(mesh, cax=cbar_ax, orientation='horizontal', extend='both')
        cb.set_label('Brightness Temperature (°C)' if band_num >= 7 else 'Reflectance (%)', size=9)
        cb.ax.tick_params(labelsize=8)
        
        fig.suptitle(f'{platform} - Band {band_id:02d}: {product_name}\n{utc_dt.strftime("%Y-%m-%d %H:%M UTC")}\n{wl:.1f} µm', y=0.98, fontsize=8, linespacing=1.5)
        ax.add_feature(cfeature.NaturalEarthFeature('cultural', 'admin_0_countries', '50m', facecolor='none'), edgecolor='white', linewidth=0.8)
        ax.add_feature(cfeature.STATES, edgecolor='white', linewidth=0.5) # Feature extra do sudeste
        ax.gridlines(draw_labels=False, linestyle='--', alpha=0.7)
        ax.xaxis.set_major_formatter(LongitudeFormatter(number_format='.0f°'))
        ax.yaxis.set_major_formatter(LatitudeFormatter(number_format='.0f°'))
        
        # Logos SUDESTE (Tamanhos menores: 4.5 e 5.5)
        add_logo_on_map(ax, logo_left_img, config.DOMAIN_SUDESTE[0] + 1.0, config.DOMAIN_SUDESTE[2] + 1.0, 4.5)
        add_logo_on_map(ax, logo_right_img, config.DOMAIN_SUDESTE[1] - 1.0, config.DOMAIN_SUDESTE[3] - 0.5, 5.5, 'top-right')
        
        jpg_se_name = f'{ts_str}_Band{band_num:02d}_Sudeste_{os.path.basename(nc_path).replace(".nc", "")}.jpg'
        jpg_se_path = os.path.join(out_dir, 'Sudeste', jpg_se_name)
        os.makedirs(os.path.dirname(jpg_se_path), exist_ok=True)
        fig.savefig(jpg_se_path, format='jpeg', bbox_inches='tight')
        plt.close(fig)
        gc.collect()

        # ==========================================
        # 4. RECORTE E LIMPEZA
        # ==========================================
        recorte_dir = os.path.join(out_dir, "NetCDF")
        caminho_recortado = processing.recortar_e_salvar_netcdf(nc_path, recorte_dir, utc_dt)
        
        if caminho_recortado:
            # Recorte OK -> Tenta remover original (com retries)
            if not file_manager.safe_remove(nc_path):
                logging.warning(f"Falha ao remover original após recorte: {nc_path}")
        else:
            # Recorte falhou -> Backup do original para a pasta final
            try:
                destino_backup = os.path.join(recorte_dir, os.path.basename(nc_path))
                shutil.move(nc_path, destino_backup)
                logging.warning(f"Recorte falhou. Original movido para backup: {destino_backup}")
            except Exception as e:
                logging.warning(f"Erro ao mover backup: {e}")

        logging.info(f"Processado: {os.path.basename(nc_path)}")

    except Exception as e:
        logging.exception(f"Erro fatal processando {nc_path}: {e}")