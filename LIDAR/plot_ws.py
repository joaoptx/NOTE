import time
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

ARQ = r"C:/Users/lamce/Desktop/Lidar/dados_modbuspoll/dados_tratados.csv"
ALTURAS = [40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300]
APENAS_VALIDOS = True

SUAVIZAR_JANELA = 1     # 1 sem suavizar, 3 ou 5 para suavização leve

plt.ion()
fig, ax = plt.subplots(figsize=(6, 6))
linha, = ax.plot([], [], marker='o')  
ax.set_ylabel("Altura (m)")
ax.set_xlabel("Velocidade horizontal (m/s)")
ax.grid(True, alpha=0.3)
ax.set_title("Perfil vertical – aguardando dados…")
ax.set_ylim(min(ALTURAS) - 10, max(ALTURAS) + 10)

def atualizar(_):
    try:
        df = pd.read_csv(ARQ)
    except Exception:
        return

    if df.empty:
        return

    ultimo_ts = df['datetime'].iloc[-1]
    bloco = df[df['datetime'] == ultimo_ts].copy()

    if APENAS_VALIDOS:
        bloco = bloco[bloco['id_valid'] == 0]
    bloco = bloco.sort_values('altura')

    if SUAVIZAR_JANELA > 1:
        ultimos_ts = df['datetime'].drop_duplicates().tail(SUAVIZAR_JANELA).tolist()
        dfn = df[df['datetime'].isin(ultimos_ts)].copy()
        if APENAS_VALIDOS:
            dfn = dfn[dfn['id_valid'] > 0]
        bloco = (
            dfn.groupby('altura', as_index=False)['vel_horiz']
               .mean()
               .merge(dfn[['altura']].drop_duplicates(), on='altura', how='right')
               .sort_values('altura'))
        titulo_ts = ultimo_ts
    else:
        titulo_ts = ultimo_ts
    try:
        x = bloco['vel_horiz'].values
        y = bloco['altura'].values
    except KeyError:
        # se faltar coluna, não atualiza
        return

    if len(x) == 0:
        return

    linha.set_xdata(x)
    linha.set_ydata(y)

    xmin = min(0.0, float(x.min()) - 0.5)
    xmax = float(x.max()) + 0.5
    if xmax - xmin < 2:
        xmax = xmin + 2
    ax.set_xlim(xmin, xmax)

    ax.set_title(f"Perfil vertical – {titulo_ts}")

ani = FuncAnimation(fig, atualizar, interval=1000)
plt.tight_layout()
plt.show()

while plt.fignum_exists(fig.number):
    plt.pause(0.5)
