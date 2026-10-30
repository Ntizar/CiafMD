# CiafMD

Corpus completo de informes de investigación ferroviaria de la CIAF (Comisión de Investigación de Accidentes Ferroviarios, España) — **374 informes, 7.305 páginas** — convertidos de PDF a markdown de alta coherencia.

## Cómo se ha generado

Pipeline propio con **qwen3.6 en modo visión** vía API de NaN.builders: rasterizado página a página (pypdfium2, ~144 dpi) → lectura visual por el modelo → post-filtro de ruido de layout. Sin PyMuPDF, sin OCR clásico, sin GPU.

| Métrica | Valor |
|---|---|
| Informes convertidos | **374/374** (0 fallos) |
| Páginas totales | 7.305 |
| Tokens consumidos | ~19,3M |
| Tiempo total | ~13 h (VM 2 vCPU, todo en background) |
| Mayor informe | 423 páginas (convertido en 101 min) |

## Estructura

- `md/ES/` — un `.md` por informe, con frontmatter de trazabilidad (PDF origen, URL oficial, páginas, tokens, fecha)
- `data/resultados.jsonl` — log de conversión (1 línea por informe, con estado y métricas)
- `data/pdf-manifest/ES.json` — manifest de origen (374 PDFs de era.europa.eu)
- `scripts/tirada_completa.py` — pipeline reanudable (cache a nivel de página en `data/pagecache/`)
- `scripts/vigia_repechaje.py` — orquestador de tandas de reintento

## Marcadores de calidad

- `[ilegible]` — fragmento que el modelo no pudo leer con seguridad (205 en todo el corpus, 0,003% de las páginas)
- `[página N sin convertir]` — página perdida por timeout tras 4 reintentos (1 en todo el corpus)

Hecho con ❤️ por David Antizar — pipeline diseñado y operado por Mastermind (Hermes Agent + qwen3.6 de NaN.builders)
