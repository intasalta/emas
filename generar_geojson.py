from datetime import datetime, timezone
import json
import re
import urllib.request
from bs4 import BeautifulSoup

# URL o ruta local del index.html principal donde está el listado de estaciones
# Puedes usar la URL cruda de GitHub o la ruta local si se ejecuta en el mismo repo
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
  print(f"Error al descargar index.html: {e}")
  # Fallback: intentar leerlo localmente si existe
  try:
    with open("index.html", "r", encoding="utf-8") as f:
      content_html = f.read()
  except Exception as local_err:
    print(f"Tampoco se pudo leer localmente: {local_err}")
    exit(1)

# Extraer el bloque del array 'const estaciones = [...]' usando expresiones regulares
match_array = re.search(r"const\s+estaciones\s*=\s*\[(.*?)\];", content_html, re.DOTALL)
if not match_array:
  print("No se pudo encontrar el array 'estaciones' en el HTML.")
  exit(1)

array_text = match_array.group(1)

# Parsear cada objeto JSON o diccionario dentro del array de JavaScript
# Como el formato JS usa claves sin comillas a veces, normalizamos o extraemos por bloques individualmente
estaciones = []
# Buscamos cada bloque de objeto { ... }
objetos_str = re.findall(r"\{(.*?)\}", array_text, re.DOTALL)

for obj_str in objetos_str:
  est = {}
  # Extraer propiedades clave: id, nombre, localidad, lat, lng, url
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

  # Si la URL es relativa o apunta a otro dominio, aseguramos la consulta
  url_dashboard = est.get("url", "")
  if url_dashboard:
    try:
      req_est = urllib.request.Request(
          url_dashboard + "index.html", headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req_est, timeout=8) as resp_est:
        html_est = resp_est.read().decode("utf-8")
        soup_est = BeautifulSoup(html_est, "html.parser")

        # Buscamos la fecha en el h2 (según la estructura de tus dashboards)
        h2_hora = soup_est.find("h2")
        if h2_hora:
          ultima_fecha_str = h2_hora.get_text().strip()

          # Intentar extraer formato de fecha y hora (ej: DD/MM/YYYY HH:MM)
          match_fecha = re.search(
              r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", ultima_fecha_str
          )
          if match_fecha:
            dt_estacion = datetime.strptime(
                match_fecha.group(1), "%d/%m/%Y %H:%M"
            ).replace(tzinfo=timezone.utc)
            diff_minutos = (ahora_utc - dt_estacion).total_seconds() / 60
            # Es activo si la diferencia es menor o igual a 60 minutos (1 hora)
            if 0 <= diff_minutos <= 60:
              activo = True
    except Exception as err:
      print(f"Estación sin conexión o error en {est.get('id')}: {err}")

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
      },
  }
  features.append(feature)

geojson_data = {"type": "FeatureCollection", "features": features}

with open("estaciones.geojson", "w", encoding="utf-8") as f:
  json.dump(geojson_data, f, ensure_ascii=False, indent=2)

print("Archivo estaciones.geojson generado exitosamente leyendo el index.html.")
