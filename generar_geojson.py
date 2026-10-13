from datetime import datetime, timezone
import json
import re
import urllib.request
from bs4 import BeautifulSoup

# URL del index.html principal de tu repositorio donde está el array de estaciones
INDEX_URL = (
    "https://raw.githubusercontent.com/intasalta/emas/main/index.html"
)

print(f"Descargando el listado desde: {INDEX_URL}")
try:
  req = urllib.request.Request(
      INDEX_URL, headers={"User-Agent": "Mozilla/5.0"}
  )
  with urllib.request.urlopen(req, timeout=10) as response:
    content_html = response.read().decode("utf-8")
except Exception as e:
  print(f"Error al descargar index.html de GitHub: {e}")
  # Fallback: intentar leerlo localmente si se ejecuta dentro del mismo repo
  try:
    with open("index.html", "r", encoding="utf-8") as f:
      content_html = f.read()
  except Exception as local_err:
    print(f"Tampoco se pudo leer el archivo localmente: {local_err}")
    exit(1)

# Extraer el bloque del array 'const estaciones = [...]' usando expresiones regulares
match_array = re.search(
    r"const\s+estaciones\s*=\s*\[(.*?)\];", content_html, re.DOTALL
)
if not match_array:
  print("No se pudo encontrar el array 'estaciones' en el HTML.")
  exit(1)

array_text = match_array.group(1)

# Parsear las estaciones individuales dentro del array de JavaScript
estaciones = []
objetos_str = re.findall(r"\{(.*?)\}", array_text, re.DOTALL)

for obj_str in objetos_str:
  est = {}
  for key in ["id", "nombre", "localidad", "url"]:
    m = re.search(rf"{key}\s*:\s*['\"'](.*?)['\"']", obj_str)
    if m:
      est[key] = m.group(1)

  for key in ["lat", "lng"]:
    m = re.search(rf"{key}\s*:\s*([-\d.]+)", obj_str)
    if m:
      est[key] = float(m.group(1))

  if "id" in est and "lat" in est and "lng" in est:
    estaciones.append(est)

print(f"Se encontraron {len(estaciones)} estaciones en el código.")

features = []
ahora_utc = datetime.now(timezone.utc)

for est in estaciones:
  ultima_fecha_str = "Sin registro"
  activo = False

  url_dashboard = est.get("url", "")
  if url_dashboard:
    try:
      # Petición al dashboard de cada estación
      req_est = urllib.request.Request(
          url_dashboard + "index.html", headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req_est, timeout=8) as resp_est:
        html_est = resp_est.read().decode("utf-8")
        soup_est = BeautifulSoup(html_est, "html.parser")

        # Buscar la fecha de última actualización en el elemento h2
        # Buscar la fecha de última actualización de forma más flexible en el h2
        h2_hora = soup_est.find('h2')
        if h2_hora:
          ultima_fecha_str = h2_hora.get_text().strip()

          # Buscar cualquier patrón de hora de 24 horas (ej: 14:30 o 08:15) en el texto del h2
          match_hora = re.search(r'(\d{2}):(\d{2})', ultima_fecha_str)
          
          if match_hora:
            # Si encontrarmos una hora en el h2 del día de hoy, asumimos que está activo
            # O podemos comparar con la hora actual de Argentina (UTC-3)
            hora_est = int(match_hora.group(1))
            min_est = int(match_hora.group(2))
            
            # Hora actual en Argentina
            ahora_arg = datetime.now(timezone(timedelta(hours=-3)))
            
            # Verificamos si la hora de la estación pertenece al día de hoy y está dentro de la última hora y media
            if ahora_arg.hour == hora_est and abs(ahora_arg.minute - min_est) <= 90:
              activo = True
            elif abs(ahora_arg.hour - hora_est) == 1 and ahora_arg.minute + (60 - min_est) <= 90:
              activo = True
    except Exception as err:
      print(f"Estación sin conexión o error en {est.get('id')}: {err}")

  # Definir color y simbología directamente en los atributos para el visor (Argenmap / Leaflet)
  color_marcador = (
      "#16a34a" if activo else "#dc2626"
  )  # Verde si activo, Rojo si inactivo
  estado_texto = "Activa" if activo else "Sin conexión"

  feature = {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [est["lng"], est["lat"]]},
      "properties": {
          "id": est.get("id"),
          "nombre": est.get("nombre"),
          "localidad": est.get("localidad"),
          "lat": est.get("lat"),
          "lng": est.get("lng"),
          "url": url_dashboard,
          "ultima_fecha": ultima_fecha_str,
          "activo": activo,
          "estado_texto": estado_texto,
          # Propiedades de estilo integradas para visores web
          "marker-color": color_marcador,
          "fillColor": color_marcador,
          "color": "#ffffff",  # Borde blanco
      },
  }
  features.append(feature)

geojson_data = {"type": "FeatureCollection", "features": features}

# Guardar el archivo GeoJSON resultante
with open("estaciones.geojson", "w", encoding="utf-8") as f:
  json.dump(geojson_data, f, ensure_ascii=False, indent=2)

print(
    "Archivo estaciones.geojson generado exitosamente con la simbología"
    " incluida."
)
