#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vigía de CiafMD: cuando acaba la tirada actual, repite tandas de repechaje
(limpiando sin-pdf/error del log para reintentarlas) hasta que no se recupere
nada nuevo. Push final. Deja data/repechaje_resumen.json con el resultado."""
import json, os, subprocess, time

RAIZ = os.path.expanduser('~/Projects/CiafMD')
LOG = f'{RAIZ}/data/resultados.jsonl'
TOTAL = 374

def contar():
    est = {}
    for l in open(LOG):
        try:
            e = json.loads(l).get('estado', '?')
            est[e] = est.get(e, 0) + 1
        except Exception:
            pass
    return est

def limpiar_fallos():
    lineas = [l for l in open(LOG)]
    nuevas, borradas = [], 0
    for l in lineas:
        try:
            e = json.loads(l).get('estado')
        except Exception:
            e = None
        if e in ('sin-pdf', 'error', 'demasiadas-paginas'):
            borradas += 1
            continue
        nuevas.append(l)
    open(LOG, 'w').write(''.join(nuevas))
    return borradas

# 1) Esperar a que acabe la tirada actual (proceso con tirada_completa.py)
while True:
    r = subprocess.run(['pgrep', '-f', 'tirada_completa.py'], capture_output=True, text=True)
    if not r.stdout.strip():
        break
    time.sleep(60)
print('tirada actual acabada:', contar(), flush=True)

# 2) Repechajes hasta que no se recupere nada nuevo
for ronda in range(1, 8):
    borradas = limpiar_fallos()
    est = contar()
    if est.get('ok', 0) >= TOTAL or borradas == 0:
        break
    print(f'== repechaje ronda {ronda}: {borradas} fallos a reintentar ==', flush=True)
    subprocess.run(['python3', 'scripts/tirada_completa.py'], cwd=RAIZ, timeout=36000)
    print('tras ronda', ronda, ':', contar(), flush=True)

# 3) Push final
subprocess.run(['git', 'add', '-A'], cwd=RAIZ)
subprocess.run(['git', 'commit', '-m', 'datos: tirada completa + repechajes finalizados'], cwd=RAIZ)
p = subprocess.run(['git', 'push'], cwd=RAIZ, capture_output=True, text=True)
print('push:', p.returncode, flush=True)

est = contar()
resumen = {'estados': est, 'total_log': sum(est.values()), 'objetivo': TOTAL,
           'fin': time.strftime('%Y-%m-%d %H:%M')}
json.dump(resumen, open(f'{RAIZ}/data/repechaje_resumen.json', 'w'), indent=2)
print('RESUMEN FINAL:', resumen, flush=True)
