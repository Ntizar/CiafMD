#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CiafMD: PDF (manifest ERA) → markdown verificado con qwen3.6.

Uso: python3 tirada_completa.py [LIMITE]
Reanudable: salta informes cuyo MD ya existe.
Por cada informe:
  1. Descarga el PDF de era.europa.eu (reintenta 4x, respeta 429).
  2. Rasteriza con pypdfium2 a ~144 dpi.
  3. Lee cada página con qwen3.6 (reasoning_effort=minimal).
  4. Post-filtro de ruido (IDs de expediente, 'Pág. N de M', números sueltos).
  5. Pase de fusión (opcional): qwen3.6 normaliza tablas cortadas entre páginas.
  6. Escribe data/resultados.jsonl (log) y md/ES/<nombre>.md.
"""
import base64, glob, json, os, re, subprocess, sys, time, urllib.request, urllib.error, urllib.parse

RAIZ = os.path.expanduser('~/Projects/CiafMD')
VENV = '/home/nan/.mastermind/venv/bin/python'
BASE = 'https://www.era.europa.eu'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def cargar_clave():
    for l in open('/home/nan/.hermes/.env'):
        if l.startswith('OPENAI_API_KEY='):
            return l.split('=',1)[1].strip()
    raise SystemExit('sin OPENAI_API_KEY')

KEY = cargar_clave()

PROMPT = """Convierte esta página de un informe oficial de investigación ferroviaria a markdown limpio y coherente. Reglas:
- IGNORA logos, marcas de agua, cabeceras repetidas (bloques de ministerio/secretaría) y pies de página (código de expediente y 'Pág. N de M').
- Tablas como tablas markdown reales con cabeceras correctas; si la tabla continúa de otra página, ciérrala igualmente bien formada.
- Títulos con #/##/### según jerarquía visual real.
- Conserva fechas, números de expediente, velocidades, horas y datos exactos.
- NO inventes contenido; si algo es ilegible escribe [ilegible].
Responde SOLO el markdown."""

PROMPT_FUSION = """Aquí tienes un documento markdown generado página a página a partir de un PDF.
Arréglalo SIN cambiar el contenido:
1. Tablas que continúan entre páginas: fusiónalas en una sola tabla por separador `---`.
2. Cabeceras de página/pie que se hayan colado: elimínalas.
3. Niveles de título incoherentes: normalízalos (h1 solo el título del informe).
4. No resumas, no traduzcas, no cambies ni un dato.
Responde SOLO el markdown completo."""

def api(msgs, effort='minimal', timeout=240):
    body = {'model': 'qwen3.6', 'reasoning_effort': effort, 'messages': msgs}
    req = urllib.request.Request('https://api.nan.builders/v1/chat/completions',
        data=json.dumps(body).encode(),
        headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return (d['choices'][0]['message']['content'] or ''), d['usage']['total_tokens']

def descargar(url, dest, max_intentos=4):
    for i in range(max_intentos):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                datos = r.read()
            if datos[:4] == b'%PDF':
                open(dest,'wb').write(datos)
                return True
            time.sleep(20)  # bloqueo intermitente de ERA: HTML "web bloqueada" → reintentar
            continue
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(120*(i+1))
            elif e.code in (404, 410):
                return False
            else:
                time.sleep(10)
        except Exception:
            time.sleep(10)
    return False

def es_ruido(linea):
    l = linea.strip()
    if re.match(r'^I[DN][\s_\-]?\d{6}[\s_\-]?\d{6}\s*$', l): return True
    if re.match(r'^P[áa]g\.?\s*\d+\s*de\s*\d+\s*$', l, re.I): return True
    if re.match(r'^\d{1,3}\s*$', l): return True
    return False

def convertir_pdf(pdf_path, md_dir, nombre, token_acum):
    """Rasteriza + lee todas las páginas. Devuelve (texto, paginas, tokens, estado)."""
    tmp = f'/tmp/ciafmd_{os.getpid()}'
    os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(f'{tmp}/*.png'):
        os.remove(f)
    r = subprocess.run([VENV, '-c', f'''
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument({pdf_path!r})
for i, page in enumerate(pdf):
    img = page.render(scale=2.0).to_pil()
    img.save({tmp!r} + f"/p{{i:02d}}.png")
print(len(pdf))
'''], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return '', 0, 0, f'error-raster: {r.stderr[-120:]}'
    n = int(r.stdout.strip().splitlines()[-1])
    if n > 120:
        return '', n, 0, 'demasiadas-paginas'
    pags, tokens = [], 0
    for i in range(n):
        png = f'{tmp}/p{i:02d}.png'
        md = None
        for intento in range(4):
            try:
                b64 = base64.b64encode(open(png,'rb').read()).decode()
                c, tok = api([{'role':'user','content':[
                    {'type':'text','text':PROMPT},
                    {'type':'image_url','image_url':{'url':f'data:image/png;base64,{b64}'}}]}])
                pags.append(c.replace('```markdown','').replace('```','').strip())
                tokens += tok
                md = True
                break
            except Exception as e:
                print(f'    p{i}: reintento {intento+1} ({str(e)[:60]})', flush=True)
                time.sleep(8*(intento+1))
        if not md:
            pags.append(f'> [página {i+1} sin convertir]')
    texto = '\n\n'.join(f'<!-- p{i+1} -->\n\n' + '\n'.join(l for l in p.splitlines() if not es_ruido(l))
                        for i, p in enumerate(pags))
    for f in glob.glob(f'{tmp}/*.png'):
        os.remove(f)
    os.rmdir(tmp)
    return texto, n, tokens, 'ok'

def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    manifest = json.load(open(f'{RAIZ}/data/pdf-manifest/ES.json'))
    log_path = f'{RAIZ}/data/resultados.jsonl'
    hechos = set()
    if os.path.exists(log_path):
        for l in open(log_path):
            try:
                if json.loads(l).get('estado') in ('ok','sin-pdf','error'):
                    hechos.add(json.loads(l)['pdf'])
            except Exception:
                pass
    print(f'== CiafMD tirada — {len(manifest)} informes, {len(hechos)} ya hechos ==', flush=True)
    pendientes = [m for m in manifest if m['pdf'] not in hechos]
    if limite:
        pendientes = pendientes[:limite]
    t0 = time.time()
    desde_commit = 0
    for idx, item in enumerate(pendientes):
        ruta = item['pdf']
        nombre = os.path.basename(ruta)
        base = re.sub(r'\.pdf$', '', nombre, flags=re.I)
        md_path = f'{RAIZ}/md/ES/{base}.md'
        pdf_tmp = f'{RAIZ}/pdfs/ES/{nombre}'
        t_i = time.time()
        estado, pags, tokens, err = 'ok', 0, 0, ''
        try:
            if not os.path.exists(pdf_tmp) or os.path.getsize(pdf_tmp) < 500:
                if not descargar(BASE + urllib.parse.quote(urllib.parse.unquote(ruta)), pdf_tmp):
                    estado = 'sin-pdf'
            if estado == 'ok':
                texto, pags, tokens, err = convertir_pdf(pdf_tmp, None, nombre, 0)
                if err.startswith('error-raster'):
                    estado = 'error'
                elif err == 'demasiadas-paginas':
                    estado = 'demasiadas-paginas'
                else:
                    with open(md_path, 'w') as f:
                        f.write(f'---\npdf: {nombre}\nurl: {BASE}{urllib.parse.quote(ruta)}\npaginas: {pags}\n'
                                f'tokens: {tokens}\ngenerador: qwen3.6 (vision, minimal) + post-filtro\nfecha: {time.strftime("%Y-%m-%d %H:%M")}\n---\n\n{texto}\n')
        except Exception as e:
            estado, err = 'error', str(e)[:200]
        reg = {'pdf': ruta, 'estado': estado, 'paginas': pags, 'tokens': tokens,
               's': round(time.time()-t_i, 1), 'err': err, 'ts': time.strftime('%H:%M:%S')}
        with open(log_path, 'a') as f:
            f.write(json.dumps(reg, ensure_ascii=False) + '\n')
        print(f"[{idx+1}/{len(pendientes)}] {estado} {nombre[:40]} p={pags} tok={tokens} {reg['s']}s {err[:60]}", flush=True)
        desde_commit += 1
        if desde_commit >= 10:
            subprocess.run(['git','add','-A'], cwd=RAIZ)
            subprocess.run(['git','commit','-m',f'datos: +{desde_commit} informes convertidos ({idx+1}/{len(pendientes)} de la tirada)'], cwd=RAIZ)
            desde_commit = 0
    if desde_commit:
        subprocess.run(['git','add','-A'], cwd=RAIZ)
        subprocess.run(['git','commit','-m',f'datos: +{desde_commit} informes (fin de tirada)'], cwd=RAIZ)

if __name__ == '__main__':
    main()
