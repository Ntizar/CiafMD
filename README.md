# CiafMD

Corpus de informes de investigación ferroviaria de la CIAF (Comisión de Investigación de Accidentes Ferroviarios, España) en markdown de alta coherencia, generado a partir de los PDFs oficiales alojados en era.europa.eu.

**352 documentos únicos** — informes finales completos (los resúmenes ejecutivos, la nota de avance y la edición inglesa se descartaron al ser derivados de informes ya presentes).

## Nombres

`informe-NNNN-AÑO.md` con el **número oficial de informe** extraído de la portada de cada documento (p. ej. `informe-0064-2024.md` = IF 64/2024, `informe-0041-2016.md` = el mayor, 423 páginas). Duplicados exactos eliminados por md5 del PDF (3 casos de ERA que aloja el mismo fichero dos veces).

## Cómo se ha generado

1. **Descarga** de los 374 PDFs del manifest (era.europa.eu, con reintento por el bloqueo intermitente del servidor).
2. **Rasterizado** página a página con pypdfium2 a ~144 dpi (determinista).
3. **Lectura visual** de cada página con **qwen3.6** vía API NaN.builders (prompt fijo: ignorar logos/cabeceras/pies, tablas como markdown, jerarquía real, `[ilegible]` si no se lee con seguridad, no inventar).
4. **Post-filtro** regex de ruido (IDs de expediente, «Pág. N de M», números de página sueltos).

Métricas de la conversión: 7.305 páginas, ~19,3M tokens, ~13 h en background sobre VM de 2 vCPU sin GPU. Cada fichero lleva frontmatter con trazabilidad: PDF de origen, URL oficial, páginas y fecha.

## Determinismo y límites honestos

El pipeline **NO es determinista al 100%**. Desglose:

**Determinista:**
- Rasterizado, orden de páginas, frontmatter, post-filtros y nombres (reglas fijas).

**No determinista (decodificación del modelo):**
- Dos pasadas sobre la misma página pueden diferir en puntuación, alguna frase o el nivel exacto de un título. El contenido factual (fechas, números, nombres) es estable en las verificaciones hechas, pero **conviene verificar contra el PDF original cualquier dato crítico** (la URL oficial está en el frontmatter de cada fichero para eso).

**Dónde puede fallar específicamente:**

- **Tablas densas o con celdas combinadas**: el modelo reconstruye la estructura desde la imagen; en tablas muy apretadas puede fusionar o partir filas. Las tablas que **cruzan de página** quedan como dos tablas (una por página) — no se fusionan automáticamente.
- **Imágenes y gráficos**: una fotografía o un gráfico del PDF solo aporta lo que el modelo pueda leer de él (título, ejes, etiquetas legibles). **Los datos de un gráfico no se transcriben** — no existen en el markdown. Para gráficos relevantes, ir al PDF original.
- **Escaneos de baja calidad**: por debajo de ~150 dpi efectivos o con ruido fuerte, crecen los marcadores `[ilegible]` (205 en todo el corpus, 0,003% de las páginas) — el pipeline declara lo que no puede leer en vez de inventarlo.
- **1 página de 7.305** quedó `[página N sin convertir]` (timeout de API tras 4 reintentos).

## Estructura del repo

- `md/ES/` — los 352 informes, un `.md` por informe oficial
- `data/resultados.jsonl` — log completo de la conversión (estados, métricas, duplicados y descartes anotados)
- `data/pdf-manifest/ES.json` — manifest de origen
- `scripts/tirada_completa.py` — pipeline reanudable con cache a nivel de página (`data/pagecache/`)
- `scripts/vigia_repechaje.py` — orquestador de tandas de reintento

Hecho con ❤️ por David Antizar — pipeline diseñado y operado por Mastermind (Hermes Agent + qwen3.6 de NaN.builders)
