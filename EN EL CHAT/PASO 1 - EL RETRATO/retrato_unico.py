# -*- coding: utf-8 -*-
"""
retrato_unico.py — el skill retrato-corpus en UN SOLO ARCHIVO.

    python retrato_unico.py tu_export.txt --titulo "..." --ecuacion "..."

Escribe DOS archivos junto al .txt: retrato.html y retrato_data.json.
Sin dependencias: Python 3.9+ y nada más. No usa internet.

GENERADO por construir_unico.py a partir de retrato-corpus v0.6.1.
NO SE EDITA A MANO: se edita el skill y se regenera. Una copia que se
toca por su cuenta se separa del original sin que nadie lo note.
"""
import io, os, re, sys, json, statistics
import html as _html
from collections import Counter, defaultdict

VERSION = "0.6.1"

# ───────────────────────────────────────────────────────────── utilidades

def utf8():
    """La consola de Windows llega en cp1252 y parte los acentos."""
    if getattr(utf8, "hecho", False):
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    utf8.hecho = True


def arg_config(argv, script):
    """CAMBIADA respecto del skill: aquí el .txt se pasa directo, sin retrato.json.
    Es la única diferencia de comportamiento entre este archivo y el skill, y es
    de interfaz — ni una línea de cálculo cambia. Se sigue aceptando un .json por
    si alguien trae un proyecto ya montado."""
    args = [a for a in argv[1:]]
    if not args:
        print(f"uso:  python {script} tu_export.txt "
              f'--titulo "..." --ecuacion "..."\n\n'
              f"      --titulo    cuatro o cinco palabras para la cabecera\n"
              f"      --ecuacion  la ecuacion con la que bajaste el export\n"
              f"      --salida    carpeta de salida (por defecto, junto al .txt)\n\n"
              f"      Los dos primeros son opcionales: sin ellos corre igual, pero\n"
              f"      la lamina de temas se llena con tus propios terminos de busqueda.",
              file=sys.stderr)
        raise SystemExit(2)

    ruta, opciones = args[0], {}
    i = 1
    while i < len(args):
        clave = args[i]
        if not clave.startswith("--"):
            print(f"argumento suelto que no entiendo: {clave}", file=sys.stderr)
            raise SystemExit(2)
        if i + 1 >= len(args):
            print(f"a {clave} le falta el valor", file=sys.stderr)
            raise SystemExit(2)
        opciones[clave[2:]] = args[i + 1]
        i += 2

    if not os.path.exists(ruta):
        print(f"no existe el archivo: {ruta}", file=sys.stderr)
        raise SystemExit(2)

    if ruta.lower().endswith(".json"):
        with io.open(ruta, encoding="utf-8") as f:
            cfg = json.load(f)
        base = os.path.dirname(os.path.abspath(ruta))
        for k in ("fuente", "salida"):
            if cfg.get(k) and not os.path.isabs(cfg[k]):
                cfg[k] = os.path.join(base, cfg[k])
        return cfg

    salida = opciones.get("salida") or os.path.dirname(os.path.abspath(ruta))
    cfg = {
        "fuente": os.path.abspath(ruta),
        "salida": os.path.abspath(salida),
        "titulo": opciones.get("titulo", ""),
        "ecuacion_base": opciones.get("ecuacion", opciones.get("ecuacion_base", "")),
        "anio_actual": int(opciones.get("anio_actual", 0) or 0),
        "idioma": opciones.get("idioma", "es"),
    }
    if not os.path.isdir(cfg["salida"]):
        os.makedirs(cfg["salida"])
    return cfg



def pct(parte, total, dec=1):
    return round(100.0 * parte / total, dec) if total else 0.0


def top_estable(cuenta, n=None):
    """Counter.most_common() rompe los empates por orden de inserción, y ese orden
    depende de cómo se recorrieron los CONJUNTOS de palabras clave — que Python
    aleatoriza en cada proceso. Dos corridas del mismo corpus daban ficheros
    distintos. Aquí el empate se rompe por la clave: mismo corpus, mismo archivo."""
    pares = sorted(cuenta.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return pares[:n] if n else pares


# ───────────────────────────────────────────────────────── parseo del export

# Un registro empieza cuando aparece la línea del año: "(2021) Revista, 13 (2), ... Cited 36 times."
_LINEA_ANIO = re.compile(r"^\((\d{4})\)\s*(.*)$")
# Colas que NO forman parte del nombre de la revista. El orden importa poco; la
# trampa es que el nombre SÍ puede llevar paréntesis —«Sustainability (Switzerland)»—,
# así que solo se descarta el paréntesis cuando ocupa el segmento entero.
_COLA = re.compile(r"""^(?:
      \d+\s*\([^)]*\)          # volumen con fascículo: 13 (2), 9 (SI), 34 (S2), 60 (SUPPL.2)
    | \([^)]*\)                # fascículo suelto: (1), (JULY SUPPL.), (Special Issue 3)
    | \d+                      # volumen a secas
    | art\.\s*no\..*
    | pp?\..*                  # pp. 1 - 22, p. 45
    | \d+\s*[-–]\s*\d+         # rango de páginas suelto
    | Cited\s+\d+\s+times?\.?
    | Article\s+in\s+Press.*
    | Suppl\..*
    | [A-Z]?\d+                # 12A, A3
    )$""", re.I | re.X)
_CITAS = re.compile(r"Cited\s+(\d+)\s+times?", re.I)


_TAGS = re.compile(r"<[^>]{1,40}>")


def limpiar(t):
    """Scopus exporta acentos como entidades —&#x00E9; por é— y a veces deja
    etiquetas <inf>. La entidad TERMINA EN PUNTO Y COMA, que es justo el separador
    de direcciones en AFFILIATIONS: sin deshacerla, «Universidad Técnica» se parte
    en «Universidad T&» y «#x00E9;cnica», y el país se pierde.

    Y a veces viene DOBLEMENTE escapada —&amp;#x00E9;—, así que una sola pasada
    deja &#x00E9; con su punto y coma. Se deshace hasta que deje de cambiar."""
    if not t:
        return t
    t = _TAGS.sub("", t)
    for _ in range(3):
        d = _html.unescape(t)
        if d == t:
            break
        t = d
    return t


# El resumen suele terminar con el pie del editor pegado al texto: «© 2024 The
# Authors», «Published by Elsevier», «Licensee MDPI, Basel, Switzerland». No es
# del autor y contamina todo lo que se lea del resumen —una frase con «© 2024»
# llegó a contarse como oración relacional—. Se corta en la primera marca del
# TRAMO FINAL, para no truncar un resumen que hable de copyright legítimamente.
_PIE = re.compile(
    r"(©|\(c\)\s*\d{4}|Copyright\s*(?:©|\(c\))?\s*\d{4}|All rights reserved"
    r"|Licensee\s+\w+|Published by\s+\w+|The Author\(s\)|This is an open access)",
    re.I)


def _sin_pie(t, cola=0.35):
    if not t:
        return t
    desde = int(len(t) * (1 - cola))
    m = _PIE.search(t, desde)
    return t[:m.start()].rstrip(" .,;·-") if m else t


def _campo(bloque, nombre):
    """Campos con la forma  NOMBRE: valor, que pueden ocupar varias líneas."""
    m = re.search(rf"^{nombre}:(.*?)(?=^[A-Z][A-Z0-9 /&'-]{{2,44}}:|\Z)",
                  bloque, re.S | re.M)
    return limpiar(" ".join(m.group(1).split())) if m else ""


def _revista(resto):
    """De  'Sustainability (Switzerland), 13 (2), art. no. 550, pp. 1 - 22, Cited 36 times.'
    saca  'Sustainability (Switzerland)'. El nombre puede llevar comas, así que se
    recorta por la cola, no por la primera coma."""
    partes = [p.strip() for p in resto.split(",")]
    fuera = []
    for p in partes:
        if _COLA.match(p) or not p:
            break
        fuera.append(p)
    return ", ".join(fuera).strip(" .,")


def parsear(ruta):
    """Devuelve (registros, n_bloques). Un registro es un dict con campos ya limpios."""
    with io.open(ruta, encoding="utf-8", errors="replace") as f:
        crudo = f.read()
    bloques = [b for b in crudo.split("SOURCE: Scopus") if b.strip()]
    # el último trozo tras el separador final suele ser basura de cierre
    bloques = [b for b in bloques if len(b.strip()) > 200]

    recs = []
    for i, b in enumerate(bloques, 1):
        lineas = b.strip().split("\n")
        anio, titulo, rev, citas = "", "", "", 0
        for j, ln in enumerate(lineas):
            m = _LINEA_ANIO.match(ln.strip())
            if not m:
                continue
            anio = m.group(1)
            rev = _revista(m.group(2))
            c = _CITAS.search(ln)
            citas = int(c.group(1)) if c else 0
            # el título es la línea no vacía anterior
            for k in range(j - 1, -1, -1):
                t = lineas[k].strip()
                if t and not t.endswith(":") and not re.match(r"^[\d;\s]+$", t):
                    titulo = t
                    break
            break
        # La primera línea del bloque es la lista corta de autores — salvo en el
        # PRIMER registro, porque el .txt abre con la cabecera del export:
        #     Scopus
        #     EXPORT DATE: 10 July 2026
        # y sin saltarla el paper 1 se queda con «Scopus» de autor. Es una sola
        # fila de cada corpus, pero es la primera que se ve en la matriz.
        autores = ""
        for ln in lineas:
            t = ln.strip()
            if not t or t == "Scopus" or re.match(r"^EXPORT DATE:", t, re.I):
                continue
            if not re.match(r"^[A-Z][A-Z0-9 /&'-]{2,44}:", t):
                autores = t
                break

        recs.append({
            "id": i,
            "au": limpiar(autores),
            "t": limpiar(titulo),
            "y": anio,
            "rev": limpiar(rev),
            "cit": citas,
            "doi": _campo(b, "DOI").split()[0] if _campo(b, "DOI") else "",
            "dt": _campo(b, "DOCUMENT TYPE"),
            "a": _sin_pie(_campo(b, "ABSTRACT")),
            "k": _campo(b, "AUTHOR KEYWORDS"),
            "afil": _campo(b, "AFFILIATIONS"),
        })
    return recs, len(bloques)


_EXPORT = re.compile(r"^EXPORT DATE:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.I | re.M)
_MES_EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
           "december": 12}
_MES_ES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
           7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
           12: "diciembre"}


def fecha_export(ruta):
    """La cabecera del .txt trae «EXPORT DATE: 10 July 2026». Es el dato honesto
    sobre hasta dónde llega el corpus, y por dos razones.

    La primera es que lo que hace incompleto a un año NO es que el año siga
    corriendo: es el día en que se bajó el archivo. Un export de julio no tiene
    el segundo semestre, y no lo va a tener nunca por mucho que pase el tiempo.
    La frase «2026 está incompleto y lo estará mientras corra el año» caduca;
    «2026 está incompleto EN ESTE EXPORT» es cierta también en 2028.

    La segunda es que el dato está dentro del propio archivo, así que no hay que
    preguntarlo —el contrato es cero preguntas— ni leer el reloj del sistema,
    que haría que el mismo corpus diera un sha256 distinto en enero.

    Devuelve un dict, o uno vacío si el .txt no trae cabecera (un archivo
    editado a mano). En ese caso NO se afirma nada sobre el último año."""
    try:
        with io.open(ruta, encoding="utf-8", errors="replace") as f:
            cab = f.read(500)
    except Exception:
        return {}
    m = _EXPORT.search(cab)
    if not m:
        return {}
    mes = _MES_EN.get(m.group(2).lower())
    return {"anio": int(m.group(3)), "mes": mes,
            "texto": f"{int(m.group(1))} de {_MES_ES.get(mes, m.group(2))} de {m.group(3)}"}


# ─────────────────────────────────────────────────── candado 0 — la entrada

COB_PARA, COB_AVISA = 0.50, 0.80

# Cláusulas de Scopus que piden por INSTITUCIÓN o por AUTOR, no por tema.
_CLAUSULA_AFIL = re.compile(
    r"(?<![A-Za-z-])(AFFILORG|AFFILCOUNTRY|AFFILCITY|AFFIL|AF-ID|AU-ID)"
    r"\s*\(", re.I)


def _norm_titulo(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", t.lower())).strip()


def candado0(recs, nbloques, cfg):
    """Valida la entrada antes de calcular nada. Devuelve (informe, avisos, parar)."""
    n = len(recs)
    avisos, parar = [], []

    if n != nbloques:
        parar.append(f"el archivo trae {nbloques} bloques y se parsearon {n} registros; "
                     "un corpus mal parseado hace falsas todas las cifras siguientes")

    cob = {
        "titulo": sum(1 for r in recs if r["t"].strip()),
        "anio": sum(1 for r in recs if r["y"]),
        "resumen": sum(1 for r in recs if r["a"].strip()),
        "keywords": sum(1 for r in recs if r["k"].strip()),
        "revista": sum(1 for r in recs if r["rev"].strip()),
        "doi": sum(1 for r in recs if r["doi"]),
        "afiliacion": sum(1 for r in recs if r["afil"].strip()),
    }
    for campo, v in cob.items():
        if campo in ("doi", "afiliacion"):
            continue                                    # no bloquean ninguna capa
        if v / n < COB_PARA:
            parar.append(f"solo el {pct(v, n):.0f}% de los registros trae «{campo}»; "
                         "por debajo del 50% no se sostiene ninguna capa")
        elif v / n < COB_AVISA:
            avisos.append(f"«{campo}» cubre el {pct(v, n):.0f}% de los registros")

    # ── duplicados ──────────────────────────────────────────────────────
    por_doi, por_tit = defaultdict(list), defaultdict(list)
    for r in recs:
        if r["doi"]:
            por_doi[r["doi"].lower()].append(r["id"])
        if r["t"].strip():
            por_tit[_norm_titulo(r["t"])].append(r["id"])

    dups, vistos = [], set()
    for doi, ids in sorted(por_doi.items()):
        if len(ids) > 1:
            dups.append({"por": "doi", "clave": doi, "ids": ids,
                         "citas": [next(x["cit"] for x in recs if x["id"] == i) for i in ids]})
            vistos.update(ids[1:])
    for tit, ids in sorted(por_tit.items()):
        if len(ids) > 1 and not any(i in vistos for i in ids):
            dups.append({"por": "titulo", "clave": tit[:70], "ids": ids,
                         "citas": [next(x["cit"] for x in recs if x["id"] == i) for i in ids]})
            vistos.update(ids[1:])

    distintos = [r for r in recs if r["id"] not in vistos]
    if dups:
        avisos.append(f"{len(dups)} paper(es) repetido(s): el export trae {n} registros y "
                      f"{len(distintos)} distintos. Todo lo que sigue cuenta {len(distintos)}")

    # La ecuación declarada dice de qué se bajó el corpus. Una cláusula de
    # afiliación ahí no es un indicio: es la prueba de que el export se pidió por
    # institución y no por tema, y este skill trabaja con corpus temáticos.
    eq = (cfg.get("ecuacion_base") or "")
    m_afil = _CLAUSULA_AFIL.search(eq)
    if m_afil:
        parar.append(f"la ecuación declarada contiene «{m_afil.group(0)}»: este export se bajó por "
                     f"AFILIACIÓN, no por tema. El retrato saldría entero y describiría a una "
                     f"institución, no a un campo. Baja el corpus por tema, o quita esa cláusula de "
                     f"«ecuacion_base» si de verdad quieres el retrato de una institución")

    if not eq.strip():
        avisos.append("no se declaró la ecuación base: la cabecera no podrá mostrarla y el mapa "
                      "de vocabulario no sabrá qué términos neutralizar")

    informe = {
        "n_bloques": nbloques, "n_parseados": n, "n_distintos": len(distintos),
        "cobertura": {k: {"n": v, "pct": pct(v, n)} for k, v in cob.items()},
        "duplicados": dups,
        "descartados": sorted(vistos),
    }
    return informe, avisos, parar, distintos


# ────────────────────────────────────────────────────────── capa 1 — tiempo

RUIDO_COLA = 2        # un año con 1 o 2 registros no es un año: es un in-press adelantado
TECHO_ARRANQUE = 0.10  # si el PRIMER año ya trae esto del pico, el export vino recortado


def capa_tiempo(recs, cfg, export=None):
    export = export or {}
    anios = [int(r["y"]) for r in recs if r["y"].isdigit()]
    if not anios:
        return {"error": "ningún registro trae año"}
    lo, hi = min(anios), max(anios)
    cuenta = Counter(anios)
    serie = {a: cuenta.get(a, 0) for a in range(lo, hi + 1)}   # los años sin papers van con 0
    n, tope = len(anios), max(cuenta.values())

    # ── la cola: años finales con uno o dos registros son ruido, no años ──
    fin_real = hi
    while fin_real > lo and serie[fin_real] <= RUIDO_COLA:
        fin_real -= 1
    cola_ruido = [a for a in range(fin_real + 1, hi + 1) if serie[a]]

    # ── ¿contra qué año se mide si el corpus llega o no hasta el final? ──
    # Por orden: lo que se declare en retrato.json, y si no, la FECHA DEL EXPORT,
    # que viene dentro del .txt. Si no hay ninguna de las dos, no se afirma nada.
    #
    # Antes, sin declarar, se usaba el año más alto del corpus. Con eso
    # `fin_real >= actual` era SIEMPRE verdadero y un corpus que muere en 2019
    # decía «2019 está incompleto y lo estará mientras corra el año», dibujaba su
    # línea de corte, y además corría `ultimo_completo` un año hacia atrás — con
    # lo que el crecimiento se calculaba sobre una ventana equivocada, en
    # silencio. Y es el camino POR DEFECTO: la plantilla trae anio_actual = 0.
    declarado = int(cfg.get("anio_actual") or 0)
    actual = declarado or int(export.get("anio") or 0)
    de_donde = "declarado" if declarado else ("export" if actual else "ninguna")
    parcial = bool(actual) and fin_real >= actual
    # El año incompleto es el del export, no el mayor del corpus: si el corpus
    # trae volumen fechado más allá del export —ahead-of-print—, el que está a
    # medias sigue siendo el del export.
    anio_incompleto = actual if parcial else None
    ultimo_completo = min(fin_real, actual - 1) if parcial else fin_real

    # ── ¿el export viene recortado por fecha? Un campo arranca despacio; un
    #    recorte arranca alto. Si el primer año ya pesa, no hay rampa de entrada.
    recortado = serie[lo] >= TECHO_ARRANQUE * tope

    # año en que se acumula la mitad del corpus
    acum, mediana = 0, hi
    for a in range(lo, hi + 1):
        acum += serie[a]
        if acum >= n / 2:
            mediana = a
            break

    # ── despegue: primer año desde el cual TODOS los años COMPLETOS llegan al
    #    25% del máximo. Nunca se calcula sobre el año en curso ni sobre la cola.
    despegue, motivo = None, ""
    if recortado:
        motivo = (f"el export viene recortado desde {lo} —el primer año ya trae "
                  f"{serie[lo]} registro{'' if serie[lo] == 1 else 's'}—, así que el despegue "
                  f"del campo queda fuera de la ventana y no es medible")
    elif ultimo_completo <= lo:
        motivo = "la ventana de años completos es demasiado corta"
    else:
        umbral = 0.25 * tope
        for a in range(lo, ultimo_completo + 1):
            if all(serie[x] >= umbral for x in range(a, ultimo_completo + 1)):
                despegue = a
                break
        if despegue is None:
            motivo = ("ningún año sostiene el 25% del máximo hasta el final: la serie "
                      "es irregular y no hay un despegue reconocible")

    desde_despegue = sum(serie[x] for x in range(despegue, hi + 1)) if despegue else 0

    # ── crecimiento: solo si los seis años completos existen DE VERDAD ──
    crecimiento, crec_nota = None, ""
    ini = ultimo_completo - 5
    if ini < lo:
        crec_nota = (f"no se calcula: harían falta los años {ini}–{ultimo_completo} y el "
                     f"export empieza en {lo}")
    else:
        ult3 = sum(serie[x] for x in range(ultimo_completo - 2, ultimo_completo + 1))
        pre3 = sum(serie[x] for x in range(ini, ini + 3))
        crecimiento = round(ult3 / pre3, 2) if pre3 else None
        if crecimiento is None:
            crec_nota = "no se calcula: los tres años de referencia están vacíos"

    return {
        "serie": serie, "desde": lo, "hasta": hi, "n": n,
        "anio_mediana": mediana,
        "despegue": despegue, "sin_despegue": motivo,
        "n_desde_despegue": desde_despegue,
        "pct_desde_despegue": pct(desde_despegue, n) if despegue else None,
        "antes_del_despegue": (n - desde_despegue) if despegue else None,
        "pico": {"anio": max(cuenta, key=lambda a: (cuenta[a], -a)), "n": tope},
        "recortado": recortado,
        "ultimo_parcial": parcial, "ultimo_real": fin_real, "ultimo_completo": ultimo_completo,
        "anio_incompleto": anio_incompleto,
        "anio_referencia": actual or None, "referencia_de": de_donde,
        "export": export,
        "cola_ruido": {"anios": cola_ruido, "n": sum(serie[a] for a in cola_ruido)},
        "n_ultimo": serie[fin_real],
        "crecimiento_3a": crecimiento, "crecimiento_nota": crec_nota,
    }


# ──────────────────────────────────────────────────────── capa 7 — revistas

def capa_revistas(recs, top=12):
    c = Counter(r["rev"] for r in recs if r["rev"].strip())
    n = sum(c.values())
    if not n:
        return {"error": "ningún registro trae revista"}
    orden = top_estable(c)
    acum = lambda k: sum(v for _, v in orden[:k])
    return {
        "n_con_revista": n,
        "n_distintas": len(c),
        "top": [{"rev": k, "n": v, "pct": pct(v, n)} for k, v in orden[:top]],
        "pct_top2": pct(acum(2), n),
        "pct_top5": pct(acum(5), n),
        "pct_top10": pct(acum(10), n),
        "n_una_sola": sum(1 for _, v in orden if v == 1),
        "tipos": dict(top_estable(Counter(r["dt"] for r in recs if r["dt"]))),
    }


# ─────────────────────────────────────────────────────────── capa 9 — citas

def _ficha(r, hasta):
    edad = max(1, hasta - int(r["y"]) + 1) if r["y"].isdigit() else 1
    return {"id": r["id"], "t": r["t"], "y": r["y"], "rev": r["rev"], "doi": r["doi"],
            "dt": r["dt"], "cit": r["cit"], "cpa": round(r["cit"] / edad, 1)}


def capa_citas(recs, hasta, top=10, frontera_anios=3):
    """`hasta` es el último año REAL, no el máximo del corpus.

    Scopus fecha los ahead-of-print en el futuro. Con `hasta` = máximo, un solo
    registro de 2027 entre 8.189 estiraba la ventana entera: la frontera se
    rotulaba 2025–2027 —dos años después de que la lámina 1 hubiera dicho que
    2027 «no cuenta como año»— y la edad de TODOS los papers subía uno, con lo
    que cada cifra de citas/año del retrato bajaba alrededor de un 20%. El paper
    más citado del corpus de IA pasaba de 475 a 380 citas/año. Nada se rompía y
    nada se veía."""
    citas = [r["cit"] for r in recs]
    n, total = len(recs), sum(citas)
    if total == 0:
        return {"error": "el export no trae conteos de citas"}
    orden = sorted(recs, key=lambda r: (-r["cit"], r["id"]))
    s = sorted(citas, reverse=True)

    canon = {k: pct(sum(s[:k]), total, 0) for k in (10, 25, 50) if k <= n}
    n_canon = min(50, n)
    en_canon = orden[:n_canon]

    revs_corpus = sum(1 for r in recs if r["dt"].lower() == "review")
    revs_canon = sum(1 for r in en_canon if r["dt"].lower() == "review")

    reciente = [r for r in recs if r["y"].isdigit() and int(r["y"]) > hasta - frontera_anios]
    front = sorted(reciente, key=lambda r: (-r["cit"], r["id"]))[:top]

    # «Casi todos son recientes: no son papers malos, son papers nuevos» era una
    # frase FIJA sobre los papers sin citar. Un paper sin citar de hace ocho años
    # no es nuevo, es ignorado, y son cosas distintas. Aquí se mide.
    ceros = [r for r in recs if r["cit"] == 0]
    ceros_nuevos = sum(1 for r in ceros if r["y"].isdigit() and int(r["y"]) > hasta - frontera_anios)

    # «La de la derecha son papers que NO aparecen en la primera» era otra frase
    # fija, y nada impide que un paper reciente y muy citado esté en las dos.
    en_ambas = sorted({r["id"] for r in front} & {r["id"] for r in orden[:top]})

    return {
        "total": total,
        "mediana": int(statistics.median(citas)),
        "maximo": max(citas),
        "n_cero": len(ceros),
        "pct_cero": pct(len(ceros), n),
        "cero": {"n": len(ceros), "recientes": ceros_nuevos,
                 "pct_recientes": pct(ceros_nuevos, len(ceros)),
                 "desde": hasta - frontera_anios + 1},
        "canon": canon,
        "n_canon": n_canon,
        "mas_citados": [_ficha(r, hasta) for r in orden[:top]],
        "por_anio": [_ficha(r, hasta) for r in
                     sorted(recs, key=lambda r: (-_ficha(r, hasta)["cpa"], r["id"]))[:top]],
        "frontera": {
            "desde": hasta - frontera_anios + 1,
            "n": len(reciente),
            "papers": [_ficha(r, hasta) for r in front],
            "en_ambas": en_ambas,
        },
        "revisiones": {
            "corpus": revs_corpus, "pct_corpus": pct(revs_corpus, n),
            "canon": revs_canon, "pct_canon": pct(revs_canon, n_canon),
            "razon": round((revs_canon / n_canon) / (revs_corpus / n), 2) if revs_corpus else None,
        },
        "sin_doi": {
            "n": sum(1 for r in recs if not r["doi"]),
            "en_canon": [r["id"] for r in en_canon if not r["doi"]],
            "ids": [r["id"] for r in recs if not r["doi"]],
        },
    }


# ─────────────────────────────────────────────────── recursos de referencia

_FICHAS = json.loads('{"regiones.json": "{\\n \\"_que_es\\": \\"Regi\\u00f3n DEL ESTUDIO, le\\u00edda del resumen: d\\u00f3nde dice el paper que trabaj\\u00f3. No es la afiliaci\\u00f3n de los autores \\u2014eso va en paises.json y significa otra cosa.\\",\\n \\"_sin_declarar\\": \\"Sin regi\\u00f3n decl.\\",\\n \\"_glosa_sin_declarar\\": \\"Papers que no dicen a qu\\u00e9 regi\\u00f3n se refieren: estudios globales, te\\u00f3ricos o de modelaci\\u00f3n sin pa\\u00eds nombrado. No es un vac\\u00edo, es el dato que falta.\\",\\n \\"familias\\": {\\n  \\"\\u00c1frica subs.\\": {\\n   \\"patrones\\": [\\n    \\"sub.saharan\\",\\n    \\"\\\\\\\\bethiopia\\",\\n    \\"\\\\\\\\bkenya\\\\\\\\b\\",\\n    \\"\\\\\\\\bghana\\\\\\\\b\\",\\n    \\"\\\\\\\\bnigeria\\\\\\\\b\\",\\n    \\"\\\\\\\\btanzania\\",\\n    \\"\\\\\\\\buganda\\\\\\\\b\\",\\n    \\"\\\\\\\\bmalawi\\\\\\\\b\\",\\n    \\"\\\\\\\\bzambia\\\\\\\\b\\",\\n    \\"\\\\\\\\bzimbabwe\\\\\\\\b\\",\\n    \\"burkina faso\\",\\n    \\"\\\\\\\\bmali\\\\\\\\b\\",\\n    \\"\\\\\\\\bsenegal\\\\\\\\b\\",\\n    \\"\\\\\\\\bmozambique\\\\\\\\b\\",\\n    \\"\\\\\\\\brwanda\\\\\\\\b\\",\\n    \\"\\\\\\\\bcameroon\\\\\\\\b\\",\\n    \\"\\\\\\\\bbenin\\\\\\\\b\\",\\n    \\"\\\\\\\\bniger\\\\\\\\b\\",\\n    \\"south africa\\",\\n    \\"\\\\\\\\bc\\u00f4te d.ivoire|\\\\\\\\bivory coast\\",\\n    \\"(?<!north )(?<!northern )\\\\\\\\bafrican?\\\\\\\\b\\",\\n    \\"\\\\\\\\bsomalia\\\\\\\\b\\",\\n    \\"\\\\\\\\bcongo\\\\\\\\b|\\\\\\\\bdrc\\\\\\\\b\\",\\n    \\"\\\\\\\\bsudan\\\\\\\\b\\",\\n    \\"\\\\\\\\bchad\\\\\\\\b\\",\\n    \\"\\\\\\\\bangola\\\\\\\\b\\",\\n    \\"\\\\\\\\bmadagascar\\\\\\\\b\\",\\n    \\"\\\\\\\\bsierra leone\\\\\\\\b\\",\\n    \\"\\\\\\\\bnamibia\\\\\\\\b\\",\\n    \\"\\\\\\\\bbotswana\\\\\\\\b\\",\\n    \\"\\\\\\\\blesotho\\\\\\\\b\\",\\n    \\"\\\\\\\\btogo\\\\\\\\b\\",\\n    \\"\\\\\\\\bliberia\\\\\\\\b\\"\\n   ],\\n   \\"glosa\\": \\"<b>\\u00c1frica subsahariana</b> \\u2014 \\u00c1frica al sur del S\\u00e1hara: Etiop\\u00eda, Kenia, Ghana, Nigeria, Tanzania, Uganda, Malaui, Zambia, Zimbabue, Burkina Faso, Mal\\u00ed, Senegal, Mozambique, Ruanda, Camer\\u00fan, Ben\\u00edn, N\\u00edger, Sud\\u00e1frica y Costa de Marfil. <b>Es la columna de referencia:</b> cada casilla se contrasta contra ella porque es la regi\\u00f3n dominante del campo.\\"\\n  },\\n  \\"Asia del Sur\\": {\\n   \\"patrones\\": [\\n    \\"south asia\\",\\n    \\"\\\\\\\\bindia\\\\\\\\b\\",\\n    \\"\\\\\\\\bindian\\\\\\\\b\\",\\n    \\"\\\\\\\\bpakistan\\",\\n    \\"\\\\\\\\bbangladesh\\",\\n    \\"\\\\\\\\bnepal\\\\\\\\b\\",\\n    \\"sri lanka\\",\\n    \\"\\\\\\\\bafghanistan\\\\\\\\b\\"\\n   ],\\n   \\"glosa\\": \\"<b>Asia del Sur</b> \\u2014 India, Pakist\\u00e1n, Banglad\\u00e9s, Nepal y Sri Lanka.\\"\\n  },\\n  \\"Asia Or. y SE\\": {\\n   \\"patrones\\": [\\n    \\"\\\\\\\\bchina\\\\\\\\b|\\\\\\\\bchinese\\\\\\\\b\\",\\n    \\"\\\\\\\\bvietnam\\",\\n    \\"\\\\\\\\bindonesia\\",\\n    \\"\\\\\\\\bthailand\\",\\n    \\"\\\\\\\\bphilippine\\",\\n    \\"\\\\\\\\bmalaysia\\",\\n    \\"\\\\\\\\bcambodia\\",\\n    \\"\\\\\\\\bmyanmar\\",\\n    \\"southeast asia|south.east asia\\",\\n    \\"\\\\\\\\bjapan\\",\\n    \\"\\\\\\\\bkorea\\",\\n    \\"\\\\\\\\btaiwan\\\\\\\\b\\",\\n    \\"\\\\\\\\bmongolia\\\\\\\\b\\",\\n    \\"\\\\\\\\blaos\\\\\\\\b|\\\\\\\\blao pdr\\\\\\\\b\\",\\n    \\"\\\\\\\\bsingapore\\\\\\\\b\\",\\n    \\"east asia\\"\\n   ],\\n   \\"glosa\\": \\"<b>Asia Oriental y Sudeste</b> \\u2014 China, Vietnam, Indonesia, Tailandia, Filipinas, Malasia, Camboya y Myanmar. China aporta por s\\u00ed sola m\\u00e1s de la mitad de la columna.\\"\\n  },\\n  \\"Am. Latina\\": {\\n   \\"patrones\\": [\\n    \\"latin america\\",\\n    \\"\\\\\\\\bbrazil|\\\\\\\\bbrazilian\\\\\\\\b\\",\\n    \\"\\\\\\\\bmexico\\\\\\\\b|\\\\\\\\bmexican\\\\\\\\b\\",\\n    \\"\\\\\\\\bperu\\\\\\\\b|\\\\\\\\bperuvian\\\\\\\\b\\",\\n    \\"\\\\\\\\becuador\\",\\n    \\"\\\\\\\\bcolombia\\",\\n    \\"\\\\\\\\bchile\\\\\\\\b\\",\\n    \\"\\\\\\\\bargentin\\",\\n    \\"\\\\\\\\bbolivia\\",\\n    \\"\\\\\\\\bcaribbean\\\\\\\\b\\",\\n    \\"central america|\\\\\\\\bguatemala|\\\\\\\\bhonduras|\\\\\\\\bnicaragua|costa rica\\",\\n    \\"\\\\\\\\buruguay\\\\\\\\b\\",\\n    \\"\\\\\\\\bvenezuela\\\\\\\\b\\",\\n    \\"\\\\\\\\bparaguay\\\\\\\\b\\",\\n    \\"\\\\\\\\bpanama\\\\\\\\b\\",\\n    \\"south america\\"\\n   ],\\n   \\"glosa\\": \\"<b>Am\\u00e9rica Latina y el Caribe.</b> <b>Es la columna foco:</b> una casilla delgada aqu\\u00ed, con la fila viva en el resto del mundo, es donde vive la oportunidad para esta facultad.\\"\\n  },\\n  \\"Europa\\": {\\n   \\"patrones\\": [\\n    \\"\\\\\\\\beurope\\",\\n    \\"european union|\\\\\\\\beu\\\\\\\\b\\",\\n    \\"\\\\\\\\bspain\\\\\\\\b|\\\\\\\\bspanish\\\\\\\\b\\",\\n    \\"\\\\\\\\bitaly\\\\\\\\b|\\\\\\\\bitalian\\\\\\\\b\\",\\n    \\"\\\\\\\\bgermany\\\\\\\\b|\\\\\\\\bgerman\\\\\\\\b\\",\\n    \\"\\\\\\\\bfrance\\\\\\\\b|\\\\\\\\bfrench\\\\\\\\b\\",\\n    \\"\\\\\\\\bpoland\\\\\\\\b\\",\\n    \\"netherlands|\\\\\\\\bdutch\\\\\\\\b\\",\\n    \\"\\\\\\\\bgreece\\\\\\\\b\\",\\n    \\"\\\\\\\\bportugal\\",\\n    \\"\\\\\\\\bukraine\\\\\\\\b|\\\\\\\\bukrainian\\\\\\\\b\\",\\n    \\"\\\\\\\\brussia\\",\\n    \\"\\\\\\\\bsweden\\\\\\\\b|\\\\\\\\bswedish\\\\\\\\b\\",\\n    \\"\\\\\\\\baustria\\",\\n    \\"\\\\\\\\bswitzerland\\\\\\\\b|\\\\\\\\bswiss\\\\\\\\b\\",\\n    \\"\\\\\\\\bnorway\\\\\\\\b\\",\\n    \\"\\\\\\\\bireland\\\\\\\\b|\\\\\\\\birish\\\\\\\\b\\",\\n    \\"\\\\\\\\bczech\\",\\n    \\"\\\\\\\\bromania\\",\\n    \\"\\\\\\\\bdenmark\\\\\\\\b|\\\\\\\\bdanish\\\\\\\\b\\",\\n    \\"\\\\\\\\bhungary\\\\\\\\b\\",\\n    \\"\\\\\\\\bbulgaria\\\\\\\\b\\",\\n    \\"\\\\\\\\bserbia\\\\\\\\b\\",\\n    \\"\\\\\\\\bcroatia\\\\\\\\b\\",\\n    \\"\\\\\\\\bslovak|\\\\\\\\bslovenia\\\\\\\\b\\",\\n    \\"\\\\\\\\blithuania\\\\\\\\b|\\\\\\\\blatvia\\\\\\\\b|\\\\\\\\bestonia\\\\\\\\b\\",\\n    \\"united kingdom|\\\\\\\\bbritain\\\\\\\\b|\\\\\\\\bbritish\\\\\\\\b\\"\\n   ],\\n   \\"glosa\\": \\"<b>Europa</b> \\u2014 Europa continental y la Uni\\u00f3n Europea.\\"\\n  },\\n  \\"Am. del Norte\\": {\\n   \\"patrones\\": [\\n    \\"united states\\",\\n    \\"\\\\\\\\bu\\\\\\\\.s\\\\\\\\.\\\\\\\\b|\\\\\\\\busa\\\\\\\\b\\",\\n    \\"\\\\\\\\bcanada\\\\\\\\b|\\\\\\\\bcanadian\\\\\\\\b\\",\\n    \\"north america\\"\\n   ],\\n   \\"glosa\\": \\"<b>Am\\u00e9rica del Norte</b> \\u2014 Estados Unidos y Canad\\u00e1.\\"\\n  },\\n  \\"Ocean\\u00eda\\": {\\n   \\"patrones\\": [\\n    \\"\\\\\\\\baustralia\\",\\n    \\"new zealand\\",\\n    \\"pacific island\\"\\n   ],\\n   \\"glosa\\": \\"<b>Ocean\\u00eda</b> \\u2014 Australia, Nueva Zelanda y las islas del Pac\\u00edfico. Columna delgada (58 papers): no sostiene conclusiones.\\"\\n  },\\n  \\"Medio Oriente\\": {\\n   \\"patrones\\": [\\n    \\"middle east\\",\\n    \\"\\\\\\\\biran\\\\\\\\b|\\\\\\\\biranian\\\\\\\\b\\",\\n    \\"\\\\\\\\begypt\\",\\n    \\"\\\\\\\\bmorocco\\\\\\\\b\\",\\n    \\"\\\\\\\\btunisia\\\\\\\\b\\",\\n    \\"\\\\\\\\bturkey\\\\\\\\b|\\\\\\\\bturkish\\\\\\\\b\\",\\n    \\"\\\\\\\\bjordan\\\\\\\\b\\",\\n    \\"saudi arabia\\",\\n    \\"north africa\\",\\n    \\"\\\\\\\\biraq\\",\\n    \\"\\\\\\\\bisrael\\",\\n    \\"\\\\\\\\balgeria\\",\\n    \\"\\\\\\\\blibya\\\\\\\\b\\",\\n    \\"\\\\\\\\bsyria\\",\\n    \\"\\\\\\\\blebanon\\\\\\\\b\\",\\n    \\"\\\\\\\\byemen\\\\\\\\b\\",\\n    \\"\\\\\\\\boman\\\\\\\\b\\",\\n    \\"\\\\\\\\bqatar\\\\\\\\b\\",\\n    \\"\\\\\\\\bkuwait\\\\\\\\b\\",\\n    \\"united arab emirates\\",\\n    \\"\\\\\\\\bpalestin\\"\\n   ],\\n   \\"glosa\\": \\"<b>Medio Oriente y Norte de \\u00c1frica</b> \\u2014 del Magreb a Ir\\u00e1n, incluida Turqu\\u00eda.\\"\\n  }\\n }\\n}", "paises.json": "{\\n \\"_que_es\\": \\"Pa\\u00eds de AFILIACI\\u00d3N \\u2192 regi\\u00f3n. Scopus escribe el pa\\u00eds como \\u00faltimo campo de cada direcci\\u00f3n en AFFILIATIONS, as\\u00ed que basta con emparejar ese \\u00faltimo token.\\",\\n \\"_ojo\\": \\"Esto dice de d\\u00f3nde son los autores, NO d\\u00f3nde se hizo el estudio. Un equipo de Wageningen puede estudiar hogares de Kenia. Nunca fusionar con regiones.json.\\",\\n \\"_como_se_amplia\\": \\"Si el candado 0 reporta pa\\u00edses no reconocidos, se a\\u00f1aden aqu\\u00ed con la graf\\u00eda exacta que usa Scopus.\\",\\n \\"regiones\\": {\\n  \\"Europa\\": [\\n   \\"United Kingdom\\",\\n   \\"Italy\\",\\n   \\"Poland\\",\\n   \\"Romania\\",\\n   \\"Germany\\",\\n   \\"Portugal\\",\\n   \\"Sweden\\",\\n   \\"Spain\\",\\n   \\"Netherlands\\",\\n   \\"Denmark\\",\\n   \\"Hungary\\",\\n   \\"Greece\\",\\n   \\"Switzerland\\",\\n   \\"Serbia\\",\\n   \\"Norway\\",\\n   \\"Austria\\",\\n   \\"Belgium\\",\\n   \\"Lithuania\\",\\n   \\"Finland\\",\\n   \\"Ireland\\",\\n   \\"France\\",\\n   \\"Czech Republic\\",\\n   \\"Czechia\\",\\n   \\"Russian Federation\\",\\n   \\"Russia\\",\\n   \\"Bosnia and Herzegovina\\",\\n   \\"Latvia\\",\\n   \\"Slovenia\\",\\n   \\"Croatia\\",\\n   \\"Slovakia\\",\\n   \\"Iceland\\",\\n   \\"North Macedonia\\",\\n   \\"Macedonia\\",\\n   \\"Albania\\",\\n   \\"Estonia\\",\\n   \\"Georgia\\",\\n   \\"Ukraine\\",\\n   \\"Belarus\\",\\n   \\"Bulgaria\\",\\n   \\"Montenegro\\",\\n   \\"Moldova\\",\\n   \\"Luxembourg\\",\\n   \\"Malta\\",\\n   \\"Cyprus\\",\\n   \\"Monaco\\",\\n   \\"Liechtenstein\\",\\n   \\"Andorra\\",\\n   \\"San Marino\\",\\n   \\"Kosovo\\"\\n  ],\\n  \\"Am. del Norte\\": [\\n   \\"United States\\",\\n   \\"Canada\\"\\n  ],\\n  \\"Asia Or. y SE\\": [\\n   \\"China\\",\\n   \\"Malaysia\\",\\n   \\"Japan\\",\\n   \\"Indonesia\\",\\n   \\"Taiwan\\",\\n   \\"Thailand\\",\\n   \\"South Korea\\",\\n   \\"Korea\\",\\n   \\"Republic of Korea\\",\\n   \\"Viet Nam\\",\\n   \\"Vietnam\\",\\n   \\"Hong Kong\\",\\n   \\"Macao\\",\\n   \\"Macau\\",\\n   \\"Singapore\\",\\n   \\"Philippines\\",\\n   \\"Brunei Darussalam\\",\\n   \\"Brunei\\",\\n   \\"Cambodia\\",\\n   \\"Lao People\'s Democratic Republic\\",\\n   \\"Laos\\",\\n   \\"Myanmar\\",\\n   \\"Mongolia\\",\\n   \\"Timor-Leste\\"\\n  ],\\n  \\"Asia del Sur\\": [\\n   \\"India\\",\\n   \\"Pakistan\\",\\n   \\"Bangladesh\\",\\n   \\"Sri Lanka\\",\\n   \\"Nepal\\",\\n   \\"Afghanistan\\",\\n   \\"Bhutan\\",\\n   \\"Maldives\\"\\n  ],\\n  \\"Medio Oriente\\": [\\n   \\"Turkey\\",\\n   \\"T\\u00fcrkiye\\",\\n   \\"Iran\\",\\n   \\"Saudi Arabia\\",\\n   \\"United Arab Emirates\\",\\n   \\"Lebanon\\",\\n   \\"Qatar\\",\\n   \\"Israel\\",\\n   \\"Palestine\\",\\n   \\"Jordan\\",\\n   \\"Oman\\",\\n   \\"Bahrain\\",\\n   \\"Iraq\\",\\n   \\"Kuwait\\",\\n   \\"Syrian Arab Republic\\",\\n   \\"Syria\\",\\n   \\"Yemen\\"\\n  ],\\n  \\"Ocean\\u00eda\\": [\\n   \\"Australia\\",\\n   \\"New Zealand\\",\\n   \\"Samoa\\",\\n   \\"Fiji\\",\\n   \\"Papua New Guinea\\",\\n   \\"Vanuatu\\",\\n   \\"Solomon Islands\\",\\n   \\"Tonga\\",\\n   \\"New Caledonia\\",\\n   \\"French Polynesia\\"\\n  ],\\n  \\"Am. Latina y Caribe\\": [\\n   \\"Antigua and Barbuda\\",\\n   \\"Argentina\\",\\n   \\"Aruba\\",\\n   \\"Bahamas\\",\\n   \\"Barbados\\",\\n   \\"Belize\\",\\n   \\"Bermuda\\",\\n   \\"Bolivia\\",\\n   \\"Brazil\\",\\n   \\"Cayman Islands\\",\\n   \\"Chile\\",\\n   \\"Colombia\\",\\n   \\"Costa Rica\\",\\n   \\"Cuba\\",\\n   \\"Curacao\\",\\n   \\"Cura\\u00e7ao\\",\\n   \\"Dominica\\",\\n   \\"Dominican Republic\\",\\n   \\"Ecuador\\",\\n   \\"El Salvador\\",\\n   \\"French Guiana\\",\\n   \\"Grenada\\",\\n   \\"Guadeloupe\\",\\n   \\"Guatemala\\",\\n   \\"Guyana\\",\\n   \\"Haiti\\",\\n   \\"Honduras\\",\\n   \\"Jamaica\\",\\n   \\"Martinique\\",\\n   \\"Mexico\\",\\n   \\"Nicaragua\\",\\n   \\"Panama\\",\\n   \\"Paraguay\\",\\n   \\"Peru\\",\\n   \\"Puerto Rico\\",\\n   \\"Saint Kitts and Nevis\\",\\n   \\"Saint Lucia\\",\\n   \\"Saint Vincent and the Grenadines\\",\\n   \\"Suriname\\",\\n   \\"Trinidad and Tobago\\",\\n   \\"Uruguay\\",\\n   \\"Venezuela\\"\\n  ],\\n  \\"\\u00c1frica subs.\\": [\\n   \\"South Africa\\",\\n   \\"Ghana\\",\\n   \\"Kenya\\",\\n   \\"Nigeria\\",\\n   \\"Ethiopia\\",\\n   \\"Cameroon\\",\\n   \\"Zimbabwe\\",\\n   \\"Tanzania\\",\\n   \\"Uganda\\",\\n   \\"Zambia\\",\\n   \\"Malawi\\",\\n   \\"Mozambique\\",\\n   \\"Botswana\\",\\n   \\"Namibia\\",\\n   \\"Senegal\\",\\n   \\"C\\u00f4te d\'Ivoire\\",\\n   \\"Ivory Coast\\",\\n   \\"Benin\\",\\n   \\"Burkina Faso\\",\\n   \\"Mali\\",\\n   \\"Niger\\",\\n   \\"Rwanda\\",\\n   \\"Burundi\\",\\n   \\"Democratic Republic Congo\\",\\n   \\"Congo\\",\\n   \\"Angola\\",\\n   \\"Madagascar\\",\\n   \\"Mauritius\\",\\n   \\"Sierra Leone\\",\\n   \\"Liberia\\",\\n   \\"Togo\\",\\n   \\"Gambia\\",\\n   \\"Guinea\\",\\n   \\"Somalia\\",\\n   \\"South Sudan\\",\\n   \\"Sudan\\",\\n   \\"Eritrea\\",\\n   \\"Lesotho\\",\\n   \\"Eswatini\\",\\n   \\"Swaziland\\",\\n   \\"Gabon\\",\\n   \\"Seychelles\\",\\n   \\"Cabo Verde\\",\\n   \\"Cape Verde\\"\\n  ],\\n  \\"\\u00c1frica del Norte\\": [\\n   \\"Tunisia\\",\\n   \\"Algeria\\",\\n   \\"Egypt\\",\\n   \\"Morocco\\",\\n   \\"Libya\\",\\n   \\"Mauritania\\"\\n  ],\\n  \\"Asia Central y C\\u00e1ucaso\\": [\\n   \\"Uzbekistan\\",\\n   \\"Azerbaijan\\",\\n   \\"Kazakhstan\\",\\n   \\"Kyrgyzstan\\",\\n   \\"Tajikistan\\",\\n   \\"Turkmenistan\\",\\n   \\"Armenia\\"\\n  ]\\n }\\n}", "metodos.json": "{\\n  \\"_que_es\\": \\"C\\u00f3mo se recogi\\u00f3 y trat\\u00f3 el dato. Gen\\u00e9rico: estos instrumentos existen en cualquier disciplina emp\\u00edrica, as\\u00ed que no hay que declararlos por tema.\\",\\n  \\"_regla\\": \\"Un paper puede llevar varios m\\u00e9todos; la suma pasa del total y as\\u00ed debe mostrarse.\\",\\n  \\"_techo\\": \\"Se lee el RESUMEN. Un estudio que hizo encuesta y no la menciona en el resumen no aparece aqu\\u00ed. Mide lo que el campo declara, no lo que hizo.\\",\\n\\n  \\"familias\\": {\\n    \\"Encuesta o cuestionario\\": [\\n      \\"\\\\\\\\bsurveys?\\\\\\\\b\\", \\"questionnaires?\\", \\"self-reported\\", \\"respondents\\"\\n    ],\\n    \\"Entrevistas y cualitativo\\": [\\n      \\"\\\\\\\\binterviews?\\\\\\\\b\\", \\"qualitative\\", \\"focus group\\", \\"thematic analysis\\",\\n      \\"content analysis\\", \\"grounded theory\\", \\"ethnograph\\"\\n    ],\\n    \\"Experimento o intervenci\\u00f3n\\": [\\n      \\"\\\\\\\\bexperiments?\\\\\\\\b\\", \\"experimental design\\", \\"randomi[sz]ed\\", \\"\\\\\\\\btrial\\\\\\\\b\\",\\n      \\"interventions? (?:study|studies|trial|group|design|programme|program|arm)\\",\\n      \\"(?:conducted|implemented|delivered|tested|evaluated) (?:an?|the|two|three) [^.;]{0,30}\\\\\\\\bintervention\\",\\n      \\"pre-?post (?:design|test)\\", \\"treatment group\\", \\"control group\\", \\"choice experiment\\",\\n      \\"quasi-experiment\\"\\n    ],\\n    \\"Modelo estructural (SEM/PLS)\\": [\\n      \\"structural equation\\", \\"\\\\\\\\bSEM\\\\\\\\b\\", \\"\\\\\\\\bPLS\\\\\\\\b\\", \\"partial least squares\\",\\n      \\"confirmatory factor\\", \\"path analysis\\"\\n    ],\\n    \\"Regresi\\u00f3n y econometr\\u00eda\\": [\\n      \\"regression\\", \\"\\\\\\\\blogit\\\\\\\\b\\", \\"\\\\\\\\bprobit\\\\\\\\b\\", \\"\\\\\\\\btobit\\\\\\\\b\\", \\"fixed[- ]effects\\",\\n      \\"random[- ]effects\\", \\"instrumental variable\\", \\"difference-in-difference\\",\\n      \\"propensity score\\", \\"econometric\\", \\"\\\\\\\\bpanel data\\\\\\\\b\\"\\n    ],\\n    \\"Revisi\\u00f3n y bibliometr\\u00eda\\": [\\n      \\"systematic (literature )?review\\", \\"scoping review\\", \\"narrative review\\",\\n      \\"meta-analys\\", \\"bibliometric\\", \\"\\\\\\\\bPRISMA\\\\\\\\b\\", \\"literature review\\"\\n    ],\\n    \\"Medici\\u00f3n directa u observaci\\u00f3n\\": [\\n      \\"waste composition\\", \\"direct measurement\\", \\"\\\\\\\\bweigh(ed|ing|t-based)\\\\\\\\b\\",\\n      \\"\\\\\\\\bdiary\\\\\\\\b\\", \\"diaries\\", \\"observational study\\", \\"field observation\\", \\"audit\\"\\n    ],\\n    \\"Estudio de caso\\": [\\n      \\"case study\\", \\"case studies\\"\\n    ],\\n    \\"Conglomerados y segmentaci\\u00f3n\\": [\\n      \\"cluster analysis\\", \\"k-means\\", \\"latent class\\", \\"segmentation\\"\\n    ],\\n    \\"Simulaci\\u00f3n y modelado\\": [\\n      \\"simulation\\", \\"agent-based\\", \\"monte carlo\\", \\"scenario analysis\\",\\n      \\"life cycle assessment\\", \\"\\\\\\\\bLCA\\\\\\\\b\\", \\"system dynamics\\"\\n    ],\\n    \\"Ensayo de campo y dise\\u00f1o agron\\u00f3mico\\": [\\n      \\"field (?:trial|experiment|study)\\", \\"randomi[sz]ed complete block\\",\\n      \\"\\\\\\\\bRCBD\\\\\\\\b\\", \\"split-?plot\\", \\"completely randomi[sz]ed design\\",\\n      \\"(?:experimental|field|research|demonstration|treatment) plots?\\",\\n      \\"greenhouse (?:experiment|trial|study|conditions|pot)\\",\\n      \\"nursery\\", \\"cultivar (?:trial|evaluation)\\",\\n      \\"agronomic (?:trial|evaluation)\\"\\n    ],\\n    \\"Laboratorio y an\\u00e1lisis instrumental\\": [\\n      \\"in vitro\\", \\"in vivo\\", \\"\\\\\\\\bbioassay\\", \\"laboratory (?:analysis|trial|experiment)\\",\\n      \\"chromatograph\\", \\"spectroscop\\", \\"\\\\\\\\bHPLC\\\\\\\\b\\", \\"\\\\\\\\bPCR\\\\\\\\b\\", \\"sequencing\\",\\n      \\"physicochemical (?:analysis|characteri[sz]ation)\\", \\"proximate analysis\\",\\n      \\"microbiological analysis\\", \\"titrat\\"\\n    ],\\n    \\"Evaluaci\\u00f3n sensorial\\": [\\n      \\"sensory (?:evaluation|analysis|panel|attributes)\\", \\"hedonic (?:scale|test)\\",\\n      \\"taste panel\\", \\"triangle test\\", \\"consumer panel\\"\\n    ],\\n    \\"Muestreo y trabajo de terreno\\": [\\n      \\"sampling (?:design|strategy|campaign)\\", \\"transects?\\", \\"quadrats?\\",\\n      \\"soil sampl\\", \\"water sampl\\", \\"field survey\\", \\"georeferenc\\",\\n      \\"remote sensing\\", \\"\\\\\\\\bGIS\\\\\\\\b\\", \\"satellite imagery\\"\\n    ],\\n    \\"An\\u00e1lisis documental y discursivo\\": [\\n      \\"document analysis\\", \\"discourse analysis\\", \\"narrative (?:analysis|inquiry)\\",\\n      \\"hermeneutic\\", \\"textual analysis\\", \\"archival research\\", \\"corpus analysis\\"\\n    ]\\n  },\\n\\n  \\"_nota_dominio\\": \\"Las seis \\u00faltimas familias se a\\u00f1adieron tras probar el skill en un corpus de agronom\\u00eda, donde el 54% de los papers sal\\u00eda \\u00absin m\\u00e9todo declarado\\u00bb \\u2014 no porque no lo declararan, sino porque la ficha estaba escrita con vocabulario de ciencias sociales. Si aparece otro dominio con una tasa alta de no declarados, mirar sus res\\u00famenes antes de dar el dato por bueno.\\",\\n\\n  \\"_patrones_retirados\\": \\"Medido patr\\u00f3n a patr\\u00f3n sobre los tres corpus de trabajo, contando cu\\u00e1ntos papers depend\\u00edan SOLO de cada uno. Un patr\\u00f3n que nombra el TEMA en vez del DISE\\u00d1O infla su familia y la l\\u00e1mina corona un instrumento que el campo no usa: es el defecto que sale impecable y no es cierto. Retirados o estrechados: \\u00abgreenhouse\\u00bb reclamaba 330 papers en el corpus de cambio clim\\u00e1tico y 314 depend\\u00edan solo de \\u00e9l \\u2014era \\u00abgreenhouse gas emissions\\u00bb\\u2014, as\\u00ed que ahora exige que sea un invernadero usado como instalaci\\u00f3n; \\u00abgrowing season\\u00bb (58) y \\u00abharvest\\u00bb (72) son periodos del cultivo, no dise\\u00f1os, y se fueron; \\u00abplots\\u00bb (56) casaba con \\u00abbox plots\\u00bb y \\u00abscatter plots\\u00bb, as\\u00ed que ahora exige el adjetivo; \\u00abpanel data\\u00bb (211) es econometr\\u00eda y no una encuesta, y se mud\\u00f3 de familia \\u2014eso solo bastaba para decidir cu\\u00e1l era el instrumento dominante del corpus, que iba 734 contra 724\\u2014; \\u00abintervention\\u00bb a secas reclamaba 127 papers en el corpus de desperdicio y 113 depend\\u00edan solo de \\u00e9l, casi siempre en \\u00abthe need for tailored interventions\\u00bb, que es una recomendaci\\u00f3n de pol\\u00edtica y no un experimento: ahora exige que la intervenci\\u00f3n se haya hecho.\\",\\n\\n  \\"_como_auditar\\": \\"Ante un dominio nuevo, contar para cada patr\\u00f3n cu\\u00e1ntos papers lo activan y cu\\u00e1ntos dependen SOLO de \\u00e9l. Si un patr\\u00f3n sostiene por s\\u00ed mismo m\\u00e1s de la mitad de su familia, leer veinte res\\u00famenes suyos antes de creerse la cifra.\\"\\n}\\n", "relaciones.json": "{\\n  \\"_que_es\\": \\"Marcos gramaticales con los que un autor declara que algo se relaciona con algo. Gen\\u00e9ricos: pertenecen al ingl\\u00e9s acad\\u00e9mico, no al tema.\\",\\n\\n  \\"_por_que_no_se_recortan_las_ranuras\\": \\"Se prob\\u00f3 extraer X e Y con grupos de captura y falla: la gram\\u00e1tica se dobla de m\\u00e1s maneras de las que un patr\\u00f3n prev\\u00e9 \\u2014\\u00abpandemic had various influences on people\'s lives\\u00bb devuelve basura\\u2014. Peor a\\u00fan, parte de las frases lleva negaci\\u00f3n y un recorte mec\\u00e1nico INVIERTE EL SENTIDO: \\u00abage does not predict leftover packaging behavior\\u00bb se convierte en \\u00abage \\u2192 leftover packaging behavior\\u00bb. Por eso esta capa guarda LA ORACI\\u00d3N ENTERA Y TEXTUAL, y quien nombra los constructos lee la oraci\\u00f3n completa, con su negaci\\u00f3n incluida.\\",\\n\\n  \\"_reparto\\": \\"Python recorta (barato, exacto, imposible de fabricar). El modelo lee las oraciones recortadas \\u2014una fracci\\u00f3n del corpus\\u2014 y nombra los constructos. Nunca al rev\\u00e9s.\\",\\n\\n  \\"marcos\\": {\\n    \\"efecto\\":    [\\"\\\\\\\\b(?:effects?|impacts?|influence)s? of\\\\\\\\b[^.;]{3,80}\\\\\\\\bon\\\\\\\\b\\"],\\n    \\"mediador\\":  [\\"\\\\\\\\b(?:mediating|moderating) (?:role|effect|variable)\\", \\"\\\\\\\\bmediat(?:e|es|ed|ing)\\\\\\\\b\\", \\"\\\\\\\\bmoderat(?:e|es|ed|ing)\\\\\\\\b\\"],\\n    \\"papel\\":     [\\"\\\\\\\\brole of\\\\\\\\b[^.;]{3,80}\\\\\\\\b(?:in|on|for)\\\\\\\\b\\"],\\n    \\"relacion\\":  [\\"\\\\\\\\b(?:relationships?|associations?|links?|nexus|correlations?|interplay) between\\\\\\\\b\\"],\\n    \\"predictor\\": [\\"\\\\\\\\b(?:predictors?|determinants?|antecedents?|drivers?|factors|causes)\\\\\\\\b[^.;]{0,20}\\\\\\\\b(?:of|affecting|influencing|driving|shaping|underlying)\\\\\\\\b\\"],\\n    \\"verbo\\":     [\\"\\\\\\\\b(?:affects?|influences?|predicts?|determines?|shapes?|drives?|explains?)\\\\\\\\b\\"],\\n    \\"asociado\\":  [\\"\\\\\\\\b(?:positively|negatively|significantly|strongly|weakly) (?:associated|correlated|related|linked)\\\\\\\\b\\"],\\n    \\"condicion\\": [\\"\\\\\\\\bdepends? on\\\\\\\\b\\", \\"\\\\\\\\bconditional on\\\\\\\\b\\", \\"\\\\\\\\bcontingent on\\\\\\\\b\\"]\\n  },\\n\\n  \\"negacion\\": [\\n    \\"\\\\\\\\bdid not\\\\\\\\b\\", \\"\\\\\\\\bdoes not\\\\\\\\b\\", \\"\\\\\\\\bdo not\\\\\\\\b\\", \\"\\\\\\\\bwas not\\\\\\\\b\\", \\"\\\\\\\\bwere not\\\\\\\\b\\",\\n    \\"\\\\\\\\bno significant\\\\\\\\b\\", \\"\\\\\\\\bnot significant\\", \\"\\\\\\\\bnon-?significant\\\\\\\\b\\",\\n    \\"\\\\\\\\bnor did\\\\\\\\b\\", \\"\\\\\\\\bneither\\\\\\\\b\\", \\"\\\\\\\\bfailed to\\\\\\\\b\\", \\"\\\\\\\\bnot observed\\\\\\\\b\\",\\n    \\"\\\\\\\\bno statistically significant\\\\\\\\b\\", \\"\\\\\\\\bnot exert\\\\\\\\b\\", \\"\\\\\\\\black of significant\\\\\\\\b\\",\\n    \\"\\\\\\\\bno (?:direct )?(?:association|correlation|relationship|effect|influence)\\\\\\\\b\\",\\n    \\"\\\\\\\\bwhereas .{0,40}\\\\\\\\bnot\\\\\\\\b\\", \\"\\\\\\\\bcontrary to\\\\\\\\b\\"\\n  ],\\n\\n  \\"_encuadre\\": \\"Oraciones donde el SUJETO ES EL PROPIO ESTUDIO \\u2014\\u00abthis study examines the impact of AI on higher education\\u00bb\\u2014 o que cierran con la aportaci\\u00f3n, las implicaciones o el panorama. Declaran una relaci\\u00f3n de verdad, por eso se recortan, pero sus extremos suelen ser OBJETOS y no constructos: no hay variable latente que nombrar. Se cuentan aparte para que el conteo de familias no las mezcle con las oraciones que s\\u00ed tienen un constructo sin nombrar.\\",\\n\\n  \\"encuadre\\": [\\n    \\"\\\\\\\\bthis (?:study|paper|research|article|review|work|investigation|chapter)\\\\\\\\b[^.;]{0,60}\\\\\\\\b(?:examine|investigate|explore|analy[sz]e|assess|address|aim|seek|attempt|propose|present|report|evaluate|discuss|review)\\",\\n    \\"\\\\\\\\bthe (?:aim|purpose|objective|goal|focus|contribution) of (?:this|the present|our)\\\\\\\\b\\",\\n    \\"\\\\\\\\bthe present (?:study|paper|research|work|article)\\\\\\\\b\\",\\n    \\"\\\\\\\\bwe (?:examine|investigate|explore|analy[sz]e|assess|address|aim to|seek to|propose|present|report|evaluate)\\\\\\\\b\\",\\n    \\"\\\\\\\\b(?:this|the) (?:study|paper|article) (?:is|was) (?:designed|conducted|carried out) to\\\\\\\\b\\",\\n    \\"\\\\\\\\bfuture (?:research|studies|work) (?:should|could|may|might|needs? to)\\\\\\\\b\\",\\n    \\"\\\\\\\\b(?:these|the) (?:insights|findings|results|conclusions) (?:contribute|offer|provide|underscore|highlight|suggest|have implications)\\",\\n    \\"\\\\\\\\b(?:this|the) (?:study|paper|research|review|work) (?:makes|offers|provides|contributes|underscores|highlights|advances|extends)\\\\\\\\b\\",\\n    \\"\\\\\\\\bcontribut\\\\\\\\w+ to the (?:ongoing )?(?:discourse|literature|debate|body of knowledge|understanding)\\\\\\\\b\\",\\n    \\"\\\\\\\\b(?:practical|theoretical|managerial|policy|pedagogical) implications\\\\\\\\b\\",\\n    \\"\\\\\\\\b(?:anticipates?|outlines?|discusses?) (?:future|potential) (?:directions|avenues|research|developments)\\\\\\\\b\\",\\n    \\"\\\\\\\\bis (?:increasingly |widely |generally )?(?:recognized|acknowledged|regarded|seen|considered) as\\\\\\\\b\\"\\n  ],\\n\\n  \\"_ruido\\": \\"Oraciones que citan la f\\u00f3rmula sin declarar una relaci\\u00f3n propia del estudio.\\",\\n  \\"ruido\\": [\\n    \\"^(?:the )?(?:aim|purpose|objective) of this (?:paper|study|article|review) is to (?:review|summari[sz]e|describe|present)\\\\\\\\b\\",\\n    \\"\\\\\\\\bthis (?:paper|study) (?:reviews|summari[sz]es|describes) the literature\\\\\\\\b\\"\\n  ],\\n\\n  \\"minimo_palabras\\": 9\\n}\\n", "vacios.json": "{\\n  \\"_que_es\\": \\"F\\u00f3rmulas con las que un autor declara que algo falta. Gen\\u00e9ricas: pertenecen al oficio acad\\u00e9mico en ingl\\u00e9s, no al tema.\\",\\n  \\"_regla\\": \\"Lo que se guarda es la ORACI\\u00d3N ENTERA Y TEXTUAL donde aparece la f\\u00f3rmula, nunca una par\\u00e1frasis. Esa frase es lo que el investigador podr\\u00e1 citar, con su registro y su DOI detr\\u00e1s.\\",\\n  \\"_techo\\": \\"Un vac\\u00edo que el autor no enuncia en el resumen no existe para esta capa. Que no haya vac\\u00edo declarado no significa que no haya vac\\u00edo.\\",\\n\\n  \\"senales\\": [\\n    \\"remains? (?:largely |relatively |still )?(?:under-?explored|under-?researched|under-?studied|unexplored|unclear|unknown|poorly understood)\\",\\n    \\"(?:is|are|has been|have been) (?:largely |relatively |still |often )?(?:overlooked|neglected|understudied|under-?researched|under-?explored)\\",\\n    \\"little (?:is|has been) known\\",\\n    \\"(?:scant|scarce|limited|insufficient) (?:attention|research|evidence|literature|knowledge|information|studies)\\",\\n    \\"(?:research|knowledge|literature|empirical) gaps?\\",\\n    \\"gaps? in the (?:literature|research|knowledge|evidence)\\",\\n    \\"(?:few|no) (?:studies|papers|works|articles|authors) have\\",\\n    \\"to (?:the best of )?our knowledge,? (?:no|few|this is the first)\\",\\n    \\"(?:has|have) (?:not|yet to) been (?:examined|investigated|explored|studied|addressed|analy[sz]ed|tested)\\",\\n    \\"there (?:is|are|has been|have been) (?:a )?(?:lack|dearth|paucity|absence) of\\",\\n    \\"(?:warrants?|calls? for|requires?|needs?) (?:further|additional|more) (?:research|investigation|study|attention)\\",\\n    \\"future (?:research|studies) should\\",\\n    \\"this (?:study|paper|research|article) (?:seeks to |aims to |attempts to )?(?:fills?|addresses(?:es)?|bridges?) (?:this |the |a )?gap\\",\\n    \\"(?:remains?|is) an? (?:open|unanswered) question\\",\\n    \\"yet to be (?:fully )?(?:understood|established|determined|explored)\\",\\n\\n    \\"there (?:is|are|remains?) (?:still )?(?:a |an )?(?:need|lack|absence|dearth) (?:for|of) (?:more |further |additional )?(?:research|studies|information|knowledge|data|evidence|literature)\\",\\n    \\"lack of (?:scientific |published |available |detailed |sufficient )?(?:information|knowledge|research|studies|data|evidence|literature)\\",\\n    \\"little (?:information|research|data|evidence|attention) (?:on|about|regarding|exists|is available)\\",\\n    \\"remains? to be (?:more (?:deeply )?)?(?:studied|investigated|explored|determined|elucidated|established|assessed)\\",\\n    \\"(?:is|are|remains?) (?:still )?poorly (?:understood|documented|studied|characteri[sz]ed|known)\\",\\n    \\"(?:this is the )?first (?:report|record) of\\"\\n  ],\\n\\n  \\"_nota_dominio\\": \\"Las seis \\u00faltimas se a\\u00f1adieron tras revisar un corpus de agronom\\u00eda, donde solo el 3% declaraba vac\\u00edo frente al 10-13% de los corpus de ciencias sociales. NO se a\\u00f1adi\\u00f3 \\u00ablack of\\u00bb a secas, aunque abunda: en agronom\\u00eda significa casi siempre falta de transporte refrigerado, falta de tiempo o diversidad gen\\u00e9tica escasa \\u2014carencias del mundo, no de la literatura\\u2014. Solo cuenta cuando el objeto es epist\\u00e9mico: informaci\\u00f3n, conocimiento, investigaci\\u00f3n, datos, evidencia. Un patr\\u00f3n que infla la cifra es peor que uno que se queda corto.\\"\\n}\\n"}')


# Las cinco fichas van INCRUSTADAS, no en disco: este archivo tiene que viajar
# solo. Son las mismas de retrato-corpus/references/, copiadas por
# construir_unico.py — no se editan aquí, se editan alli y se regenera.

def recurso(nombre):
    """Las fichas se cargan solo cuando su capa corre, no al arrancar. Se vuelve
    a parsear en cada llamada, igual que la version de disco, para que quien
    reciba la ficha pueda modificarla sin afectar a la siguiente capa."""
    if nombre not in _FICHAS:
        raise KeyError(nombre)
    return json.loads(_FICHAS[nombre])



def _blob(r):
    """El texto donde se busca: título, resumen y palabras clave. La afiliación NO
    entra — mencionar Kiel no significa haber estudiado Alemania."""
    return " ".join((r["t"], r["a"], r["k"])).lower()


def _compilar(patrones):
    return re.compile("|".join(patrones), re.I)


# ─────────────────────────────────────────────────── capa 3 — vocabulario

TECHO_HUB, MIN_DF, TOP_ARISTAS, MIN_RACIMO, MIN_PAPERS = 0.20, 3, 8, 3, 10
TOPE_TARJETAS = 12    # más de una docena de racimos dibujados es un muro, no un mapa


def _normkw(k):
    k = k.lower().strip()
    k = k.replace("behaviour", "behavior").replace("modelling", "modeling")
    k = k.replace("organisation", "organization").replace("optimisation", "optimization")
    k = re.sub(r"[-_/]", " ", k)
    k = re.sub(r"[^a-z0-9 ]", "", k)
    return re.sub(r"\s+", " ", k).strip()


def capa_vocabulario(recs, cfg):
    import math
    docs = []
    for r in recs:
        ks = {_normkw(k) for k in r["k"].split(";")} if r["k"] else set()
        docs.append({k for k in ks if len(k) > 2})
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(d)
    # plurales cuyo singular también existe
    canon = {}
    for k in df:
        if k.endswith("s") and len(k) > 4 and k[:-1] in df:
            canon[k] = k[:-1]
        elif k.endswith("es") and len(k) > 5 and k[:-2] in df:
            canon[k] = k[:-2]
    docs = [{canon.get(k, k) for k in d} for d in docs]
    df = Counter()
    for d in docs:
        df.update(d)
    crudas = len(df) + len(canon)

    # lo que la ecuación ya pidió no puede ser un hallazgo; los países viven en otra capa
    eq = cfg.get("ecuacion_base", "") or ""
    eqt = {_normkw(x) for x in re.findall(r'"([^"]+)"', eq)} | \
          {_normkw(x) for x in re.findall(r"\b([a-zA-Z]{4,})\b", eq)}
    geo = set()
    try:
        for lst in recurso("paises.json")["regiones"].values():
            geo |= {_normkw(p) for p in lst}
    except Exception:
        pass
    hubs = {}
    for k, v in df.items():
        if v / n > TECHO_HUB:
            hubs[k] = f"está en el {pct(v, n):.0f}% del corpus"
        elif k in eqt and v >= MIN_DF:
            hubs[k] = "término de la ecuación base"
        elif k in geo and v >= MIN_DF:
            hubs[k] = "nombre de país — vive en la capa de regiones"

    # PROBADO Y DESCARTADO — expandir la neutralización por contención: si una
    # palabra contiene a otra ya neutralizada, quitarla también. Resolvía a medias
    # el caso de las variantes repartidas («generative ai» / «genai» / «generative
    # artificial intelligence», ninguna llegando al techo por separado) y en cambio
    # ARRUINABA un corpus que funcionaba: «consumer behavior» y «household food
    # waste» desaparecían por contener «consumer» y «food waste», y los racimos
    # caían de 14 a 4. Una regla que arregla un corpus y rompe otro no es una regla.
    #
    # El caso de las variantes se resuelve donde debe: DECLARANDO LA ECUACIÓN en
    # retrato.json. Si no se declara, la lámina lo dice y el investigador decide.

    vocab = [k for k, v in df.items() if v >= MIN_DF and k not in hubs]
    idx = {k: i for i, k in enumerate(vocab)}
    co = defaultdict(int)
    for d in docs:
        ks = sorted(idx[k] for k in d if k in idx)
        for a in range(len(ks)):
            for b in range(a + 1, len(ks)):
                co[(ks[a], ks[b])] += 1
    peso = {p: c / math.sqrt(df[vocab[p[0]]] * df[vocab[p[1]]])
            for p, c in co.items() if c >= 2}

    vec = defaultdict(list)
    for (a, b), w in peso.items():
        vec[a].append((w, b)); vec[b].append((w, a))
    ady = defaultdict(dict)
    for nd, l in vec.items():
        for w, m in sorted(l, key=lambda x: (-x[0], x[1]))[:TOP_ARISTAS]:
            ady[nd][m] = w; ady[m][nd] = w

    lab = {i: i for i in range(len(vocab))}
    orden = sorted(range(len(vocab)), key=lambda i: (-df[vocab[i]], vocab[i]))
    for _ in range(40):
        cambios = 0
        for nd in orden:
            if not ady[nd]:
                continue
            ps = defaultdict(float)
            for m, w in ady[nd].items():
                ps[lab[m]] += w
            mejor = sorted(ps.items(), key=lambda kv: (-kv[1], vocab[kv[0]]))[0][0]
            if mejor != lab[nd]:
                lab[nd] = mejor; cambios += 1
        if not cambios:
            break

    grupos = defaultdict(list)
    for nd, l in lab.items():
        grupos[l].append(nd)
    grandes = {l for l, ns in grupos.items() if len(ns) >= MIN_RACIMO}
    for l, ns in list(grupos.items()):                      # huérfanos al racimo más afín
        if l in grandes:
            continue
        for nd in ns:
            mej, mw = None, 0.0
            for g in grandes:
                w = sum(peso.get((min(nd, m), max(nd, m)), 0) for m in grupos[g])
                if w > mw:
                    mej, mw = g, w
            if mej is not None:
                lab[nd] = mej
    grupos = defaultdict(list)
    for nd, l in lab.items():
        if lab[nd] in grandes:
            grupos[lab[nd]].append(nd)

    def papers(ns):
        kws = {vocab[i] for i in ns}
        return {i for i, d in enumerate(docs) if d & kws}

    ls = list(grupos); fus = True                            # fusionar los muy solapados
    while fus:
        fus = False
        for a in range(len(ls)):
            for b in range(a + 1, len(ls)):
                A, B = papers(grupos[ls[a]]), papers(grupos[ls[b]])
                if A and B and len(A & B) / len(A | B) > 0.30:
                    grupos[ls[a]] += grupos[ls[b]]; del grupos[ls[b]]
                    ls = list(grupos); fus = True; break
            if fus:
                break

    racimos, cub = [], set()
    for l, ns in grupos.items():
        kws = sorted((vocab[i] for i in ns), key=lambda k: (-df[k], k))
        P = papers(ns); cub |= P
        racimos.append({"rotulo": kws[0], "n_papers": len(P), "pct": pct(len(P), n),
                        "menor": len(P) < MIN_PAPERS, "motivo": "",
                        "kw": [{"k": k, "n": df[k]} for k in kws]})
    racimos.sort(key=lambda r: (-r["n_papers"], r["rotulo"]))

    # Un corpus grande produce decenas de racimos y la lámina se vuelve un muro.
    # Se dibuja una docena; el resto se LISTA —nada se esconde— con su rótulo.
    for i, r in enumerate(racimos):
        if r["menor"]:
            r["motivo"] = f"menos de {MIN_PAPERS} papers"
        elif i >= TOPE_TARJETAS:
            r["menor"] = True
            r["motivo"] = f"fuera de los {TOPE_TARJETAS} mayores"

    techo = sum(1 for d in docs if d & {k for k, v in df.items()
                                        if v >= MIN_DF and k not in hubs})

    # ── el agrupamiento puede degenerar ────────────────────────────────
    # Un racimo que se lleva casi todo no es un racimo: es el corpus con una
    # etiqueta encima. Cuando pasa, no se dibuja: se dice que falló.
    mayor = max((r["n_papers"] for r in racimos), default=0)
    degenerado = bool(cub) and mayor / len(cub) > 0.40

    # ── qué es OBJETO DE ESTUDIO y qué pertenece a otra lámina ─────────
    # Las palabras clave no distinguen tema de constructo: el autor etiqueta su
    # paper con su objeto Y con sus variables en la misma lista. Lo que sí las
    # distingue es de dónde vienen — así que se resta lo que otra lámina ya
    # reclamó, y lo que queda son objetos de verdad.
    #
    # Aquí se restaba también lo que la lámina 2 reclamaba como constructo. Ya no:
    # esa lámina dejó de nombrarlos. Lo que hace ese trabajo ahora es la ECUACIÓN
    # BASE — los términos que la búsqueda ya pidió no pueden contar como hallazgo—,
    # así que declararla en retrato.json importa más que antes.
    reclamado = {}
    # Los economistas etiquetan sus papers con códigos JEL —Q54, C23, O13— y son
    # palabras clave como cualquier otra. En el corpus de cambio climático «q54»
    # entraba en la lista de OBJETOS DE ESTUDIO con 49 papers detrás, entre
    # «vulnerability» y «economic growth». No es un objeto: es una signatura.
    #
    # Pero la FORMA no basta para reconocerlos, y esto costó un defecto propio:
    # «k12» tiene forma de código JEL válido (K12 = derecho penal) y en el corpus
    # de IA en educación es K-12, un objeto de estudio de pleno derecho, que la
    # primera versión de esta regla borró en silencio. Lo que distingue a un
    # código de clasificación no es su forma: es que NUNCA VIENE SOLO. Un corpus
    # que usa JEL trae decenas —el de agronomía trae 102—; el de educación traía
    # uno. Así que la regla solo se aplica cuando hay un sistema, no un parecido.
    jel = [k for k in df if re.fullmatch(r"[a-ry-z]\d{2}", k)]   # A–R, Y, Z: las letras JEL
    if len(jel) >= 5:
        for k in jel:
            reclamado[k] = "código de clasificación JEL"
    for ficha, etq, lam in (("metodos.json", "método", 6), ("regiones.json", "región", 4)):
        try:
            fam = recurso(ficha)["familias"]
            pats = [p for v in fam.values() for p in (v if isinstance(v, list) else v["patrones"])]
            rx = _compilar(pats)
            for k in df:
                if k not in reclamado and rx.search(k):
                    reclamado[k] = f"{etq} · lámina {lam}"
        except Exception:
            pass

    objetos = [{"k": k, "n": v, "pct": pct(v, n)} for k, v in df.items()
               if v >= MIN_DF and k not in hubs and k not in reclamado]
    objetos.sort(key=lambda x: (-x["n"], x["k"]))

    # ── variantes repartidas: se SEÑALAN, no se agrupan ────────────────
    # Un campo escribe el mismo término de varias maneras —«generative ai»,
    # «generative artificial intelligence», «genai»— y cada grafía compite como
    # si fuera un objeto distinto: ninguna refleja su peso real y el primero de
    # la lista puede no ser el mayor. Agrupar por contención ya se probó y se
    # descartó: arreglaba un corpus y rompía otro (ver el comentario de arriba).
    # Así que aquí no se decide nada — se avisa cuando el reparto hace frágil el
    # orden, y quien mira la lista decide. La prueba es concreta: ¿hay entradas
    # que comparten un término y que, SIN contar a la primera, suman más que ella?
    STOP = {"the", "and", "for", "with", "from", "its", "new", "use", "using", "based",
            "study", "studies", "analysis", "research", "approach", "model", "models",
            "effect", "effects", "role", "case", "review", "data", "impact", "impacts"}
    variantes, cabeza = None, objetos[:15]
    if len(cabeza) > 1:
        raices = defaultdict(list)
        for o in cabeza:
            for w in set(o["k"].split()):
                if len(w) >= 3 and w not in STOP:
                    raices[w].append(o)
        lider, cands = cabeza[0], []
        for w, grupo in raices.items():
            otros = [x for x in grupo if x["k"] != lider["k"]]
            suma = sum(x["n"] for x in otros)
            if len(otros) >= 2 and suma > lider["n"]:
                cands.append({"raiz": w, "suma": suma,
                              "entradas": [{"k": x["k"], "n": x["n"]} for x in otros],
                              "lider": {"k": lider["k"], "n": lider["n"]}})
        if cands:
            cands.sort(key=lambda c: (-c["suma"], c["raiz"]))
            variantes = cands[0]

    return {
        "n_con_keywords": sum(1 for d in docs if d),
        "kw_crudas": crudas, "kw_normalizadas": len(df),
        "hapax": sum(1 for v in df.values() if v == 1),
        "pct_hapax": pct(sum(1 for v in df.values() if v == 1), len(df)),
        "repetidas": sum(1 for v in df.values() if v >= 2),
        "neutralizados": [{"k": k, "n": df[k], "motivo": m}
                          for k, m in sorted(hubs.items(), key=lambda kv: (-df[kv[0]], kv[0]))],
        "racimos": racimos,
        "umbral_menor": MIN_PAPERS,
        "degenerado": degenerado,
        "mayor_racimo": {"n": mayor, "pct_de_cubiertos": pct(mayor, len(cub))},
        "objetos": objetos,
        "variantes": variantes,
        "reclamado": [{"k": k, "n": df[k], "por": v} for k, v in
                      sorted(reclamado.items(), key=lambda kv: (-df[kv[0]], kv[0]))],
        "cobertura": {"n": len(cub), "pct": pct(len(cub), n),
                      "techo": techo, "pct_techo": pct(techo, n)},
    }


# ──────────────────────────────────────── capa 4 — región DEL ESTUDIO

def capa_region(recs):
    ref = recurso("regiones.json")
    fam = {k: _compilar(v["patrones"]) for k, v in ref["familias"].items()}
    glosa = {k: v["glosa"] for k, v in ref["familias"].items()}
    n = len(recs)
    cuenta, sin_decl, multi = Counter(), [], 0
    for r in recs:
        b = _blob(r)
        hit = [k for k, rx in fam.items() if rx.search(b)]
        if not hit:
            sin_decl.append(r["id"])
        else:
            cuenta.update(hit)
            if len(hit) > 1:
                multi += 1
    declaran = n - len(sin_decl)

    # ¿De verdad la lámina de al lado recupera el hueco de esta? El pie lo
    # afirmaba fijo —«recupera a casi todos»— y nadie lo había medido nunca. Se
    # mide donde importa: sobre los papers que NO declaran región, cuántos sí
    # resuelven un país de afiliación. Va en su propio try: si paises.json no
    # carga, esta capa sigue entera y el pie se calla en vez de inventar.
    recupera = None
    try:
        pais2reg = {p: k for k, ps in recurso("paises.json")["regiones"].items() for p in ps}
        mudos, rec = set(sin_decl), 0
        for r in recs:
            if r["id"] not in mudos:
                continue
            if any((partes := [x.strip() for x in dire.split(",") if x.strip()])
                   and partes[-1] in pais2reg for dire in r["afil"].split(";")):
                rec += 1
        recupera = {"n": rec, "pct": pct(rec, len(sin_decl))}
    except Exception:
        pass

    return {
        "n": n, "n_declaran": declaran, "pct_declaran": pct(declaran, n),
        "recupera_afiliacion": recupera,
        "n_sin_declarar": len(sin_decl), "pct_sin_declarar": pct(len(sin_decl), n),
        "multiregion": multi,
        "familias": [{"fam": k, "n": v, "pct_de_declarados": pct(v, declaran), "glosa": glosa[k]}
                     for k, v in top_estable(cuenta)],
        "pct_top2": pct(sum(v for _, v in cuenta.most_common(2)), declaran, 0),
        "_base": "los porcentajes son sobre los que SÍ declaran región, no sobre el corpus",
    }


# ──────────────────────────────────── capa 5 — afiliación de los autores

_AFIL_PAIS = re.compile(r"[^,;]+$")


def capa_afiliacion(recs):
    reg = recurso("paises.json")["regiones"]
    pais2reg = {p: k for k, ps in reg.items() for p in ps}
    n = len(recs)
    cpais, creg, nreg = Counter(), Counter(), Counter()
    sin_campo, sin_reconocer = [], Counter()
    for r in recs:
        if not r["afil"].strip():
            sin_campo.append(r["id"]); continue
        paises, regiones = set(), set()
        for dire in r["afil"].split(";"):
            partes = [x.strip() for x in dire.split(",") if x.strip()]
            if not partes:
                continue
            ult = partes[-1]
            if ult in pais2reg:
                paises.add(ult); regiones.add(pais2reg[ult])
            else:
                sin_reconocer[ult] += 1
        if not regiones:
            continue
        cpais.update(paises); creg.update(regiones); nreg[len(regiones)] += 1
    resueltos = sum(nreg.values())
    colab = sum(v for k, v in nreg.items() if k >= 2)
    return {
        "n": n, "n_resueltos": resueltos, "pct_resueltos": pct(resueltos, n),
        "n_sin_campo": len(sin_campo),
        "n_sin_reconocer": sum(1 for _ in sin_reconocer),
        "no_reconocidos": [{"token": k, "n": v} for k, v in top_estable(sin_reconocer, 15)],
        "regiones": [{"reg": k, "n": v, "pct": pct(v, n)} for k, v in top_estable(creg)],
        "paises": [{"pais": k, "n": v} for k, v in top_estable(cpais, 20)],
        "colaboracion": {"n": colab, "pct": pct(colab, resueltos) if resueltos else 0},
        "_ojo": "de dónde son los autores, no dónde se hizo el estudio",
    }


# ─────────────────────────────────────────────────────── capa 6 — método

def capa_metodo(recs):
    fam = {k: _compilar(v) for k, v in recurso("metodos.json")["familias"].items()}
    n = len(recs)
    cuenta, ninguno = Counter(), 0
    for r in recs:
        b = _blob(r)
        hit = [k for k, rx in fam.items() if rx.search(b)]
        cuenta.update(hit)
        if not hit:
            ninguno += 1
    orden = top_estable(cuenta)
    # ¿Hay un instrumento dominante, o dos empatados? El titular de la lámina se
    # elige con esto y no puede escribirse fijo. En el corpus de agronomía el
    # primero le saca DIEZ papers al segundo sobre 3.441 —734 contra 724— y la
    # lámina decía «es el instrumento dominante del campo»: un hallazgo
    # fabricado por un desempate alfabético. Candado 4.
    ventaja = round(orden[0][1] / orden[1][1], 2) if len(orden) >= 2 and orden[1][1] else None
    # La BASE de esta lámina, que hasta ahora solo se decía en el pie. Hace falta
    # arriba: «no declarado» aquí conflaciona dos cosas —que el resumen no nombre
    # el método, y que ESTA FICHA no conozca el vocabulario del dominio—. La
    # segunda es un defecto del instrumento, no del corpus, y con una base
    # delgada el titular llegaría a coronar un instrumento dominante entre el
    # poco que supo ver. Es el mismo agujero que tenía la lámina de región.
    declaran = n - ninguno
    return {
        "n": n,
        "familias": [{"fam": k, "n": v, "pct": pct(v, n)} for k, v in orden],
        "ventaja_sobre_2o": ventaja,
        "n_declaran": declaran, "pct_declaran": pct(declaran, n),
        "sin_metodo_declarado": ninguno, "pct_sin_declarar": pct(ninguno, n),
        "_techo": "se lee el resumen: un método usado y no mencionado no aparece",
    }


# ──────────────────────────────────────── capa 8 — vacíos declarados

_ORACION = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")


def capa_vacios(recs, max_citas=3):
    rx = _compilar(recurso("vacios.json")["senales"])
    n = len(recs)
    con, citas = [], []
    for r in recs:
        if not r["a"].strip():
            continue
        frases = [o.strip() for o in _ORACION.split(r["a"]) if len(o.strip()) > 40]
        propias = [o for o in frases if rx.search(o)]
        if not propias:
            continue
        con.append(r["id"])
        citas.append({"id": r["id"], "y": r["y"], "doi": r["doi"],
                      "t": r["t"], "frases": propias[:max_citas]})
    return {
        "n": n, "n_declaran": len(con), "pct": pct(len(con), n),
        "papers": citas,
        "_regla": "la frase es textual del autor; nunca se parafrasea",
        "_techo": "que no haya vacío declarado no significa que no haya vacío",
    }


# ──────────────────────────────────── capa 2 — relaciones y constructos

def capa_relaciones(recs, cfg):
    """Recorta las oraciones donde un autor declara una relación. Nada más.

    HUBO una segunda mitad: el modelo leía estas oraciones, las agrupaba en
    familias y la lámina dibujaba el mapa de constructos del campo. Se quitó, y
    no por mala: por dónde caía. Obligaba a una lectura entre dos corridas del
    script —romper el «una invocación, cero preguntas»—, y era el ÚNICO punto de
    todo el retrato donde el modelo tenía que leer contenido del corpus. Con
    1,9 MB en el corpus más pequeño, eso no cabe en ninguna ventana de contexto,
    así que tampoco portaba a un GPT ni a un cuaderno. Nombrar constructos es
    trabajo de la matriz de síntesis, donde el humano ya está leyendo de todos
    modos. Aquí queda lo que SÍ es un cálculo: cuánto de este campo mide en vez
    de describir, y qué relaciones sus autores declaran que NO aparecieron.
    """
    ref = recurso("relaciones.json")
    marcos = {k: _compilar(v) for k, v in ref["marcos"].items()}
    neg = _compilar(ref["negacion"])
    enc = _compilar(ref["encuadre"]) if ref.get("encuadre") else None
    ruido = _compilar(ref["ruido"]) if ref.get("ruido") else None
    minp = ref.get("minimo_palabras", 9)

    frases, con = [], set()
    for r in recs:
        if not r["a"].strip():
            continue
        for o in _ORACION.split(r["a"]):
            o = " ".join(o.split())
            if len(o.split()) < minp:
                continue
            if ruido and ruido.search(o):
                continue
            hit = [k for k, rx in marcos.items() if rx.search(o)]
            if not hit:
                continue
            con.add(r["id"])
            frases.append({"id": r["id"], "y": r["y"], "doi": r["doi"],
                           "marcos": sorted(hit),
                           "neg": bool(neg.search(o)),
                           # De encuadre: el sujeto es el propio estudio —«this study
                           # examines the effect of X on Y»—. Declara una relación de
                           # verdad, pero anuncia lo que se propuso, no lo que halló.
                           "enc": bool(enc.search(o)) if enc else False,
                           "o": o})

    n = len(recs)
    negs = [f for f in frases if f["neg"]]
    encs = [f for f in frases if f["enc"]]
    # Las citas del panel: las negaciones más cortas, que son las que se leen.
    # NO de encuadre —«este estudio examina si X no afecta a Y» no es un resultado
    # nulo, es un plan— y con DOI, para que se puedan comprobar.
    citas = sorted((f for f in negs if not f["enc"]),
                   key=lambda f: (len(f["o"]), f["id"]))[:4]

    return {
        "n": n, "n_papers": len(con), "pct_papers": pct(len(con), n),
        "n_frases": len(frases),
        "por_marco": dict(top_estable(Counter(m for f in frases for m in f["marcos"]))),
        "negaciones": {"n_frases": len(negs), "n_papers": len({f["id"] for f in negs}),
                       "pct_frases": pct(len(negs), len(frases)), "citas": citas},
        "encuadre": {"n_frases": len(encs), "pct_frases": pct(len(encs), len(frases))},
        # Todas, no una muestra: aquí ya no las lee nadie. Se guardan porque son la
        # materia prima con la que la matriz de síntesis nombrará los constructos,
        # y sin ellas ese paso tendría que volver a parsear el .txt entero.
        "frases": frases,
        "_regla": "las oraciones son textuales y no se recortan las ranuras X e Y: parte "
                  "de ellas lleva negación y un recorte mecánico invertiría el sentido",
    }


# ─────────────────────────────────────── la tabla: una fila por paper

def tabla_papers(recs):
    """Una fila por paper, con lo que cada capa sabe de él. NO se dibuja en el
    retrato: se guarda para el paso siguiente.

    Las capas cuentan y tiran la asignación individual —a la lámina de método le
    importa que 340 papers usen encuesta, no cuáles—. La matriz de síntesis
    necesita justo lo contrario: qué método, qué región y qué vacío tiene ESTE
    paper, para poder filtrar «SEM + Asia + declara vacío» y quedarse con doce.
    Sin esta tabla, el paso 2 tendría que volver a parsear el .txt entero.

    Va aparte y con su propio try por ficha: es material del paso 2, y un fallo
    suyo no puede tumbar una lámina del paso 1. Si una ficha no carga, esa
    columna sale vacía y las demás siguen.
    """
    def clasificador(ficha, llave="familias"):
        try:
            fam = recurso(ficha)[llave]
            return {k: _compilar(v["patrones"] if isinstance(v, dict) else v)
                    for k, v in fam.items()}
        except Exception:
            return {}

    regs = clasificador("regiones.json")
    mets = clasificador("metodos.json")
    try:
        vac = _compilar(recurso("vacios.json")["senales"])
    except Exception:
        vac = None
    try:
        pais2reg = {p: k for k, ps in recurso("paises.json")["regiones"].items() for p in ps}
    except Exception:
        pais2reg = {}

    filas = []
    for r in recs:
        b = _blob(r)
        paises = set()
        for dire in r["afil"].split(";"):
            partes = [x.strip() for x in dire.split(",") if x.strip()]
            if partes and partes[-1] in pais2reg:
                paises.add(partes[-1])
        filas.append({
            "id": r["id"], "doi": r["doi"], "t": r["t"], "au": r["au"], "y": r["y"],
            "rev": r["rev"], "cit": r["cit"], "dt": r["dt"],
            "kw": [k.strip().lower() for k in r["k"].split(";") if k.strip()],
            "region": sorted(k for k, rx in regs.items() if rx.search(b)),
            "metodo": sorted(k for k, rx in mets.items() if rx.search(b)),
            "paises": sorted(paises),
            "reg_afil": sorted({pais2reg[p] for p in paises}),
            "vacio": bool(vac.search(r["a"])) if (vac and r["a"]) else False,
            "resumen": bool(r["a"].strip()),
        })
    return filas


# ─────────────────────────────── diagnóstico — qué FORMA tiene este corpus

COB_RACIMOS_BAJA = 45      # por debajo, el vocabulario no encuentra un tema común
REG_AFIL_DOMINA = 90       # por encima, todos los autores son del mismo sitio


def diagnostico(capas):
    """Detecta que el export NO ES EL QUE SE QUERÍA ANALIZAR.

    Este skill trabaja con corpus temáticos. Un export bajado por afiliación —la
    producción indexada de una universidad— pasa por el motor sin romper nada y
    produce cifras impecables sobre algo que a nadie le sirve. Pasó de verdad: se
    coló un archivo equivocado y el retrato salió entero, sin una sola señal de
    alarma, describiendo agronomía, acuicultura y educación a la vez.
    Las señales estaban a la vista pero nadie las ataba: aquí se atan.

    Medido en tres corpus reales:
        cobertura de racimos   temático 69% y 90%   ·  institucional 31%
        región de afiliación   temático 53% y 34%   ·  institucional 99,9%
    Las otras señales candidatas —revistas por paper, revistas con un solo
    artículo— NO discriminan: dan casi lo mismo en los tres."""
    avisos = []
    voc, afi = capas.get("vocabulario"), capas.get("afiliacion")
    if not (voc and afi) or "error" in voc or "error" in afi or not afi.get("regiones"):
        return avisos

    cob = voc["cobertura"]["pct"]
    top = afi["regiones"][0]
    if cob < COB_RACIMOS_BAJA and top["pct"] >= REG_AFIL_DOMINA:
        avisos.append({
            "clave": "institucional",
            "titulo": "Comprueba que este es el archivo que querías analizar",
            "texto": (f"El {top['pct']:.0f}% de los papers está firmado desde {top['reg']} y el "
                      f"vocabulario compartido solo alcanza al {cob:.0f}% del corpus —en un corpus "
                      f"temático pasa del 65%—. Las dos cosas juntas señalan un export bajado por "
                      f"AFILIACIÓN y no por tema: la producción de una institución, con disciplinas "
                      f"que no comparten vocabulario. Este skill está hecho para corpus temáticos; "
                      f"sobre uno institucional las cifras salen impecables y no sirven para nada, "
                      f"porque describen a una universidad y no a un campo. Si era lo que querías, "
                      f"sigue; si no, vuelve a Scopus y baja el corpus por tema."),
            "senales": {"cobertura_racimos": cob, "region_top": top["reg"], "pct_region": top["pct"]},
        })
    return avisos


# ────────────────────────────────────────────────────────────────── informe

def linea(txt=""):
    print(txt)


def _calcular():
    utf8()
    cfg = arg_config(sys.argv, os.path.basename(__file__))
    export = fecha_export(cfg["fuente"])
    recs, nbloques = parsear(cfg["fuente"])
    if not recs:
        print("no se parseó ningún registro; ¿es un export de Scopus en .txt?", file=sys.stderr)
        raise SystemExit(1)

    inf0, avisos, parar, recs = candado0(recs, nbloques, cfg)

    linea(f"RETRATO DEL CORPUS · v{VERSION}")
    linea(f"fuente: {os.path.basename(cfg['fuente'])}")
    linea("─" * 74)
    linea(f"CANDADO 0 · {inf0['n_bloques']} bloques → {inf0['n_parseados']} parseados → "
          f"{inf0['n_distintos']} distintos")
    for k, v in inf0["cobertura"].items():
        linea(f"    {k:12s} {v['n']:5d}  {v['pct']:5.1f}%")
    for d in inf0["duplicados"]:
        linea(f"    ! repetido por {d['por']}: registros {d['ids']} · citas {d['citas']}")
    for a in avisos:
        linea(f"    aviso: {a}")
    if parar:
        for p in parar:
            print(f"    ALTO: {p}", file=sys.stderr)
        raise SystemExit(1)

    capas, fallos = {}, {}
    LAS_CAPAS = [
        ("tiempo",      lambda: capa_tiempo(recs, cfg, export)),
        ("relaciones",  lambda: capa_relaciones(recs, cfg)),
        ("vocabulario", lambda: capa_vocabulario(recs, cfg)),
        ("region",      lambda: capa_region(recs)),
        ("afiliacion",  lambda: capa_afiliacion(recs)),
        ("metodo",      lambda: capa_metodo(recs)),
        ("revistas",    lambda: capa_revistas(recs)),
        ("vacios",      lambda: capa_vacios(recs)),
        ("citas",       lambda: capa_citas(recs, capas["tiempo"]["ultimo_real"])),
    ]
    for nombre, fn in LAS_CAPAS:
        try:
            capas[nombre] = fn()
        except Exception as e:                       # una capa que cae no tumba las demás
            fallos[nombre] = f"{type(e).__name__}: {e}"

    diag = diagnostico(capas)
    for d in diag:
        linea()
        linea(f"DIAGNÓSTICO · {d['titulo'].upper()}")
        for x in re.findall(r".{1,86}(?:\s|$)", d["texto"]):
            linea(f"    {x.strip()}")

    # ── a pantalla ──────────────────────────────────────────────────────
    t = capas.get("tiempo", {})
    if t and "error" not in t:
        linea()
        linea(f"CAPA 1 · TIEMPO   {t['desde']}–{t['hasta']}")
        if t["despegue"]:
            linea(f"    despegue en {t['despegue']}: {t['pct_desde_despegue']:.0f}% del corpus "
                  f"({t['n_desde_despegue']}) es de ese año en adelante · "
                  f"antes: {t['antes_del_despegue']} papers")
        else:
            linea(f"    SIN DESPEGUE MEDIBLE — {t['sin_despegue']}")
        linea(f"    mitad del corpus publicada desde {t['anio_mediana']} · "
              f"pico {t['pico']['anio']} con {t['pico']['n']}")
        if t["recortado"]:
            linea(f"    ! el export está RECORTADO POR FECHA: empieza en {t['desde']} con "
                  f"{t['serie'][t['desde']]} registros, sin rampa de entrada")
        if t["cola_ruido"]["anios"]:
            linea(f"    ! cola de ruido: {t['cola_ruido']['anios']} con "
                  f"{t['cola_ruido']['n']} registro(s) — tratados como in-press, no como año")
        if t["ultimo_parcial"]:
            linea(f"    {t['anio_incompleto']} incompleto en este export "
                  f"({t['n_ultimo']} hasta ahora) · referencia: {t['referencia_de']}"
                  + (f" ({t['export']['texto']})" if t["export"].get("texto") else ""))
        elif not t["anio_referencia"]:
            linea("    ! sin EXPORT DATE en el .txt y sin «anio_actual» declarado: "
                  "no se afirma nada sobre si el último año está completo")
        if t["crecimiento_3a"]:
            linea(f"    últimos 3 años completos ×{t['crecimiento_3a']} frente a los 3 anteriores")
        elif t["crecimiento_nota"]:
            linea(f"    crecimiento: {t['crecimiento_nota']}")

    rel = capas.get("relaciones", {})
    if rel and "error" not in rel:
        linea()
        linea(f"CAPA 2 · RELACIONES   {rel['n_papers']} papers ({rel['pct_papers']:.0f}%) declaran "
              f"una relación · {rel['n_frases']} oraciones recortadas")
        linea(f"    con negación: {rel['negaciones']['n_frases']} frases en "
              f"{rel['negaciones']['n_papers']} papers · {len(rel['negaciones']['citas'])} citables")
        linea(f"    de encuadre (dicen qué se propuso el estudio): "
              f"{rel['encuadre']['n_frases']} ({rel['encuadre']['pct_frases']:.0f}%)")

    v = capas.get("vocabulario", {})
    if v and "error" not in v:
        linea()
        linea(f"CAPA 3 · VOCABULARIO   {v['kw_normalizadas']} keywords normalizadas "
              f"(de {v['kw_crudas']} crudas) · {v['hapax']} aparecen una sola vez "
              f"({v['pct_hapax']:.0f}%)")
        linea(f"    {len(v['racimos'])} racimos · cubren {v['cobertura']['pct']:.0f}% del corpus "
              f"(techo estructural {v['cobertura']['pct_techo']:.0f}%)")
        for x in v["neutralizados"][:4]:
            linea(f"    neutralizado: {x['k']} ({x['n']}) — {x['motivo']}")
        for x in v["racimos"][:6]:
            marca = " ·menor" if x["menor"] else ""
            linea(f"    {x['n_papers']:4d}  {x['rotulo'][:28]:28s}{marca}  "
                  f"{' · '.join(k['k'] for k in x['kw'][1:5])}")

    g = capas.get("region", {})
    if g and "error" not in g:
        linea()
        linea(f"CAPA 4 · REGIÓN DEL ESTUDIO   {g['n_declaran']} declaran "
              f"({g['pct_declaran']:.0f}%) · {g['n_sin_declarar']} no lo dicen")
        for x in g["familias"][:5]:
            linea(f"    {x['n']:4d}  {x['pct_de_declarados']:5.1f}% de los declarados  {x['fam']}")

    af = capas.get("afiliacion", {})
    if af and "error" not in af:
        linea()
        linea(f"CAPA 5 · AFILIACIÓN   {af['n_resueltos']} de {af['n']} resuelven país "
              f"({af['pct_resueltos']:.1f}%) · colaboración internacional "
              f"{af['colaboracion']['n']} ({af['colaboracion']['pct']:.0f}%)")
        for x in af["regiones"][:5]:
            linea(f"    {x['n']:4d}  {x['pct']:5.1f}%  {x['reg']}")
        if af["no_reconocidos"]:
            linea(f"    tokens de país no reconocidos: "
                  f"{', '.join(x['token'][:28] for x in af['no_reconocidos'][:5])}")

    m = capas.get("metodo", {})
    if m and "error" not in m:
        linea()
        linea(f"CAPA 6 · MÉTODO   {m['sin_metodo_declarado']} sin método declarado "
              f"({m['pct_sin_declarar']:.0f}%)")
        for x in m["familias"][:6]:
            linea(f"    {x['n']:4d}  {x['pct']:5.1f}%  {x['fam']}")

    r = capas.get("revistas", {})
    if r and "error" not in r:
        linea()
        linea(f"CAPA 7 · REVISTAS   {r['n_distintas']} distintas · "
              f"top2 {r['pct_top2']:.0f}% · top5 {r['pct_top5']:.0f}% · top10 {r['pct_top10']:.0f}%")
        for x in r["top"][:5]:
            linea(f"    {x['n']:4d}  {x['pct']:4.1f}%  {x['rev'][:56]}")
        linea(f"    con un solo paper: {r['n_una_sola']} revistas · tipos: {r['tipos']}")

    c = capas.get("citas", {})
    if c and "error" not in c:
        linea()
        linea(f"CAPA 9 · CITAS   {c['total']:,} en total · mediana {c['mediana']} · "
              f"máx {c['maximo']} · {c['n_cero']} sin citar ({c['pct_cero']:.0f}%)")
        linea("    " + " · ".join(f"top{k} = {v:.0f}% de las citas" for k, v in c["canon"].items()))
        rv = c["revisiones"]
        if rv["razon"]:
            linea(f"    revisiones: {rv['pct_corpus']:.0f}% del corpus → {rv['pct_canon']:.0f}% "
                  f"del canon (×{rv['razon']})")
        linea(f"    sin DOI: {c['sin_doi']['n']} · en el canon: "
              f"{c['sin_doi']['en_canon'] or 'ninguno'}")
        linea("    los 3 más citados:")
        for x in c["mas_citados"][:3]:
            linea(f"       {x['cit']:4d}c  {x['cpa']:5.1f}/a  {x['y']}  {x['t'][:56]}")
        linea(f"    la frontera ({c['frontera']['desde']}–{t.get('ultimo_real')}), 3 primeros:")
        for x in c["frontera"]["papers"][:3]:
            linea(f"       {x['cit']:4d}c  {x['cpa']:5.1f}/a  {x['y']}  {x['t'][:56]}")

    vc = capas.get("vacios", {})
    if vc and "error" not in vc:
        linea()
        linea(f"CAPA 8 · VACÍOS DECLARADOS   {vc['n_declaran']} papers ({vc['pct']:.0f}%) "
              f"enuncian uno con sus propias palabras")
        for x in vc["papers"][:2]:
            linea(f"    #{x['id']} ({x['y']}) «{x['frases'][0][:120]}…»")

    for k, e in fallos.items():
        linea(f"\n    CAYÓ la capa «{k}»: {e}  — las demás siguieron")

    # ── al disco ────────────────────────────────────────────────────────
    os.makedirs(cfg["salida"], exist_ok=True)
    datos = {
        "version": VERSION,
        "meta": {
            "fuente": os.path.basename(cfg["fuente"]),
            "export": export,          # la cabecera del .txt: hasta dónde llega el corpus
            "titulo": cfg.get("titulo", ""),
            "ecuacion_base": cfg.get("ecuacion_base", ""),
            "idioma": cfg.get("idioma", "es"),
            "n": len(recs),
        },
        "candado0": inf0,
        # No se dibuja: es la fila de la matriz de síntesis del paso siguiente.
        "papers": tabla_papers(recs),
        "avisos": avisos,
        "capas": capas,
        "diagnostico": diag,
        "fallos": fallos,
        "pendientes": [n for n in ("relaciones", "vocabulario", "region", "afiliacion",
                                   "metodo", "vacios") if n not in capas],
    }
    destino = os.path.join(cfg["salida"], "retrato_data.json")
    with io.open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    linea()
    linea("─" * 74)
    linea(f"escrito: {destino}")
    linea(f"capas pendientes (n = ?): {', '.join(datos['pendientes'])}")
    # El título vacío no rompe nada, y por eso pasa desapercibido hasta que alguien
    # abre el HTML y lee «scopus_export_Aug 7-2026_26c24....txt» como encabezado.
    if not cfg.get("titulo", "").strip():
        linea()
        linea("AVISO: no pasaste --titulo. La cabecera del HTML mostrará el")
        linea(f"       nombre del archivo — «{os.path.basename(cfg['fuente'])[:52]}» —")
        linea("       que es lo primero que ve quien lo abre. Escribe cuatro o cinco palabras.")


# -*- coding: utf-8 -*-
"""
emitir.py — dibuja el retrato a partir de retrato_data.json. No calcula nada:
si una cifra no está en el JSON, no aparece en la pantalla.

    python emitir.py <proyecto>/retrato.json

Reglas que el archivo hace cumplir:
  · Una capa ausente NO bloquea ni se inventa: se dibuja con «n = ?» diciendo qué falta.
  · Ningún titular es una carencia. El titular dice lo que el dato habilita; la
    cautela va al pie, con el rótulo «Tómalo con mesura».
  · El pie de límites se genera de lo que corrió, no es un texto fijo.
"""
import io, os, re, sys, json, html


_VERSION_EMITIR = "0.6.1"
e = html.escape

# ─────────────────────────────────────────────────────── cadenas visibles

L = {
    "es": {
        "kicker": "Retrato del corpus · antes de decidir nada",
        "registros": "registros distintos", "ventana": "ventana",
        "revistas": "revistas", "palabras": "palabras clave",
        "con_resumen": "con resumen", "con_kw": "con keywords",
        "mesura": "Tómalo con mesura:", "habilita": "Esto te habilita a",
        "pendiente": "todavía sin calcular",
        "limites_tit": "Lo que este retrato <b>no</b> dice",
        "pie": "Retrato generado sobre",
        "t1": "Cuándo se escribió", "t2": "Cuánto de tu campo mide",
        "t3": "Y de qué temas habla",
        "t4": "Dónde se estudia",
        "t5": "De dónde son los autores", "t6": "Con qué lo estudian",
        "t7": "Dónde se publica", "t8": "Qué dicen tus autores que falta",
        "t9": "Por dónde empezar a leer",
    }
}

CSS = """
:root{--tinta:#10222B;--tinta-2:#3D5561;--tinta-3:#6E838C;--linea:#D3DCD9;--papel:#EDF1EF;
 --sup:#FFF;--verde:#1F6F6B;--verde2:#2E948C;--vino:#8E3550;--ambar:#B8891C;
 --sombra:0 1px 0 rgba(16,34,43,.04),0 8px 24px -18px rgba(16,34,43,.5);
 --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
 --sans:"Segoe UI",-apple-system,Inter,system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--papel);color:var(--tinta);font-family:var(--sans);font-size:15px;
 line-height:1.5;-webkit-font-smoothing:antialiased}
.hoja{max-width:1180px;margin:0 auto;padding:32px 24px 64px}
header.portada{background:var(--tinta);color:#EAF1EF;border-radius:14px;padding:26px 30px 22px;
 box-shadow:var(--sombra);position:relative;overflow:hidden}
header.portada::after{content:"";position:absolute;right:-70px;top:-70px;width:260px;height:260px;
 border-radius:50%;background:radial-gradient(circle,rgba(46,148,140,.30),transparent 68%)}
.kicker{font-size:11px;letter-spacing:.20em;text-transform:uppercase;color:#8FBDB6;font-weight:600}
header.portada h1{font-family:var(--serif);font-weight:400;font-size:31px;line-height:1.18;
 margin:8px 0 4px;max-width:28ch}
.ecuacion{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;color:#9DB7B4;margin-top:10px;
 padding-top:10px;border-top:1px solid rgba(255,255,255,.13);max-width:80ch;line-height:1.65}
.ecuacion b{color:#CFE3DF}
.censo{display:flex;flex-wrap:wrap;gap:26px;margin-top:16px;position:relative;z-index:1}
.censo div{min-width:78px}
.censo b{display:block;font-family:var(--serif);font-size:26px;line-height:1;color:#fff}
.censo span{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#8FBDB6}
.rejilla{display:grid;grid-template-columns:repeat(6,1fr);gap:18px;margin-top:18px}
.bloque{background:var(--sup);border:1px solid var(--linea);border-radius:14px;padding:20px 22px 18px;
 box-shadow:var(--sombra);display:flex;flex-direction:column}
.w6{grid-column:span 6}.w3{grid-column:span 3}
@media(max-width:900px){.w3{grid-column:span 6}}
.rotulo{font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--tinta-3);font-weight:700}
.rotulo .ac{color:var(--ambar);letter-spacing:.1em}
.cifra{font-family:var(--serif);font-size:54px;line-height:.92;letter-spacing:-.02em;margin:12px 0 2px}
.cifra small{font-size:24px;letter-spacing:0}
.cifra.hueco{color:var(--tinta-3)}
.frase{font-family:var(--serif);font-size:17px;line-height:1.35;margin:6px 0 0;max-width:36ch}
.nota{font-size:12.5px;color:var(--tinta-2);margin-top:8px}
.habilita{margin-top:auto;padding:2px 0 0 13px;border-left:3px solid var(--verde2);font-size:12.5px;
 color:var(--tinta-2);margin-left:1px}
.habilita b{color:var(--verde);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
 display:block;margin-bottom:3px}
.sep{height:1px;background:var(--linea);margin:16px 0 14px}
.par{display:flex;gap:30px;align-items:flex-start;flex-wrap:wrap;margin-top:6px}
.izq{flex:0 0 208px}
.der{flex:1 1 320px;min-width:290px}
.barras{display:grid;grid-template-columns:auto 1fr auto;gap:5px 12px;align-items:center;font-size:13px}
.barras i{font-style:normal;color:var(--tinta-2);white-space:nowrap;overflow:hidden;
 text-overflow:ellipsis;max-width:29ch}
.barras u{text-decoration:none;height:11px;border-radius:3px;background:var(--verde2);display:block;opacity:.92}
.barras b{font-variant-numeric:tabular-nums;font-size:12.5px;font-weight:600;min-width:34px;text-align:right}
.barras .pale u{background:#B7C9C6}
.pt{width:9px;height:9px;border-radius:2px;display:inline-block}
.pila{display:flex;height:26px;border-radius:5px;overflow:hidden;margin:14px 0 8px;border:1px solid var(--linea)}
.pila span{display:flex;align-items:center;justify-content:center;font-size:11px;color:#fff;font-weight:600;
 overflow:hidden;white-space:nowrap}
.leyenda{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--tinta-2)}
.leyenda i{font-style:normal;display:inline-flex;align-items:center;gap:6px}
.cita{border-left:2px solid var(--linea);padding:2px 0 2px 12px;margin:11px 0;font-size:12.5px;
 color:var(--tinta-2);font-style:italic;line-height:1.45}
.cita span{display:block;font-style:normal;font-size:11px;color:var(--tinta-3);margin-top:4px}
.rej3{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:0 24px}
.lec{list-style:none;margin:0;padding:0}
.lec li{display:flex;gap:12px;align-items:baseline;padding:8px 0;border-bottom:1px dotted var(--linea)}
.lec li:last-child{border-bottom:0}
.lec .c{font-family:var(--serif);font-size:20px;line-height:1;color:var(--verde);min-width:46px;
 text-align:right;font-variant-numeric:tabular-nums}
.lec .tt{font-family:var(--serif);font-size:14px;line-height:1.28;display:block}
.lec .m{font-size:11.5px;color:var(--tinta-3);display:block;margin-top:2px}
.lec .m u{text-decoration:none;color:var(--tinta-2);font-weight:600}
.lec a{color:inherit;text-decoration:none}
.lec a:hover .tt{text-decoration:underline}
.tag{display:inline-block;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;background:#F2F6F4;
 border:1px solid var(--linea);border-radius:20px;padding:1px 7px;color:var(--tinta-2);vertical-align:1px}
.subrot{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--tinta-2);font-weight:700;
 margin:0 0 6px}
.tiras{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.tira{flex:1 1 200px;background:#FCFDFC;border:1px solid var(--linea);border-radius:10px;padding:10px 13px}
.tira b{font-family:var(--serif);font-size:19px;display:block;line-height:1.1}
.tira span{font-size:11.5px;color:var(--tinta-2);display:block;margin-top:3px;line-height:1.4}
.anios{display:flex;justify-content:space-between;font-size:10.5px;color:var(--tinta-3);margin-top:2px;
 font-variant-numeric:tabular-nums}
.hueco-caja{border:1px dashed #C9B98E;background:#FFFDF6;border-radius:12px;padding:16px 18px;margin-top:10px}
.hueco-caja b{color:#6E5A18}
.diag{margin-top:18px;background:#FDF6F7;border:1px solid #E3C6CE;border-left:5px solid var(--vino);
 border-radius:12px;padding:15px 20px 13px;box-shadow:var(--sombra)}
.diag h3{font-family:var(--serif);font-weight:400;font-size:19px;margin:0 0 6px;color:var(--vino)}
.diag p{margin:0;font-size:13.5px;color:var(--tinta-2);line-height:1.55;max-width:88ch}
.diag+.diag{margin-top:10px}
.limites{margin-top:18px;background:#FFFDF6;border:1px solid #E6DCC2;border-radius:14px;padding:18px 22px}
.limites h3{font-family:var(--serif);font-weight:400;font-size:18px;margin:0 0 10px;color:#6E5A18}
.limites ul{margin:0;padding-left:18px;font-size:13px;color:var(--tinta-2);line-height:1.6}
.limites li{margin-bottom:5px}.limites b{color:var(--tinta)}
.nulos{border:1px solid var(--linea);border-left:3px solid var(--vino);border-radius:0 11px 11px 0;
 padding:13px 16px 9px;margin-top:16px;background:#FDFBFB}
.nulos>b{font-family:var(--serif);font-weight:400;font-size:16px;display:block;margin-bottom:2px}
.pie{margin-top:22px;font-size:11.5px;color:var(--tinta-3);text-align:center;line-height:1.6}
"""

COLORES = ["#1F6F6B", "#8E3550", "#2E948C", "#B8891C", "#3F8F6B", "#4A6D8C", "#A35A2A",
           "#6B5B95", "#2C7A7B", "#94643E", "#55806E", "#8C6D9E", "#5A7A50", "#7A5A46"]


# ───────────────────────────────────────────────────────────── piezas sueltas

def mil(x):
    return f"{x:,}".replace(",", ".")


def plural(n, singular, plural_=None):
    """«1 registro» / «10 registros», no «1 registro(s)». La forma con paréntesis
    se cuela sola al escribir la cadena y se ve en cuanto n vale 1."""
    return f"{mil(n)} {singular if n == 1 else (plural_ or singular + 's')}"


def conc(n, uno, varios):
    """La forma que le toca al verbo o al sustantivo según n. Existe porque
    «1 papers declaran» y «1 revistas aportan un solo paper» solo se ven cuando
    n vale UNO — y en los tres corpus de trabajo ninguna cifra vale uno, así que
    el defecto vivió entero hasta que un corpus sintético de un solo paper lo
    sacó. Es el mismo descuido que dejó una cifra de cuatro dígitos sin separar:
    interpolar el número crudo saltándose la función que existe para eso."""
    return uno if n == 1 else varios


def dec(x, n=1):
    """Un decimal con COMA, y sin el «,0» cuando no aporta.

    Dos motivos. El «.0» sobra —«100%», no «100.0%»—. Y el punto NO puede ser el
    separador decimal aquí: el documento entero usa el punto para los miles, así
    que «3.8%» junto a «1.310 papers» se lee como treinta y ocho por ciento."""
    t = f"{float(x):.{n}f}"
    t = t[:-(n + 1)] if t.endswith("." + "0" * n) else t
    return t.replace(".", ",")


def hab(txt):
    return f'<div class="habilita"><b>{L["es"]["habilita"]}</b>{txt}</div>'


def mesura(txt):
    return f'<p class="nota"><b>{L["es"]["mesura"]}</b> {txt}</p>'


def lente(valor, casos):
    """El titular se ELIGE por umbral, no se escribe fijo.

    Una frase fija —«hay un canon, y es corto»— produce el hallazgo pase lo que
    pase: es una cuota disfrazada. Aquí cada lámina declara sus cortes y la
    frase sale del dato. Si ninguna lente dispara, se dice qué se midió y ya.

    `casos` es una lista de (umbral_mínimo, texto) de mayor a menor.
    """
    for corte, texto in casos:
        if valor >= corte:
            return texto
    return casos[-1][1]


HUECOS = []          # los rótulos que salieron con «n = ?», para reportarlos al final


def hueco(rotulo, que_falta, como):
    """Una capa que no corrió —o que corrió y espera una lectura—: se dibuja el
    hueco, no se inventa ni se calla. Y se anota, para que la consola no diga
    «0 huecos» mientras la pantalla enseña uno."""
    HUECOS.append(rotulo)
    return f"""<section class="bloque w6">
<div class="rotulo">{rotulo} <span class="ac">· {L['es']['pendiente']}</span></div>
<div class="par"><div class="izq"><div class="cifra hueco">n = ?</div></div>
<div class="der"><div class="hueco-caja"><b>{que_falta}</b><p class="nota" style="margin-top:6px">{como}</p></div></div></div>
</section>"""


def barras(filas, tope=None, pale_desde=None):
    if not filas:
        return ""
    tope = tope or max(f[1] for f in filas) or 1
    out = []
    for i, (etq, n, *resto) in enumerate(filas):
        cls = ' class="pale"' if pale_desde is not None and i >= pale_desde else ""
        out.append(f'<i{cls}>{e(etq)}</i><u style="width:{100.0*n/tope:.1f}%"></u>'
                   f'<b>{mil(n)}</b>')
    return '<div class="barras">' + "".join(out) + "</div>"


def enlace(x):
    """El título con su DOI detrás. La clase `tt` le da la tipografía de la lista;
    sin ella el título sale como texto corrido y la lámina pierde jerarquía."""
    t = f'<span class="tt">{e(x["t"] or "(sin título)")}</span>'
    return f'<a href="https://doi.org/{e(x["doi"])}" target="_blank" rel="noopener">{t}</a>' \
        if x.get("doi") else t


# ─────────────────────────────────────────────────────────────── las láminas

def b_tiempo(c):
    s = c.get("serie") or {}
    if not s:
        return ""
    anios = sorted(int(a) for a in s)
    vals = [s[str(a)] if str(a) in s else s[a] for a in anios]
    W, H, PAD, TOP = 600, 150, 20, 14
    tope = max(vals) or 1
    pts = []
    for i, v in enumerate(vals):
        x = PAD + (i * (W - 2 * PAD) / max(1, len(vals) - 1))
        y = H - 10 - (v / tope) * (H - 10 - TOP)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    area = f"M{PAD},{H-10} L" + " L".join(pts) + f" L{W-PAD},{H-10} Z"
    ipico = vals.index(tope)
    px, py = pts[ipico].split(",")
    corte = ""
    if c["ultimo_parcial"] and c.get("anio_incompleto") in anios:
        # La línea va sobre el año que de verdad está a medias —el del export—,
        # no sobre el borde derecho: con ahead-of-print el borde es otro año.
        ix = anios.index(c["anio_incompleto"])
        cx = PAD + (ix * (W - 2 * PAD) / max(1, len(vals) - 1))
        corte = (f'<line x1="{cx:.1f}" y1="20" x2="{cx:.1f}" y2="{H-10}" stroke="#B8891C" '
                 f'stroke-width="1" stroke-dasharray="3 3"/>'
                 f'<text x="{cx-4:.1f}" y="72" font-size="10" fill="#B8891C" text-anchor="end">'
                 f'{c["anio_incompleto"]} parcial</text>')
    avisos = []
    exp = (c.get("export") or {}).get("texto")
    if c["ultimo_parcial"]:
        # Lo que deja incompleto un año no es que el año siga corriendo: es el día
        # en que se bajó el archivo. Dicho así, la frase no caduca.
        avisos.append(f'El export se bajó el {exp}, así que {c["anio_incompleto"]} '
                      f'está incompleto <b>en este archivo</b>: la caída del final es de la '
                      f'fecha en que lo pediste, no del campo.'
                      if exp else
                      f'{c["anio_incompleto"]} lleva {mil(c["n_ultimo"])} registros y está '
                      f'incompleto: la caída del final es del calendario, no del campo.')
    elif c.get("anio_referencia"):
        avisos.append(f'El corpus llega completo hasta {c["ultimo_real"]}.')
    else:
        avisos.append(f'El <i>.txt</i> no trae fecha de export y no se declaró <code>anio_actual</code>: '
                      f'esta lámina no puede decir si {c["ultimo_real"]} está completo o a medias.')
    if c["cola_ruido"]["anios"]:
        nc = c["cola_ruido"]["n"]
        avisos.append(f'{plural(nc, "registro fechado", "registros fechados")} en '
                      f'{", ".join(str(a) for a in c["cola_ruido"]["anios"])} '
                      f'{conc(nc, "es un adelanto", "son adelantos")} <i>in press</i>: '
                      f'no {conc(nc, "cuenta", "cuentan")} como año.')
    nota = " ".join(avisos)

    # dec(): el punto ya separa los miles en este documento, así que «por 1.32»
    # se lee como ciento treinta y dos. Se arregló para los porcentajes y se
    # quedó sin arreglar para las razones, que es donde nadie miró.
    cre = (f' Los últimos tres años completos multiplican por <b>{dec(c["crecimiento_3a"], 2)}</b> '
           f'a los tres anteriores.' if c.get("crecimiento_3a") else "")

    if c["despegue"]:
        titular = (f'<div class="cifra">{c["pct_desde_despegue"]:.0f}<small>%</small></div>'
                   f'<p class="frase" style="font-size:15.5px">del corpus se publicó '
                   f'<b>desde {c["despegue"]}</b>. Antes de ese año hay '
                   f'{mil(c["antes_del_despegue"])} papers.</p>'
                   f'<p class="nota">La mitad del corpus es posterior a '
                   f'{c["anio_mediana"]}.{cre}</p>')
    else:
        titular = (f'<div class="cifra">{c["anio_mediana"]}</div>'
                   f'<p class="frase" style="font-size:15.5px">es el año en que se acumula '
                   f'<b>la mitad del corpus</b>. No hay despegue medible.</p>'
                   + mesura(f'{e(c["sin_despegue"])}. Por eso esta lámina no da un año de '
                            f'arranque: daría uno falso.'))
    if c["recortado"]:
        titular += mesura(f'el export <b>viene recortado por fecha</b>: empieza en {c["desde"]} '
                          f'con {plural(vals[0], "registro")}, sin rampa de entrada. Lo que ves es '
                          f'la ventana que pediste, no la historia del campo.')
    if not c.get("crecimiento_3a") and c.get("crecimiento_nota"):
        titular += f'<p class="nota">Crecimiento: {e(c["crecimiento_nota"])}.</p>'

    return f"""<section class="bloque w6">
<div class="rotulo">{L['es']['t1']}</div>
<div class="par">
 <div class="izq">{titular}</div>
 <div class="der">
  <svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img">
   <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#2E948C" stop-opacity=".38"/>
    <stop offset="100%" stop-color="#2E948C" stop-opacity=".03"/></linearGradient></defs>
   <line x1="{PAD}" y1="{H-10}" x2="{W-PAD}" y2="{H-10}" stroke="#D3DCD9"/>
   <path d="{area}" fill="url(#g1)"/>
   <polyline points="{poly}" fill="none" stroke="#1F6F6B" stroke-width="2.2" stroke-linejoin="round"/>
   <circle cx="{px}" cy="{py}" r="3.4" fill="#1F6F6B"/>
   <text x="{float(px)-3:.0f}" y="{float(py)-5:.0f}" font-size="11" fill="#1F6F6B"
     text-anchor="end" font-weight="700">{mil(tope)}</text>{corte}
  </svg>
  <div class="anios"><span>{anios[0]}</span><span>{anios[len(anios)//2]}</span><span>{anios[-1]}</span></div>
  <p class="nota">{nota}</p></div></div>
{hab(f"situar tu revisión en el tiempo. Un campo que concentra el {c['pct_desde_despegue']:.0f}% "
     f"de su producción desde {c['despegue']} no tiene consenso todavía: tiene frentes abiertos "
     f"—y una revisión de hace tres años ya envejeció."
     if c["despegue"] else
     f"saber qué ventana estás mirando. La mitad de lo que tienes es posterior a "
     f"{c['anio_mediana']}, pero el arranque del campo queda fuera del export: para hablar de "
     f"cuándo empezó todo esto harías falta bajar el corpus sin filtro de fecha.")}
</section>"""


def b_relaciones(c):
    """Cuánto de este campo MIDE en vez de describir — y qué no le resultó.

    Aquí hubo un mapa de constructos, con fichas de antecedentes, mediadores y
    desenlaces. Se retiró: exigía que alguien leyera y nombrara las familias entre
    dos corridas del script, y era el único punto del retrato donde el modelo tenía
    que leer el corpus. Lo que queda sale del mismo recorte, sin lectura ninguna,
    y el panel de resultados nulos es lo que más rinde de toda la lámina: una
    relación que un autor publicó como NO significativa es una pregunta ya
    contestada — sirve para no repetirla y sirve para discutirla.
    """
    if not c.get("n_frases"):
        return ""

    ng, en = c["negaciones"], c["encuadre"]
    citas = "".join(
        f'<p class="cita">{e(x["o"])}<span>{e(x["y"])}'
        + (f' · <a href="https://doi.org/{e(x["doi"])}" target="_blank" rel="noopener">doi</a>'
           if x.get("doi") else "") + '</span></p>' for x in ng.get("citas", []))
    nulos = ""
    if ng["n_frases"]:
        nulos = f"""<div class="nulos"><b>Y lo que no resultó</b>
<p class="nota" style="margin-top:2px">{mil(ng['n_frases'])} de esas oraciones —el
 {ng['pct_frases']:.0f}%, en {plural(ng['n_papers'], "paper")}— {conc(ng['n_frases'], "declara", "declaran")}
 que la relación <b>no</b> apareció.
 Un resultado nulo publicado es una pregunta ya contestada.</p>{citas}</div>"""

    # Los marcos, ordenados: con qué fórmula gramatical declara este campo.
    MARCO = {"efecto": "el efecto de… sobre…", "mediador": "el papel mediador de…",
             "papel": "el papel de… en…", "relacion": "la relación entre… y…",
             "predictor": "los determinantes de…", "verbo": "afecta · predice · explica",
             "asociado": "asociado positiva o negativamente",
             "condicion": "depende de…"}
    filas = [(MARCO.get(k, k), v) for k, v in c["por_marco"].items()]

    cifra = mil(c["n_papers"])
    suj = "de tus papers declaran" if c["n_papers"] != 1 else "paper de tu corpus declara"
    frase = lente(c["pct_papers"], [
        (65, f"{suj} una relación entre variables. Este es un campo que "
             "<b>mide</b>: casi todo lo que hay dentro pone una cosa a explicar otra."),
        (35, f"{suj} una relación entre variables. Conviven dos literaturas: "
             "una que <b>mide</b> y otra que <b>describe</b>."),
        (0,  f"{suj} una relación entre variables. El resto <b>describe</b>: "
             "casos, panoramas, revisiones."),
    ])

    return f"""<section class="bloque w6">
<div class="rotulo">{L['es']['t2']} <span class="ac">· medir no es lo mismo que describir</span></div>
<div class="par">
 <div class="izq"><div class="cifra">{cifra}</div>
  <p class="frase" style="font-size:15.5px">{frase}</p>
  <p class="nota">Sale de <b>{mil(c['n_frases'])}</b> oraciones donde un autor escribe «el efecto
   de… sobre…», «el papel mediador de…», «predice». Son textuales y se conserva la negación: un
   recorte mecánico convertiría «la edad <i>no</i> predice» en «edad →».</p>
  {mesura(f"{mil(en['n_frases'])} de esas oraciones —el {en['pct_frases']:.0f}%— "
          f"{conc(en['n_frases'], 'es', 'son')} de <b>encuadre</b>: "
          f"{conc(en['n_frases'], 'anuncia', 'anuncian')} lo que el estudio se propuso, no lo que "
          f"halló. Y esto cuenta oraciones, no hallazgos: un paper que declara cinco relaciones "
          f"pesa cinco veces aquí.")}</div>
 <div class="der"><p class="subrot">Con qué fórmula lo declaran</p>
  {barras(filas, pale_desde=4)}{nulos}</div></div>
{hab("saber si tu pregunta encaja. En un campo que mide, una pregunta descriptiva se defiende "
     "sola pero compite con poco; en uno que describe, medir es la contribución. Y los resultados "
     "nulos de arriba son las preguntas que ya no hace falta volver a hacer.")}
</section>"""


def b_vocabulario(c):
    """Los objetos de estudio: lo que queda tras restar lo que otra lámina reclamó.

    Una nube de palabras clave mezcla el objeto con las variables, porque el autor
    etiqueta su paper con los dos. Aquí se resta lo que las láminas de método y
    región ya nombraron, y lo que sobra se enseña como lista corta: quince líneas se
    leen en veinte segundos; sesenta racimos no se leen nunca.

    Lo que separa objeto de variable sin más ayuda es la ECUACIÓN BASE: los términos
    que la búsqueda ya pidió no pueden contar como hallazgo. Declararla importa.
    """
    obj = c.get("objetos") or []
    if not obj:
        return ""
    TOPE = 15
    top = obj[:TOPE]
    filas = [(o["k"], o["n"]) for o in top]
    rec = c.get("reclamado") or []
    por_lamina = {}
    for r in rec:
        por_lamina.setdefault(r["por"], []).append(r["k"])
    resta = " · ".join(
        f'<b>{len(v)}</b> a {e(k)} <i>({", ".join(e(x) for x in v[:3])}…)</i>'
        for k, v in sorted(por_lamina.items(), key=lambda kv: -len(kv[1])))

    neu = ", ".join(f'<b>«{e(x["k"])}»</b> — {e(x["motivo"])}' for x in c["neutralizados"][:4])
    # El aviso SEÑALA, no agrupa. No dice que sean sinónimos —eso no lo puede
    # saber un recuento—: dice que el orden de la lista es frágil y que hay que
    # mirarlo antes de creerse el titular.
    var, avi = c.get("variantes"), ""
    if var:
        lista = " · ".join(f'«{e(x["k"])}» {mil(x["n"])}' for x in var["entradas"][:4])
        avi = mesura(
            f'el orden de esta lista <b>depende de una lectura tuya</b>. '
            f'{plural(len(var["entradas"]), "entrada")} de aquí '
            f'{conc(len(var["entradas"]), "contiene", "contienen")} «<b>{e(var["raiz"])}</b>» y entre '
            f'ellas suman {mil(var["suma"])} papers — por encima de los {mil(var["lider"]["n"])} de '
            f'«{e(var["lider"]["k"])}», que encabeza. {lista}. Si son <b>la misma cosa escrita de '
            f'varias maneras</b>, ninguna grafía enseña su peso real y el orden de arriba engaña; si '
            f'son <b>objetos distintos que comparten una palabra</b>, el orden está bien. Un recuento '
            f'no puede distinguirlo. Tú sí, leyéndolas.')
    deg = ""
    if c.get("degenerado"):
        deg = mesura(
            f'el agrupamiento por co-ocurrencia <b>degeneró</b>: un solo racimo se llevó el '
            f'{c["mayor_racimo"]["pct_de_cubiertos"]:.0f}% de los papers cubiertos, así que no dice '
            f'nada y no se dibuja. La lista de arriba no depende de él —sale de contar palabras, '
            f'no de agruparlas—.')

    return f"""<section class="bloque w6">
<div class="rotulo">{L['es']['t3']} <span class="ac">· los objetos de estudio, no las variables</span></div>
<div class="par">
 <div class="izq"><div class="cifra">{mil(top[0]['n'])}</div>
  <p class="frase" style="font-size:15.5px">papers estudian <b>{e(top[0]['k'])}</b>, el objeto más
   frecuente de tu corpus. Debajo, los {len(top)} mayores.</p>
  <p class="nota">Una palabra clave no distingue el <i>objeto</i> de la <i>variable</i>: el autor
   etiqueta su paper con los dos. Por eso aquí se resta lo que otra lámina ya nombró — {resta}.</p>
  {mesura(f"{mil(c['hapax'])} de las {mil(c['kw_normalizadas'])} palabras clave —el "
          f"{c['pct_hapax']:.0f}%— aparecen una sola vez y no entran en ninguna cuenta. El "
          f"vocabulario compartido de este campo es pequeño.")}</div>
 <div class="der">{barras(filas, pale_desde=8)}</div></div>
<p class="nota" style="margin-top:12px"><b>Fuera del mapa</b>: {neu}. Lo que tu ecuación ya pidió no
 puede ser un hallazgo.</p>
{avi}
{deg}
{hab("ver dónde cae tu tema y cuánta compañía tiene. Si tu objeto está arriba, compites; si no "
     "aparece, o es nuevo o lo llamas de otra manera — y las dos cosas se comprueban buscándolo "
     "en esta lista.")}
</section>"""


def b_region(c):
    fam = c.get("familias") or []
    if not fam:
        return ""
    filas = [(f["fam"], f["n"]) for f in fam]
    dos = c.get("pct_top2", 0)
    if len(fam) == 1:                      # un corpus con una sola región declarada
        return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t4']}</div>
<div class="cifra">{mil(fam[0]["n"])}</div>
<p class="frase">estudios situados, <b>todos en {e(fam[0]['fam'])}</b>. Es la única región que
 aparece declarada.</p>
{mesura(f"{conc(c['n_declaran'], 'es el único paper que sí dice', 'son los ' + mil(c['n_declaran']) + ' papers que sí dicen')} "
        f"dónde; los otros {mil(c['n_sin_declarar'])} no lo mencionan en el resumen. Con una sola "
        f"región no hay comparación posible: mira el bloque de afiliación para saber si el campo "
        f"es así o el corpus lo es.")}
{hab("saber que tu corpus no reparte terreno. O el tema es local, o la búsqueda lo acotó.")}
</section>"""
    # El titular miraba solo la concentración y nunca lo DELGADA que era la base.
    # En el corpus de IA solo un tercio del corpus dice dónde, y la lámina
    # declaraba «el terreno del campo es estrecho» con la misma seguridad que en
    # un corpus donde lo dicen tres cuartas partes. Con la base por debajo del
    # 40% el titular deja de hablar del campo y habla de lo que sí puede.
    base = c.get("pct_declaran", 100)
    if base < 40:
        titular = (f'<div class="cifra">{mil(c["n_declaran"])}</div>'
                   f'<p class="frase">estudios dicen <b>en qué terreno</b> se hicieron: el '
                   f'{dec(base)}% del corpus. Entre ellos {e(fam[0]["fam"])} encabeza con el '
                   f'{fam[0]["pct_de_declarados"]:.0f}%, y ese reparto es el de ese tercio, no el '
                   f'del campo.</p>')
    else:
        # `pct_top2` SUMA dos barras, y un estudio situado en las dos cuenta en
        # las dos: era el único número de esta lámina que no era un conteo de
        # papers, y se enseñaba como si lo fuera. Las cifras por familia sí lo
        # son —«Europa 170» son 170 papers—, así que el titular usa esas dos y
        # el solape se declara en el pie. `dos` se queda como umbral, no como
        # cifra: decide qué frase sale, no se enseña.
        titular = lente(dos, [
            (60, (f'<div class="cifra">{fam[0]["pct_de_declarados"]:.0f}<small>%</small></div>'
                  f'<p class="frase">de los estudios situados ocurren en <b>{e(fam[0]["fam"])}</b> '
                  f'y el {fam[1]["pct_de_declarados"]:.0f}% en <b>{e(fam[1]["fam"])}</b>. '
                  f'El terreno del campo es estrecho.</p>')),
            (0, (f'<div class="cifra">{len(fam)}</div>'
                 f'<p class="frase">regiones aparecen en los estudios situados, y <b>ninguna manda</b>: '
                 f'{e(fam[0]["fam"])} encabeza con el {fam[0]["pct_de_declarados"]:.0f}%. '
                 f'Es un campo repartido por el mundo.</p>')),
        ])
    # «El bloque de al lado recupera a casi todos» era una frase fija que nadie
    # había medido. Ahora la capa cuenta, sobre los papers que NO declaran
    # región, cuántos sí resuelven país de afiliación — y la frase sale de ahí.
    rec, recu = c.get("recupera_afiliacion"), ""
    if rec and c["n_sin_declarar"]:
        recu = lente(rec["pct"], [
            (85, f' De esos, <b>{mil(rec["n"])}</b> sí resuelven el país de sus autores en el bloque '
                 f'de al lado: el hueco es del resumen, no del corpus.'),
            (40, f' De esos, {mil(rec["n"])} —el {rec["pct"]:.0f}%— resuelven el país de sus autores '
                 f'en el bloque de al lado; del resto no queda rastro ninguno.'),
            (0,  f' Y solo {mil(rec["n"])} —el {rec["pct"]:.0f}%— resuelven país de afiliación, así '
                 f'que el bloque de al lado <b>no</b> recupera este hueco.'),
        ])
    return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t4']}</div>
{titular}
<div class="sep"></div>
{barras(filas)}
{mesura(f"los porcentajes son sobre los <b>{mil(c['n_declaran'])} papers que sí declaran dónde</b>. "
        f"Un estudio puede situarse en <b>más de una región</b> —{mil(c.get('multiregion', 0))} lo "
        f"hacen— y cuenta en cada una, así que la suma de las barras pasa del total. "
        f"Los otros {mil(c['n_sin_declarar'])} no lo mencionan en el resumen —y eso no significa que no "
        f"tengan terreno, sino que el resumen no lo dice—.{recu}")}
{hab("ver en qué territorios el campo ya trabajó y en cuáles apenas asomó. Y a distinguir dos cosas "
     "que se confunden: que <em>nadie lo haya estudiado aquí</em>, y que <em>nadie diga dónde lo "
     "estudió</em>.")}
</section>"""


def b_afiliacion(c):
    filas = [(r["reg"], r["n"]) for r in c["regiones"]]
    top = ", ".join(f'{e(p["pais"])} {mil(p["n"])}' for p in c["paises"][:8])
    # «La afiliación sí está» se imprimía igual con el 99% que con el 30%.
    titular = lente(c["pct_resueltos"], [
        (85, (f'<div class="cifra">{c["pct_resueltos"]:.0f}<small>%</small></div>'
              f'<p class="frase">La afiliación <b>sí está</b>: {mil(c["n_resueltos"])} de '
              f'{plural(c["n"], "registro")} {conc(c["n_resueltos"], "trae", "traen")} país. '
              f'Donde el resumen callaba, el pie de autor habla.</p>')),
        (50, (f'<div class="cifra">{c["pct_resueltos"]:.0f}<small>%</small></div>'
              f'<p class="frase">de los registros resuelven el país de sus autores — '
              f'{mil(c["n_resueltos"])} de {mil(c["n"])}. Más de la mitad, <b>no todos</b>: lo que '
              f'sigue describe a esos.</p>')),
        (0,  (f'<div class="cifra">{mil(c["n_resueltos"])}</div>'
              f'<p class="frase">registros resuelven el país de sus autores, el '
              f'{dec(c["pct_resueltos"])}% del corpus. Bastan para ver <b>quién firma esto</b>, no '
              f'para hablar del campo entero.</p>')),
    ])
    return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t5']} <span class="ac">· no dónde se hizo el estudio</span></div>
{titular}
<div class="sep"></div>
{barras(filas)}
<p class="nota" style="margin-top:12px">Países con más firmas: {top}.</p>
<p class="nota">{mil(c['colaboracion']['n'])} papers ({c['colaboracion']['pct']:.0f}%) están firmados
 desde más de una región: colaboración internacional.</p>
{mesura("esto mide quién produce el conocimiento; el bloque anterior, sobre qué territorio. "
        "Un equipo de Wageningen puede estudiar hogares de Kenia. No son lo mismo y conviene no "
        "cruzarlos.")}
{hab("ver que el hueco del bloque anterior era <em>del resumen</em>, no del campo — y saber con "
     "quién se colabora en este tema.")}
</section>"""


def b_metodo(c):
    fam = c.get("familias") or []
    if not fam:
        return ""
    filas = [(f["fam"], f["n"]) for f in fam]
    p = fam[0]
    dos = fam[1] if len(fam) > 1 else None
    # El titular se elige por la VENTAJA sobre el segundo, no se escribe fijo.
    # En el corpus de agronomía el primero le saca diez papers al segundo sobre
    # 3.441 —734 contra 724, y el desempate es alfabético— y esta frase decía
    # «es el instrumento dominante del campo». Candado 4.
    v = c.get("ventaja_sobre_2o")
    base = c.get("pct_declaran", 100)
    cifra = mil(p["n"])
    # Con la base delgada el titular deja de hablar del campo y habla de lo que
    # sí puede — igual que la lámina 4 por debajo del 40% de declarantes. Aquí
    # importa más todavía: «sin método declarado» no distingue entre un resumen
    # que calla y una ficha que no conoce el vocabulario del dominio. Sin este
    # tramo, un corpus de enfermería podía coronar «encuesta o cuestionario»
    # como instrumento dominante del campo siendo dominante entre el 15% que la
    # ficha supo reconocer.
    if base < 40:
        cifra = mil(c.get("n_declaran", p["n"]))
        frase = (f'estudios nombran algún instrumento en su resumen: el {dec(base)}% del corpus. '
                 f'Entre ellos encabeza <b>{e(p["fam"].lower())}</b> con {mil(p["n"])} — y ese '
                 f'reparto es el de esa parte, no el del campo.')
    elif not dos:
        frase = (f'estudios usan <b>{e(p["fam"].lower())}</b>: es el único instrumento que este '
                 f'corpus llega a declarar.')
    elif not v:
        frase = (f'estudios usan <b>{e(p["fam"].lower())}</b>, el instrumento más frecuente, por '
                 f'delante de {e(dos["fam"].lower())} ({mil(dos["n"])}).')
    else:
        # La razón se ENSEÑA, no se adjetiva. «Con casi el doble que el siguiente»
        # era una frase fija colgada de un umbral que dispara desde 1,50 y no
        # tiene techo: decía lo mismo con 1,5 que con 2,5 que con 6 — y en el
        # corpus de desperdicio, con 2,48, subestimaba. Es el mismo defecto que
        # esta lámina venía a arreglar, cometido al arreglarlo. Si hay número,
        # va el número.
        frase = lente(v, [
            (1.50, f'estudios usan <b>{e(p["fam"].lower())}</b>: es el instrumento dominante del '
                   f'campo — multiplica por <b>{dec(v, 2)}</b> a {e(dos["fam"].lower())}, que va '
                   f'segundo con {mil(dos["n"])}.'),
            (1.15, f'estudios usan <b>{e(p["fam"].lower())}</b>, el instrumento más frecuente, por '
                   f'delante de {e(dos["fam"].lower())} ({mil(dos["n"])}).'),
            (0,    f'estudios usan <b>{e(p["fam"].lower())}</b> y {mil(dos["n"])} usan '
                   f'<b>{e(dos["fam"].lower())}</b>: van <b>a la par</b>. Este campo no tiene un '
                   f'instrumento dominante — tiene dos, y elegir entre ellos es una decisión tuya.'),
        ])
    # Cuando la mitad del corpus sale sin método, la sospecha razonable ya no es
    # que los autores callen: es que la ficha esté escrita en otro vocabulario.
    # Pasó de verdad —un corpus de agronomía daba 54% con una ficha de ciencias
    # sociales— y no se puede detectar desde dentro, así que se declara.
    ficha = (" Y si tu campo pasa del <b>medio centenar por ciento</b> sin declarar, sospecha de "
             "la ficha antes que del corpus: estas familias se escribieron mirando ciencias "
             "sociales, agronomía y educación, y otro dominio puede nombrar sus instrumentos con "
             "palabras que aquí no están."
             if c["pct_sin_declarar"] >= 50 else "")
    return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t6']}</div>
<div class="cifra">{cifra}</div>
<p class="frase">{frase}</p>
<div class="sep"></div>
{barras(filas, pale_desde=5)}
{mesura(f"{mil(c['sin_metodo_declarado'])} papers ({c['pct_sin_declarar']:.0f}%) no nombran ningún método "
        f"<i>en el resumen</i>. Pueden estar usándolo sin declararlo, y muchos son conceptuales o "
        f"de revisión. Un paper puede llevar varios métodos: la suma pasa del total.{ficha}")}
{hab(f"elegir con qué compites. Si eliges {e(p['fam'].lower())} entras donde ya hay {mil(p['n'])}; "
     f"los instrumentos del final de la lista están casi libres.")}
</section>"""


def b_revistas(c):
    top = c.get("top") or []
    if not top:
        return ""
    # Se dibujan hasta CINCO segmentos, pero pueden ser menos. Restar 5 fijo daba
    # «otras -4 revistas» en cualquier corpus con menos de cinco — y salía junto a
    # «el 100% del corpus vive en dos revistas de las 1 que hay».
    seg, ley = [], []
    pintadas = top[:5]
    for i, x in enumerate(pintadas):
        col = COLORES[i % 6]
        etq = f'{e(x["rev"][:26])} · {mil(x["n"])}' if x["pct"] > 8 else ""
        seg.append(f'<span style="width:{x["pct"]:.1f}%;background:{col}">{etq}</span>')
        ley.append(f'<i><span class="pt" style="background:{col}"></span>{e(x["rev"][:30])} {x["n"]}</i>')
    otras = c["n_distintas"] - len(pintadas)
    if otras > 0:
        resto = 100 - sum(x["pct"] for x in pintadas)
        seg.append(f'<span style="width:{max(0,resto):.1f}%;background:#D3DCD9"></span>')
        ley.append(f'<i><span class="pt" style="background:#D3DCD9"></span>otras '
                   f'{plural(otras, "revista")}</i>')
    p1 = top[0]["pct"]
    # Con una sola revista, pct_top2 vale 100 y el primer caso de la lente decía
    # «el 100% del corpus vive en DOS revistas de las 1 que hay». La palabra
    # «dos» está escrita fija y da por hecho que hay al menos dos.
    if c["n_distintas"] < 2:
        titular = (f'<div class="cifra">1</div>'
                   f'<p class="frase">revista, y dentro de ella está <b>el corpus entero</b>. '
                   f'No hay reparto que mirar: o el tema vive ahí, o tu búsqueda lo acotó a esa '
                   f'revista — y las dos cosas conviene decirlas en el método.</p>')
        return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t7']}</div>
{titular}
<div class="sep"></div>
<p class="nota">{e(top[0]['rev'])} · {plural(top[0]['n'], "paper")}. Tipos de documento:
 {', '.join(f'{k} {mil(v)}' for k, v in c['tipos'].items())}.</p>
{mesura("una sola revista no es un campo: es un canal. Nombrarlo en tu método evita que un lector "
        "confunda el alcance de la revista con el alcance del tema.")}
{hab("saber que este corpus no informa sobre dónde se publica el tema, porque no hay comparación "
     "posible dentro de él.")}
</section>"""
    titular = lente(c["pct_top2"], [
        (25, (f'<div class="cifra">{c["pct_top2"]:.0f}<small>%</small></div>'
              f'<p class="frase">del corpus vive en <b>dos revistas</b> de las '
              f'{mil(c["n_distintas"])} que hay.</p>')),
        (15, (f'<div class="cifra">{c["pct_top2"]:.0f}<small>%</small></div>'
              f'<p class="frase">en las dos primeras revistas. Hay cabeza, pero '
              f'<b>no una revista-hogar</b>: {mil(c["n_distintas"])} títulos se reparten el resto.</p>')),
        (0, (f'<div class="cifra">{mil(c["n_distintas"])}</div>'
             f'<p class="frase">revistas distintas y <b>ninguna domina</b>: la primera apenas '
             f'reúne el {dec(p1)}%. Es una producción dispersa, sin revista-hogar.</p>')),
    ])
    return f"""<section class="bloque w3">
<div class="rotulo">{L['es']['t7']}</div>
{titular}
<div class="pila">{''.join(seg)}</div>
<div class="leyenda">{''.join(ley)}</div>
<p class="nota" style="margin-top:12px">{plural(c['n_una_sola'], "revista")}
 {conc(c['n_una_sola'], "aporta", "aportan")} un solo paper.
 Tipos de documento: {', '.join(f'{k} {mil(v)}' for k, v in c['tipos'].items())}.</p>
{mesura("que unas pocas revistas marquen el ritmo condiciona lo que el corpus contiene. No es un "
        "defecto del campo ni de tu búsqueda: es una característica que conviene nombrar en tu método.")}
{hab("saber a dónde se manda este tema, y con qué tiempos.")}
</section>"""


def b_vacios(c):
    if not c.get("papers"):
        return ""
    cit = []
    for p in c["papers"][:3]:
        if not p.get("frases"):
            continue
        f = p["frases"][0]
        f = f if len(f) < 300 else f[:297] + "…"
        cit.append(f'<div class="cita">«{e(f)}»<span>#{p["id"]} · {e(p["y"])}'
                   f'{" · " + e(p["doi"]) if p["doi"] else ""}</span></div>')
    return f"""<section class="bloque w6">
<div class="rotulo">{L['es']['t8']}</div>
<div class="par">
 <div class="izq"><div class="cifra">{mil(c["n_declaran"])}</div>
  <p class="frase" style="font-size:15.5px">papers te entregan un vacío <b>con las palabras de su
   autor</b>, listo para citar en tu justificación.</p>
  {mesura(f"son {c['pct']:.0f} de cada 100. No esperes encontrar uno hecho a la medida de tu tema "
          f"—y que un vacío no esté declarado no significa que no exista.")}</div>
 <div class="der"><div class="rej3">{''.join(cit)}</div></div></div>
{hab("escribir tu justificación citando a otros y no a ti mismo. Cada frase es textual y viene con "
     "su registro y su DOI detrás.")}
</section>"""


def b_citas(c, hasta):
    def lista(items):
        out = []
        for x in items:
            rv = ' <span class="tag">revisión</span>' if x["dt"].lower() == "review" else ""
            uni = "cita" if x["cpa"] == 1 else "citas"      # «1 citas/año» no es español
            out.append(f'<li><span class="c">{mil(x["cit"])}</span><div>{enlace(x)}'
                       f'<span class="m">{e(x["y"])} · {e(x["rev"][:38])} · '
                       f'<u>{dec(x["cpa"])} {uni}/año</u>{rv}</span></div></li>')
        return '<ol class="lec">' + "".join(out) + "</ol>"

    # El canon sale vacío cuando el corpus es minúsculo o nadie tiene citas: no hay
    # nada que concentrar. Sin esta guarda, `list(can.values())[-1]` reventaba con
    # IndexError y se caía la lámina entera — un corpus de tres papers, que es
    # justo lo que trae alguien probando el skill por primera vez.
    can = c["canon"] or {}
    k50 = can.get(50) or (list(can.values())[-1] if can else 0)
    rv = c["revisiones"]
    tiras = [f'<div class="tira"><b>{mil(c["mediana"])}</b><span>citas tiene el paper <b>mediano</b>. '
             f'El más citado llega a {mil(c["maximo"])}.</span></div>']
    if rv.get("razon"):
        tiras.append(f'<div class="tira"><b>{rv["pct_corpus"]:.0f}% → {rv["pct_canon"]:.0f}%</b>'
                     f'<span>Las <b>revisiones</b> son el {rv["pct_corpus"]:.0f}% del corpus pero el '
                     f'{rv["pct_canon"]:.0f}% del canon: ×{dec(rv["razon"], 2)} de lo que les tocaría. '
                     f'Son el atajo para entrar.</span></div>')
    # «Casi todos son recientes» era una frase fija: nadie miraba el año de esos
    # papers. Un paper sin citar de hace ocho años no es nuevo, es ignorado.
    cz = c.get("cero") or {}
    cola = lente(cz.get("pct_recientes", 100), [
        (80, 'Casi todos son recientes: no son papers malos, son papers nuevos.'),
        (50, f'{mil(cz.get("recientes", 0))} son de {cz.get("desde", "")} en adelante; los demás '
             f'llevan más tiempo publicados sin que nadie los cite.'),
        (0,  f'Solo {mil(cz.get("recientes", 0))} son de {cz.get("desde", "")} en adelante: la '
             f'mayoría lleva años publicada y sigue sin recibir una cita.'),
    ]) if cz.get("n") else ""
    tiras.append(f'<div class="tira"><b>{mil(c["n_cero"])}</b><span>papers tienen <b>cero citas</b>. '
                 f'{cola}</span></div>')
    if c["sin_doi"]["n"]:
        tiras.append(f'<div class="tira"><b>{mil(c["sin_doi"]["n"])} sin DOI</b><span>y '
                     f'{"ninguno está" if not c["sin_doi"]["en_canon"] else "alguno está"} en estas '
                     f'listas. Para esos, la trazabilidad llega hasta la referencia, no hasta el '
                     f'enlace.</span></div>')
    return f"""<section class="bloque w6">
<div class="rotulo">{L['es']['t9']} <span class="ac">· conteo de citas del propio export</span></div>
<div class="par">
 <div class="izq">{lente(k50, [
      (40, (f'<div class="cifra">{mil(c["n_canon"])}</div>'
            f'<p class="frase" style="font-size:15.5px">papers concentran el <b>{k50:.0f}%</b> de '
            f'las {mil(c["total"])} citas. <b>Hay un canon, y es corto.</b></p>')),
      (25, (f'<div class="cifra">{k50:.0f}<small>%</small></div>'
            f'<p class="frase" style="font-size:15.5px">de las {mil(c["total"])} citas está en '
            f'{mil(c["n_canon"])} papers. <b>Hay una cabeza reconocible</b>, pero no manda sola.</p>')),
      (0, (f'<div class="cifra">{mil(c["total"])}</div>'
           f'<p class="frase" style="font-size:15.5px">citas en total. '
           + (f'Los {mil(c["n_canon"])} más citados reúnen solo el {k50:.0f}%: este campo <b>no tiene '
              f'obra de referencia</b> — nadie puede decir «los cinco imprescindibles».</p>'
              if can else
              '<b>No hay canon que medir</b>: el corpus es demasiado pequeño, o casi nadie '
              'ha sido citado todavía.</p>'))),
  ])}
  {f'<p class="nota">{" · ".join(f"los {k} primeros suman el {v:.0f}%" for k, v in can.items())}.</p>'
   if can else ""}
  <p class="nota" style="margin-top:9px">{
   'Las dos listas no son la misma ordenada distinto: la de la derecha son papers que '
   '<b>no aparecen</b> en la primera todavía.'
   if not (c["frontera"].get("en_ambas") or []) else
   f'Las dos listas <b>se solapan</b> en {plural(len(c["frontera"]["en_ambas"]), "paper")}: hay '
   f'trabajo reciente que ya entró en el canon del campo.'}</p></div>
 <div class="der"><p class="subrot">El canon · lo más citado</p>{lista(c['mas_citados'][:6])}</div>
 <div class="der"><p class="subrot">La frontera · {c['frontera']['desde']}–{hasta}</p>
  {lista(c['frontera']['papers'][:6])}</div></div>
<div class="tiras">{''.join(tiras)}</div>
{mesura("las citas miden atención, no calidad. Favorecen lo antiguo, lo publicado en inglés y lo que "
        "sale en revistas de alta rotación. Sirven para decidir por dónde entrar, no qué vale.")}
{hab("empezar el lunes por la mañana. Y si tu tema queda lejos de ambas listas, eso también es una "
     "respuesta.")}
</section>"""


# ────────────────────────────────────────────── pie de límites, generado

def limites(d):
    c, capas = d["candado0"], d["capas"]
    li = ["<b>No dice calidad.</b> Cuenta papers, no los pesa: un artículo antiguo con cientos de "
          "citas vale aquí lo mismo que uno recién salido."]
    if c["duplicados"]:
        ids = ", ".join("#%d y #%d" % (x["ids"][0], x["ids"][1]) for x in c["duplicados"][:3])
        li.append(f"<b>El export traía {plural(len(c['duplicados']), 'paper repetido', 'papers repetidos')}</b> ({ids}): "
                  f"{mil(c['n_parseados'])} registros, {mil(c['n_distintos'])} distintos. Se cuenta una sola "
                  f"vez. Lo que no puede detectar es la misma obra publicada con DOI distintos.")
    g = capas.get("region")
    if g:
        li.append(f"<b>«Sin región declarada» no es «sin región».</b> Son {mil(g['n_sin_declarar'])} "
                  f"papers cuyo resumen no menciona dónde. El dato falta en el texto, no "
                  f"necesariamente en el estudio.")
    if capas.get("afiliacion"):
        li.append("<b>La afiliación no es el lugar del estudio.</b> Dice desde qué institución se "
                  "firma; para saber dónde se trabajó hay que leer el artículo.")
    if capas.get("vocabulario"):
        v = capas["vocabulario"]
        li.append(f"<b>Una palabra clave no es un tema.</b> El {v['pct_hapax']:.0f}% de las palabras "
                  f"clave de este corpus aparece una sola vez, así que la lista de objetos enseña lo "
                  f"que se repite, no todo lo que se estudia. Lo que no se repite no sale.")
    rl = capas.get("relaciones")
    if rl and rl.get("n_frases"):
        li.append(f"<b>La lámina 2 cuenta oraciones, no hallazgos, y NO dice qué se relaciona con "
                  f"qué.</b> Dice cuántos papers declaran alguna relación y con qué fórmula la "
                  f"enuncian; un paper que declara cinco pesa cinco veces. Nombrar las variables "
                  f"del campo exige leer las {mil(rl['n_frases'])} oraciones — están en "
                  f"<code>retrato_data.json</code>, y ese es trabajo de la matriz de síntesis.")
    if capas.get("metodo") or capas.get("vacios"):
        li.append("<b>Todo se lee del resumen, no del artículo.</b> Un método usado sin mencionarlo, "
                  "o un vacío que el autor no enuncia, no aparecen aquí. Esto describe <b>lo que el "
                  "corpus declara</b>, no lo que el campo hizo.")
    t = capas.get("tiempo")
    if t and t.get("ultimo_parcial"):
        # Antes decía «y lo estará mientras corra el año», y eso caduca: quien
        # abra este retrato en 2028 leería una frase falsa. Lo que deja el año a
        # medias es la FECHA DEL EXPORT, que está en la cabecera del .txt y no
        # cambia nunca. Dicho así, sigue siendo cierto dentro de diez años.
        curso = t.get("anio_incompleto") or t.get("ultimo_real") or t["hasta"]
        exp = (t.get("export") or {}).get("texto")
        li.append(f"<b>{curso} está incompleto en este export</b>"
                  + (f", que se bajó el {exp}" if exp else "") +
                  ". Lo que falta de ese año no es del campo: es de la fecha en que pediste "
                  "el archivo, y no va a aparecer por esperar.")
    elif t and not t.get("anio_referencia"):
        li.append("<b>No se sabe si el último año está completo.</b> El <code>.txt</code> no trae "
                  "<code>EXPORT DATE</code> y no se declaró <code>anio_actual</code>, así que esta "
                  "lámina no afirma nada sobre el final de la serie.")
    if d.get("pendientes"):
        li.append(f"<b>Faltan capas por calcular</b>: {', '.join(d['pendientes'])}. Sus bloques "
                  f"aparecen arriba con «n = ?» en vez de con una cifra inventada.")
    for k, v in (d.get("fallos") or {}).items():
        li.append(f"<b>La capa «{k}» falló</b> y no se dibujó: {e(str(v))}")
    return ('<div class="limites"><h3>' + L["es"]["limites_tit"] + "</h3><ul>"
            + "".join(f"<li>{x}</li>" for x in li) + "</ul></div>")


# ────────────────────────────────────────────────────────────────── armado

def construir(d_):
    HUECOS.clear()
    d = d_
    m, capas = d["meta"], d["capas"]
    c0 = d["candado0"]
    cob = c0["cobertura"]
    partes = []

    dup = ""
    if c0["duplicados"]:
        n_p, n_d = c0["n_parseados"], c0["n_distintos"]
        dup = (f'<br>El export trae <b>{plural(n_p, "registro")} y {mil(n_d)} '
               f'{conc(n_d, "es distinto", "son distintos")}</b>: '
               f'{plural(len(c0["duplicados"]), "repetido")} por DOI o título idéntico. '
               f'Todo lo que sigue cuenta {mil(n_d)}.')
    t = capas.get("tiempo", {})
    r = capas.get("revistas", {})
    v = capas.get("vocabulario", {})
    censo = [(mil(c0["n_distintos"]), L["es"]["registros"]),
             (f'{t.get("desde","?")}–{t.get("hasta","?")}', L["es"]["ventana"]),
             (mil(r.get("n_distintas", 0)), L["es"]["revistas"]),
             (mil(v.get("kw_normalizadas", 0)), L["es"]["palabras"]),
             (f'{dec(cob["resumen"]["pct"])}%', L["es"]["con_resumen"]),
             (f'{dec(cob["keywords"]["pct"])}%', L["es"]["con_kw"])]

    diag = "".join(
        f'<div class="diag"><h3>{e(d["titulo"])}</h3><p>{e(d["texto"])}</p></div>'
        for d in d_.get("diagnostico", []))

    partes.append(f"""<header class="portada">
<div class="kicker">{L['es']['kicker']}</div>
<h1>{e(m['titulo'] or m['fuente'])}</h1>
<div class="censo">{''.join(f'<div><b>{a}</b><span>{b}</span></div>' for a,b in censo)}</div>
<div class="ecuacion">{e(m['ecuacion_base']) or '(ecuación base no declarada)'}{dup}</div>
</header>{diag}<div class="rejilla">""")

    # CANDADO 5 · una capa que no está SE DIBUJA. Cada lámina declara qué necesita
    # para salir; si eso falta, en su lugar va el hueco con «n = ?» diciendo por
    # qué. Nunca desaparece en silencio: un retrato al que le faltan dos láminas y
    # no lo dice es un retrato que miente por omisión, y el lector no tiene forma
    # de saber si su corpus no daba para eso o si el script se rompió.
    LAMINAS = [
        ("tiempo",      L["es"]["t1"], None,        lambda c: b_tiempo(c)),
        ("relaciones",  L["es"]["t2"], "n_frases",  lambda c: b_relaciones(c)),
        ("vocabulario", L["es"]["t3"], "objetos",   lambda c: b_vocabulario(c)),
        ("region",      L["es"]["t4"], "familias",  lambda c: b_region(c)),
        ("afiliacion",  L["es"]["t5"], "regiones",  lambda c: b_afiliacion(c)),
        ("metodo",      L["es"]["t6"], "familias",  lambda c: b_metodo(c)),
        ("revistas",    L["es"]["t7"], None,        lambda c: b_revistas(c)),
        ("vacios",      L["es"]["t8"], "papers",    lambda c: b_vacios(c)),
        # El rótulo de la frontera usa el último año REAL: `hasta` puede ser un
        # ahead-of-print que la lámina 1 acaba de declarar que no cuenta como año.
        ("citas",       L["es"]["t9"], None,        lambda c: b_citas(c, t.get("ultimo_real", ""))),
    ]
    fallos = d_.get("fallos") or {}
    for clave, rot, exige, dibuja in LAMINAS:
        capa = capas.get(clave)
        if capa is None:
            partes.append(hueco(rot, "la capa no llegó a correr",
                                "No está en <code>retrato_data.json</code>. Vuelve a correr "
                                "<code>retrato_unico.py</code> y mira qué dice la consola."))
        elif "error" in capa or clave in fallos:
            partes.append(hueco(rot, "la capa falló y no se dibuja",
                                f"<code>{e(str(capa.get('error') or fallos.get(clave)))}</code>. "
                                f"Las demás láminas no dependen de esta."))
        elif exige and not capa.get(exige):
            partes.append(hueco(rot, "el corpus no dio material para esta lámina",
                                f"La capa corrió, pero <code>{exige}</code> salió vacío: este "
                                f"corpus no declara lo que esta lámina cuenta. No es un fallo "
                                f"del script — es un dato sobre tu corpus."))
        else:
            partes.append(dibuja(capa))

    partes.append("</div>")
    partes.append(limites(d))
    partes.append(f'<div class="pie">{L["es"]["pie"]} <b>{e(m["fuente"])}</b> · '
                  f'{mil(c0["n_parseados"])} registros en el export, {mil(c0["n_distintos"])} distintos · '
                  f'sin léxico declarado para ninguna de estas cifras.<br>'
                  f'retrato-corpus v{VERSION}</div>')

    return (f'<!DOCTYPE html><html lang="{m.get("idioma","es")}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(m["titulo"] or m["fuente"])} — retrato del corpus</title>'
            f'<style>{CSS}</style></head><body><div class="hoja">'
            + "".join(partes) + "</div></body></html>")


def _emitir():
    utf8()
    cfg = arg_config(sys.argv, os.path.basename(__file__))
    origen = os.path.join(cfg["salida"], "retrato_data.json")
    if not os.path.exists(origen):
        print(f"no encuentro {origen}\ncorre antes:  python retrato.py {sys.argv[1]}",
              file=sys.stderr)
        raise SystemExit(1)
    with io.open(origen, encoding="utf-8") as f:
        d = json.load(f)

    destino = os.path.join(cfg["salida"], "retrato.html")
    with io.open(destino, "w", encoding="utf-8") as f:
        f.write(construir(d))
    dibujadas = [k for k, v in d["capas"].items() if "error" not in v]
    print(f"escrito: {destino}  ({os.path.getsize(destino)/1024:.0f} KB)")
    print(f"láminas dibujadas: {len(dibujadas)} · con hueco «n = ?»: {len(HUECOS)}"
          f"{' (' + ', '.join(HUECOS) + ')' if HUECOS else ''}")


# ══════════════════════════════════════════════════════════════════════════
#  La CLI del archivo único: calcular y emitir en una sola pasada.
#  En el skill son dos comandos porque el JSON se puede reusar sin recalcular.
#  Aquí es uno solo: quien corre esto lo hace una vez, en un chat.
# ══════════════════════════════════════════════════════════════════════════

def main():
    utf8()
    _calcular()
    _emitir()
    print()
    print("LISTO. Se escribieron DOS archivos:")
    print("   retrato.html       ábrelo en el navegador")
    print("   retrato_data.json  NO lo borres: es lo que necesita el paso 2")


if __name__ == "__main__":
    main()
