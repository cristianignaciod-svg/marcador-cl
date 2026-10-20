#!/usr/bin/env python3
"""Publica en Instagram (API oficial con Instagram Login) lo que está en historias/cola.json.

Necesita dos secretos en GitHub (Settings → Secrets and variables → Actions):
  IG_TOKEN    token de acceso de larga duración de la cuenta @marcador_cl
  IG_USER_ID  id de la cuenta de Instagram (lo muestra el panel de Meta al generar el token)
Si faltan, no hace nada (el resto del proceso sigue funcionando).

Variables opcionales (Settings → Variables): PUBLICAR_HISTORIAS / PUBLICAR_RESUMENES = "no" para pausar cada tipo.
"""
import datetime as dt
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ.get("IG_TOKEN", "").strip()
USER = os.environ.get("IG_USER_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "cristianignaciod-svg/marcador-cl")
SHA = os.environ.get("SHA", "main")
MAX_EDAD = dt.timedelta(hours=6)   # no publicar cosas atrasadas

LIGA_NOMBRE = {"esp.1": "LaLiga", "eng.1": "la Premier League", "chi.1": "la Liga de Primera",
               "chi.pb": "la Primera B", "uefa.champions": "la Champions League",
               "uefa.europa": "la Europa League", "conmebol.libertadores": "la Copa Libertadores",
               "conmebol.sudamericana": "la Copa Sudamericana"}
LIGA_TAGS = {"esp.1": ["#LaLiga", "#LaLigaEA", "#FutbolEspañol"],
             "eng.1": ["#PremierLeague", "#EPL", "#FutbolInglés"],
             "chi.1": ["#CampeonatoNacional", "#FutbolChileno", "#LigaDePrimera"],
             "chi.pb": ["#PrimeraB", "#FutbolChileno", "#AscensoChile"],
             "uefa.champions": ["#ChampionsLeague", "#UCL"],
             "uefa.europa": ["#EuropaLeague", "#UEL"],
             "conmebol.libertadores": ["#Libertadores", "#CopaLibertadores"],
             "conmebol.sudamericana": ["#Sudamericana", "#CopaSudamericana"]}
TAG_EQUIPO = {"Man. City": "#ManCity", "Man. United": "#ManUnited", "U. de Chile": "#UdeChile",
              "U. Católica": "#UC", "Universidad Católica": "#UC", "Colo-Colo": "#ColoColo",
              "Nottingham F.": "#NottinghamForest", "Santiago Wanderers": "#Wanderers",
              "S. Wanderers": "#Wanderers", "PSG": "#PSG", "Atlético": "#Atleti"}
CHILENOS = {"chi.1", "chi.pb"}


def api(metodo, ruta, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{ruta}"
    if metodo == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"{ex.code} {ex.read().decode()[:400]}")


def esperar(cid):
    for _ in range(20):
        st = api("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"contenedor {cid}: {st}")
        time.sleep(6)
    raise RuntimeError(f"contenedor {cid}: no terminó")


def url_jpg(ruta):
    return f"https://raw.githubusercontent.com/{REPO}/{SHA}/{ruta[:-4]}.jpg"


def tag(nombre):
    if nombre in TAG_EQUIPO:
        return TAG_EQUIPO[nombre]
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return "#" + "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)


def texto_resumen(item):
    liga = item["liga"]
    nombre = LIGA_NOMBRE.get(liga, liga)
    jug = [p for p in item["partidos"] if "gl" in p]
    rnd = random.Random(item["clave"])
    lineas = []
    if jug:
        dif = max(jug, key=lambda p: (abs(p["gl"] - p["gv"]), p["gl"] + p["gv"]))
        goles = max(jug, key=lambda p: (p["gl"] + p["gv"], abs(p["gl"] - p["gv"])))
        d = abs(dif["gl"] - dif["gv"])
        gan, per = (dif["local"], dif["visita"]) if dif["gl"] > dif["gv"] else (dif["visita"], dif["local"])
        mx, mn = max(dif["gl"], dif["gv"]), min(dif["gl"], dif["gv"])
        if d >= 3:
            lineas.append(rnd.choice([
                f"¡{gan} le metió {mx} a {per}! 🔥 El {mx}-{mn} fue el resultado más abultado de la fecha en {nombre}.",
                f"Goleada de {gan}: {mx}-{mn} a {per} 🔥 Lo más fuerte de la fecha en {nombre}.",
            ]))
        elif goles["gl"] + goles["gv"] >= 5:
            lineas.append(f"Partidazo en {nombre}: {goles['local']} {goles['gl']}-{goles['gv']} {goles['visita']} ⚽🔥")
        else:
            lineas.append(rnd.choice([f"Así quedó la fecha en {nombre} ⚽", f"Se cerró la fecha en {nombre} ⚽"]))
        otros = [p for p in sorted(jug, key=lambda p: -(p["gl"] + p["gv"] + abs(p["gl"] - p["gv"])))
                 if p is not dif and p is not goles][:3]
        frases = []
        for p in otros:
            if p["gl"] == p["gv"]:
                frases.append(f"{p['local']} y {p['visita']} empataron {p['gl']}-{p['gv']}")
            elif p["gl"] > p["gv"]:
                frases.append(f"{p['local']} le ganó {p['gl']}-{p['gv']} a {p['visita']}")
            else:
                frases.append(f"{p['visita']} ganó {p['gv']}-{p['gl']} de visita ante {p['local']}")
        if frases:
            lineas.append((", ".join(frases[:-1]) + " y " + frases[-1] if len(frases) > 1 else frases[0]) + ".")
    pend = [p for p in item["partidos"] if p.get("estado")]
    if pend:
        lineas.append("Quedó pendiente: " + ", ".join(f"{p['local']}–{p['visita']}" for p in pend) + ".")
    lineas.append(rnd.choice(["¿Cuál fue para ustedes el resultado de la fecha? 👇",
                              "¿Quién la rompió esta fecha? 👇", "¿Qué resultado no se esperaban? 👇"]))
    equipos = []
    for p in item["partidos"]:
        equipos += [p["local"], p["visita"]]
    tags = ["#MarcadorCL", "#Futbol"] + LIGA_TAGS.get(liga, [])
    for e in equipos:
        t = tag(e)
        if t not in tags and len(tags) < 5:
            tags.append(t)
    return "\n".join(lineas) + "\n\n" + " ".join(tags)


def publicar(item):
    archivos = item["archivos"]
    if item["tipo"] == "historia":
        ultimo = None
        for a in archivos:  # una o varias historias seguidas (ej. agenda de 2 páginas)
            c = api("POST", f"{USER}/media", image_url=url_jpg(a), media_type="STORIES")["id"]
            esperar(c)
            ultimo = api("POST", f"{USER}/media_publish", creation_id=c)["id"]
            time.sleep(3)
        return ultimo
    else:
        caption = item.get("texto") or texto_resumen(item)
        item["texto"] = caption
        if len(archivos) == 1:
            c = api("POST", f"{USER}/media", image_url=url_jpg(archivos[0]), caption=caption)["id"]
        else:
            hijos = [api("POST", f"{USER}/media", image_url=url_jpg(a), is_carousel_item="true")["id"]
                     for a in archivos]
            for h in hijos:
                esperar(h)
            c = api("POST", f"{USER}/media", media_type="CAROUSEL", children=",".join(hijos),
                    caption=caption)["id"]
    esperar(c)
    return api("POST", f"{USER}/media_publish", creation_id=c)["id"]


def verificar():
    """Comprueba la conexión (sin publicar) y deja el resultado en estado_instagram.json."""
    est = {}
    try:
        me = api("GET", "me", fields="user_id,username,account_type")
        est.update(ok=True, usuario=me.get("username"), tipo=me.get("account_type"),
                   id_coincide=str(me.get("user_id")) == USER or str(me.get("id")) == USER)
        lim = api("GET", f"{USER}/content_publishing_limit", fields="quota_usage,config")
        est["cupo"] = lim.get("data", [{}])[0]
    except Exception as ex:
        est.update(ok=False, error=str(ex)[:300])
    json.dump(est, open(os.path.join(BASE, "estado_instagram.json"), "w"), ensure_ascii=False, indent=1)
    print("Conexión Instagram:", est)


def main():
    if not TOKEN or not USER:
        print("Sin IG_TOKEN / IG_USER_ID: no se publica nada.")
        return
    if os.environ.get("SOLO_VERIFICAR") or os.path.exists(os.path.join(BASE, "verificar_ahora")):
        verificar()
        return
    p0 = os.path.join(BASE, "cola.json")
    if not any(not x.get("enviado") for x in json.load(open(p0))):
        print("Nada pendiente: no se consulta la API.")
        return
    verificar()
    try:
        conf = json.load(open(os.path.join(BASE, "config.json")))
    except Exception:
        conf = {}
    activar = {"historia": bool(conf.get("publicar_historias")) and os.environ.get("PUBLICAR_HISTORIAS") != "no",
               "resumen": bool(conf.get("publicar_resumenes")) and os.environ.get("PUBLICAR_RESUMENES") != "no"}
    p = os.path.join(BASE, "cola.json")
    cola = json.load(open(p))
    ahora = dt.datetime.now(dt.timezone.utc)
    hechos = 0
    for item in cola:
        if item.get("enviado") or not activar.get(item["tipo"], False):
            continue
        creado = dt.datetime.fromisoformat(item["creado"])
        if item["tipo"] == "resumen":
            # los resúmenes solo salen con aprobación del usuario ("aprobado": true en cola.json)
            if ahora - creado > dt.timedelta(hours=48):
                item["enviado"] = "vencido"
                continue
            if item.get("aprobado") is not True:
                continue
        elif ahora - creado > MAX_EDAD:
            item["enviado"] = "vencido"
            continue
        try:
            item["ig_id"] = publicar(item)
            item["enviado"] = True
            item["publicado"] = ahora.isoformat(timespec="seconds")
            hechos += 1
            print("Publicado:", item["titulo"])
        except Exception as ex:
            item["error"] = str(ex)[:300]
            item["intentos"] = item.get("intentos", 0) + 1
            if item["intentos"] >= 3:
                item["enviado"] = "error"
            print("Error con", item["titulo"], ex, file=sys.stderr)
        json.dump(cola, open(p, "w"), ensure_ascii=False, indent=1)
        time.sleep(5)
    print(f"{hechos} publicaciones en Instagram")


if __name__ == "__main__":
    main()
