#!/usr/bin/env python3
"""Busca partidos terminados y fechas completas, y deja la lista para render.py.

Lo ejecuta GitHub Actions cada 15 minutos (.github/workflows/historias.yml).
Consulta ESPN directamente (sin caché intermedia) y FotMob para la Primera B.

Escribe:
  historias/pendientes.json  -> lo que hay que dibujar ahora (entrada de render.py)
  historias/cola.json        -> lo listo para enviar a Metricool (lo consume la tarea de Claude)
  historias/publicados.json  -> claves ya procesadas (para no repetir)
  historias/resumenes.json   -> fechas completas ya procesadas
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import urllib.request
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
CL = ZoneInfo("America/Santiago")
ESPN = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/"
LIGAS = ["chi.1", "esp.1", "eng.1", "uefa.champions", "uefa.europa",
         "conmebol.libertadores", "conmebol.sudamericana"]
UA = {"User-Agent": "Mozilla/5.0 (MarcadorCL)", "Accept": "application/json"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
CORTOS = {  # nombres cortos en español
    "Manchester City": "Man. City", "Manchester United": "Man. United",
    "Tottenham Hotspur": "Tottenham", "Nottingham Forest": "Nottingham F.",
    "Brighton & Hove Albion": "Brighton", "Wolverhampton Wanderers": "Wolves",
    "Atlético Madrid": "Atlético", "Atlético de Madrid": "Atlético", "Athletic Club": "Athletic",
    "Universidad de Chile": "U. de Chile", "Universidad Católica": "U. Católica",
    "Paris Saint-Germain": "PSG", "Bayern Munich": "Bayern", "Bayern Múnich": "Bayern",
    "Newcastle United": "Newcastle", "AFC Bournemouth": "Bournemouth", "Leeds United": "Leeds",
    "Ipswich Town": "Ipswich", "Coventry City": "Coventry", "West Ham United": "West Ham",
    "Celta Vigo": "Celta", "Deportivo La Coruña": "Deportivo", "Sevilla FC": "Sevilla",
    "Racing Santander": "Racing", "Rayo Vallecano": "Rayo", "Real Betis": "Betis",
}
TERMINADO = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN",
             "STATUS_END_OF_EXTRATIME", "STATUS_FINAL_AGT"}
NO_SE_JUEGA = {"STATUS_POSTPONED": "Post.", "STATUS_CANCELED": "Canc.", "STATUS_SUSPENDED": "Susp.",
               "STATUS_ABANDONED": "Susp.", "STATUS_DELAYED": "Post."}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def cargar(n, defecto):
    p = os.path.join(BASE, n)
    try:
        return json.load(open(p))
    except Exception:
        return defecto


def guardar(n, v):
    json.dump(v, open(os.path.join(BASE, n), "w"), ensure_ascii=False, indent=1)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def nombre(team):
    n = team.get("displayName") or team.get("shortDisplayName") or team.get("name", "")
    return CORTOS.get(n, n)


def hora_cl(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(CL)


def scoreboard(liga, dia):
    try:
        return get(f"{ESPN}{liga}/scoreboard?dates={dia:%Y%m%d}&lang=es&region=cl")
    except Exception as ex:
        print("ESPN falla", liga, dia, ex, file=sys.stderr)
        return {}


def fase_de(data, ev):
    comp = ev["competitions"][0]
    for n in comp.get("notes", []) + ev.get("notes", []):
        if n.get("headline"):
            return n["headline"]
    w = (data.get("week") or ev.get("week") or {}).get("number")
    return f"Fecha {w}" if w else ""


def detalle(liga, ev):
    comp = ev["competitions"][0]
    lados = {c["team"]["id"]: c["homeAway"] for c in comp["competitors"]}
    lado = lambda tid: "local" if lados.get(str(tid)) == "home" else "visita"
    goles, tarjetas, anulados = [], [], []
    for d in comp.get("details", []):
        quien = (d.get("athletesInvolved") or [{}])[0].get("displayName", "")
        minuto = re.sub(r"'\+", "+", (d.get("clock") or {}).get("displayValue", ""))
        tid = (d.get("team") or {}).get("id")
        if d.get("scoringPlay"):
            goles.append({"min": minuto, "jugador": quien, "lado": lado(tid),
                          "penal": bool(d.get("penaltyKick")), "autogol": bool(d.get("ownGoal"))})
        elif d.get("redCard"):
            txt = ((d.get("type") or {}).get("text", "")).lower()
            doble = bool(re.search(r"segunda|second|doble|yellow.?red", txt))
            tarjetas.append({"min": minuto, "jugador": quien, "lado": lado(tid), "tipo": "doble" if doble else "roja"})
        elif d.get("yellowCard"):
            tarjetas.append({"min": minuto, "jugador": quien, "lado": lado(tid), "tipo": "amarilla"})
    # segunda amarilla (solo si ESPN la marca así): no repetir esa amarilla
    for t in tarjetas:
        if t["tipo"] == "doble":
            prev = [x for x in tarjetas if x["tipo"] == "amarilla" and x["jugador"] == t["jugador"]]
            if prev:
                t["tipo"] = "doble"
                for x in prev:
                    tarjetas.remove(x)
    # goles anulados por VAR (si ESPN los informa en los eventos clave)
    try:
        s = get(f"{ESPN}{liga}/summary?event={ev['id']}&lang=es&region=cl")
        for k in s.get("keyEvents", []):
            txt = ((k.get("type") or {}).get("text", "") + " " + k.get("text", "")).lower()
            if "var" in txt and re.search(r"anula|disallow|no gol|cancel", txt):
                part = (k.get("participants") or [{}])[0].get("athlete", {}).get("displayName", "")
                motivo = "fuera de juego" if re.search(r"fuera de juego|offside", txt) else (
                    "mano" if re.search(r"mano|handball", txt) else (
                        "falta" if re.search(r"falta|foul", txt) else ""))
                anulados.append({"min": (k.get("clock") or {}).get("displayValue", ""), "jugador": part,
                                 "lado": lado((k.get("team") or {}).get("id")), "motivo": motivo})
    except Exception as ex:
        print("summary falla", ev["id"], ex, file=sys.stderr)
    return goles, tarjetas, [a for a in anulados if a["jugador"]]


def primera_b(dias):
    """Primera B desde FotMob (solo marcador). Devuelve lista de partidos terminados."""
    out = []
    for d in dias:
        try:
            data = get(f"https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}&timezone=America/Santiago&ccode3=CHL")
        except Exception as ex:
            print("FotMob falla", d, ex, file=sys.stderr)
            continue
        for lg in data.get("leagues", []):
            if lg.get("primaryId") != 9126:
                continue
            for m in lg.get("matches", []):
                st = m.get("status", {})
                if not st.get("finished") or st.get("cancelled"):
                    continue
                gl, gv = m["home"].get("score"), m["away"].get("score")
                if gl is None or gv is None:
                    continue
                inicio = hora_cl(st.get("utcTime") or m.get("time"))
                out.append({"id": f"fm{m['id']}", "local": m["home"]["name"], "visita": m["away"]["name"],
                            "gl": int(gl), "gv": int(gv), "inicio": inicio, "fase": ""})
    return out


def main():
    ahora = dt.datetime.now(CL)
    hoy = ahora.date()
    publicados = set(cargar("publicados.json", []))
    resumenes = set(cargar("resumenes.json", []))
    cola = cargar("cola.json", [])
    pendientes = []

    for liga in LIGAS:
        # ventana para detectar fechas completas: 5 días atrás a 3 adelante
        eventos, datas = {}, {}
        for k in range(-5, 4):
            data = scoreboard(liga, hoy + dt.timedelta(days=k))
            for ev in data.get("events", []):
                eventos[ev["id"]] = ev
                datas[ev["id"]] = data
        if not eventos:
            continue
        lista = sorted(eventos.values(), key=lambda e: e["date"])

        # A) historias: terminados de hoy o ayer (hora Chile)
        for ev in lista:
            st = ev["status"]["type"]
            if st.get("name") not in TERMINADO and not (st.get("completed") and st.get("state") == "post"):
                continue
            inicio = hora_cl(ev["date"])
            if ahora - inicio > dt.timedelta(hours=8):
                continue  # solo partidos recientes (no publicar atrasados)
            clave = f"{liga}:{ev['id']}"
            if clave in publicados:
                continue
            comp = ev["competitions"][0]
            loc = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            vis = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            goles, tarjetas, anulados = detalle(liga, ev)
            p = {"id": f"{liga.replace('.', '')}-{slug(nombre(loc['team']))}-{slug(nombre(vis['team']))}",
                 "liga": liga, "fase": fase_de(datas[ev["id"]], ev), "fecha": inicio.date().isoformat(),
                 "local": nombre(loc["team"]), "visita": nombre(vis["team"]),
                 "gl": int(loc.get("score", 0)), "gv": int(vis.get("score", 0)),
                 "goles": goles, "tarjetas": tarjetas, "anulados": anulados}
            pendientes.append(p)
            publicados.add(clave)
            cola.append({"tipo": "historia", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                         "archivos": [f"historias/img/{p['fecha']}/{p['id']}.png"],
                         "titulo": f"{p['local']} {p['gl']}–{p['gv']} {p['visita']}", "liga": liga, "enviado": False})

        # B) resumen: agrupar en fechas (bloques de días seguidos, cortando con 2+ días sin partidos)
        bloques, actual, ult = [], [], None
        for ev in lista:
            d = hora_cl(ev["date"]).date()
            if ult and (d - ult).days >= 2:
                bloques.append(actual)
                actual = []
            actual.append(ev)
            ult = d
        if actual:
            bloques.append(actual)
        for b in bloques:
            estados = [e["status"]["type"].get("name") for e in b]
            jugados = [e for e, s in zip(b, estados) if s in TERMINADO or e["status"]["type"].get("completed")]
            if not jugados or len(jugados) < 2:
                continue
            if not all(s in TERMINADO or s in NO_SE_JUEGA or e["status"]["type"].get("completed")
                       for e, s in zip(b, estados)):
                continue
            fin = max(hora_cl(e["date"]).date() for e in jugados)
            if (hoy - fin).days > 1:
                continue  # fecha vieja: no publicar tarde
            ini = min(hora_cl(e["date"]).date() for e in b)
            clave = f"{liga}:{ini.isoformat()}"
            if clave in resumenes:
                continue
            filas = []
            for e in b:
                c = e["competitions"][0]
                lo = next(x for x in c["competitors"] if x["homeAway"] == "home")
                vi = next(x for x in c["competitors"] if x["homeAway"] == "away")
                h = hora_cl(e["date"])
                f = {"dia": f"{DIAS[h.weekday()]} {h.day}", "local": nombre(lo["team"]), "visita": nombre(vi["team"])}
                s = e["status"]["type"].get("name")
                if s in NO_SE_JUEGA and not e["status"]["type"].get("completed"):
                    f["estado"] = NO_SE_JUEGA[s]
                else:
                    f["gl"], f["gv"] = int(lo.get("score", 0)), int(vi.get("score", 0))
                filas.append(f)
            fase = fase_de(datas[b[0]["id"]], b[0])
            rango = (f"{ini.day} al {fin.day} de {MESES[fin.month - 1]}" if ini.month == fin.month
                     else f"{ini.day} de {MESES[ini.month - 1]} al {fin.day} de {MESES[fin.month - 1]}")
            if ini == fin:
                rango = f"{fin.day} de {MESES[fin.month - 1]}"
            rid = f"{liga.replace('.', '')}-{ini:%Y%m%d}"
            r = {"tipo": "resumen", "id": rid, "liga": liga, "fase": fase, "fecha": fin.isoformat(),
                 "rango": rango, "partidos": filas}
            pendientes.append(r)
            resumenes.add(clave)
            n = (len(filas) + 9) // 10
            cola.append({"tipo": "resumen", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                         "archivos": [f"historias/img/{fin.isoformat()}/{rid}-{i + 1}.png" for i in range(n)],
                         "titulo": f"{liga} {fase or rango}".strip(), "liga": liga, "fase": fase, "rango": rango,
                         "partidos": filas, "enviado": False})

    # Primera B (FotMob): historias solo con marcador; resumen cuando no queden partidos del fin de semana
    pb = primera_b([hoy - dt.timedelta(days=1), hoy])
    for m in pb:
        clave = f"chi.pb:{m['id']}"
        if clave in publicados or ahora - m["inicio"] > dt.timedelta(hours=8):
            continue
        p = {"id": f"chipb-{slug(m['local'])}-{slug(m['visita'])}", "liga": "chi.pb", "fase": "",
             "fecha": m["inicio"].date().isoformat(), "local": m["local"], "visita": m["visita"],
             "gl": m["gl"], "gv": m["gv"], "goles": []}
        pendientes.append(p)
        publicados.add(clave)
        cola.append({"tipo": "historia", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                     "archivos": [f"historias/img/{p['fecha']}/{p['id']}.png"],
                     "titulo": f"{p['local']} {p['gl']}–{p['gv']} {p['visita']}", "liga": "chi.pb",
                     "sin_goleadores": True, "enviado": False})

    cola = cola[-300:]
    guardar("pendientes.json", pendientes)
    guardar("cola.json", cola)
    guardar("publicados.json", sorted(publicados)[-3000:])
    guardar("resumenes.json", sorted(resumenes)[-500:])
    print(f"{len(pendientes)} imágenes por generar")


if __name__ == "__main__":
    main()
