#!/usr/bin/env python3
"""Genera historias de Instagram (1080x1920 PNG) de Marcador CL.

Uso:  python3 historias/render.py partidos.json
partidos.json es una lista de objetos:
  {"id": "401879257", "liga": "eng.1", "fase": "Fecha 8",
   "fecha": "2026-10-19",
   "local": "Tottenham Hotspur", "visita": "Coventry City",
   "gl": 1, "gv": 0,
   "goles": [{"min": "14'", "jugador": "James Maddison", "lado": "local",
              "penal": false, "autogol": false}],
   "anulados": [{"min": "25'", "jugador": "X", "lado": "local", "motivo": "fuera de juego"}],
   "tarjetas": [{"min": "40'", "jugador": "Y", "lado": "visita", "tipo": "amarilla"}]}
  tipo de tarjeta: "amarilla", "roja" (roja directa) o "doble" (segunda amarilla).
  "anulados" y "tarjetas" son opcionales; si vienen vacíos, la sección no aparece.
Las imágenes quedan en historias/img/<fecha>/<id>.png
"""
import base64, difflib, html, json, os, re, sys, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))

LIGAS = {
    "esp.1": ("LaLiga", ["laliga"]),
    "eng.1": ("Premier League", ["premier-league"]),
    "chi.1": ("Liga de Primera", ["chile-primera"]),
    "chi.pb": ("Primera B", ["chile-primera-b"]),
    "uefa.champions": ("Champions League", ["champions"]),
    "uefa.europa": ("Europa League", ["europa-league"]),
    "conmebol.libertadores": ("Copa Libertadores", ["libertadores"]),
    "conmebol.sudamericana": ("Copa Sudamericana", ["sudamericana"]),
}
TODAS = sorted(os.listdir(os.path.join(BASE, "escudos")))

STOP = {"fc", "cf", "cd", "sc", "ac", "afc", "club", "de", "del", "la", "el", "the",
        "deportes", "deportivo", "sd", "ud", "rc", "ca", "cs", "sv", "fk", "sk", "as", "us"}
ALIAS = {
    "man city": "manchester-city", "manchester city": "manchester-city",
    "man united": "manchester-united", "manchester united": "manchester-united",
    "spurs": "tottenham-hotspur", "wolves": "wolverhampton",
    "psg": "paris-saint-germain", "inter": "inter-milan", "internazionale": "inter-milan",
    "bayern munich": "bayern-munchen", "bayern munchen": "bayern-munchen",
    "atletico madrid": "atletico-madrid", "athletic bilbao": "athletic-club",
    "u de chile": "universidad-de-chile", "universidad de chile": "universidad-de-chile",
    "u catolica": "universidad-catolica", "universidad catolica": "universidad-catolica",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(w for w in s.split() if w not in STOP)


def escudo(liga, nombre):
    """Busca el escudo del equipo; devuelve data URI o None."""
    carpetas = LIGAS.get(liga, ("", []))[1]
    orden = carpetas + [c for c in TODAS if c not in carpetas]
    clave = norm(nombre)
    alias = ALIAS.get(nombre.lower()) or ALIAS.get(clave)
    mejor, puntaje = None, 0.0
    for i, c in enumerate(orden):
        d = os.path.join(BASE, "escudos", c)
        for f in os.listdir(d):
            slug = f[:-4]
            if alias and slug == alias:
                return datauri(os.path.join(d, f))
            n = norm(slug.replace("-", " "))
            r = difflib.SequenceMatcher(None, clave, n).ratio()
            if clave and (clave in n or n in clave):
                r = max(r, 0.9)
            r -= 0.05 * (i >= len(carpetas))  # preferir la carpeta de la liga
            if r > puntaje:
                mejor, puntaje = os.path.join(d, f), r
    return datauri(mejor) if mejor and puntaje >= 0.72 else None


def datauri(p):
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()


def font(n):
    return "file://" + os.path.join(BASE, "fuentes", n)


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def fecha_txt(iso):
    import datetime
    d = datetime.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def corto(n):
    n = n.strip()
    return n if len(n) <= 16 else n


def html_partido(p):
    e = html.escape
    liga = LIGAS.get(p["liga"], (p.get("liga_nombre", p["liga"]), []))[0]
    gl, gv = int(p["gl"]), int(p["gv"])
    mut = "#93a399"
    cl = mut if gl < gv else "#e8eee9"
    cv = mut if gv < gl else "#e8eee9"

    def chip(nombre):
        uri = escudo(p["liga"], nombre)
        if uri:
            inner = f'<img src="{uri}" style="width:200px;height:200px;object-fit:contain">'
        else:
            ini = "".join(w[0] for w in norm(nombre).split()[:2]).upper() or "?"
            inner = f'<span style="font:800 130px Saira;color:#0f1512">{e(ini)}</span>'
        return (f'<div style="width:272px;height:272px;border-radius:50%;background:#e8eee9;'
                f'display:flex;align-items:center;justify-content:center">{inner}</div>')

    # Detalle: goles, anulados por VAR, rojas y amarillas. Todo en em para poder achicarlo
    # automáticamente (ver script al final) si no cabe sobre la franja ámbar.
    ICON = {
        "amarilla": '<span style="display:inline-block;width:.55em;height:.75em;border-radius:.08em;background:#f2c230;flex:none;transform:translateY(.08em)"></span>',
        "roja": '<span style="display:inline-block;width:.55em;height:.75em;border-radius:.08em;background:#ff4b3e;flex:none;transform:translateY(.08em)"></span>',
        "doble": '<span style="display:inline-flex;flex:none;transform:translateY(.08em)"><span style="width:.55em;height:.75em;border-radius:.08em;background:#f2c230"></span><span style="width:.55em;height:.75em;border-radius:.08em;background:#ff4b3e;margin-left:-.25em;box-shadow:-.06em 0 0 #0f1512"></span></span>',
    }

    def linea(minuto, texto, icono="", tachado=False):
        t = f'<span style="text-decoration:line-through;text-decoration-thickness:.07em;color:#93a399">{texto}</span>' if tachado else f"<span>{texto}</span>"
        return (f'<div style="display:flex;gap:.45em;align-items:baseline">'
                f'<span style="font-family:Saira;font-weight:700;font-size:1.06em;color:#e9a63b;min-width:2.5em">{e(minuto)}</span>'
                f'{icono}<span style="white-space:nowrap">{t}</span></div>')

    def seccion(titulo, items, fn):
        if not items:
            return ""
        col = lambda lado: "".join(fn(x) for x in items if x.get("lado") == lado)
        return (f'<div style="margin-top:1.1em">'
                f'<div style="font-weight:700;font-size:.8em;letter-spacing:.12em;text-transform:uppercase;color:#93a399;margin-bottom:.6em">{titulo}</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;column-gap:1.25em;line-height:1.25">'
                f'<div style="display:flex;flex-direction:column;gap:.4em">{col("local")}</div>'
                f'<div style="display:flex;flex-direction:column;gap:.4em">{col("visita")}</div></div></div>')

    def gol(g):
        extra = " (p)" if g.get("penal") else (" (ag)" if g.get("autogol") else "")
        return linea(g["min"], e(g["jugador"]) + extra)

    def anulado(g):
        motivo = f' <span style="color:#93a399;font-size:.8em">({e(g["motivo"])})</span>' if g.get("motivo") else ""
        h = linea(g["min"], e(g["jugador"]), tachado=True)
        return h[:-len("</div>")] + motivo + "</div>"

    def tarjeta(t):
        return linea(t["min"], e(t["jugador"]), ICON.get(t.get("tipo", "amarilla"), ICON["amarilla"]))

    tarjetas = p.get("tarjetas", [])
    rojas = [t for t in tarjetas if t.get("tipo") in ("roja", "doble")]
    amarillas = [t for t in tarjetas if t.get("tipo", "amarilla") == "amarilla"]
    cuerpo = (seccion("Goles", p.get("goles", []), gol)
              + seccion("Anulados por VAR", p.get("anulados", []), anulado)
              + seccion("Expulsados", rojas, tarjeta)
              + seccion("Amarillas", amarillas, tarjeta))
    goles = ""
    if cuerpo:
        goles = f'''
  <div id="det" style="margin-top:64px;border-top:2px solid #2c3830;padding-top:.2em;font:600 36px Figtree">{cuerpo}</div>'''
    fase = f' · {e(p["fase"])}' if p.get("fase") else ""
    tam = 52 if max(len(p["local"]), len(p["visita"])) > 14 else 62
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-ExtraBold.ttf")}");font-weight:800}}
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-Bold.ttf")}");font-weight:700}}
@font-face{{font-family:Figtree;src:url("{font("Figtree.ttf")}");font-weight:300 900}}
html,body{{margin:0;background:#0f1512}}
</style></head><body>
<div style="width:1080px;height:1920px;position:relative;overflow:hidden;background:#0f1512;color:#e8eee9;font-family:Figtree">
  <div style="position:absolute;left:70px;top:70px;right:70px;bottom:70px;border:4px solid #1d2722"></div>
  <div style="position:absolute;left:290px;top:-340px;width:500px;height:500px;border:4px solid #1d2722;border-radius:50%"></div>
  <div style="position:absolute;left:290px;bottom:-340px;width:500px;height:500px;border:4px solid #1d2722;border-radius:50%"></div>

  <div style="position:absolute;left:90px;right:90px;top:185px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="font:800 84px/1 Saira;text-transform:uppercase;position:relative">Marcador <span style="color:#e9a63b">CL</span>
        <span style="position:absolute;right:-22px;top:6px;width:14px;height:14px;border-radius:50%;background:#ff5a4f"></span></div>
      <div style="font:700 30px Saira;letter-spacing:.08em;text-transform:uppercase;color:#0f1512;background:#e9a63b;padding:8px 22px;border-radius:6px">Final</div>
    </div>
    <div style="margin-top:52px;font:800 100px/0.95 Saira;text-transform:uppercase">{e(liga)}</div>
    <div style="margin-top:16px;font:600 34px Figtree;color:#93a399">{e(fecha_txt(p["fecha"]))}{fase}</div>

    <div style="margin-top:80px;display:grid;grid-template-columns:1fr auto 1fr;align-items:start">
      <div style="display:flex;flex-direction:column;align-items:center;gap:28px">{chip(p["local"])}
        <div style="font:700 {tam}px/1.05 Saira;text-transform:uppercase;text-align:center;color:{cl}">{e(corto(p["local"]))}</div></div>
      <div style="font:800 206px/272px Saira;font-variant-numeric:tabular-nums;white-space:nowrap;padding:0 22px">
        <span style="color:{cl}">{gl}</span><span style="color:#4a5a50">–</span><span style="color:{cv}">{gv}</span></div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:28px">{chip(p["visita"])}
        <div style="font:700 {tam}px/1.05 Saira;text-transform:uppercase;text-align:center;color:{cv}">{e(corto(p["visita"]))}</div></div>
    </div>
    {goles}
  </div>

  <div style="position:absolute;left:0;right:0;bottom:150px;height:84px;background:#e9a63b;color:#0f1512;font:700 38px/84px Saira;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;overflow:hidden;padding-left:40px">Resultados · Goles y goleadores · Fútbol · Resultados · Goles y goleadores · Fútbol · Resultados ·</div>
</div>
<script>
window.fit=function(){{var d=document.getElementById("det");if(!d)return;var fs=38;d.style.fontSize=fs+"px";
while(d.getBoundingClientRect().bottom>1650&&fs>20){{fs-=1;d.style.fontSize=fs+"px";}}}};
</script></body></html>'''


def html_resumen(r, filas, pagina, total):
    """Imagen 1080x1350 con los resultados de una fecha completa."""
    e = html.escape
    liga = LIGAS.get(r["liga"], (r.get("liga_nombre", r["liga"]), []))[0]
    fg, mut = "#e8eee9", "#93a399"
    alto = 78 if len(filas) > 9 else 84
    def chip(n):
        uri = escudo(r["liga"], n)
        img = f'<img src="{uri}" style="width:40px;height:40px;object-fit:contain">' if uri else ""
        return (f'<div style="flex:none;width:54px;height:54px;border-radius:50%;background:#e8eee9;'
                f'display:flex;align-items:center;justify-content:center">{img}</div>')
    rows = ""
    for f in filas:
        if f.get("estado"):
            sc = f'<div style="font:700 24px Saira;letter-spacing:.06em;text-transform:uppercase;color:#e9a63b;border:2px solid #e9a63b;border-radius:8px;padding:8px 12px">{e(f["estado"])}</div>'
            cl = cv = fg
        else:
            gl, gv = int(f["gl"]), int(f["gv"])
            cl, cv = (mut if gl < gv else fg), (mut if gv < gl else fg)
            sc = (f'<div style="font:800 38px/1 Saira;background:#18201b;border:2px solid #2c3830;border-radius:8px;'
                  f'padding:6px 14px;font-variant-numeric:tabular-nums;white-space:nowrap">{gl}–{gv}</div>')
        rows += f'''<div style="display:grid;grid-template-columns:84px minmax(0,1fr) 150px minmax(0,1fr);align-items:center;min-height:{alto}px;border-bottom:1px solid #1f2924;column-gap:14px">
  <div style="font:700 16px Figtree;letter-spacing:.08em;text-transform:uppercase;color:#93a399">{e(f.get("dia",""))}</div>
  <div style="display:flex;align-items:center;justify-content:flex-end;gap:14px;min-width:0"><div style="text-align:right;font:600 27px/1.1 Figtree;color:{cl}">{e(f["local"])}</div>{chip(f["local"])}</div>
  <div style="display:flex;justify-content:center">{sc}</div>
  <div style="display:flex;align-items:center;gap:14px;min-width:0">{chip(f["visita"])}<div style="font:600 27px/1.1 Figtree;color:{cv}">{e(f["visita"])}</div></div>
</div>'''
    tam = 120 if len(liga) <= 15 else 96
    pie = f"{pagina}/{total} · Desliza para ver más" if total > 1 and pagina < total else "Resultados · Goles y goleadores"
    fase = f'<div style="font:700 44px/1 Saira;text-transform:uppercase;color:#e9a63b;white-space:nowrap">{e(r.get("fase",""))}</div>' if r.get("fase") else ""
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-ExtraBold.ttf")}");font-weight:800}}
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-Bold.ttf")}");font-weight:700}}
@font-face{{font-family:Figtree;src:url("{font("Figtree.ttf")}");font-weight:300 900}}
html,body{{margin:0;background:#0f1512}}
</style></head><body>
<div style="width:1080px;height:1350px;box-sizing:border-box;background:#0f1512;color:#e8eee9;font-family:Figtree;display:flex;flex-direction:column;padding:72px 80px 64px;overflow:hidden">
  <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:24px;padding-bottom:28px;border-bottom:2px solid #2c3830">
    <div style="font:800 64px/0.9 Saira;letter-spacing:.01em;text-transform:uppercase">Marcador <span style="color:#e9a63b">CL</span></div>
    <div style="text-align:right;font:400 22px/1.35 Figtree;color:#93a399">
      <div style="font-weight:700;color:#e8eee9;letter-spacing:.08em;text-transform:uppercase;font-size:20px">Resultados</div>
      <div>{e(r.get("rango",""))}</div></div>
  </div>
  <div style="padding-top:44px;display:flex;align-items:baseline;justify-content:space-between;gap:24px">
    <div style="font:800 {tam}px/0.9 Saira;text-transform:uppercase">{e(liga)}</div>{fase}
  </div>
  <div style="margin-top:28px;display:flex;flex-direction:column">{rows}</div>
  <div style="margin-top:auto;padding-top:28px;border-top:2px solid #2c3830;font:400 22px/1.35 Figtree;color:#93a399">{e(pie)}</div>
</div></body></html>'''


def render(pg, contenido, out, w, h):
    tmp = os.path.join(BASE, ".tmp.html")
    open(tmp, "w").write(contenido)
    pg.set_viewport_size({"width": w, "height": h})
    pg.goto("file://" + tmp, wait_until="load")
    pg.evaluate("document.fonts.ready.then(() => window.fit && window.fit())")
    pg.screenshot(path=out)
    print(os.path.relpath(out, os.path.dirname(BASE)))


def main():
    """Cada elemento es un partido (historia) o, con "tipo": "resumen", una fecha completa:
    {"tipo":"resumen","id":"eng1-fecha8","liga":"eng.1","fase":"Fecha 8","fecha":"2026-10-19",
     "rango":"17 al 19 de octubre","partidos":[{"dia":"Sáb 17","local":"Everton","visita":"Chelsea",
     "gl":0,"gv":2}, {"dia":"Dom 18","local":"X","visita":"Y","estado":"Susp."}]}
    Los resúmenes de más de 10 partidos se dividen en varias imágenes (carrusel): <id>-1.png, <id>-2.png..."""
    from playwright.sync_api import sync_playwright
    items = json.load(open(sys.argv[1]))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        for p in items:
            d = os.path.join(BASE, "img", p["fecha"])
            os.makedirs(d, exist_ok=True)
            if p.get("tipo") == "resumen":
                ps = p["partidos"]
                n = (len(ps) + 9) // 10
                tam = -(-len(ps) // n)
                for i in range(n):
                    render(pg, html_resumen(p, ps[i * tam:(i + 1) * tam], i + 1, n),
                           os.path.join(d, f'{p["id"]}-{i + 1}.png'), 1080, 1350)
            else:
                render(pg, html_partido(p), os.path.join(d, f'{p["id"]}.png'), 1080, 1920)
        b.close()


if __name__ == "__main__":
    main()
