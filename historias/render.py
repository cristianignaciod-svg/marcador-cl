#!/usr/bin/env python3
"""Genera historias de Instagram (1080x1920 PNG) de Marcador CL.

Uso:  python3 historias/render.py partidos.json
partidos.json es una lista de objetos:
  {"id": "401879257", "liga": "eng.1", "fase": "Fecha 8",
   "fecha": "2026-10-19",
   "local": "Tottenham Hotspur", "visita": "Coventry City",
   "gl": 1, "gv": 0,
   "goles": [{"min": "14'", "jugador": "James Maddison", "lado": "local",
              "penal": false, "autogol": false}]}
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
            inner = f'<img src="{uri}" style="width:184px;height:184px;object-fit:contain">'
        else:
            ini = "".join(w[0] for w in norm(nombre).split()[:2]).upper() or "?"
            inner = f'<span style="font:800 110px Saira;color:#0f1512">{e(ini)}</span>'
        return (f'<div style="width:250px;height:250px;border-radius:50%;background:#e8eee9;'
                f'display:flex;align-items:center;justify-content:center">{inner}</div>')

    def gol(g):
        extra = " (p)" if g.get("penal") else (" (ag)" if g.get("autogol") else "")
        return (f'<div style="display:flex;gap:16px;align-items:baseline">'
                f'<span style="font:700 34px Saira;color:#e9a63b;min-width:100px">{e(g["min"])}</span>'
                f'<span>{e(g["jugador"])}{extra}</span></div>')

    gl_list = "".join(gol(g) for g in p.get("goles", []) if g["lado"] == "local")
    gv_list = "".join(gol(g) for g in p.get("goles", []) if g["lado"] == "visita")
    goles = ""
    if p.get("goles"):
        goles = f'''
  <div style="margin-top:70px;border-top:2px solid #2c3830;padding-top:44px">
    <div style="font:700 26px Figtree;letter-spacing:.12em;text-transform:uppercase;color:#93a399;margin-bottom:26px">Goles</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;column-gap:40px;font:600 32px/1.3 Figtree">
      <div style="display:flex;flex-direction:column;gap:16px">{gl_list}</div>
      <div style="display:flex;flex-direction:column;gap:16px">{gv_list}</div>
    </div>
  </div>'''
    fase = f' · {e(p["fase"])}' if p.get("fase") else ""
    tam = 46 if max(len(p["local"]), len(p["visita"])) > 14 else 54
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-ExtraBold.ttf")}");font-weight:800}}
@font-face{{font-family:Saira;src:url("{font("SairaCondensed-Bold.ttf")}");font-weight:700}}
@font-face{{font-family:Figtree;src:url("{font("Figtree.ttf")}");font-weight:300 900}}
html,body{{margin:0;background:#0f1512}}
</style></head><body>
<div style="width:1080px;height:1920px;position:relative;overflow:hidden;background:#0f1512;color:#e8eee9;font-family:Figtree">
  <div style="position:absolute;left:70px;top:70px;right:70px;bottom:70px;border:4px solid #1d2722"></div>
  <div style="position:absolute;left:290px;top:-250px;width:500px;height:500px;border:4px solid #1d2722;border-radius:50%"></div>
  <div style="position:absolute;left:290px;bottom:-250px;width:500px;height:500px;border:4px solid #1d2722;border-radius:50%"></div>

  <div style="position:absolute;left:110px;right:110px;top:270px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="font:800 76px/1 Saira;text-transform:uppercase;position:relative">Marcador <span style="color:#e9a63b">CL</span>
        <span style="position:absolute;right:-22px;top:6px;width:14px;height:14px;border-radius:50%;background:#ff5a4f"></span></div>
      <div style="font:700 30px Saira;letter-spacing:.08em;text-transform:uppercase;color:#0f1512;background:#e9a63b;padding:8px 22px;border-radius:6px">Final</div>
    </div>
    <div style="margin-top:56px;font:800 84px/0.95 Saira;text-transform:uppercase">{e(liga)}</div>
    <div style="margin-top:14px;font:600 30px Figtree;color:#93a399">{e(fecha_txt(p["fecha"]))}{fase}</div>

    <div style="margin-top:90px;display:grid;grid-template-columns:1fr auto 1fr;align-items:start">
      <div style="display:flex;flex-direction:column;align-items:center;gap:28px">{chip(p["local"])}
        <div style="font:700 {tam}px/1.05 Saira;text-transform:uppercase;text-align:center;color:{cl}">{e(corto(p["local"]))}</div></div>
      <div style="font:800 190px/270px Saira;font-variant-numeric:tabular-nums;white-space:nowrap;padding:0 18px">
        <span style="color:{cl}">{gl}</span><span style="color:#4a5a50">–</span><span style="color:{cv}">{gv}</span></div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:28px">{chip(p["visita"])}
        <div style="font:700 {tam}px/1.05 Saira;text-transform:uppercase;text-align:center;color:{cv}">{e(corto(p["visita"]))}</div></div>
    </div>
    {goles}
  </div>

  <div style="position:absolute;left:0;right:0;bottom:250px;height:80px;background:#e9a63b;color:#0f1512;font:700 36px/80px Saira;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;overflow:hidden;padding-left:40px">Resultados · Goles y goleadores · Fútbol · Resultados · Goles y goleadores · Fútbol · Resultados ·</div>
</div></body></html>'''


def main():
    from playwright.sync_api import sync_playwright
    partidos = json.load(open(sys.argv[1]))
    salida = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for p in partidos:
            d = os.path.join(BASE, "img", p["fecha"])
            os.makedirs(d, exist_ok=True)
            out = os.path.join(d, f'{p["id"]}.png')
            tmp = os.path.join(BASE, ".tmp.html")
            open(tmp, "w").write(html_partido(p))
            pg.goto("file://" + tmp, wait_until="load")
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=out)
            salida.append(os.path.relpath(out, os.path.dirname(BASE)))
            print(salida[-1])
        b.close()


if __name__ == "__main__":
    main()
