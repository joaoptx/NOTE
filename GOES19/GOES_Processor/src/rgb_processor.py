import os
import logging
import gc
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime, timezone
import GOES
from scipy.ndimage import zoom

from src import config, visualization, utils

def align_resolutions_high_quality(file_b01, file_b02, file_b03):
    """
    Alinhamento com interpolação Bicúbica (Order=3) para eliminar serrilhados.
    """
    ds01 = None; ds02 = None; ds03 = None
    try:
        logging.info(f"Carregando bandas para alinhamento (Alta Qualidade)...")
        ds01 = GOES.open_dataset(file_b01)
        ds02 = GOES.open_dataset(file_b02)
        ds03 = GOES.open_dataset(file_b03)

        domain = config.DOMAIN

        # Extração
        CMI_1, _, _ = ds01.image('CMI', lonlat='corner', domain=domain)
        CMI_2, Lon_obj, Lat_obj = ds02.image('CMI', lonlat='corner', domain=domain)
        CMI_3, _, _ = ds03.image('CMI', lonlat='corner', domain=domain)

        data1 = np.array(CMI_1.data)
        data2 = np.array(CMI_2.data)
        data3 = np.array(CMI_3.data)
        
        Lon = np.squeeze(np.array(Lon_obj.data))
        Lat = np.squeeze(np.array(Lat_obj.data))

        del ds01, ds02, ds03, CMI_1, CMI_2, CMI_3, Lon_obj, Lat_obj
        gc.collect()

        target_shape = data2.shape 
        
        def resize_high_quality(arr, shape):
            if arr.shape == shape: return arr
            factors = (shape[0]/arr.shape[0], shape[1]/arr.shape[1])
            # ORDER=3 (Bicúbico) é essencial para qualidade visual
            return zoom(arr, factors, order=3) 

        B = resize_high_quality(data1, target_shape)
        R = data2 
        N = resize_high_quality(data3, target_shape)

        return R, B, N, Lon, Lat

    except Exception as e:
        logging.error(f"Erro alinhamento RGB: {e}")
        return None, None, None, None, None

def process_true_color(timestamp_str, files_dict):
    fig = None
    R_raw = B_raw = N_raw = RGB = None 
    
    try:
        result = align_resolutions_high_quality(files_dict[1], files_dict[2], files_dict[3])
        if result is None or result[0] is None: return
        
        R_raw, B_raw, N_raw, Lon, Lat = result

        logging.info(f"Processando True Color (Padrão CIMSS/NOAA) para {timestamp_str}...")

        # === 1. CORREÇÃO DE RAYLEIGH (Remoção da Névoa Azul) ===
        # A banda azul sofre muito espalhamento. Subtraímos um valor base para limpar.
        # Valores conservadores para evitar preto total no espaço.
        R = np.clip(R_raw - 0.015, 0, 1) # Pequena correção no vermelho
        B = np.clip(B_raw - 0.050, 0, 1) # Forte correção no azul (Rayleigh)
        N = np.clip(N_raw - 0.005, 0, 1)

        # === 2. SÍNTESE DO VERDE (FÓRMULA CIMSS) ===
        # Conforme relatório: G_true = 0.45*R + 0.10*Veggie + 0.45*B
        G = 0.45 * R + 0.10 * N + 0.45 * B
        G = np.clip(G, 0, 1)

        # === 3. EMPILHAMENTO ===
        RGB = np.dstack([R, G, B])
        
        # === 4. CORREÇÃO DE GAMMA (Padrão Internacional 2.2) ===
        # O relatório especifica que satélites são lineares e monitores não.
        # Correção: Valor^(1/Gamma). Gamma padrão = 2.2.
        gamma_val = 2.2
        RGB = np.power(RGB, 1/gamma_val)

        # === 5. CONTRASTE FINAL (Stretch) ===
        # Cortamos os 0.5% mais escuros e mais claros para maximizar o contraste visual
        # Isso simula a normalização solar citada no texto.
        vmin = np.nanpercentile(RGB, 0.5)
        vmax = np.nanpercentile(RGB, 99.5)
        RGB = (RGB - vmin) / (vmax - vmin)
        RGB = np.clip(RGB, 0, 1)

        ts_obj = datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M').replace(tzinfo=timezone.utc)
        extent = [np.nanmin(Lon), np.nanmax(Lon), np.nanmin(Lat), np.nanmax(Lat)]

        # --- PLOTAGEM ---
        def create_plot(region_extent, region_name, logo_scale_left, logo_scale_right):
            fig = plt.figure(figsize=(12, 9), dpi=200)
            
            # Fundo preto para ressaltar a atmosfera
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_facecolor('black')
            ax.set_extent([region_extent[0]+360, region_extent[1]+360, region_extent[2], region_extent[3]])
            
            ax.imshow(RGB, origin='upper', extent=extent, transform=ccrs.PlateCarree())
            
            ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor='white', alpha=0.6)
            ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor='white', alpha=0.6)
            
            visualization.add_logo_on_map(ax, visualization.logo_left_img, 
                                    region_extent[0] + 1.0, region_extent[2] + 1.0, logo_scale_left)
            visualization.add_logo_on_map(ax, visualization.logo_right_img, 
                                    region_extent[1] - 1.0, region_extent[3] - 0.5, logo_scale_right, 'top-right')
            
            title = f'GOES-19 True Color (CIMSS Protocol)'
            if region_name == "Sudeste": title += " - Sudeste"
            ax.set_title(f'{title}\n{ts_obj.strftime("%Y-%m-%d %H:%M UTC")}', loc='left', fontsize=9, weight='bold', color='white')

            out_path = utils.get_structure_path(ts_obj, "imagem", region=region_name, banda="TrueColor")
            filename = f"{timestamp_str}_TrueColor_{region_name}.jpg"
            full_path = os.path.join(out_path, filename)
            
            plt.savefig(full_path, bbox_inches='tight', pad_inches=0.1, dpi=200, facecolor='black')
            
            # GLM Overlay (Azul)
            has_lightning = visualization.plot_glm_overlay(ax, ts_obj)
            if has_lightning:
                glm_path = utils.get_structure_path(ts_obj, "glm", region=region_name, banda="TrueColor")
                plt.savefig(os.path.join(glm_path, filename), bbox_inches='tight', pad_inches=0.1, dpi=200, facecolor='black')

            plt.close(fig)

        create_plot(config.DOMAIN, "Brasil", 13.5, 14.5)
        create_plot(config.DOMAIN_SUDESTE, "Sudeste", 4.5, 5.5)

        logging.info(f"True Color (Standard) gerado com sucesso.")

    except Exception as e:
        logging.exception(f"Erro fatal True Color: {e}")
    finally:
        if fig: plt.close(fig)
        try: del R_raw, B_raw, N_raw, RGB, Lon, Lat
        except: pass
        gc.collect()