import simplekml
import pandas as pd

# Dados
data = pd.DataFrame({
    'nome': [
        'Urca',
        'Ilha de Paquetá',
        'Apa de Guapimirim',
        'Lamce - UFRJ',
        'Lamce - UFF',
        'Forte Duque de Caxias',
        'Forte da Urca',
        'Ilha da Laje',
        'Mauá',
        'O Globo - Duque de Caxias'],

    'latitude': [
        -22.95532,
        -22.76781,
        -22.67654,
        -22.863336,
        -22.906125,
        -22.963206,
        -22.940567,
        -22.934461,
        -22.713861,
        -22.786164],

    'longitude': [
        -43.17588,
        -43.11344,
        -42.97651,
        -43.214455,
        -43.133900,
        -43.161989,
        -43.152511,
        -43.146958,
        -43.166906,
        -43.280556],

    'descricao': [
        "Nome: Urca\nVariáveis: O3\nTipo: Automática\nEmpresa: Inea",
        "Nome: Ilha de Paquetá\nVariáveis: CO2, O3, SO2, MP10, PTS, TEMP, PRESSÃO, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Inea",
        "Nome: Apa de Guapimirim\nVariáveis: SO2, MP10, PTS, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: COMPERJ",
        "Nome: Lamce - UFRJ\nVariáveis: CO, O3, NO2, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Nome: Lamce - UFF\nVariáveis: CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Sugestão de local\nNome: Forte Duque de Caxias\nVariáveis: CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Sugestão de local\nNome: Forte da Urca\nVariáveis: CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Sugestão de local\nNome: Ilha da Laje\nVariáveis:CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Sugestão de local\nNome: Mauá\nVariáveis: CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ",
        "Sugestão de local\nNome: O Globo - Duque de Caxias\nVariáveis: CO, CO2, H2S, NO, NO2, O3, MP2.5, MP10, TEMP, PRECIP, RADIAÇÃO, VEL VENTO, DIR VENTO, UR\nTipo: Automática\nEmpresa: Lamce - COPPE - UFRJ"],

    'cor': ['ff0000ff', 'ff0000ff', 'ff0000ff', 'ff00ff00', 'ff00ff00', 'ff00ffff', 'ff00ffff', 'ff00ffff', 'ff00ffff', 'ff00ffff']
    # KML usa cores no formato AABBGGRR
})

# Criar objeto KML
kml = simplekml.Kml()

for _, row in data.iterrows():
    lat = row['latitude']
    lon = row['longitude']

    descricao_completa = f"""{row['descricao']}
Latitude: {lat}
Longitude: {lon}"""

    pnt = kml.newpoint(name=row['nome'],
                       coords=[(lon, lat)])
    pnt.description = descricao_completa
    pnt.style.iconstyle.color = row['cor']
    pnt.style.iconstyle.scale = 1.2
    pnt.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"

# Salva arquivo
kml.save("estacoes_baia.kml")
