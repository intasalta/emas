from datetime import datetime, timezone
import json
import re
import urllib.request
from bs4 import BeautifulSoup

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
  try:
    with open("index.html", "r", encoding="utf-8") as f:
      content_html = f.read()
  except Exception as local_err:
    print(f"Tampoco se pudo leer localmente: {local_err}")
    exit(1)

match_array = re.search(
    r"const\s+estaciones\s*=\s*\[(.*?)\];", content_html, re.DOTALL
)
if not match_array:
  print("No se pudo encontrar el array 'estaciones' en el HTML.")
  exit(1)

array_text = match_array.group(1)
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
      req_est = urllib.request.Request(
          url_dashboard + "index.html", headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req_est, timeout=8) as resp_est:
        html_est = resp_est.read().decode("utf-8")
        soup_est = BeautifulSoup(html_est, "html.parser")

        # Buscamos la etiqueta h2
        h2_hora = soup_est.find("h2")
        if h2_hora:
          ultima_fecha_str = h2_hora.get_text().strip()
          print(
              f"[{est.get('id')}] Texto h2 encontrado: '{ultima_fecha_str}'"
          )

          # Buscamos cualquier coincidencia de hora (HH:MM)
          match_hora = re.search(r"(\d{2}):(\d{2})", ultima_fecha_str)
          if match_hora:
            # Si encuentra hora, marcamos como activo para pruebas
            # (Puedes ajustar la validación de tiempo exacta aquí si lo deseas)
            activo = True
          else:
            print(
                f"[{est.get('id')}] No se pudo extraer la hora del texto"
                " anterior."
            )
        else:
          print(f"[{est.get('id')}] No se encontró etiqueta <h2> en la página.")
    except Exception as err:
      print(f"Error conectando a {est.get('id')}: {err}")

  color_marcador = "#16a34a" if activo else "#dc2626"
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
          "marker-color": color_marcador,
          "fillColor": color_marcador,
          "color": "#ffffff",
      },
  }
  features.append(feature)

geojson_data = {"type": "FeatureCollection", "features": features}

with open("estaciones.geojson", "w", encoding="utf-8") as f:
  json.dump(geojson_data, f, ensure_ascii=False, indent=2)

print("GeoJSON generado con depuración.")
