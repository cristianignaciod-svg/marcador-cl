#!/usr/bin/env python3
"""Guarda el resultado de publicar.py sin pisar cambios hechos en paralelo (p. ej. la tarea que pide aprobación).

Uso: fusionar.py <cola_local.json> <hechos_local.json> <estado_local.json>
Se ejecuta sobre la copia recién bajada de origin/main: copia a cada ítem de la cola remota los campos
que escribe publicar.py (enviado, ig_id, publicado, error, intentos, texto) y une ig_hechos.json."""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CAMPOS = ("enviado", "ig_id", "publicado", "error", "intentos")


def leer(p, defecto):
    try:
        return json.load(open(p))
    except Exception:
        return defecto


cola_loc, hechos_loc, estado_loc = sys.argv[1:4]
loc = {(x.get("clave"), x.get("creado")): x for x in leer(cola_loc, [])}
p = os.path.join(BASE, "cola.json")
cola = leer(p, [])
for x in cola:
    y = loc.get((x.get("clave"), x.get("creado")))
    if not y:
        continue
    for c in CAMPOS:
        if c in y and y.get(c) != x.get(c):
            # nunca "desmarcar" algo que el remoto ya da por enviado
            if c == "enviado" and x.get("enviado") and not y.get("enviado"):
                continue
            x[c] = y[c]
    if y.get("enviado") is True and y.get("texto") and not x.get("texto"):
        x["texto"] = y["texto"]
json.dump(cola, open(p, "w"), ensure_ascii=False, indent=1)

ph = os.path.join(BASE, "ig_hechos.json")
hechos = leer(ph, {})
hechos.update(leer(hechos_loc, {}))
json.dump(hechos, open(ph, "w"), ensure_ascii=False, indent=1)

est = leer(estado_loc, None)
if est is not None:
    json.dump(est, open(os.path.join(BASE, "estado_instagram.json"), "w"), ensure_ascii=False, indent=1)
