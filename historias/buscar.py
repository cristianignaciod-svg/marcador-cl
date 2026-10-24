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
LIGAS_PRINCIPALES = ["chi.1", "esp.1", "eng.1", "uefa.champions", "uefa.europa",
                     "conmebol.libertadores", "conmebol.sudamericana"]
# Solo historias por partido (sin resumen de fecha ni agenda de la mañana)
SOLO_HISTORIAS = ["ger.1", "ita.1", "fra.1", "arg.1"]
LIGAS = LIGAS_PRINCIPALES + SOLO_HISTORIAS
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
    "Borussia Mönchengladbach": "M'gladbach", "Bayer Leverkusen": "Leverkusen", "Eintracht Frankfurt": "Eintracht",
    "Internazionale": "Inter", "AC Milan": "Milan", "Olympique de Marseille": "Marsella", "Olympique Lyonnais": "Lyon",
}
TERMINADO = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN",
             "STATUS_END_OF_EXTRATIME", "STATUS_FINAL_AGT"}
NO_SE_JUEGA = {"STATUS_POSTPONED": "Post.", "STATUS_CANCELED": "Canc.", "STATUS_SUSPENDED": "Susp.",
               "STATUS_ABANDONED": "Susp.", "STATUS_DELAYED": "Post."}


DIAG = {"errores": [], "eventos": {}}


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
        DIAG["errores"].append(f"ESPN {liga} {dia}: {str(ex)[:120]}")
        return {}


def fase_de(data, ev):
    comp = ev["competitions"][0]
    for n in comp.get("notes", []) + ev.get("notes", []):
        if n.get("headline"):
            # "Juego de Vuelta - Empatados en el global - ..." -> "Vuelta" (el resto va aparte)
            h = n["headline"].split(" - ")[0].strip()
            h = re.sub(r"(?i)^juego de ", "", h)
            return h[:40]
    w = (data.get("week") or ev.get("week") or {}).get("number")
    return f"Fecha {w}" if w else ""


def serie(ev, loc, vis):
    """Penales de definición, marcador global y quién clasifica (solo si aplica)."""
    out = {}
    def num(c, k):
        v = c.get(k)
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None
    pl, pv = num(loc, "shootoutScore"), num(vis, "shootoutScore")
    al, av = num(loc, "aggregateScore"), num(vis, "aggregateScore")
    nl, nv = nombre(loc["team"]), nombre(vis["team"])
    if pl is not None and pv is not None and (pl or pv):
        out["penales"] = [pl, pv]
        out["clasifica"] = nl if pl > pv else nv
    if al is not None and av is not None:
        out["global"] = [al, av]
        if "clasifica" not in out and al != av:
            notas = " ".join(n.get("headline", "") for n in ev["competitions"][0].get("notes", [])).lower()
            if "vuelta" in notas or "2nd leg" in notas or "second leg" in notas:
                out["clasifica"] = nl if al > av else nv
    return out


def detalle(liga, ev):
    comp = ev["competitions"][0]
    lados = {c["team"]["id"]: c["homeAway"] for c in comp["competitors"]}
    lado = lambda tid: "local" if lados.get(str(tid)) == "home" else "visita"
    goles, tarjetas, anulados = [], [], []
    for d in comp.get("details", []):
        quien = (d.get("athletesInvolved") or [{}])[0].get("displayName", "")
        minuto = re.sub(r"'\+", "+", (d.get("clock") or {}).get("displayValue", ""))
        tid = (d.get("team") or {}).get("id")
        if d.get("shootout"):
            continue  # tanda de penales: va aparte, no como goles del partido
        if d.get("scoringPlay"):
            goles.append({"min": minuto, "jugador": quien, "lado": lado(tid),
                          "penal": bool(d.get("penaltyKick")), "autogol": bool(d.get("ownGoal"))})
        elif d.get("redCard"):
            txt = ((d.get("type") or {}).get("text", "")).lower()
            doble = bool(re.search(r"segunda|second|doble|yellow.?red", txt))
            tarjetas.append({"min": minuto, "jugador": quien, "lado": lado(tid), "tipo": "doble" if doble else "roja",
                             "directa": bool(re.search(r"directa|straight", txt))})
        elif d.get("yellowCard"):
            tarjetas.append({"min": minuto, "jugador": quien, "lado": lado(tid), "tipo": "amarilla"})
    # roja de alguien que ya tenía amarilla = segunda amarilla (lo normal), salvo que ESPN diga "directa"
    for t in tarjetas:
        if t["tipo"] == "roja" and t["jugador"] and not t.get("directa"):
            if any(x["tipo"] == "amarilla" and x["jugador"] == t["jugador"] for x in tarjetas):
                t["tipo"] = "doble"
    # segunda amarilla: no repetir esa amarilla
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
        # tarjetas sin nombre en el marcador: buscar el nombre en los eventos clave del resumen
        sin_nombre = [t for t in tarjetas if not t["jugador"]]
        if sin_nombre:
            claves = []
            for k in s.get("keyEvents", []):
                txt = ((k.get("type") or {}).get("text", "") + " " + (k.get("text") or ""))
                if not re.search(r"(?i)amarilla|roja|yellow|red card|tarjeta", txt):
                    continue
                mn = re.sub(r"'\+", "+", (k.get("clock") or {}).get("displayValue", ""))
                part = (k.get("participants") or [{}])[0].get("athlete", {}).get("displayName", "")
                if not part:
                    m = re.search(r"(?:para|a|to|booked:?)\s+([A-ZÁÉÍÓÚÑ][^()]{2,40}?)\s*\(", k.get("text") or "")
                    part = m.group(1).strip() if m else ""
                tecnico = bool(re.search(r"(?i)entrenador|t[eé]cnico|manager|coach|asistente|banco", txt))
                claves.append((mn, lado((k.get("team") or {}).get("id")), part, tecnico))
            usados = {(x["min"], x["lado"], x["jugador"]) for x in tarjetas if x["jugador"]}
            for t in sin_nombre:
                for mn, ld, part, tecnico in claves:
                    if mn != t["min"] or ld != t["lado"]:
                        continue
                    if part and (mn, ld, part) in usados:
                        continue  # ese nombre ya tiene su tarjeta: no repetirlo
                    if part or tecnico:
                        t["jugador"] = part or "Cuerpo técnico"
                        usados.add((mn, ld, t["jugador"]))
                        break
    except Exception as ex:
        print("summary falla", ev["id"], ex, file=sys.stderr)
    # si aun así no hay nombre (suele ser alguien del banco), no se muestra la tarjeta
    tarjetas = [t for t in tarjetas if t["jugador"]]
    vistos, unicas = set(), []
    for t in tarjetas:
        k = (t["min"], t["jugador"], t["lado"], t["tipo"])
        if k not in vistos:
            vistos.add(k)
            unicas.append({x: t[x] for x in ("min", "jugador", "lado", "tipo")})
    tarjetas = unicas
    return goles, tarjetas, [a for a in anulados if a["jugador"]]


def fotmob_detalle(mid):
    """Goles, tarjetas y anulados por VAR desde FotMob (matchDetails)."""
    data = get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}")
    evs = (((data.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    goles, tarjetas, anulados = [], [], []
    for e in evs:
        t = e.get("type")
        lado = "local" if e.get("isHome") else "visita"
        quien = (e.get("player") or {}).get("name") or e.get("nameStr") or e.get("fullName") or ""
        base = e.get("time")
        extra = e.get("overloadTime")
        minuto = f"{base}+{extra}'" if extra else f"{base}'"
        if e.get("isPenaltyShootoutEvent"):
            continue
        txt = json.dumps(e, ensure_ascii=False).lower()
        if t == "Goal":
            if re.search(r"cancel|disallow|anulad", txt):
                anulados.append({"min": minuto, "jugador": quien, "lado": lado, "motivo": ""})
                continue
            desc = str(e.get("goalDescription") or "").lower()
            goles.append({"min": minuto, "jugador": quien, "lado": lado,
                          "penal": "penal" in desc or "penalty" in desc, "autogol": bool(e.get("ownGoal"))})
        elif t == "Card":
            c = str(e.get("card") or "").lower()
            tipo = "doble" if "yellowred" in c else ("roja" if "red" in c else "amarilla")
            tarjetas.append({"min": minuto, "jugador": quien, "lado": lado, "tipo": tipo})
        elif t == "VAR" and re.search(r"goal.?cancel|disallow|anulad|no.?goal", txt):
            anulados.append({"min": minuto, "jugador": quien, "lado": lado, "motivo": ""})
    for t in [x for x in tarjetas if x["tipo"] == "doble"]:
        for x in [y for y in tarjetas if y["tipo"] == "amarilla" and y["jugador"] == t["jugador"]]:
            tarjetas.remove(x)
    return goles, tarjetas, anulados, data


def primera_b_resumen(hoy, ahora, resumenes, pendientes, cola):
    """Resumen de fecha de la Primera B (FotMob): bloque de días seguidos con todos los partidos terminados."""
    partidos = []
    for k in range(-5, 4):
        d = hoy + dt.timedelta(days=k)
        try:
            data = get(f"https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}&timezone=America/Santiago&ccode3=CHL")
        except Exception as ex:
            print("FotMob falla", d, ex, file=sys.stderr)
            return
        for lg in data.get("leagues", []):
            if lg.get("primaryId") != 9126:
                continue
            for m in lg.get("matches", []):
                st = m.get("status", {})
                partidos.append({"id": m["id"], "inicio": hora_cl(st.get("utcTime") or m.get("time")),
                                 "local": m["home"]["name"], "visita": m["away"]["name"],
                                 "gl": m["home"].get("score"), "gv": m["away"].get("score"),
                                 "fin": bool(st.get("finished")), "canc": bool(st.get("cancelled"))})
    partidos.sort(key=lambda m: m["inicio"])
    bloques, actual, ult = [], [], None
    for m in partidos:
        d = m["inicio"].date()
        if ult and (d - ult).days >= 2:
            bloques.append(actual)
            actual = []
        actual.append(m)
        ult = d
    if actual:
        bloques.append(actual)
    for b in bloques:
        jugados = [m for m in b if m["fin"] and not m["canc"]]
        if len(jugados) < 2 or not all(m["fin"] or m["canc"] for m in b):
            continue
        ini, fin = b[0]["inicio"].date(), max(m["inicio"].date() for m in jugados)
        if (hoy - fin).days > 1:
            continue
        clave = f"chi.pb:{ini.isoformat()}"
        if clave in resumenes:
            continue
        fase = ""
        try:
            raw = get(f"https://www.fotmob.com/api/data/matchDetails?matchId={jugados[-1]['id']}")
            rnd = (raw.get("general") or {}).get("matchRound")
            fase = f"Fecha {rnd}" if rnd else ""
        except Exception:
            pass
        if fase and f"chi.pb:{fase.lower().replace(' ', '-')}" in resumenes:
            resumenes.add(clave)
            continue
        filas = []
        for m in b:
            f = {"dia": f"{DIAS[m['inicio'].weekday()]} {m['inicio'].day}", "local": m["local"], "visita": m["visita"]}
            if m["canc"] or not m["fin"]:
                f["estado"] = "Susp."
            else:
                f["gl"], f["gv"] = int(m["gl"]), int(m["gv"])
            filas.append(f)
        rango = (f"{ini.day} al {fin.day} de {MESES[fin.month - 1]}" if ini.month == fin.month
                 else f"{ini.day} de {MESES[ini.month - 1]} al {fin.day} de {MESES[fin.month - 1]}")
        rid = f"chipb-{ini:%Y%m%d}"
        pendientes.append({"tipo": "resumen", "id": rid, "liga": "chi.pb", "fase": fase, "fecha": fin.isoformat(),
                           "rango": rango, "partidos": filas})
        resumenes.add(clave)
        cola.append({"tipo": "resumen", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                     "archivos": [f"historias/img/{fin.isoformat()}/{rid}-1.png"],
                     "titulo": f"Primera B {fase or rango}", "liga": "chi.pb", "fase": fase, "rango": rango,
                     "partidos": filas, "enviado": False})


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


TV_DEFECTO = {"chi.1": "TNT Sports Premium · HBO Max", "chi.pb": "TNT Sports · HBO Max",
              "esp.1": "DSports o ESPN", "eng.1": "ESPN · Disney+ Premium",
              "uefa.champions": "ESPN · Disney+ Premium", "uefa.europa": "ESPN · Disney+ Premium",
              "conmebol.libertadores": "ESPN · Disney+ Premium", "conmebol.sudamericana": "ESPN · Disney+ Premium · DSports"}
ORDEN_AGENDA = ["chi.1", "chi.pb", "conmebol.libertadores", "conmebol.sudamericana",
                "uefa.champions", "uefa.europa", "esp.1", "eng.1"]


def _parecido(a, b):
    a, b = slug(a), slug(b)
    return bool(a and b) and (a in b or b in a or a.split("-")[0] == b.split("-")[0])


def agenda_del_dia(ahora, publicados, pendientes, cola):
    """Historia de la mañana 'Hoy se juega' con hora de Chile y canal.
    Sale entre 09:20 y 12:00; espera hasta las 10:15 a que exista canales_hoy.json de hoy."""
    hoy = ahora.date()
    clave = f"agenda:{hoy.isoformat()}"
    if clave in publicados or not (dt.time(9, 20) <= ahora.time() <= dt.time(12, 0)):
        return
    canales = cargar("canales_hoy.json", {})
    if canales.get("fecha") != hoy.isoformat() and ahora.time() < dt.time(10, 15):
        return
    tv_hoy = canales.get("partidos", []) if canales.get("fecha") == hoy.isoformat() else []

    def canal(liga, loc, vis):
        for c in tv_hoy:
            if _parecido(c.get("local", ""), loc) and _parecido(c.get("visita", ""), vis):
                return c.get("tv") or TV_DEFECTO.get(liga, "")
        return TV_DEFECTO.get(liga, "")

    grupos = {}
    for liga in LIGAS_PRINCIPALES:
        vistos = set()
        for k in (0, 1):
            for ev in scoreboard(liga, hoy + dt.timedelta(days=k)).get("events", []):
                h = hora_cl(ev["date"])
                if h.date() != hoy or ev["id"] in vistos:
                    continue
                if ev["status"]["type"].get("name") in NO_SE_JUEGA:
                    continue
                vistos.add(ev["id"])
                c = ev["competitions"][0]
                lo = nombre(next(x for x in c["competitors"] if x["homeAway"] == "home")["team"])
                vi = nombre(next(x for x in c["competitors"] if x["homeAway"] == "away")["team"])
                grupos.setdefault(liga, []).append({"h": h, "hora": f"{h:%H:%M}", "local": lo, "visita": vi,
                                                    "tv": canal(liga, lo, vi)})
    try:
        data = get(f"https://www.fotmob.com/api/data/matches?date={hoy:%Y%m%d}&timezone=America/Santiago&ccode3=CHL")
        for lg in data.get("leagues", []):
            if lg.get("primaryId") != 9126:
                continue
            for m in lg.get("matches", []):
                st = m.get("status", {})
                if st.get("cancelled"):
                    continue
                h = hora_cl(st.get("utcTime") or m.get("time"))
                if h.date() != hoy:
                    continue
                lo, vi = m["home"]["name"], m["away"]["name"]
                grupos.setdefault("chi.pb", []).append({"h": h, "hora": f"{h:%H:%M}", "local": lo, "visita": vi,
                                                        "tv": canal("chi.pb", lo, vi)})
    except Exception as ex:
        print("FotMob agenda falla", ex, file=sys.stderr)
    if not grupos:
        publicados.add(clave)
        return
    gr = []
    for liga in ORDEN_AGENDA:
        if liga in grupos:
            ps = sorted(grupos[liga], key=lambda m: m["h"])
            for m in ps:
                del m["h"]
            gr.append({"liga": liga, "partidos": ps})
    aid = f"agenda-{hoy.isoformat()}"
    pendientes.append({"tipo": "agenda", "id": aid, "fecha": hoy.isoformat(), "grupos": gr})
    publicados.add(clave)
    sys.path.insert(0, BASE)
    from render import paginas_agenda
    n = len(paginas_agenda(gr))
    total = sum(len(g["partidos"]) for g in gr)
    cola.append({"tipo": "historia", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                 "archivos": [f"historias/img/{hoy.isoformat()}/{aid}-{i + 1}.png" for i in range(n)],
                 "titulo": f"Hoy se juega ({total} partidos)", "liga": "agenda", "enviado": False})


def main():
    if os.environ.get("DEBUG_FM_ID"):
        mid = os.environ["DEBUG_FM_ID"]
        g, t, a, raw = fotmob_detalle(mid)
        os.makedirs(os.path.join(BASE, "debug"), exist_ok=True)
        evs = (((raw.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
        guardar(f"debug/fotmob_{mid}.json", {"goles": g, "tarjetas": t, "anulados": a, "eventos_crudos": evs[:40]})
        print("Detalle FotMob guardado", len(g), len(t), len(a))
        return
    ahora = dt.datetime.now(CL)
    hoy = ahora.date()
    publicados = set(cargar("publicados.json", []))
    resumenes = set(cargar("resumenes.json", []))
    cola = cargar("cola.json", [])
    pendientes = []

    for liga in LIGAS:
        # ventana para detectar fechas completas: 5 días atrás a 3 adelante
        eventos, datas = {}, {}
        for k in ((-1, 0) if liga in SOLO_HISTORIAS else range(-5, 4)):
            data = scoreboard(liga, hoy + dt.timedelta(days=k))
            for ev in data.get("events", []):
                eventos[ev["id"]] = ev
                datas[ev["id"]] = data
        if not eventos:
            continue
        lista = sorted(eventos.values(), key=lambda e: e["date"])
        DIAG["eventos"][liga] = [f'{e["id"]} {e["status"]["type"].get("name")} {e["date"]}' for e in lista
                                 if abs((hora_cl(e["date"]).date() - hoy).days) <= 1]

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
                 "gl": int(loc.get("score", 0)), "gv": int(vis.get("score", 0)), **serie(ev, loc, vis),
                 "goles": goles, "tarjetas": tarjetas, "anulados": anulados}
            pendientes.append(p)
            publicados.add(clave)
            cola.append({"tipo": "historia", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                         "archivos": [f"historias/img/{p['fecha']}/{p['id']}.png"],
                         "titulo": f"{p['local']} {p['gl']}–{p['gv']} {p['visita']}", "liga": liga, "enviado": False})

        if liga in SOLO_HISTORIAS:
            continue
        # B) resumen: agrupar en fechas (bloques de días seguidos, cortando con 2+ días sin partidos).
        #    Champions y Europa League: un resumen por cada día de la jornada.
        por_dia = liga in ("uefa.champions", "uefa.europa")
        bloques, actual, ult = [], [], None
        for ev in lista:
            d = hora_cl(ev["date"]).date()
            if ult and ((d - ult).days >= 2 or (por_dia and d != ult)):
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
                    sr = serie(e, lo, vi)
                    if sr.get("penales"):
                        f["pen"] = sr["penales"]
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
        goles, tarjetas, anulados = [], [], []
        try:
            goles, tarjetas, anulados, _ = fotmob_detalle(m["id"][2:])
        except Exception as ex:
            print("FotMob detalle falla", m["id"], ex, file=sys.stderr)
        # si hubo goles pero el detalle aún no llega, esperar (hasta ~3 h desde el inicio)
        if m["gl"] + m["gv"] > 0 and len(goles) < m["gl"] + m["gv"] and ahora - m["inicio"] < dt.timedelta(hours=3):
            print("Detalle incompleto, se reintenta:", m["local"], m["visita"], file=sys.stderr)
            continue
        p = {"id": f"chipb-{slug(m['local'])}-{slug(m['visita'])}", "liga": "chi.pb", "fase": "",
             "fecha": m["inicio"].date().isoformat(), "local": m["local"], "visita": m["visita"],
             "gl": m["gl"], "gv": m["gv"], "goles": goles, "tarjetas": tarjetas, "anulados": anulados}
        pendientes.append(p)
        publicados.add(clave)
        cola.append({"tipo": "historia", "clave": clave, "creado": ahora.isoformat(timespec="seconds"),
                     "archivos": [f"historias/img/{p['fecha']}/{p['id']}.png"],
                     "titulo": f"{p['local']} {p['gl']}–{p['gv']} {p['visita']}", "liga": "chi.pb",
                     "sin_goleadores": not goles and p["gl"] + p["gv"] > 0, "enviado": False})

    primera_b_resumen(hoy, ahora, resumenes, pendientes, cola)
    agenda_del_dia(ahora, publicados, pendientes, cola)

    try:
        guardar("diag.json", DIAG)
    except Exception:
        pass
    cola = cola[-300:]
    guardar("pendientes.json", pendientes)
    guardar("cola.json", cola)
    guardar("publicados.json", sorted(publicados)[-3000:])
    guardar("resumenes.json", sorted(resumenes)[-500:])
    print(f"{len(pendientes)} imágenes por generar")


if __name__ == "__main__":
    main()
