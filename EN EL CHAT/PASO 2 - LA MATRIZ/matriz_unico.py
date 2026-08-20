# -*- coding: utf-8 -*-
"""
matriz_unico.py — el skill matriz-sintesis en UN SOLO ARCHIVO.

    python matriz_unico.py

Busca en la carpeta el .txt de Scopus y el retrato_data.json que dejó el
paso 1, y escribe matriz.html. Sin dependencias: Python 3.9+ y nada más.

La columna de CONSTRUCTOS va vacía y declarada: nombrarlos es un paso
aparte, porque la ficha que los define tiene que poder auditarse.

GENERADO por construir_unico_matriz.py desde matriz-sintesis v0.1.
NO SE EDITA A MANO: se edita el skill y se regenera.
"""
import io, os, re, sys
from collections import Counter

RX_DOI = re.compile(r"^DOI:\s*(\S+)", re.M)
RX_REFS = re.compile(r"^REFERENCES:\s*(.*)", re.M | re.S)
RX_CAMPO = re.compile(r"^[A-Z][A-Z0-9 /&'()-]{2,44}:", re.M)
RX_NOALFA = re.compile(r"[^a-z0-9]+")
LARGO_MIN = 34          # un titulo mas corto que esto no es distintivo


def norm(s):
    return RX_NOALFA.sub(" ", (s or "").lower()).strip()


def _refs_de(b):
    """Se busca sobre el BLOQUE ENTERO, no sobre el texto ya recortado.

    Buscando dentro del recorte, la posicion 0 cuenta como principio de linea
    para `^`, asi que un registro cuyo campo empieza por una palabra en
    mayusculas seguida de dos puntos se cortaba a cero. Medido: pasaba en 33 de
    1.198 registros y se perdian sus referencias enteras, en silencio."""
    import re as _re
    m = _re.search(r"^REFERENCES:(.*?)(?=^[A-Z][A-Z0-9 /&'-]{2,44}:|\Z)", b, _re.S | _re.M)
    return m.group(1) if m else ""


def refs_por_doi(ruta_txt):
    crudo = io.open(ruta_txt, encoding="utf-8", errors="replace").read()
    d = {}
    for b in crudo.split("SOURCE: Scopus"):
        if len(b.strip()) <= 200:
            continue
        m = RX_DOI.search(b)
        if m:
            d[m.group(1).strip().lower()] = _refs_de(b)
    return d


def indexar(papers):
    """Indice de titulos del corpus por su palabra MAS RARA, para no comparar
    cada referencia contra los 1.196 titulos."""
    tit = {}
    for p in papers:
        t = norm(p["t"])
        if len(t) >= LARGO_MIN:
            tit[p["id"]] = t
    df = Counter()
    for t in tit.values():
        df.update(set(w for w in t.split() if len(w) >= 5))
    indice = {}
    for pid, t in tit.items():
        pals = [w for w in set(t.split()) if len(w) >= 5]
        if pals:
            indice.setdefault(min(pals, key=lambda w: df[w]), []).append(pid)
    return tit, indice


def casar(e_norm, tit, indice, excluir=None):
    """¿Que papers del corpus estan citados en esta entrada de referencia?

    Se comprueba que el titulo del corpus este DENTRO de la entrada entera, no
    que sea igual a un trozo: un titulo con coma —«…food prices, production and
    resource use»— se parte al trocear y dejaria de coincidir. Este fallo dio
    obras marcadas «fuera» que si estaban dentro del corpus.
    """
    fuera = set()
    for w in set(e_norm.split()):
        for pid in indice.get(w, ()):
            if pid == excluir or pid in fuera:
                continue
            if tit[pid] in e_norm:
                fuera.add(pid)
    return fuera


def construir(papers, refs):
    """papers: lista de dicts con id, t, doi, cit. refs: doi -> texto de referencias.
    Devuelve (cita, citado) con conjuntos de ids."""
    tit, indice = indexar(papers)
    cita = {p["id"]: set() for p in papers}
    citado = {p["id"]: set() for p in papers}
    for p in papers:
        r = refs.get((p.get("doi") or "").strip().lower(), "")
        if not r.strip():
            continue
        for entrada in r.split(";"):
            e = norm(entrada)
            if len(e) < LARGO_MIN:
                continue
            for pid in casar(e, tit, indice, p["id"]):
                cita[p["id"]].add(pid)
                citado[pid].add(p["id"])
    return cita, citado

    for trozo in entrada.split(","):
        t = trozo.strip()
        if not t or RX_AUTOR.match(t) or len(t.split()) < 4:
            continue
        return t
    return ""


# ── el canon: a quien lee este campo ─────────────────────────────────────
# «Apellido X.», «Apellido de la X.Y.», «O'Brien A.B.» -> bloque de autores
RX_AUTOR = re.compile(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ'’-]*(?:\s+[\wÀ-ÿ'’-]+)*\s+[A-ZÀ-Ý]\.(?:[A-ZÀ-Ý]\.)*$")
RX_ANIO = re.compile(r"\((\d{4})\)")


def titulo_de(entrada):
    """El PRIMER trozo que no es autor: en una referencia de Scopus el
    titulo va justo detras de los autores y antes de la revista.

    Antes se cogia el trozo MAS LARGO, y eso fallaba cuando la revista
    abreviada era mas larga que el titulo: «Ajzen I., The theory of planned
    behavior, Organ. Behav. Hum. Decis. Process., ...» devolvia la revista, y
    la obra mas reconocible del campo —123 papers la citan— desaparecia del
    canon sin que nada lo avisara."""
    for trozo in entrada.split(","):
        t = trozo.strip()
        if not t or RX_AUTOR.match(t) or len(t.split()) < 4:
            continue
        return t
    return ""


def canon(refs, papers, tope=30):
    """Devuelve (lista, resumen). Cada obra: titulo, año, papers que la citan,
    y si esta dentro del corpus (con el id, para poder abrir su ficha).

    La clave de una obra es el ID DEL PAPER si la entrada cita a alguien del
    corpus, y el titulo troceado solo si no. Antes se agrupaba siempre por el
    trozo mas largo entre comas, y un titulo con coma dentro —«…food prices,
    production and resource use»— se truncaba: quedaba marcado «fuera» estando
    dentro, y ademas se partia en varias obras distintas.
    """
    tit, indice = indexar(papers)
    por_id = {p["id"]: p for p in papers}

    obras, muestra, anios = Counter(), {}, {}
    n_ent = n_tit = 0
    for r in refs.values():
        if not r.strip():
            continue
        vistas = set()
        for entrada in r.split(";"):
            n_ent += 1
            e = norm(entrada)
            if len(e) < LARGO_MIN:
                continue
            a = RX_ANIO.search(entrada)
            dentro_ids = casar(e, tit, indice)
            if dentro_ids:
                for pid in dentro_ids:
                    k = ("id", pid)
                    vistas.add(k)
                    muestra.setdefault(k, por_id[pid]["t"])
                    anios.setdefault(k, str(por_id[pid]["y"]))
                n_tit += 1
                continue
            t = titulo_de(entrada)
            # umbral PROPIO, mas bajo que el de `casar`. Aquel compara por
            # SUBCADENA y necesita titulos largos para no dar falsos positivos;
            # aqui se agrupa por coincidencia EXACTA y no corre ese riesgo. Con
            # 34 se caia «The theory of planned behavior» —30 caracteres— y con
            # ella la obra que 123 papers del corpus citan.
            if len(t) < 20:
                continue
            n_tit += 1
            k = ("t", norm(t))
            vistas.add(k)
            muestra.setdefault(k, t)
            if a:
                anios.setdefault(k, a.group(1))
        obras.update(vistas)

    # ORDEN ESTABLE. `Counter.most_common()` rompe los empates por orden de
    # inserción, y ese orden depende de recorrer conjuntos de cadenas, que Python
    # aleatoriza en cada proceso: dos corridas daban artefactos distintos. Es el
    # mismo defecto que el bloque 1 resolvió con `top_estable()`. El desempate
    # explícito es por la clave, que no cambia entre corridas.
    orden = sorted(obras.items(), key=lambda kv: (-kv[1], str(kv[0])))

    lista = []
    for k, c in orden[:tope]:
        esta = k[0] == "id"
        lista.append({"t": muestra[k], "y": anios.get(k, ""), "n": c,
                      "dentro": esta, "id": k[1] if esta else None})
    resumen = {
        "entradas": n_ent,
        "obras": len(obras),
        "fuera_20": sum(1 for k, _ in orden[:20] if k[0] != "id"),
        "fuera_50": sum(1 for k, _ in orden[:50] if k[0] != "id"),
    }
    return lista, resumen


import io, os, re, sys, json, html, statistics
from collections import Counter

VERSION = "0.1"
AQUI = os.path.dirname(os.path.abspath(__file__))
_FICHAS = json.loads('{"marcos.json": "{\\n  \\"_que_es\\": \\"Nombres de teor\\u00edas con las que un autor declara el marco de su estudio. A DIFERENCIA de las cinco fichas del bloque 1, esta NO es gen\\u00e9rica: cada disciplina tiene sus teor\\u00edas. Nace incompleta y crece con el uso, igual que metodos.json.\\",\\n  \\"_regla\\": \\"Se busca el NOMBRE de la teor\\u00eda en t\\u00edtulo, resumen y palabras clave. Un paper puede declarar varias y la suma pasa del total. No se infiere el marco de otra cosa: si el autor no lo nombra, para esta capa no lo declara.\\",\\n  \\"_techo\\": \\"Cubre el 8,4% del corpus de desperdicio de alimentos (101 de 1.196). Ese n\\u00famero NO dice que el campo casi no tenga teor\\u00eda: dice que casi no la nombra EN EL RESUMEN. Medido: 123 papers citan a Ajzen 1991 y solo 53 declaran TPB \\u2014 pero de esos 80 que citan sin declarar, solo 6 traen el vocabulario de la teor\\u00eda, as\\u00ed que la subestimaci\\u00f3n real es del orden del 10-30%, no de 2,3 veces. Ver _por_que_no_por_citas.\\",\\n\\n  \\"familias\\": {\\n    \\"Teor\\u00eda del comportamiento planificado (TPB)\\": [\\n      \\"theory of planned behavi\\",\\n      \\"\\\\\\\\bTPB\\\\\\\\b\\",\\n      \\"planned behavi\\\\\\\\w+ theory\\"\\n    ],\\n    \\"Modelo de aceptaci\\u00f3n tecnol\\u00f3gica (TAM)\\": [\\n      \\"technology acceptance model\\",\\n      \\"\\\\\\\\bTAM\\\\\\\\b\\"\\n    ],\\n    \\"UTAUT\\": [\\n      \\"\\\\\\\\bUTAUT\\\\\\\\b\\",\\n      \\"unified theory of acceptance\\"\\n    ],\\n    \\"Teor\\u00eda de activaci\\u00f3n de normas (NAM)\\": [\\n      \\"norm activation\\",\\n      \\"\\\\\\\\bNAM\\\\\\\\b\\"\\n    ],\\n    \\"Valores-creencias-normas (VBN)\\": [\\n      \\"value[- ]belief[- ]norm\\",\\n      \\"\\\\\\\\bVBN\\\\\\\\b\\"\\n    ],\\n    \\"Teor\\u00eda cognitiva social\\": [\\n      \\"social cognitive theory\\"\\n    ],\\n    \\"Teor\\u00eda de la pr\\u00e1ctica social\\": [\\n      \\"social practice theor\\",\\n      \\"\\\\\\\\bpractice theory\\\\\\\\b\\"\\n    ],\\n    \\"Difusi\\u00f3n de innovaciones\\": [\\n      \\"diffusion of innovation\\"\\n    ],\\n    \\"Teor\\u00eda de la autodeterminaci\\u00f3n\\": [\\n      \\"self[- ]determination theory\\"\\n    ],\\n    \\"Teor\\u00eda de la motivaci\\u00f3n protectora\\": [\\n      \\"protection motivation\\"\\n    ],\\n    \\"Est\\u00edmulo-organismo-respuesta (S-O-R)\\": [\\n      \\"stimulus[- ]organism[- ]response\\",\\n      \\"\\\\\\\\bS-O-R\\\\\\\\b\\"\\n    ],\\n    \\"Teor\\u00eda del comportamiento interpersonal\\": [\\n      \\"interpersonal behavi\\\\\\\\w+ (?:theory|model)\\"\\n    ],\\n    \\"Modelo COM-B / rueda del cambio\\": [\\n      \\"\\\\\\\\bCOM-B\\\\\\\\b\\",\\n      \\"behavi\\\\\\\\w+ change wheel\\"\\n    ],\\n    \\"Teor\\u00eda institucional\\": [\\n      \\"institutional theory\\"\\n    ],\\n    \\"Visi\\u00f3n basada en recursos\\": [\\n      \\"resource[- ]based view\\",\\n      \\"\\\\\\\\bRBV\\\\\\\\b\\"\\n    ],\\n    \\"Econom\\u00eda circular como marco\\": [\\n      \\"circular economy (?:framework|theory|principles)\\"\\n    ]\\n  },\\n\\n  \\"_excluido_a_proposito\\": \\"\\u00abgrounded theory\\u00bb NO entra: es un m\\u00e9todo y ya vive en la ficha de instrumentos. Meterla aqu\\u00ed har\\u00eda que un paper cualitativo apareciera declarando marco te\\u00f3rico sin declararlo.\\",\\n\\n  \\"_por_que_no_por_citas\\": \\"Se prob\\u00f3 detectar el marco por la obra fundacional citada \\u2014\\u00absi cita a Ajzen, usa TPB\\u00bb\\u2014 y se descart\\u00f3 con medida. Si un paper CITA a Ajzen 1991, la probabilidad de que declare TPB es del 35%; si lo DECLARA, la de que lo cite es del 81%. O sea: la cita es casi obligatoria para quien usa la teor\\u00eda, pero much\\u00edsimos la citan sin usarla. De los 80 que citan y no declaran, 39 no tienen NI UNO de los cuatro constructos de la teor\\u00eda en su resumen. Ni la cita, ni el nombre, ni el vocabulario establecen que un paper USE una teor\\u00eda: eso lo decide el texto completo. La ficha dice lo que se declara, y punto.\\",\\n\\n  \\"_como_auditar\\": \\"Ante un dominio nuevo: contar cu\\u00e1ntos papers activan cada teor\\u00eda y comprobar contra un grupo de control. Al medir si una se\\u00f1al indica uso de la teor\\u00eda, la cifra decisiva no es el porcentaje entre los sospechosos sino el del grupo que NO da la se\\u00f1al \\u2014 sin esa base, un 7,5% se puede leer como mucho o como poco a voluntad.\\"\\n}\\n", "resultados.json": "{\\n  \\"_que_es\\": \\"F\\u00f3rmulas con las que un autor anuncia a qu\\u00e9 resultado lleg\\u00f3. Gen\\u00e9ricas: pertenecen al oficio acad\\u00e9mico en ingl\\u00e9s, no al tema.\\",\\n  \\"_regla\\": \\"Lo que se guarda es la ORACI\\u00d3N ENTERA Y TEXTUAL, nunca una par\\u00e1frasis. La ficha la muestra entre comillas y con su DOI: es lo que el investigador podr\\u00e1 citar. Se guardan como m\\u00e1ximo dos por paper.\\",\\n  \\"_techo\\": \\"Cobertura del 45,4% en el corpus del taller (543 de 1.196). Un paper que no anuncia su hallazgo con una de estas f\\u00f3rmulas no aparece aqu\\u00ed, y eso NO significa que no tenga resultados: significa que su resumen no los enuncia en primera persona.\\",\\n\\n  \\"senales\\": [\\n    \\"(?:the )?results (?:show|showed|indicate|indicated|reveal|revealed|suggest|suggested|demonstrate|demonstrated|confirm|confirmed|highlight)\\",\\n    \\"(?:the )?findings (?:show|indicate|reveal|suggest|demonstrate|confirm|highlight)\\",\\n    \\"\\\\\\\\bwe (?:find|found) that\\\\\\\\b\\",\\n    \\"(?:this|the) (?:study|paper|research|analysis) (?:found|finds|shows|reveals|revealed)\\",\\n    \\"\\\\\\\\bit was found that\\\\\\\\b\\",\\n    \\"(?:the )?(?:analysis|model|estimation) (?:shows|showed|reveals|revealed|indicates)\\"\\n  ],\\n\\n  \\"_no_confundir\\": \\"Esta ficha es hermana de relaciones.json del bloque 1 y NO la sustituye. Aquella detecta la GRAM\\u00c1TICA relacional \\u2014\\u00abel efecto de X sobre Y\\u00bb\\u2014 y sirve para contar cu\\u00e1nto mide el campo. Esta detecta el ANUNCIO del hallazgo, sea relacional o no. Un paper puede tener una y no la otra.\\"\\n}\\n", "limites.json": "{\\n  \\"_que_es\\": \\"F\\u00f3rmulas con las que un autor reconoce una limitaci\\u00f3n de su propio estudio. Gen\\u00e9ricas: pertenecen al oficio acad\\u00e9mico en ingl\\u00e9s.\\",\\n  \\"_regla\\": \\"Oraci\\u00f3n entera y textual, como m\\u00e1ximo dos por paper. Nunca una par\\u00e1frasis.\\",\\n  \\"_techo\\": \\"LA COBERTURA ES DEL 4,4% (53 de 1.196) Y ESO ES LA LECTURA, NO UN FALLO: las limitaciones no viven en el resumen, viven en la discusi\\u00f3n del texto completo. Un 96% vac\\u00edo quiere decir que el campo no las anuncia en el escaparate, no que no las tenga.\\",\\n\\n  \\"senales\\": [\\n    \\"\\\\\\\\blimitations?\\\\\\\\b\\",\\n    \\"(?:this|the) (?:study|research|paper) (?:is|was|has been) limited\\",\\n    \\"(?:small|limited|modest) sample size\\",\\n    \\"(?:cannot|can not|may not|should not) be generali[sz]ed\\",\\n    \\"\\\\\\\\bgenerali[sz]ability\\\\\\\\b\\",\\n    \\"(?:interpreted|treated) with caution\\",\\n    \\"self[- ]report(?:ed|ing)? (?:bias|data|measures)\\",\\n    \\"cross[- ]sectional (?:design|nature|data)\\",\\n    \\"\\\\\\\\bsocial desirability\\\\\\\\b\\"\\n  ],\\n\\n  \\"_frontera_con_vacios\\": \\"AVISO IMPORTANTE. `vacios.json` del bloque 1 contiene \\u00abfuture research should\\u00bb y \\u00abwarrants further attention\\u00bb, que son de sabor limitaci\\u00f3n. Est\\u00e1n asignadas a VAC\\u00cdOS y NO se repiten aqu\\u00ed: si las dos fichas las reclamaran, el mismo paper saldr\\u00eda en las dos columnas y nadie lo notar\\u00eda. La frontera es: un VAC\\u00cdO es lo que le falta al CAMPO; un L\\u00cdMITE es lo que le falta a ESTE estudio.\\",\\n\\n  \\"_decision_abierta\\": \\"Queda abierto si la columna merece existir con el 96% vac\\u00edo. Argumento a favor, y por eso sigue: un paper que S\\u00cd los reconoce en el resumen es una se\\u00f1al de calidad y merece verse. Se remidi\\u00f3 sobre el corpus de 1.196 y la cobertura no cambi\\u00f3 (4% en 638, 4,4% en 1.196), as\\u00ed que el corpus nuevo no resolvi\\u00f3 la duda.\\"\\n}\\n", "ejes.json": "{\\n  \\"_que_es\\": \\"El reparto de las quince familias de `metodos.json` en TRES EJES distintos. No a\\u00f1ade patrones ni detecta nada nuevo: solo dice a qu\\u00e9 eje pertenece cada familia que el bloque 1 ya reconoci\\u00f3.\\",\\n  \\"_regla\\": \\"Toda familia de `metodos.json` tiene que estar en exactamente UN eje. Si el bloque 1 a\\u00f1ade una familia y aqu\\u00ed no se reparte, la matriz la perder\\u00eda en silencio \\u2014 por eso el arn\\u00e9s comprueba la cobertura.\\",\\n  \\"_techo\\": \\"El eje se hereda de la familia, no del paper. Un paper que declara \\u00abencuesta\\u00bb y \\u00abregresi\\u00f3n\\u00bb aparece en instrumento Y en t\\u00e9cnica, y as\\u00ed debe ser: no son alternativas.\\",\\n\\n  \\"_por_que_existe\\": \\"`metodos.json` mete tres cosas en un solo caj\\u00f3n, y eso hac\\u00eda que el titular de la l\\u00e1mina 6 del retrato comparara \\u00ab734 encuestas contra 724 regresiones\\u00bb COMO SI FUERAN ALTERNATIVAS. No compiten: un paper hace encuesta Y regresi\\u00f3n. La foto-finish del corpus de agronom\\u00eda no era un empate, era una comparaci\\u00f3n mal planteada. Separados en tres ejes, la pregunta deja de ser \\u00abcu\\u00e1l gana\\u00bb y pasa a ser \\u00abcon qu\\u00e9 recogi\\u00f3, con qu\\u00e9 analiz\\u00f3 y c\\u00f3mo mont\\u00f3 el estudio\\u00bb, que son tres preguntas distintas y todas contestables.\\",\\n\\n  \\"ejes\\": {\\n    \\"instrumento\\": {\\n      \\"rotulo\\": \\"instrumento de recolecci\\u00f3n\\",\\n      \\"pregunta\\": \\"\\u00bfcon qu\\u00e9 recogi\\u00f3 el dato?\\",\\n      \\"familias\\": [\\n        \\"Encuesta o cuestionario\\",\\n        \\"Entrevistas y cualitativo\\",\\n        \\"Medici\\u00f3n directa u observaci\\u00f3n\\",\\n        \\"Evaluaci\\u00f3n sensorial\\",\\n        \\"Muestreo y trabajo de terreno\\",\\n        \\"Laboratorio y an\\u00e1lisis instrumental\\"\\n      ]\\n    },\\n    \\"tecnica\\": {\\n      \\"rotulo\\": \\"t\\u00e9cnica de an\\u00e1lisis\\",\\n      \\"pregunta\\": \\"\\u00bfcon qu\\u00e9 lo analiz\\u00f3?\\",\\n      \\"familias\\": [\\n        \\"Modelo estructural (SEM/PLS)\\",\\n        \\"Regresi\\u00f3n y econometr\\u00eda\\",\\n        \\"Conglomerados y segmentaci\\u00f3n\\",\\n        \\"Simulaci\\u00f3n y modelado\\",\\n        \\"An\\u00e1lisis documental y discursivo\\"\\n      ]\\n    },\\n    \\"diseno\\": {\\n      \\"rotulo\\": \\"dise\\u00f1o del estudio\\",\\n      \\"pregunta\\": \\"\\u00bfc\\u00f3mo mont\\u00f3 el estudio?\\",\\n      \\"familias\\": [\\n        \\"Experimento o intervenci\\u00f3n\\",\\n        \\"Estudio de caso\\",\\n        \\"Revisi\\u00f3n y bibliometr\\u00eda\\",\\n        \\"Ensayo de campo y dise\\u00f1o agron\\u00f3mico\\"\\n      ]\\n    }\\n  },\\n\\n  \\"_abierto\\": \\"Queda abierto si el BLOQUE 1 debe partirse igual. A favor: su l\\u00e1mina 6 sigue comparando cosas que no compiten. En contra: el bloque 1 est\\u00e1 subido, en 16/16, y el cambio toca su titular y sus umbrales, que es la zona donde ya aparecieron dos defectos con el arn\\u00e9s en verde. La recomendaci\\u00f3n de la bit\\u00e1cora es hacerlo con calma y con el arn\\u00e9s del bloque 1 delante, no de paso.\\"\\n}\\n"}')
sys.path.insert(0, AQUI)
# enlaces.py va incrustado más arriba, en este mismo archivo.

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# La misma partición de bloques que usa el bloque 1, para que los id coincidan.
SEP_BLOQUE = "SOURCE: Scopus"
RX_DOI = re.compile(r"^DOI:\s*(\S+)", re.M)
RX_TAGS = re.compile(r"</?[a-z]{1,6}>", re.I)
# COPIA LITERAL de retrato.py. No es pereza: si el bloque 2 parte las oraciones
# de otra manera, las frases TEXTUALES que enseña la ficha no son las mismas que
# vio el bloque 1, y el investigador cita una versión distinta de la que se
# midió. Se comprobó: con un partidor propio, 67 papers daban un texto distinto
# —el bloque 1 corta también en punto y coma, y `_sin_pie` recorta la puntuación
# final del resumen— y 5 perdían o ganaban una oración entera.
RX_ORACION = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
RX_PIE = re.compile(
    r"(©|\(c\)\s*\d{4}|Copyright\s*(?:©|\(c\))?\s*\d{4}|All rights reserved"
    r"|Licensee\s+\w+|Published by\s+\w+|The Author\(s\)|This is an open access)",
    re.I)


def sin_pie(t, cola=0.35):
    """El pie de copyright, quitado solo si aparece en el último tercio: en el
    medio del resumen, «all rights reserved» puede ser parte del texto."""
    if not t:
        return t
    m = RX_PIE.search(t, int(len(t) * (1 - cola)))
    return t[:m.start()].rstrip(" .,;·-") if m else t


def para(msg):
    print("\n  PARADA · " + msg + "\n")
    sys.exit(2)


def limpiar(t):
    """COPIA de retrato.py. Scopus exporta acentos como entidades —&#x00E9; por
    é— y a veces doblemente escapadas. Sin deshacerlas, el texto que la ficha
    enseña como TEXTUAL del autor no es el que el autor escribió."""
    if not t:
        return t
    t = RX_TAGS.sub("", t)
    for _ in range(3):
        d = html.unescape(t)
        if d == t:
            break
        t = d
    return t


def campo(bloque, nombre):
    """COPIA de la forma de `_campo` en retrato.py, y no por comodidad.

    La versión propia buscaba el siguiente campo DENTRO del texto ya recortado,
    y ahí la posición 0 cuenta como principio de línea para `^`: un resumen
    estructurado que empieza por «BACKGROUND:» se cortaba a CERO caracteres. El
    paper se quedaba sin resultados, sin límites y sin marco, en silencio. Eran
    33 resúmenes de 1.198. Buscando sobre el bloque entero no pasa.
    """
    m = re.search(r"^%s:(.*?)(?=^[A-Z][A-Z0-9 /&'-]{2,44}:|\Z)" % nombre,
                  bloque, re.S | re.M)
    return limpiar(" ".join(m.group(1).split())) if m else ""


def parsear(ruta):
    """Devuelve {id: {doi, resumen, refs}} con el id por posición de bloque,
    que es como los numera el bloque 1."""
    crudo = io.open(ruta, encoding="utf-8", errors="replace").read()
    out = {}
    n = 0
    for b in crudo.split(SEP_BLOQUE):
        if len(b.strip()) <= 200:
            continue
        n += 1
        d = RX_DOI.search(b)
        out[n] = {"doi": (d.group(1).strip() if d else ""),
                  "resumen": sin_pie(campo(b, "ABSTRACT")),
                  "refs": campo(b, "REFERENCES")}
    return out


def oraciones(a):
    return [" ".join(o.split()) for o in RX_ORACION.split(a or "") if len(o.strip()) > 45]


# Las cuatro fichas y la plantilla van INCRUSTADAS: este archivo viaja solo.
# Son las mismas de matriz-sintesis/, copiadas por construir_unico_matriz.py.
# No se editan aquí: se editan allí y se regenera.

def ficha(nombre):
    if nombre not in _FICHAS:
        raise KeyError(nombre)
    return json.loads(_FICHAS[nombre])



def compilar(patrones):
    return re.compile("|".join(patrones), re.I)


# ───────────────────────────────────────────────────────────── configuración

def _calcular():
    # CAMBIADO respecto del skill: aquí no hay matriz.json. Las rutas las pone
    # la CLI del final, que las descubre en la carpeta. Ni una línea de cálculo
    # cambia: de aquí para abajo es el skill literal.
    p_json, p_txt, salida, raiz = _P_JSON, _P_TXT, _SALIDA, _RAIZ

    if not os.path.exists(p_json):
        para("no está el retrato: %s\n            Organizar lo que no se ha visto no es un "
             "servicio. Corre primero retrato-corpus." % p_json)
    if not os.path.exists(p_txt):
        para("no está el .txt: %s\n            Hace falta AUNQUE ya tengas el retrato: el JSON "
             "guarda `resumen` como booleano, no el texto." % p_txt)

    d = json.load(io.open(p_json, encoding="utf-8"))
    papers = d["papers"]
    bloques = parsear(p_txt)

    # ── CANDADO 0 · ¿son el mismo corpus? ─────────────────────────────────
    # Los id se asignan por posición de bloque. Si el .txt no es el que corrió
    # el retrato, las filas quedarían con el resumen de OTRO paper y no habría
    # forma de notarlo mirando la pantalla.
    con_doi = [p for p in papers if p.get("doi")]
    prueba = con_doi[:200]
    cuadran = sum(1 for p in prueba
                  if bloques.get(p["id"], {}).get("doi", "").lower() == p["doi"].lower())
    pct = 100.0 * cuadran / len(prueba) if prueba else 0
    if prueba and pct < 90:
        para("el .txt y el retrato NO son del mismo corpus: solo cuadra el %.0f%% de los DOI.\n"
             "            Comprueba que `fuente` sea el MISMO archivo que corrió el retrato." % pct)
    if len(bloques) < len(papers):
        para("el .txt trae %d registros y el retrato cuenta %d papers."
             % (len(bloques), len(papers)))

    # ── las fichas ────────────────────────────────────────────────────────
    f_marcos, f_res, f_lim, f_ejes = (ficha("marcos.json"), ficha("resultados.json"),
                                      ficha("limites.json"), ficha("ejes.json"))
    RX_MARCO = {k: compilar(v) for k, v in f_marcos["familias"].items()}
    RX_RES, RX_LIM = compilar(f_res["senales"]), compilar(f_lim["senales"])
    DE_FAMILIA = {fam: eje for eje, v in f_ejes["ejes"].items() for fam in v["familias"]}

    # una familia que el bloque 1 reconoce y aquí no se reparte se perdería en
    # silencio: mejor decirlo que descubrirlo por una columna vacía
    huerfanas = sorted({m for p in papers for m in p.get("metodo", [])} - set(DE_FAMILIA))
    if huerfanas:
        print("   AVISO: familias de método sin eje asignado en ejes.json: %s" % huerfanas)

    # ── la ficha de constructos, si el modelo la escribió ────────────────
    # Vive en el PROYECTO, no en el skill: los constructos son de un corpus
    # concreto y no viajan. Si no está, la columna va vacía y se declara.
    p_con = os.path.join(raiz, "constructos.json")
    RX_CON, meta_con = {}, {"hay": False}
    if os.path.exists(p_con):
        fc = json.load(io.open(p_con, encoding="utf-8"))
        for c in fc.get("familias", []):
            if c.get("nombre") and c.get("patrones"):
                RX_CON[c["nombre"]] = compilar(c["patrones"])
        meta_con = {"hay": bool(RX_CON), "n": len(RX_CON),
                    "nombrado_por": fc.get("_nombrado_por", ""),
                    "grupos": fc.get("grupos", []),
                    "de": {c["nombre"]: c.get("grupo", "") for c in fc.get("familias", [])
                           if c.get("nombre")}}

    vac = {x["id"]: x for x in d["capas"]["vacios"]["papers"]}
    rel = {}
    for f in d["capas"]["relaciones"]["frases"]:
        rel.setdefault(f["id"], []).append(f)
    hasta = d["capas"]["tiempo"]["ultimo_real"]

    # ── las filas ─────────────────────────────────────────────────────────
    filas = []
    for p in papers:
        i = p["id"]
        a = bloques.get(i, {}).get("resumen", "")
        fr = oraciones(a)
        rr = rel.get(i, [])
        edad = max(1, hasta - int(p["y"]) + 1) if str(p["y"]).isdigit() else 1
        blob = " ".join((p["t"], a, " ".join(p.get("kw", [])))).lower()
        filas.append({
            "id": i, "t": p["t"], "au": p["au"], "y": p["y"], "rev": p["rev"],
            "doi": p["doi"], "cit": p["cit"], "cpa": round(p["cit"] / edad, 1),
            "dt": p["dt"], "kw": p.get("kw", [])[:6],
            "region": p.get("region", []), "reg_afil": p.get("reg_afil", []),
            "decada": str(int(p["y"]) // 5 * 5) + "–" + str(int(p["y"]) // 5 * 5 + 4)
                      if str(p["y"]).isdigit() else "—",
            "instrumento": [f for f in p.get("metodo", []) if DE_FAMILIA.get(f) == "instrumento"],
            "tecnica": [f for f in p.get("metodo", []) if DE_FAMILIA.get(f) == "tecnica"],
            "diseno": [f for f in p.get("metodo", []) if DE_FAMILIA.get(f) == "diseno"],
            "marco": [k for k, rx in RX_MARCO.items() if rx.search(blob)],
            "frase_vacio": (vac[i]["frases"][0] if i in vac and vac[i]["frases"] else ""),
            "relaciones": [f["o"] for f in rr if not f["neg"] and not f["enc"]][:2],
            "nulos": [f["o"] for f in rr if f["neg"] and not f["enc"]][:2],
            "resultados": [o for o in fr if RX_RES.search(o)][:2],
            "limites": [o for o in fr if RX_LIM.search(o)][:2],
            # los constructos salen de aplicar los patrones que el MODELO nombró
            # sobre las oraciones relacionales del propio paper, no sobre todo el
            # resumen: es donde el campo declara sus variables
            "constructos": sorted(k for k, rx in RX_CON.items()
                                  if rx.search(" ".join(f["o"] for f in rr))),
        })

    # ── enlaces de cita y canon ───────────────────────────────────────────
    refs = {b["doi"].strip().lower(): b["refs"] for b in bloques.values() if b["doi"]}
    hay_refs = sum(1 for v in refs.values() if v.strip()) > 50
    cita, citado = construir(filas, refs) if hay_refs else ({}, {})
    for f in filas:
        f["cita"] = sorted(cita.get(f["id"], ()))
        f["citado"] = sorted(citado.get(f["id"], ()))
    if hay_refs:
        todas, res_canon = canon(refs, filas, 4000)
        obras = todas[:30]
        nuevas = [o for o in todas if str(o["y"]).isdigit() and int(o["y"]) >= 2021][:20]
    else:
        obras, nuevas, res_canon = [], [], {}

    # ── los papers callados ───────────────────────────────────────────────
    DUROS = ("region", "tecnica", "instrumento", "diseno")
    for f in filas:
        f["callado"] = not any(f[k] for k in DUROS)
    cal = [f for f in filas if f["callado"]]
    rev = [f for f in cal if f["dt"] == "Review"]
    art = [f for f in cal if f["dt"] != "Review"]
    cits = sorted(f["cit"] for f in cal)
    NEUTRAL = {x["k"] for x in d["capas"]["vocabulario"].get("neutralizados", [])}
    kwc = Counter(k.lower().strip() for f in art for k in f["kw"]
                  if k.lower().strip() not in NEUTRAL)
    callados = {
        "n": len(cal), "pct": round(100 * len(cal) / len(filas), 1) if filas else 0,
        "mediana": int(statistics.median(cits)) if cits else 0,
        "max": max(cits) if cits else 0,
        "revisiones": len(rev), "articulos": len(art),
        "pct_rev_grupo": round(100 * len(rev) / len(cal)) if cal else 0,
        "pct_rev_corpus": round(100 * sum(1 for f in filas if f["dt"] == "Review") / len(filas))
                          if filas else 0,
        "sin_kw": sum(1 for f in cal if not f["kw"]),
        "kw": kwc.most_common(6),
        "ecuacion_declarada": bool(d["meta"].get("ecuacion_base")),
    }

    # ── conceptos del grafo ───────────────────────────────────────────────
    conceptos = []
    # Los constructos NO son un eje del grafo ni una persiana: solo se leen en la
    # ficha del paper. Decisión del 19-ago que corrige la tabla de columnas de la
    # §8 — cuando se escribió, no se sabía que los nombraría el modelo, y eso los
    # pone en otra categoría que los ejes salidos de fichas de patrones.
    for tipo, campo_ in (("tecnica", "tecnica"), ("instrumento", "instrumento"),
                         ("diseno", "diseno"), ("region", "region"),
                         ("marco", "marco"), ("revista", None)):
        vals = {}
        for f in filas:
            for v in ([f["rev"]] if campo_ is None else f[campo_]):
                if v:
                    vals.setdefault(v, []).append(f["id"])
        # un constructo con un solo paper no dibuja nada útil, igual que un marco
        minimo = {"revista": 10, "marco": 2}.get(tipo, 1)
        for v in sorted(vals):
            if len(vals[v]) >= minimo:
                conceptos.append({"tipo": tipo, "nombre": v, "papers": vals[v]})

    datos = {
        "version": VERSION,
        "meta": {"titulo": d["meta"].get("titulo") or "", "n_total": d["meta"]["n"],
                 "n_maqueta": len(filas), "ecuacion": d["meta"].get("ecuacion_base", "")},
        "papers": filas, "conceptos": conceptos, "callados": callados,
        "citas": {"hay": hay_refs,
                  "enlaces": sum(len(f["cita"]) for f in filas),
                  "citan": sum(1 for f in filas if f["cita"]),
                  "citados": sum(1 for f in filas if f["citado"])},
        "canon": {"obras": obras, "nuevas": nuevas, "res": res_canon},
        "constructos": meta_con,
    }

    os.makedirs(salida, exist_ok=True)
    destino = os.path.join(salida, "matriz_data.json")
    with io.open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    print("escrito: %s  (%.0f KB)" % (destino, os.path.getsize(destino) / 1024))
    print("   %d papers · %d conceptos · %d callados (%.1f%%)"
          % (len(filas), len(conceptos), callados["n"], callados["pct"]))
    if meta_con["hay"]:
        etiq = sum(1 for f in filas if f["constructos"])
        print("   constructos: %d nombrados · %d papers etiquetados" % (meta_con["n"], etiq))
    else:
        print("   constructos: sin ficha en el proyecto — la columna va vacía y se declara")
    if hay_refs:
        print("   referencias SÍ · %d enlaces de cita · canon de %d obras"
              % (datos["citas"]["enlaces"], len(obras)))
    else:
        print("   referencias NO en este export: sin enlaces de cita y sin canon")


import io, os, sys, json

_VERSION_EMITIR = "0.1"

_PLANTILLA = json.loads('"<!DOCTYPE html><html lang=\\"es\\"><head><meta charset=\\"utf-8\\">\\n<meta name=\\"viewport\\" content=\\"width=device-width, initial-scale=1\\">\\n<title>Matriz de s\\u00edntesis</title>\\n<style>\\n:root{--tinta:#10222B;--tinta-2:#3D5561;--tinta-3:#6E838C;--linea:#D3DCD9;--papel:#EDF1EF;\\n --sup:#FFF;--verde:#1F6F6B;--verde2:#2E948C;--vino:#8E3550;--ambar:#B8891C;\\n --sombra:0 1px 0 rgba(16,34,43,.04),0 8px 24px -18px rgba(16,34,43,.5);\\n --serif:\\"Iowan Old Style\\",\\"Palatino Linotype\\",Palatino,Georgia,serif;\\n --sans:\\"Segoe UI\\",-apple-system,Inter,system-ui,sans-serif}\\n*{box-sizing:border-box}\\nhtml,body{height:100%;overflow:hidden}\\nbody{margin:0;background:var(--papel);color:var(--tinta);font-family:var(--sans);font-size:14px;line-height:1.5}\\n.tablero{height:100%;display:flex;flex-direction:column;gap:9px;padding:10px 12px}\\n.caja{background:var(--sup);border:1px solid var(--linea);border-radius:12px;box-shadow:var(--sombra)}\\n.rotulo{font-size:9.5px;letter-spacing:.17em;text-transform:uppercase;color:var(--tinta-3);font-weight:700}\\n.rotulo .ac{color:var(--ambar);letter-spacing:.09em}\\n\\n/* \\u2500\\u2500 barra superior: cabecera + filtros, todo en una franja \\u2500\\u2500 */\\n.superior{flex:0 0 auto;background:var(--tinta);color:#EAF1EF;border-radius:12px;padding:11px 16px 12px;\\n box-shadow:var(--sombra);position:relative;overflow:hidden}\\n.superior::after{content:\\"\\";position:absolute;right:-60px;top:-90px;width:230px;height:230px;border-radius:50%;\\n background:radial-gradient(circle,rgba(46,148,140,.28),transparent 68%)}\\n.tit{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;position:relative;z-index:1}\\n.tit h1{font-family:var(--serif);font-weight:400;font-size:20px;margin:0}\\n.tit .kicker{font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:#8FBDB6;font-weight:600}\\n.tit .cuenta{margin-left:auto;font-size:12px;color:#9DB7B4;white-space:nowrap}\\n.tit .cuenta b{font-family:var(--serif);font-size:19px;color:#fff}\\n.tit .info{font-size:11px;color:#9DB7B4;cursor:help;border-bottom:1px dotted #6E8A86}\\n.filtros{display:flex;flex-wrap:wrap;gap:5px;align-items:center;margin-top:9px;position:relative;z-index:1}\\n.filtros select,.filtros input{font:inherit;font-size:11.5px;padding:4px 7px;border-radius:6px;\\n border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.09);color:#EAF1EF;max-width:200px}\\n.filtros select option{background:#10222B;color:#EAF1EF}\\n.filtros input::placeholder{color:#7E9A97}\\n.chip{font-size:10.5px;border:1px solid rgba(255,255,255,.22);background:transparent;border-radius:20px;\\n padding:3px 10px;cursor:pointer;color:#BCD3CF}\\n.chip:hover{border-color:#8FBDB6;color:#fff}\\n.chip.on{background:#2E948C;border-color:#2E948C;color:#fff}\\n.chip.sec{opacity:.85;font-size:10px}\\n\\n/* \\u2500\\u2500 el grafo, ancho completo \\u2500\\u2500 */\\n.zona-grafo{flex:0 0 44%;min-height:170px;position:relative;padding:9px 12px 8px;display:flex;flex-direction:column}\\n.gcab{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}\\n.gctl{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-left:auto}\\n.gctl select{font:inherit;font-size:11px;padding:3px 6px;border:1px solid var(--linea);border-radius:6px;background:#FCFDFC;color:var(--tinta)}\\n.tg{font-size:10px;border:1px solid var(--linea);border-radius:20px;padding:2px 8px;cursor:pointer;color:var(--tinta-3);background:#FBFDFC}\\n.tg.on{background:var(--tinta);border-color:var(--tinta);color:#fff}\\n.btn{font-size:10.5px;background:#FBFDFC;border:1px solid var(--linea);border-radius:7px;padding:3px 9px;cursor:pointer;color:var(--tinta-2)}\\n.btn:hover{border-color:var(--verde2);color:var(--verde)}\\n#grafo{flex:1;width:100%;display:block;border-radius:9px;background:#FBFDFC;border:1px solid var(--linea);cursor:grab;min-height:0}\\n.leyenda{display:flex;flex-wrap:wrap;gap:3px 13px;font-size:10.5px;color:var(--tinta-2);margin-top:6px}\\n.leyenda i{font-style:normal;display:inline-flex;align-items:center;gap:5px}\\n.pt{width:9px;height:9px;border-radius:50%;display:inline-block}\\n.lectura{margin-top:7px;font-size:12px;color:var(--tinta-2);line-height:1.55;\\n border-top:1px solid var(--linea);padding-top:7px;display:flex;flex-wrap:wrap;gap:3px 18px}\\n.lectura span{display:inline-block}\\n.lectura b{color:var(--tinta)}\\n.lectura .fuerte{color:var(--vino);font-weight:600}\\n.lectura .censo{color:var(--tinta-3)}\\n/* la l\\u00e1mina de los papers callados: fija, NO depende de los filtros \\u2014 se afirma\\n   una vez y no se vuelve a mover. Por eso vive arriba y no en .lectura */\\n/* vive DENTRO de .superior, que es oscura: los colores son los de la cabecera,\\n   no los del papel \\u2014 con var(--tinta) el negrita sal\\u00eda invisible sobre negro */\\n.callados{margin-top:9px;padding:7px 11px;font-size:11.5px;line-height:1.55;color:#B9CBC8;\\n border-left:3px solid #C2708A;background:rgba(255,255,255,.05);border-radius:0 7px 7px 0;\\n position:relative;z-index:1}\\n.callados b{color:#fff;font-weight:600}\\n.callados .censo{color:#8FA6A3}\\n.habilita{margin-top:6px;padding:1px 0 1px 12px;border-left:3px solid var(--verde2);\\n font-size:12px;color:var(--tinta-2);line-height:1.5;flex-basis:100%}\\n.habilita b{color:var(--verde);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;\\n display:block;margin-bottom:2px}\\n\\n/* \\u2500\\u2500 tirador \\u2500\\u2500 */\\n.tirador{flex:0 0 7px;cursor:row-resize;border-radius:4px;background:transparent;position:relative}\\n.tirador::after{content:\\"\\";position:absolute;left:50%;top:2px;width:54px;height:3px;margin-left:-27px;\\n border-radius:3px;background:var(--linea)}\\n.tirador:hover::after{background:var(--verde2)}\\n\\n/* \\u2500\\u2500 abajo: la tabla y la ficha, en PESTA\\u00d1AS \\u2500\\u2500\\n   Antes iban lado a lado y la ficha se llevaba 380 px fijos, con lo que en un\\n   port\\u00e1til las columnas de t\\u00e9cnica, instrumento y dise\\u00f1o quedaban apretadas.\\n   La ficha es lo \\u00fanico de las tres zonas que no pierde nada por estar tapado:\\n   la tabla se ESCANEA \\u2014y por eso quiere al grafo al lado, reaccionando\\u2014 y la\\n   ficha se LEE, un paper cada vez. Mientras lees no est\\u00e1s mirando el grafo. */\\n.abajo{flex:1 1 auto;display:flex;flex-direction:column;gap:0;min-height:0}\\n.pestanas{flex:0 0 auto;display:flex;gap:4px;padding-left:3px}\\n.pes{font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--tinta-3);\\n border:1px solid var(--linea);border-bottom:none;border-radius:8px 8px 0 0;padding:4px 13px 5px;\\n cursor:pointer;background:#F4F8F6;position:relative;top:1px}\\n.pes:hover{color:var(--verde)}\\n.pes.on{background:var(--sup);color:var(--tinta)}\\n.pes .cta{font-weight:400;letter-spacing:0;text-transform:none;color:var(--tinta-3)}\\n/* el gemelo de \\u00abpantalla completa\\u00bb del grafo, para la mitad de abajo */\\n.pes-amp{margin-left:auto;align-self:flex-end;font-size:10.5px;background:#FBFDFC;\\n border:1px solid var(--linea);border-radius:7px;padding:3px 9px;margin-bottom:2px;\\n cursor:pointer;color:var(--tinta-2)}\\n.pes-amp:hover{border-color:var(--verde2);color:var(--verde)}\\n.tablero.solo-abajo .zona-grafo,.tablero.solo-abajo .tirador{display:none}\\n.abajo.ver-tabla .zona-ficha,.abajo.ver-tabla .zona-canon{display:none}\\n.abajo.ver-ficha .zona-tabla,.abajo.ver-ficha .zona-canon{display:none}\\n.abajo.ver-canon .zona-tabla,.abajo.ver-canon .zona-ficha{display:none}\\n.zona-tabla,.zona-ficha,.zona-canon{overflow-y:auto;padding:10px 13px;min-height:0;flex:1 1 auto;\\n border-top-left-radius:0}\\n/* el canon: una tabla corta, con la columna que de verdad importa a la derecha */\\n.canon-t{width:100%;border-collapse:collapse;font-size:12px;max-width:1000px}\\n.canon-t td{padding:5px 7px;border-bottom:1px dotted var(--linea);vertical-align:top}\\n.canon-t .n{text-align:right;font-variant-numeric:tabular-nums;color:var(--tinta-2);white-space:nowrap}\\n.canon-t .yy{color:var(--tinta-3);white-space:nowrap}\\n.canon-t tr.dentro{cursor:pointer}\\n.canon-t tr.dentro:hover td{background:#F7FAF9}\\n/* los chips de vista viven en panel CLARO: la clase .chip est\\u00e1 pensada para la\\n   cabecera oscura y aqu\\u00ed quedar\\u00eda con borde y letra invisibles */\\n.chip.cv{border-color:var(--linea);color:var(--tinta-2);background:#FBFDFC}\\n.chip.cv:hover{border-color:var(--verde2);color:var(--verde)}\\n.chip.cv.on{background:var(--verde);border-color:var(--verde);color:#fff}\\n.et-fuera{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:var(--vino)}\\n.et-dentro{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:var(--verde)}\\n/* la ficha ya no vive en una columna de 380 px: a todo el ancho, las frases\\n   textuales del autor sal\\u00edan en renglones de pantalla entera. Se le pone tope\\n   de lectura; las listas y las p\\u00edldoras se apa\\u00f1an igual */\\n.zona-ficha > *{max-width:880px}\\ntable{width:100%;border-collapse:collapse;font-size:12px}\\nthead th{position:sticky;top:-10px;background:var(--sup);z-index:2}\\nth{text-align:left;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--tinta-3);\\n border-bottom:1px solid var(--linea);padding:6px;cursor:pointer;white-space:nowrap;user-select:none}\\nth:hover{color:var(--verde)}\\ntd{padding:6px;border-bottom:1px dotted var(--linea);vertical-align:top}\\ntr.fila{cursor:pointer}\\ntr.fila:hover td{background:#F7FAF9}\\ntr.fila.sel td{background:#EAF3F1}\\n.tt{font-family:var(--serif);font-size:12.5px;line-height:1.28;display:block;max-width:38ch}\\n.mini{font-size:10px;color:var(--tinta-3);display:block;margin-top:2px}\\n.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}\\n.pill{display:inline-block;font-size:9.5px;border:1px solid var(--linea);border-radius:20px;\\n padding:1px 7px;margin:1px 2px 1px 0;color:var(--tinta-2);cursor:pointer;white-space:nowrap;background:#F7FAF9}\\n.pill:hover{border-color:var(--verde2);color:var(--verde)}\\n.pill.tecnica{background:#EAF3F1;border-color:#BFD9D5}\\n.pill.instrumento{background:#EDF2F7;border-color:#C6D5E2}\\n.pill.diseno{background:#F3F0F7;border-color:#D5CCE4}\\n.pill.region{background:#FDF6F7;border-color:#E7CDD4}\\n.pill.marco{background:#FFFDF6;border-color:#E6DCC2}\\n.marcas{white-space:nowrap;font-size:14px;line-height:1;letter-spacing:1px}\\n.marcas i{font-style:normal;color:#DDE4E2}\\n.marcas i.on{color:var(--verde)}\\n.marcas i.on.v{color:var(--ambar)}\\n.marcas i.on.l{color:var(--vino)}\\n.cargar{text-align:center;padding:10px;font-size:12px;color:var(--verde);cursor:pointer}\\n.cargar:hover{text-decoration:underline}\\n\\n/* \\u2500\\u2500 ficha \\u2500\\u2500 */\\n.cita{border-left:2px solid var(--linea);padding:3px 0 3px 11px;margin:7px 0;font-size:11.5px;color:var(--tinta-2);font-style:italic;line-height:1.5}\\n.cita.nulo{border-left-color:var(--vino)}\\n.cita.res{border-left-color:var(--verde2)}\\n.cita.lim{border-left-color:var(--vino);background:#FDFBFB}\\n.vacio-caja{border:1px dashed #C9B98E;background:#FFFDF6;border-radius:10px;padding:9px 11px;margin:8px 0;\\n font-size:11.5px;font-style:italic;color:var(--tinta-2);line-height:1.5}\\n.vacio-caja b{color:#6E5A18;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;display:block;margin-bottom:4px;font-style:normal}\\n.det h3{font-family:var(--serif);font-weight:400;font-size:15.5px;line-height:1.25;margin:4px 0 3px}\\n.det .meta{font-size:11px;color:var(--tinta-3);margin-bottom:8px}\\n.subrot{font-size:9.5px;letter-spacing:.15em;text-transform:uppercase;color:var(--tinta-2);font-weight:700;margin:11px 0 4px}\\n.pendiente{font-size:11px;color:var(--tinta-3);font-style:italic;border:1px dashed var(--linea);border-radius:8px;padding:7px 10px}\\n.lista-bl{list-style:none;margin:0;padding:0}\\n.lista-bl li{padding:5px 0;border-bottom:1px dotted var(--linea);font-size:11.5px;cursor:pointer}\\n.lista-bl li:hover{color:var(--verde)}\\n.nota{font-size:10.5px;color:var(--tinta-2);margin-top:7px;line-height:1.5}\\n.nota b{color:var(--tinta)}\\n\\n/* \\u2500\\u2500 pantalla completa \\u2500\\u2500 */\\n#velo{position:fixed;inset:0;background:rgba(16,34,43,.95);z-index:50;display:none;flex-direction:column;padding:14px 18px}\\n#velo.on{display:flex}\\n#velo .gcab{color:#EAF1EF}\\n#velo h2{font-family:var(--serif);font-weight:400;font-size:19px;margin:0}\\n#velo select,#velo .tg,#velo .btn{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.25);color:#EAF1EF}\\n#velo .tg.on{background:#EAF1EF;color:var(--tinta)}\\n#grafoBig{flex:1;width:100%;border-radius:11px;background:#0B1A21;cursor:grab;min-height:0}\\n#velo .leyenda{color:#9DB7B4}\\n</style></head><body>\\n\\n<div class=\\"tablero\\">\\n  <section class=\\"superior\\">\\n    <div class=\\"tit\\">\\n      <span class=\\"kicker\\">Bloque 2 \\u00b7 matriz de s\\u00edntesis</span>\\n      <h1 id=\\"h1\\"></h1>\\n      <span class=\\"info\\" id=\\"info\\" title=\\"\\">\\u00bfqu\\u00e9 es esto?</span>\\n      <span class=\\"cuenta\\"><b id=\\"cN\\">0</b> de <span id=\\"cT\\"></span> papers</span>\\n    </div>\\n    <div class=\\"filtros\\">\\n      <select id=\\"fMarco\\"></select><select id=\\"fTec\\"></select><select id=\\"fIns\\"></select>\\n      <select id=\\"fDis\\"></select><select id=\\"fReg\\"></select><select id=\\"fAnio\\"></select>\\n      <input id=\\"fTexto\\" placeholder=\\"buscar en t\\u00edtulo y keywords\\u2026\\">\\n      <span class=\\"chip sec\\" id=\\"fVacio\\" title=\\"papers que enuncian un vac\\u00edo en su resumen\\">con vac\\u00edo</span>\\n      <span class=\\"chip sec\\" id=\\"fNulo\\" title=\\"papers con alguna relaci\\u00f3n que NO result\\u00f3\\">con resultado nulo</span>\\n      <span class=\\"chip sec\\" id=\\"fCallado\\" title=\\"papers que no declaran ni terreno, ni instrumento, ni t\\u00e9cnica, ni dise\\u00f1o\\">sin declarar nada</span>\\n      <span class=\\"chip\\" id=\\"fReset\\">limpiar</span>\\n    </div>\\n    <div class=\\"callados\\" id=\\"callados\\"></div>\\n  </section>\\n\\n  <section class=\\"caja zona-grafo\\">\\n    <div class=\\"gcab\\">\\n      <span class=\\"rotulo\\">El grafo <span class=\\"ac\\">\\u00b7 la forma del campo</span></span>\\n      <div class=\\"gctl\\">\\n        <select id=\\"gColor\\">\\n          <option value=\\"tipo\\">color: por tipo</option>\\n          <option value=\\"region\\">color: por regi\\u00f3n</option>\\n          <option value=\\"decada\\">color: por quinquenio</option>\\n          <option value=\\"vacio\\">color: declara vac\\u00edo</option>\\n        </select>\\n        <span class=\\"tg\\" data-t=\\"marco\\">marco</span>\\n        <span class=\\"tg\\" data-t=\\"tecnica\\">t\\u00e9cnica</span>\\n        <span class=\\"tg\\" data-t=\\"instrumento\\">instrum.</span>\\n        <span class=\\"tg\\" data-t=\\"diseno\\">dise\\u00f1o</span>\\n        <span class=\\"tg\\" data-t=\\"region\\">regi\\u00f3n</span>\\n        <span class=\\"tg\\" data-t=\\"revista\\">revista</span>\\n        <button class=\\"btn\\" id=\\"btnFoco\\" style=\\"display:none\\">ver todo \\u2715</button>\\n        <button class=\\"btn\\" id=\\"btnAmp\\">pantalla completa \\u2922</button>\\n      </div>\\n    </div>\\n    <canvas id=\\"grafo\\"></canvas>\\n    <div class=\\"leyenda\\" id=\\"leyenda\\"></div>\\n    <div class=\\"lectura\\" id=\\"lectura\\"></div>\\n  </section>\\n\\n  <div class=\\"tirador\\" id=\\"tirador\\" title=\\"arrastra para repartir la altura\\"></div>\\n\\n  <div class=\\"abajo ver-tabla\\" id=\\"abajo\\">\\n    <div class=\\"pestanas\\">\\n      <span class=\\"pes on\\" data-p=\\"tabla\\">la tabla <span class=\\"cta\\" id=\\"pesN\\"></span></span>\\n      <span class=\\"pes\\" data-p=\\"ficha\\">la ficha</span>\\n      <span class=\\"pes\\" data-p=\\"canon\\" id=\\"pesCanon\\">el canon <span class=\\"cta\\" id=\\"pesCN\\"></span></span>\\n      <button class=\\"pes-amp\\" id=\\"btnAmpAbajo\\" title=\\"ocupa toda la pantalla con la tabla y la ficha\\">ampliar \\u2922</button>\\n    </div>\\n    <section class=\\"caja zona-tabla\\">\\n      <table><thead><tr>\\n        <th data-k=\\"t\\">Paper</th><th data-k=\\"y\\" class=\\"num\\">A\\u00f1o</th>\\n        <th data-k=\\"cit\\" class=\\"num\\">Citas</th><th data-k=\\"cpa\\" class=\\"num\\">C/a\\u00f1o</th>\\n        <th data-k=\\"marco\\">Marco</th>\\n        <th data-k=\\"tecnica\\">T\\u00e9cnica</th><th data-k=\\"instrumento\\">Instrumento</th>\\n        <th data-k=\\"diseno\\">Dise\\u00f1o</th><th data-k=\\"region\\">Regi\\u00f3n</th>\\n        <th data-k=\\"marcas\\" title=\\"vac\\u00edo \\u00b7 resultados \\u00b7 l\\u00edmites\\">V\\u00b7R\\u00b7L</th>\\n      </tr></thead><tbody id=\\"tb\\"></tbody></table>\\n      <div id=\\"mas\\"></div>\\n    </section>\\n    <section class=\\"caja zona-ficha det\\" id=\\"det\\"></section>\\n    <section class=\\"caja zona-canon det\\" id=\\"canon\\"></section>\\n  </div>\\n</div>\\n\\n<div id=\\"velo\\">\\n  <div class=\\"gcab\\">\\n    <h2>El grafo \\u2014 <span id=\\"veloN\\"></span></h2>\\n    <div class=\\"gctl\\">\\n      <select id=\\"gColor2\\">\\n        <option value=\\"tipo\\">color: por tipo</option>\\n        <option value=\\"region\\">color: por regi\\u00f3n</option>\\n        <option value=\\"decada\\">color: por quinquenio</option>\\n        <option value=\\"vacio\\">color: declara vac\\u00edo</option>\\n      </select>\\n      <button class=\\"btn\\" id=\\"btnFoco2\\" style=\\"display:none\\">ver todo \\u2715</button>\\n      <button class=\\"btn\\" id=\\"cerrar\\">cerrar \\u2715</button>\\n    </div>\\n  </div>\\n  <canvas id=\\"grafoBig\\"></canvas>\\n  <div class=\\"leyenda\\" id=\\"leyenda2\\"></div>\\n</div>\\n\\n<script>\\nconst D = /*__DATOS__*/;\\nconst $ = s => document.querySelector(s);\\nconst esc = s => String(s == null ? \\"\\" : s).replace(/[&<>\\"]/g, c => ({\\"&\\":\\"&amp;\\",\\"<\\":\\"&lt;\\",\\">\\":\\"&gt;\\",\'\\"\':\\"&quot;\\"}[c]));\\nconst mil = n => String(n).replace(/\\\\B(?=(\\\\d{3})+(?!\\\\d))/g, \\".\\");\\nconst dec = n => String(n).replace(\\".\\", \\",\\");\\nconst ETQ = {tecnica:\\"t\\u00e9cnica de an\\u00e1lisis\\",\\n             instrumento:\\"instrumento de recolecci\\u00f3n\\",\\n             diseno:\\"dise\\u00f1o del estudio\\", region:\\"regi\\u00f3n del estudio\\",\\n             marco:\\"marco te\\u00f3rico\\", revista:\\"revista\\"};\\n\\n$(\\"#h1\\").textContent = D.meta.titulo;\\n$(\\"#cT\\").textContent = D.meta.n_maqueta;\\n$(\\"#info\\").title = \\"Matriz de s\\u00edntesis \\u00b7 \\" + mil(D.meta.n_maqueta) + \\" papers. Todas las frases \\" +\\n  \\"son textuales de su autor: nada est\\u00e1 parafraseado. Las persianas son las columnas que el \\" +\\n  \\"retrato NO tiene: marco te\\u00f3rico, y el m\\u00e9todo partido en t\\u00e9cnica / instrumento / dise\\u00f1o. \\" +\\n  \\"Los constructos se leen en la ficha de cada paper, no filtran: son la \\u00fanica capa que nombra \\" +\\n  \\"el modelo, y no comparten fila con lo que sale de fichas de patrones.\\" +\\n  ((D.citas && D.citas.hay) ? \\"\\" :\\n   \\" Este export se baj\\u00f3 SIN referencias: la pesta\\u00f1a del canon explica qu\\u00e9 falta y c\\u00f3mo pedirlo.\\");\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 estado */\\nlet sel = null, orden = {k:\\"cit\\", asc:false}, colorPor = \\"tipo\\", tope = 250;\\n// vacio/nulo vuelven como filtros SECUNDARIOS. Se hab\\u00edan quitado por \\u00abrepetir el\\n// retrato\\u00bb, y era un error: el retrato dice CU\\u00c1NTOS hay, pero no contesta \\u00abde esos\\n// 74, \\u00bfcu\\u00e1les son de Am\\u00e9rica Latina y usan SEM?\\u00bb. Ese cruce es el bloque 2.\\nconst F = {marco:\\"\\", tecnica:\\"\\", instrumento:\\"\\", diseno:\\"\\", region:\\"\\", anio:\\"\\", texto:\\"\\",\\n           vacio:false, nulo:false, callado:false};\\n// TODAS APAGADAS al abrir. El mapa se construye por capas, delante de quien\\n// mira, en vez de caer de golpe: 1.196 papers y 51 conceptos a la vez no son un\\n// mapa, son una mancha que rebota. El orden de los botones es el mismo de las\\n// persianas de arriba \\u2014 marco, t\\u00e9cnica, instrumento, dise\\u00f1o, regi\\u00f3n \\u2014 para que\\n// no haya dos ordenaciones que aprender.\\nconst ver = {marco:0, tecnica:0, instrumento:0, diseno:0, region:0, revista:0};\\n\\nconst uni = k => [...new Set(D.papers.flatMap(p => Array.isArray(p[k]) ? p[k] : [p[k]]))].filter(Boolean).sort();\\nconst opt = (el, vals, etq) => el.innerHTML = \'<option value=\\"\\">\' + etq + \\"</option>\\" +\\n  vals.map(v => \'<option value=\\"\' + esc(v) + \'\\">\' + esc(v) + \\"</option>\\").join(\\"\\");\\nopt($(\\"#fMarco\\"), uni(\\"marco\\"), \\"Todo marco te\\u00f3rico\\");\\nopt($(\\"#fTec\\"), uni(\\"tecnica\\"), \\"Toda t\\u00e9cnica\\");\\nopt($(\\"#fIns\\"), uni(\\"instrumento\\"), \\"Todo instrumento\\");\\nopt($(\\"#fDis\\"), uni(\\"diseno\\"), \\"Todo dise\\u00f1o\\");\\nopt($(\\"#fReg\\"), uni(\\"region\\"), \\"Toda regi\\u00f3n\\");\\nopt($(\\"#fAnio\\"), uni(\\"y\\"), \\"Todo a\\u00f1o\\");\\n\\nconst tiene = (p,k,v) => !v || (Array.isArray(p[k]) ? p[k].includes(v) : p[k] === v);\\nlet cache = null;\\nfunction visibles() {\\n  if (cache) return cache;\\n  cache = D.papers.filter(p =>\\n    tiene(p,\\"marco\\",F.marco) && tiene(p,\\"tecnica\\",F.tecnica) && tiene(p,\\"instrumento\\",F.instrumento) &&\\n    tiene(p,\\"diseno\\",F.diseno) && tiene(p,\\"region\\",F.region) && tiene(p,\\"y\\",F.anio) &&\\n    (!F.vacio || p.frase_vacio) && (!F.nulo || p.nulos.length) && (!F.callado || p.callado) &&\\n    (!F.texto || (p.t + \\" \\" + p.kw.join(\\" \\")).toLowerCase().includes(F.texto))\\n  ).sort((a,b) => {\\n    const k = orden.k, s = orden.asc ? 1 : -1;\\n    if (k === \\"marcas\\") { const g = x => (x.frase_vacio?1:0)+(x.resultados.length?1:0)+(x.limites.length?1:0);\\n                          return (g(a)-g(b))*s; }\\n    let x = a[k], y = b[k];\\n    if (Array.isArray(x)) { x = x.join(); y = y.join(); }\\n    return (x > y ? 1 : x < y ? -1 : 0) * s;\\n  });\\n  return cache;\\n}\\nconst invalidar = () => cache = null;\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 tabla */\\nconst pills = (p,k) => p[k].map(v => `<span class=\\"pill ${k}\\" data-c=\\"${esc(v)}\\">${esc(v)}</span>`).join(\\"\\");\\nfunction fila(p) {\\n  return `<tr class=\\"fila${sel===p.id?\\" sel\\":\\"\\"}\\" data-id=\\"${p.id}\\">\\n    <td><span class=\\"tt\\">${esc(p.t)}</span><span class=\\"mini\\">${esc(p.au.split(\\",\\")[0])} et al. \\u00b7 ${esc(p.rev)}</span></td>\\n    <td class=\\"num\\">${p.y}</td><td class=\\"num\\">${mil(p.cit)}</td><td class=\\"num\\">${dec(p.cpa)}</td>\\n    <td>${pills(p,\\"marco\\")}</td><td>${pills(p,\\"tecnica\\")}</td><td>${pills(p,\\"instrumento\\")}</td>\\n    <td>${pills(p,\\"diseno\\")}</td><td>${pills(p,\\"region\\")}</td>\\n    <td class=\\"marcas\\"><i class=\\"v${p.frase_vacio?\\" on\\":\\"\\"}\\">\\u25cf</i><i class=\\"${p.resultados.length?\\"on\\":\\"\\"}\\">\\u25cf</i><i class=\\"l${p.limites.length?\\" on\\":\\"\\"}\\">\\u25cf</i></td></tr>`;\\n}\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 las dos pesta\\u00f1as de abajo\\n   Abrir un paper o un concepto salta a la ficha: es lo que acabas de pedir al\\n   pulsar. Volver a la tabla es un clic, y el r\\u00f3tulo de la pesta\\u00f1a lleva cu\\u00e1ntas\\n   filas te esperan ah\\u00ed para que no haya que adivinarlo. */\\nfunction pestana(cual) {\\n  const a = $(\\"#abajo\\");\\n  [\\"tabla\\", \\"ficha\\", \\"canon\\"].forEach(k => a.classList.toggle(\\"ver-\\" + k, cual === k));\\n  document.querySelectorAll(\\".pes\\").forEach(p => p.classList.toggle(\\"on\\", p.dataset.p === cual));\\n}\\ndocument.querySelectorAll(\\".pes\\").forEach(p => p.onclick = () => pestana(p.dataset.p));\\n\\n/* Ampliar la mitad de abajo: el gemelo de \\u00abpantalla completa\\u00bb del grafo. Aqu\\u00ed\\n   no hace falta velo ni segundo lienzo \\u2014 basta plegar la zona de arriba. Al\\n   volver se recalienta la simulaci\\u00f3n, porque mientras estuvo plegada el grafo\\n   no supo de los cambios de tama\\u00f1o. */\\nconst ampAbajo = () => {\\n  const t = $(\\".tablero\\"), on = t.classList.toggle(\\"solo-abajo\\");\\n  $(\\"#btnAmpAbajo\\").textContent = on ? \\"reducir \\u2921\\" : \\"ampliar \\u2922\\";\\n  if (!on) setTimeout(() => { ajusta(); alpha = 1; }, 30);\\n};\\n$(\\"#btnAmpAbajo\\").onclick = ampAbajo;\\n\\nfunction pintaTabla(reconstruir) {\\n  const v = visibles();\\n  $(\\"#cN\\").textContent = mil(v.length);\\n  $(\\"#pesN\\").textContent = \\"\\u00b7 \\" + mil(v.length);\\n  $(\\"#tb\\").innerHTML = v.slice(0, tope).map(fila).join(\\"\\");\\n  // Con 638 filas pintarlas todas de golpe hace el scroll pegajoso: se dibujan\\n  // 250 y el resto bajo demanda. Es el problema que solo aparece a escala.\\n  $(\\"#mas\\").innerHTML = v.length > tope\\n    ? `<div class=\\"cargar\\" id=\\"btnMas\\">mostrar ${mil(Math.min(250, v.length-tope))} m\\u00e1s \\u2014 quedan ${mil(v.length-tope)}</div>` : \\"\\";\\n  if (reconstruir) construye();      // primero, para saber cu\\u00e1ntos vecinos hay\\n  lectura();\\n}\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 ficha */\\nconst bloque = (t, items, cls) => items.length\\n  ? `<div class=\\"subrot\\">${t}</div>` + items.map(o => `<div class=\\"cita ${cls}\\">${esc(o)}</div>`).join(\\"\\") : \\"\\";\\nfunction panelPaper(p) {\\n  $(\\"#det\\").innerHTML = `<span class=\\"rotulo\\">La ficha <span class=\\"ac\\">\\u00b7 en palabras de su autor</span></span>\\n    <h3>${esc(p.t)}</h3>\\n    <div class=\\"meta\\">${esc(p.au)}<br>${p.y} \\u00b7 ${esc(p.rev)} \\u00b7 ${mil(p.cit)} citas (${dec(p.cpa)}/a\\u00f1o)\\n      ${p.doi ? \' \\u00b7 <a href=\\"https://doi.org/\'+esc(p.doi)+\'\\" target=\\"_blank\\" rel=\\"noopener\\">doi</a>\' : \\"\\"}</div>\\n    ${pills(p,\\"marco\\")}${pills(p,\\"tecnica\\")}${pills(p,\\"instrumento\\")}${pills(p,\\"diseno\\")}${pills(p,\\"region\\")}\\n    ${p.frase_vacio ? `<div class=\\"vacio-caja\\"><b>El vac\\u00edo que declara</b>\\u00ab${esc(p.frase_vacio)}\\u00bb</div>` : \\"\\"}\\n    ${bloque(\\"Resultados a los que llega\\", p.resultados, \\"res\\")}\\n    ${bloque(\\"Lo que mide\\", p.relaciones, \\"\\")}\\n    ${bloque(\\"Y lo que no le result\\u00f3\\", p.nulos, \\"nulo\\")}\\n    ${bloque(\\"L\\u00edmites que reconoce\\", p.limites, \\"lim\\")}\\n    ${constructos(p)}\\n    ${vecindad(p)}\\n    <div class=\\"subrot\\">Palabras clave</div>\\n    <div>${p.kw.map(k=>`<span class=\\"pill\\">${esc(k)}</span>`).join(\\"\\")}</div>`;\\n  $(\\"#det\\").scrollTop = 0;\\n  pestana(\\"ficha\\");\\n}\\n\\n/* La maqueta ten\\u00eda en la ficha un bloque \\u00abMetodolog\\u00eda, literal\\u00bb: las palabras\\n   exactas que hicieron caer a un paper en su familia de m\\u00e9todo. Se quit\\u00f3 al\\n   pasar a skill porque exige los PATRONES de metodos.json, que vive en el\\n   bloque 1 y no viaja. Duplicarlo aqu\\u00ed dejar\\u00eda dos copias de una ficha que\\n   crece, y acabar\\u00edan divergiendo sin que nadie lo note. Si alguna vez se\\n   quiere, lo correcto es que el bloque 1 guarde el literal que YA calcula y\\n   tira, no que el bloque 2 lo recalcule con una copia de sus patrones. */\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 los constructos de un paper\\n   La \\u00fanica columna que exigi\\u00f3 que el modelo leyera. Y por eso es la que m\\u00e1s se\\n   explica a s\\u00ed misma en pantalla: qui\\u00e9n la nombr\\u00f3, sobre qu\\u00e9 muestra, y el\\n   recordatorio de que NO lleva rol.\\n\\n   Si el proyecto no trae ficha de constructos, la secci\\u00f3n no se dibuja y la\\n   cabecera lo declara: mejor una ausencia dicha que una columna vac\\u00eda que\\n   parece un fallo. */\\nfunction constructos(p) {\\n  const C = D.constructos || {};\\n  if (!C.hay) return \\"\\";\\n  if (!p.constructos || !p.constructos.length)\\n    return \'<div class=\\"subrot\\">Constructos</div>\' +\\n           \'<div class=\\"pendiente\\">Sus oraciones relacionales no nombran ninguno de los \' +\\n           mil(C.n) + \' constructos de este corpus.</div>\';\\n  const porGrupo = {};\\n  p.constructos.forEach(c => {\\n    const g = (C.de || {})[c] || \\"\\";\\n    (porGrupo[g] = porGrupo[g] || []).push(c);\\n  });\\n  return \'<div class=\\"subrot\\">Constructos <span style=\\"font-weight:400;text-transform:none;\' +\\n    \'letter-spacing:0\\">\\u00b7 los que nombran sus propias oraciones</span></div>\' +\\n    Object.keys(porGrupo).map(g =>\\n      (g ? \'<div class=\\"meta\\" style=\\"margin:4px 0 2px\\">\' + esc(g) + \\"</div>\\" : \\"\\") +\\n      \\"<div>\\" + porGrupo[g].map(c => \'<span class=\\"pill\\">\' + esc(c) + \\"</span>\\").join(\\"\\") +\\n      \\"</div>\\").join(\\"\\");\\n}\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 hacia atr\\u00e1s y hacia adelante, DENTRO del corpus\\n   Una cita es un HECHO, no un parecido: est\\u00e1 escrita en la bibliograf\\u00eda del\\n   autor. Por eso esto no repite el episodio de los 744 enlaces, que eran\\n   \\u00abeste paper se parece al tuyo\\u00bb \\u2014 una inferencia puesta encima.\\n\\n   Emparejado por t\\u00edtulo normalizado; la auditor\\u00eda (nadie puede tener m\\u00e1s\\n   citadores dentro del corpus que citas totales en Scopus) pasa con 0\\n   violaciones sobre 1.196.\\n\\n   Y el techo, que va escrito en pantalla: hacia atr\\u00e1s se ve TODO lo que el\\n   paper cita del corpus, pero hacia adelante SOLO se ven los citadores que\\n   est\\u00e1n dentro. Scopus da cu\\u00e1ntas citas tiene, no de qui\\u00e9n. */\\nfunction listaPapers(ids) {\\n  return `<ul class=\\"lista-bl\\">${ids.map(i => {\\n    const q = D.papers.find(x => x.id === i); if (!q) return \\"\\";\\n    return `<li data-id=\\"${q.id}\\">${esc(q.t.slice(0,64))}\\n      <span class=\\"mini\\">${q.y} \\u00b7 ${mil(q.cit)} citas</span></li>`;\\n  }).join(\\"\\")}</ul>`;\\n}\\nfunction vecindad(p) {\\n  const atras = p.cita || [], alante = p.citado || [];\\n  // sin referencias en el export, esto no se calla: se declara una vez por ficha\\n  if (!(D.citas && D.citas.hay))\\n    return \'<div class=\\"subrot\\">A qui\\u00e9n cita y qui\\u00e9n lo cita</div>\' +\\n      \'<div class=\\"pendiente\\">Este export se baj\\u00f3 sin referencias, as\\u00ed que no se puede saber. \' +\\n      \'Se pide al exportar de Scopus \\u2014 ver la pesta\\u00f1a del canon.</div>\';\\n  if (!atras.length && !alante.length) return \\"\\";\\n  let h = \\"\\";\\n  if (atras.length)\\n    h += `<div class=\\"subrot\\">Se apoya en ${mil(atras.length)} de tu corpus\\n      <span style=\\"font-weight:400;text-transform:none;letter-spacing:0\\">\\u00b7 los cita en su bibliograf\\u00eda</span></div>` +\\n      listaPapers(atras.slice(0,25));\\n  if (alante.length)\\n    h += `<div class=\\"subrot\\">Lo citan ${mil(alante.length)} de tu corpus</div>` +\\n      listaPapers(alante.slice(0,25)) +\\n      `<p class=\\"nota\\">De fuera del corpus no se sabe qui\\u00e9n: Scopus da el n\\u00famero de citas\\n       (${mil(p.cit)}), no de qui\\u00e9n vienen. Esta lista es solo la conversaci\\u00f3n interna.</p>`;\\n  return h;\\n}\\nfunction panelConcepto(nombre) {\\n  const c = D.conceptos.find(c => c.nombre === nombre); if (!c) return;\\n  // Antes decia \\u00ablo enlazan 293 papers\\u00bb con 7 filtrados: la cifra era del corpus\\n  // entero y contradecia lo que el usuario tenia delante. Ahora manda el filtro.\\n  const enVista = new Set(visibles().map(p=>p.id));\\n  const todos = c.papers.map(id => D.papers.find(p=>p.id===id)).filter(Boolean);\\n  const ps = todos.filter(p=>enVista.has(p.id)).sort((a,b)=>b.cit-a.cit);\\n  $(\\"#det\\").innerHTML = `<span class=\\"rotulo\\">P\\u00e1gina de concepto <span class=\\"ac\\">\\u00b7 ${ETQ[c.tipo]}</span></span>\\n    <h3>${esc(nombre)}</h3>\\n    <div class=\\"meta\\">Nadie escribi\\u00f3 esta lista. La escriben los papers al enlazar aqu\\u00ed.</div>\\n    <div class=\\"subrot\\">Lo enlazan ${mil(ps.length)} papers${ps.length !== todos.length\\n      ? \\" de los que tienes filtrados <span style=\\\\\\"font-weight:400;text-transform:none;letter-spacing:0\\\\\\">(\\" + mil(todos.length) + \\" en el corpus entero)</span>\\" : \\"\\"}</div>\\n    <ul class=\\"lista-bl\\">${ps.slice(0,60).map(p=>`<li data-id=\\"${p.id}\\">${esc(p.t.slice(0,60))}\\n      <span class=\\"mini\\">${p.y} \\u00b7 ${mil(p.cit)} citas</span></li>`).join(\\"\\")}</ul>\\n    ${ps.length>60 ? \'<p class=\\"nota\\">\\u2026y \'+mil(ps.length-60)+\' m\\u00e1s.</p>\' : \\"\\"}\\n    <p class=\\"nota\\">Esto es lo que en Obsidian ser\\u00edan los <b>backlinks</b>. Aqu\\u00ed ocurre igual, sin instalar nada.</p>`;\\n  $(\\"#det\\").scrollTop = 0;\\n  pestana(\\"ficha\\");\\n}\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 el panel de lectura\\n   REGLA, la misma que sostiene el bloque 1: cada frase se ELIGE POR UMBRAL y\\n   solo dice lo que las cifras aguantan. Nada de prosa fija.\\n\\n   Y el \\u00abesto te habilita a\\u00bb es el patron del candado 4 del retrato, aplicado\\n   aqui: el HECHO dice lo que se conto; la habilitacion dice que te permite\\n   hacer. La segunda nunca afirma nada sobre el mundo \\u2014\\u00abnadie ha modelado\\n   esto\\u00bb seria falso si miden y no lo dicen en el resumen\\u2014 sino sobre TU\\n   POSICION, que es cierta pase lo que pase. Se ense\\u00f1a una sola: la del hecho\\n   mas fuerte que haya disparado. */\\nconst TODAS_REG = uni(\\"region\\");\\nconst HAB_EJE = {\\n  tecnica:     \\"si tu aporte es <b>medir</b> lo que aqu\\u00ed se argumenta, no compites con nadie.\\",\\n  instrumento: \\"si tu aporte son <b>datos propios</b>, no compites con nadie.\\",\\n  diseno:      \\"ninguno declara c\\u00f3mo mont\\u00f3 su estudio: declarar el tuyo es una ventaja barata.\\",\\n  marco:       \\"ninguno se cuelga de una teor\\u00eda con nombre: <b>elegir marco ya es aporte</b> aqu\\u00ed.\\"\\n};\\nfunction lectura() {\\n  const v = visibles(), n = v.length, out = [], hab = [];\\n  const decl = k => v.filter(p => p[k].length).length;\\n  const cuenta = k => { const c = {}; v.forEach(p => p[k].forEach(x => c[x] = (c[x]||0)+1)); return c; };\\n  const mayor = k => Object.entries(cuenta(k)).sort((a,b)=>b[1]-a[1])[0];\\n  const libre = k => !F[k];\\n  const filtrando = Object.values(F).some(Boolean);\\n\\n  out.push(\'<span class=\\"censo\\"><b>\' + mil(n) + \'</b> de \' + mil(D.papers.length) + \' papers</span>\');\\n\\n  if (n === 0) { $(\\"#lectura\\").innerHTML = out.join(\\"\\") +\\n    \'<span>Ning\\u00fan paper cumple los filtros a la vez.</span>\' +\\n    \'<div class=\\"habilita\\"><b>Esto te habilita a</b>afirmar que ese cruce <b>no existe</b> en tu corpus. \' +\\n    \'Es el hueco m\\u00e1s limpio que vas a encontrar \\u2014 y tambi\\u00e9n el m\\u00e1s dif\\u00edcil de defender: comprueba que \' +\\n    \'no sea un artefacto de la b\\u00fasqueda antes de construir sobre \\u00e9l.</div>\';\\n    return; }\\n\\n  // \\u2500\\u2500 1 \\u00b7 un EJE ENTERO vac\\u00edo. Lo m\\u00e1s fuerte que se puede decir.\\n  if (n >= 3) {\\n    [[\\"tecnica\\",\\"c\\u00f3mo lo analiza\\"],[\\"instrumento\\",\\"con qu\\u00e9 recogi\\u00f3 el dato\\"],\\n     [\\"diseno\\",\\"c\\u00f3mo mont\\u00f3 el estudio\\"],[\\"marco\\",\\"en qu\\u00e9 teor\\u00eda se apoya\\"]].forEach(([k, etq]) => {\\n      // REGLA DEL ECO: con \\u00absin declarar nada\\u00bb activo, los tres ejes duros est\\u00e1n\\n      // vac\\u00edos POR DEFINICI\\u00d3N del filtro. Decir \\u00abninguno dice c\\u00f3mo lo analiza\\u00bb\\n      // no ser\\u00eda una lectura, ser\\u00eda repetir el filtro con voz de hallazgo. El\\n      // marco s\\u00ed puede hablar: no entra en la definici\\u00f3n de callado.\\n      if (F.callado && k !== \\"marco\\") return;\\n      if (libre(k) && decl(k) === 0) {\\n        out.push(\'<span class=\\"fuerte\\">Ninguno de los \' + mil(n) + \' dice \' + etq + \' en su resumen.</span>\');\\n        hab.push([1, HAB_EJE[k]]);\\n      }\\n    });\\n  }\\n\\n  // \\u2500\\u2500 2 \\u00b7 el terreno que no aparece\\n  if (n >= 3 && libre(\\"region\\") && decl(\\"region\\") > 0) {\\n    const hay = new Set(Object.keys(cuenta(\\"region\\")));\\n    const faltan = TODAS_REG.filter(r => !hay.has(r));\\n    if (faltan.length) {\\n      out.push(\'<span>Aparecen <b>\' + hay.size + \' de \' + TODAS_REG.length +\\n               \'</b> regiones. No hay ninguno en <b>\' + faltan.join(\\", \\") + \'</b>.</span>\');\\n      // Nombrar faltan[0] era arbitrario \\u2014es el primero de la lista\\u2014 y encima\\n      // absurdo para el p\\u00fablico: recomendarle Ocean\\u00eda a un investigador\\n      // ecuatoriano. La herramienta NO PUEDE saber d\\u00f3nde trabaja: solo cuando\\n      // falta una sola regi\\u00f3n tiene sentido nombrarla.\\n      hab.push([2, faltan.length === 1\\n        ? \\"comprobar si <b>\\" + faltan[0] + \\"</b> es tu terreno: ser\\u00eda el \\u00fanico sin un solo estudio aqu\\u00ed.\\"\\n        : \\"mirar si alguna de esas <b>\\" + faltan.length + \\" regiones</b> es la tuya. Ah\\u00ed no tendr\\u00e1s \\" +\\n          \\"con qui\\u00e9n contrastar, pero tampoco con qui\\u00e9n competir.\\"]);\\n    }\\n  }\\n\\n  // \\u2500\\u2500 3 \\u00b7 el recorte min\\u00fasculo. Callarse aqu\\u00ed se lee como \\u00abno hay nada\\u00bb cuando\\n  //        lo cierto es \\u00abhay tan poco que no se puede afirmar\\u00bb \\u2014 que para quien\\n  //        busca hueco es la mejor noticia. Solo si de verdad est\\u00e1s filtrando.\\n  if (filtrando && n > 0 && n < 5) {\\n    out.push(\'<span class=\\"fuerte\\">Con \' + n + \' papers no se puede afirmar nada de este cruce.</span>\');\\n    hab.push([3, \\"tratarlo como <b>hueco, no como conclusi\\u00f3n</b>. Que casi no haya es el dato; por qu\\u00e9 \\" +\\n                 \\"no lo hay, lo tienes que averiguar t\\u00fa leyendo esos \\" + n + \\".\\"]);\\n  }\\n\\n  // \\u2500\\u2500 4 \\u00b7 concentraci\\u00f3n, sobre los que declaran\\n  [[\\"region\\",\\"dicen d\\u00f3nde\\",\\"salir de ah\\u00ed es la v\\u00eda barata de diferenciarte; quedarte te obliga a decir qu\\u00e9 a\\u00f1ades.\\"],\\n   [\\"instrumento\\",\\"dicen con qu\\u00e9 recogieron\\",\\"cambiar de instrumento es una contribuci\\u00f3n metodol\\u00f3gica defendible.\\"],\\n   [\\"tecnica\\",\\"dicen con qu\\u00e9 analizaron\\",\\"si usas lo mismo, tu aporte tendr\\u00e1 que estar en otro sitio.\\"],\\n   [\\"marco\\",\\"declaran marco\\",\\"apoyarte en otra teor\\u00eda te separa del pelot\\u00f3n sin discutirle a nadie.\\"]\\n  ].forEach(([k, etq, h]) => {\\n    if (!libre(k)) return;\\n    const d = decl(k); if (d < 4) return;\\n    const m = mayor(k); if (!m) return;\\n    if (m[1] / d >= .6) {\\n      out.push(\'<span><b>\' + mil(m[1]) + \' de los \' + mil(d) + \'</b> que \' + etq +\\n               \' son de <b>\' + m[0] + \'</b>.</span>\');\\n      hab.push([4, h]);\\n    }\\n  });\\n\\n  // \\u2500\\u2500 5 \\u00b7 base delgada: el mismo corte del 40% de la l\\u00e1mina 4 del retrato\\n  if (n >= 10) {\\n    [[\\"tecnica\\",\\"con qu\\u00e9 se analiza\\"],[\\"region\\",\\"d\\u00f3nde se hizo\\"]].forEach(([k, etq]) => {\\n      const pct = 100 * decl(k) / n;\\n      if (libre(k) && pct < 40 && decl(k) > 0) {\\n        out.push(\'<span>Solo el <b>\' + Math.round(pct) + \'%</b> dice \' + etq + \'.</span>\');\\n        hab.push([5, \\"leer lo de arriba como lo que es: <b>describe a esa parte</b>, no al recorte entero. \\" +\\n                     \\"Para afirmar algo del resto hace falta el texto completo, no el resumen.\\"]);\\n      }\\n    });\\n  }\\n\\n  // \\u2500\\u2500 6 \\u00b7 material citable\\n  const cv = F.vacio ? 0 : v.filter(p => p.frase_vacio).length;\\n  const cn = F.nulo  ? 0 : v.filter(p => p.nulos.length).length;\\n  if (cv || cn) {\\n    const tr = [];\\n    if (cv) tr.push(\'<b>\' + mil(cv) + \'</b> con vac\\u00edo declarado\');\\n    if (cn) tr.push(\'<b>\' + mil(cn) + \'</b> con resultado nulo\');\\n    out.push(\'<span>\' + tr.join(\\" \\u00b7 \\") + \'.</span>\');\\n    hab.push([6, \\"escribir tu justificaci\\u00f3n <b>citando a otros y no a ti mismo</b>: cada uno trae la \\" +\\n                 \\"frase textual de su autor, con su DOI.\\"]);\\n  }\\n  if (out.length === 1)\\n    out.push(\'<span class=\\"censo\\">Esta selecci\\u00f3n no concentra nada en particular: se reparte por regi\\u00f3n, m\\u00e9todo y a\\u00f1o.</span>\');\\n  if (hab.length) {\\n    hab.sort((a,b) => a[0]-b[0]);\\n    out.push(\'<div class=\\"habilita\\"><b>Esto te habilita a</b>\' + hab[0][1] + \'</div>\');\\n  }\\n  $(\\"#lectura\\").innerHTML = out.join(\\"\\");\\n}\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 la l\\u00e1mina de los papers callados\\n   Se pinta UNA VEZ y no se vuelve a tocar: no depende de los filtros. Es la\\n   diferencia entre afirmar un hecho y sugerirlo \\u2014 el episodio de los 744\\n   enlaces paper\\u2194paper termin\\u00f3 exactamente por no respetar esa frontera.\\n\\n   Lo que esta l\\u00e1mina NO dice, y es deliberado: que estos papers \\u00abforman una\\n   segunda literatura de sistema alimentario macro\\u00bb. Eso es la inferencia, y la\\n   pone el humano encima. El archivo se queda en el hecho. */\\n(function(){\\n  const C = D.callados;\\n  if (!C || !C.n) return;\\n  const kw = C.kw.map(x => \\"<b>\\" + esc(x[0]) + \\"</b> (\\" + x[1] + \\")\\").join(\\" \\u00b7 \\");\\n  $(\\"#callados\\").innerHTML =\\n    \\"<b>\\" + mil(C.n) + \\" papers no declaran ni terreno, ni instrumento, ni t\\u00e9cnica, ni dise\\u00f1o</b> \\u2014 el \\" +\\n    dec(C.pct) + \\"% del corpus. No son marginales: mediana de <b>\\" + mil(C.mediana) +\\n    \\"</b> citas, y el mayor con <b>\\" + mil(C.max) + \\"</b>. \\" +\\n    \\"<b>\\" + mil(C.revisiones) + \\" son revisiones</b> \\u2014 el \\" + C.pct_rev_grupo +\\n    \\"% de este grupo, frente al \\" + C.pct_rev_corpus + \\"% del corpus \\u2014, y una revisi\\u00f3n no tiene \\" +\\n    \\"terreno ni instrumento que declarar. Los <b>\\" + mil(C.articulos) + \\" restantes son art\\u00edculos</b>\\" +\\n    (kw ? \\"; sus palabras clave m\\u00e1s frecuentes son \\" + kw + \\".\\" : \\".\\") +\\n    (C.sin_kw ? \' <span class=\\"censo\\">\' + mil(C.sin_kw) + \\" del grupo no traen ninguna palabra clave, \\" +\\n                \\"as\\u00ed que no entran en ese recuento.</span>\\" : \\"\\") +\\n    (C.ecuacion_declarada ? \\"\\" :\\n      \' <span class=\\"censo\\">La corrida del retrato no declar\\u00f3 la ecuaci\\u00f3n base: sus t\\u00e9rminos siguen \' +\\n      \\"contando en esa lista.</span>\\");\\n})();\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 EL CANON \\u00b7 a qui\\u00e9n lee este campo\\n   La l\\u00e1mina 9 del retrato ordena por citas RECIBIDAS de todo Scopus: por lo que\\n   le importa al mundo. Esto es lo contrario \\u2014a qui\\u00e9n lee esta comunidad\\u2014 y son\\n   listas distintas. La columna que de verdad importa es la \\u00faltima: casi todo lo\\n   que este campo m\\u00e1s lee NO est\\u00e1 en el corpus, porque la ecuaci\\u00f3n no lo pesc\\u00f3.\\n\\n   Se cuenta por T\\u00cdTULO de la obra citada. Contar por \\u00abapellido + a\\u00f1o\\u00bb colisiona:\\n   \\u00abWang 2021\\u00bb son varios papers distintos, y esa clave lleg\\u00f3 a dar l\\u00edneas\\n   imposibles \\u2014citado por 70 papers del corpus teniendo 55 citas en Scopus\\u2014.\\n   Se pinta una vez y no depende de los filtros: es del corpus entero. */\\n(function () {\\n  const C = D.canon;\\n  // SIN REFERENCIAS la pesta\\u00f1a SALE IGUAL y dice por qu\\u00e9 est\\u00e1 vac\\u00eda. Antes se\\n  // escond\\u00eda, y esconderla es incumplir el candado 5 del bloque 1 \\u2014una capa\\n  // ausente se dibuja, no se calla\\u2014: quien no supiera que exist\\u00eda no pod\\u00eda saber\\n  // que le faltaba. Adem\\u00e1s as\\u00ed la ausencia se convierte en una instrucci\\u00f3n para\\n  // la pr\\u00f3xima exportaci\\u00f3n, que es lo \\u00fanico que la puede resolver.\\n  if (!C || !C.obras || !C.obras.length) {\\n    $(\\"#pesCN\\").textContent = \\"\\u00b7 vac\\u00edo\\";\\n    $(\\"#canon\\").innerHTML =\\n      \'<span class=\\"rotulo\\">El canon <span class=\\"ac\\">\\u00b7 a qui\\u00e9n lee este campo</span></span>\' +\\n      \'<div class=\\"pendiente\\" style=\\"max-width:760px;margin-top:8px\\">\' +\\n      \'<b>Este export se baj\\u00f3 SIN referencias, as\\u00ed que esta pesta\\u00f1a no puede decir nada.</b><br><br>\' +\\n      \'Con ellas ver\\u00edas <b>las obras que m\\u00e1s lee tu campo</b> \\u2014contando las que citan tus \' +\\n      mil(D.papers.length) + \' papers\\u2014 y, al lado de cada una, si est\\u00e1 dentro o fuera de tu corpus. \' +\\n      \'En el corpus de prueba, <b>41 de las 50 m\\u00e1s le\\u00eddas estaban fuera</b>: se puede mapear un \' +\\n      \'campo entero sin ver ni una de las obras que lo fundaron.<br><br>\' +\\n      \'Tambi\\u00e9n se apaga por lo mismo el \\u00abse apoya en / lo citan\\u00bb de cada ficha.<br><br>\' +\\n      \'Se arregla en el origen: al exportar de Scopus, marcar que <b>incluya las referencias</b>. \' +\\n      \'El archivo pesa unas cuatro veces m\\u00e1s y ese es todo el coste.</div>\';\\n    return;\\n  }\\n  $(\\"#pesCN\\").textContent = \\"\\u00b7 \\" + mil(C.res.fuera_50) + \\" de 50 fuera\\";\\n  const tabla = obras => \'<table class=\\"canon-t\\"><tbody>\' + obras.map(o => `\\n    <tr class=\\"${o.dentro ? \\"dentro\\" : \\"\\"}\\" ${o.dentro ? \'data-id=\\"\' + o.id + \'\\"\' : \\"\\"}>\\n      <td class=\\"n\\">${mil(o.n)}</td>\\n      <td class=\\"yy\\">${esc(o.y)}</td>\\n      <td>${esc(o.t)}</td>\\n      <td>${o.dentro ? \'<span class=\\"et-dentro\\">en tu corpus</span>\'\\n                     : \'<span class=\\"et-fuera\\">fuera</span>\'}</td>\\n    </tr>`).join(\\"\\") + \\"</tbody></table>\\";\\n\\n  // Dos preguntas distintas sobre el mismo dato, y por eso van juntas y no en\\n  // dos pesta\\u00f1as: \\u00aba qui\\u00e9n lee este campo\\u00bb y \\u00abqu\\u00e9 obra reciente ya se lee\\u00bb.\\n  const VISTAS = {\\n    todas: {\\n      chip: \\"las m\\u00e1s le\\u00eddas\\",\\n      obras: C.obras,\\n      sub: \\"De las 20 m\\u00e1s le\\u00eddas, \\" + C.res.fuera_20 + \\" est\\u00e1n fuera de tu corpus \\u00b7 de las 50, \\" +\\n           C.res.fuera_50,\\n      nota: \\"Las marcadas <b>fuera</b> no las captur\\u00f3 tu ecuaci\\u00f3n: puedes mapear tu campo entero \\" +\\n            \\"sin ver ni una de ellas.\\"\\n    },\\n    nuevas: {\\n      chip: \\"publicadas desde 2021\\",\\n      obras: C.nuevas,\\n      sub: \\"Obras recientes que <b>ya</b> se citan \\u2014 el canon que se est\\u00e1 formando\\",\\n      nota: \\"Son otra lista: las m\\u00e1s le\\u00eddas del campo son de 2010 a 2018, y estas de 2021 en \\" +\\n            \\"adelante. Aqu\\u00ed la proporci\\u00f3n se invierte y muchas <b>s\\u00ed</b> est\\u00e1n en tu corpus, \\" +\\n            \\"porque tu ecuaci\\u00f3n pesca lo reciente mejor que lo fundacional.\\"\\n    }\\n  };\\n  let vista = \\"todas\\";\\n  function pintaCanon() {\\n    const V = VISTAS[vista];\\n    $(\\"#canon\\").innerHTML =\\n      \'<span class=\\"rotulo\\">El canon <span class=\\"ac\\">\\u00b7 a qui\\u00e9n lee este campo</span></span>\' +\\n      \'<div class=\\"meta\\">Nadie escribi\\u00f3 esta lista: sale de contar las \' + mil(C.res.entradas) +\\n      \' referencias que tus \' + mil(D.papers.length) + \' papers citan, agrupadas por obra. \' +\\n      \'Ordena por <b>a qui\\u00e9n lee esta comunidad</b>, no por a qui\\u00e9n cita el mundo \\u2014 que es lo que \' +\\n      \'mide la l\\u00e1mina de citas del retrato, y da otra lista.</div>\' +\\n      \'<div style=\\"margin:8px 0 4px\\">\' +\\n      Object.keys(VISTAS).map(k =>\\n        \'<span class=\\"chip sec cv\' + (k === vista ? \\" on\\" : \\"\\") + \'\\" data-v=\\"\' + k + \'\\">\' +\\n        VISTAS[k].chip + \\"</span>\\").join(\\" \\") + \\"</div>\\" +\\n      \'<div class=\\"subrot\\">\' + V.sub + \\"</div>\\" +\\n      tabla(V.obras) +\\n      \'<p class=\\"nota\\">\' + V.nota + \' Las de <b>en tu corpus</b> se pulsan y abren su ficha. \' +\\n      \'Todo esto solo existe si el export se baj\\u00f3 <b>con referencias</b>.</p>\';\\n  }\\n  pintaCanon();\\n  $(\\"#canon\\").addEventListener(\\"click\\", ev => {\\n    const c = ev.target.closest(\\".cv\\");\\n    if (!c) return;\\n    vista = c.dataset.v;\\n    pintaCanon();\\n  });\\n})();\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 eventos */\\ndocument.addEventListener(\\"click\\", ev => {\\n  if (ev.target.id === \\"btnMas\\") { tope += 250; pintaTabla(false); return; }\\n  const pill = ev.target.closest(\\".pill[data-c]\\");\\n  if (pill) { sel = null; setFoco(\\"c\\"+pill.dataset.c); panelConcepto(pill.dataset.c); pintaTabla(false); return; }\\n  const li = ev.target.closest(\\".lista-bl li\\");\\n  if (li) { sel = +li.dataset.id; setFoco(\\"p\\"+sel); panelPaper(D.papers.find(p=>p.id===sel)); pintaTabla(false); return; }\\n  const cn = ev.target.closest(\\".canon-t tr.dentro\\");\\n  if (cn) { sel = +cn.dataset.id; setFoco(\\"p\\"+sel); panelPaper(D.papers.find(p=>p.id===sel));\\n            pintaTabla(false); return; }\\n  const tr = ev.target.closest(\\"tr.fila\\");\\n  if (tr) { sel = +tr.dataset.id; setFoco(\\"p\\"+sel); panelPaper(D.papers.find(p=>p.id===sel)); pintaTabla(false); }\\n});\\nconst liga = (id,k) => $(id).onchange = e => { F[k] = e.target.value; sel = null; tope = 250; invalidar(); pintaTabla(true); };\\nliga(\\"#fMarco\\",\\"marco\\"); liga(\\"#fTec\\",\\"tecnica\\"); liga(\\"#fIns\\",\\"instrumento\\");\\nliga(\\"#fDis\\",\\"diseno\\"); liga(\\"#fReg\\",\\"region\\"); liga(\\"#fAnio\\",\\"anio\\");\\n$(\\"#fTexto\\").oninput = e => { F.texto = e.target.value.toLowerCase(); tope = 250; invalidar(); pintaTabla(true); };\\nconst chip = (id,k) => $(id).onclick = e => {\\n  F[k] = !F[k]; e.target.classList.toggle(\\"on\\", F[k]);\\n  sel = null; tope = 250; invalidar(); pintaTabla(true);\\n};\\nchip(\\"#fVacio\\",\\"vacio\\"); chip(\\"#fNulo\\",\\"nulo\\"); chip(\\"#fCallado\\",\\"callado\\");\\n$(\\"#fReset\\").onclick = () => {\\n  Object.keys(F).forEach(k => F[k] = typeof F[k] === \\"boolean\\" ? false : \\"\\");\\n  $(\\"#fVacio\\").classList.remove(\\"on\\"); $(\\"#fNulo\\").classList.remove(\\"on\\");\\n  $(\\"#fCallado\\").classList.remove(\\"on\\");\\n  [\\"#fMarco\\",\\"#fTec\\",\\"#fIns\\",\\"#fDis\\",\\"#fReg\\",\\"#fAnio\\",\\"#fTexto\\"].forEach(s => $(s).value = \\"\\");\\n  sel = null; tope = 250; invalidar(); pintaTabla(true);\\n};\\ndocument.querySelectorAll(\\"th[data-k]\\").forEach(th => th.onclick = () => {\\n  orden = {k: th.dataset.k, asc: orden.k === th.dataset.k ? !orden.asc : false};\\n  invalidar(); pintaTabla(false);\\n});\\ndocument.querySelectorAll(\\".tg[data-t]\\").forEach(t => t.onclick = () => {\\n  ver[t.dataset.t] = ver[t.dataset.t] ? 0 : 1;\\n  t.classList.toggle(\\"on\\", !!ver[t.dataset.t]); construye();\\n});\\n$(\\"#gColor\\").onchange = e => { colorPor = e.target.value; $(\\"#gColor2\\").value = colorPor; leyenda(); };\\n$(\\"#gColor2\\").onchange = e => { colorPor = e.target.value; $(\\"#gColor\\").value = colorPor; leyenda(); };\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 tirador */\\nlet arrastraT = false;\\n$(\\"#tirador\\").onmousedown = () => { arrastraT = true; document.body.style.userSelect = \\"none\\"; };\\naddEventListener(\\"mouseup\\", () => { if (arrastraT) { arrastraT = false; document.body.style.userSelect = \\"\\";\\n  ajusta(); construye(); } });\\naddEventListener(\\"mousemove\\", ev => {\\n  if (!arrastraT) return;\\n  const alto_ = innerHeight, y = ev.clientY;\\n  const pct = Math.max(18, Math.min(75, (y / alto_) * 100 - 8));\\n  $(\\".zona-grafo\\").style.flexBasis = pct + \\"%\\";\\n  ajusta();\\n});\\n\\n/* \\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500 grafo */\\nconst COL_TIPO = {paper:\\"#8FA6AE\\", tecnica:\\"#1F6F6B\\", instrumento:\\"#4A6D8C\\",\\n                  diseno:\\"#6B5B95\\", region:\\"#8E3550\\", marco:\\"#B8891C\\", revista:\\"#94A399\\"};\\n// Ocho tonos SEPARADOS. La paleta anterior ten\\u00eda #1F6F6B, #3F8F6B y #2C7A7B \\u2014tres\\n// verdiazules casi iguales\\u2014 y justo ca\\u00edan en los quinquenios poblados: con el\\n// color por quinquenio, 2015-2019 y 2025-2029 no se distingu\\u00edan. Y ninguno puede\\n// ser muy oscuro: en pantalla completa el fondo del lienzo es #0B1A21.\\nconst PAL = [\\"#1F6F6B\\",\\"#8E3550\\",\\"#B8891C\\",\\"#4A6D8C\\",\\"#6B5B95\\",\\"#4C8B3F\\",\\"#C2603B\\",\\"#CE6F9B\\"];\\nlet N = [], E = [], vecinos = new Map(), arrastra = null, hover = null, alpha = 1;\\n// La clave del nodo enfocado, no su \\u00edndice: as\\u00ed sobrevive a que el grafo se\\n// reconstruya al filtrar. null = se ve todo.\\nlet focoK = null;\\nfunction setFoco(k) {\\n  focoK = k;\\n  const v = k ? \\"\\" : \\"none\\";\\n  const b1 = $(\\"#btnFoco\\"), b2 = $(\\"#btnFoco2\\");\\n  if (b1) b1.style.display = v;\\n  if (b2) b2.style.display = v;\\n  leyenda();          // las cifras de la leyenda son de la vecindad enfocada\\n}\\n\\nfunction colorDe(n) {\\n  if (n.tipo !== \\"paper\\") return COL_TIPO[n.tipo];\\n  const p = n.p;\\n  if (colorPor === \\"tipo\\") return COL_TIPO.paper;\\n  if (colorPor === \\"vacio\\") return p.frase_vacio ? \\"#B8891C\\" : \\"#C3CFCF\\";\\n  const v = colorPor === \\"region\\" ? (p.region[0] || \\"\\u2014\\") : p.decada;\\n  const ks = colorPor === \\"region\\" ? uni(\\"region\\") : [...new Set(D.papers.map(x=>x.decada))].sort();\\n  const i = ks.indexOf(v);\\n  return i < 0 ? \\"#C3CFCF\\" : PAL[i % PAL.length];\\n}\\nfunction leyenda() {\\n  /* La leyenda CUENTA, y cuenta solo lo que est\\u00e1 dibujado ahora mismo \\u2014 los\\n     nodos del grafo, no el corpus. Si contara el corpus entero mientras la\\n     pantalla ense\\u00f1a un recorte, estar\\u00eda ense\\u00f1ando una cifra que no corresponde\\n     a lo que se ve, que es la forma m\\u00e1s barata de mentir con un n\\u00famero cierto.\\n     Los colores sin ning\\u00fan paper no se listan: un quinquenio vac\\u00edo es tiempo\\n     vac\\u00edo, y de las regiones que faltan ya habla el panel de lectura. */\\n  // Y si hay un nodo enfocado, cuenta SOLO su vecindad, que es lo que queda\\n  // encendido. Enfocar TPB y leer \\u00ab394\\u00bb en la leyenda mientras en pantalla se\\n  // ven 53 ser\\u00eda la misma mentira, en otro sitio.\\n  const iFoco = focoK ? N.findIndex(n => n.k === focoK) : -1;\\n  const cercaL = iFoco >= 0 ? (vecinos.get(iFoco) || new Set()) : null;\\n  const dentro = (n, i) => !cercaL || i === iFoco || cercaL.has(i);\\n  const ps = N.filter((n, i) => n.tipo === \\"paper\\" && dentro(n, i));\\n  const cuenta = f => {\\n    const c = new Map();\\n    ps.forEach(n => { const k = f(n.p); c.set(k, (c.get(k) || 0) + 1); });\\n    return c;\\n  };\\n  const pt = (col, etq, n) =>\\n    `<i><span class=\\"pt\\" style=\\"background:${col}\\"></span>${esc(etq)}` +\\n    (n === undefined ? \\"\\" : ` \\u00b7 <b>${mil(n)}</b>`) + `</i>`;\\n  let h = \\"\\";\\n  if (colorPor === \\"tipo\\") {\\n    const capas = Object.entries(ETQ).filter(([k]) => ver[k]);\\n    // El TAMA\\u00d1O significa dos cosas en el mismo lienzo \\u2014en un concepto, cu\\u00e1ntos\\n    // papers lo declaran; en un paper, sus citas\\u2014 y hasta ahora solo se\\n    // declaraba la segunda. Un canal visual con dos sentidos sin declarar es\\n    // exactamente lo que el candado 2 proh\\u00edbe.\\n    const porTipo = new Map();\\n    N.forEach((n, i) => { if (n.tipo !== \\"paper\\" && dentro(n, i))\\n      porTipo.set(n.tipo, (porTipo.get(n.tipo) || 0) + 1); });\\n    h = capas.map(([k,e]) => pt(COL_TIPO[k], e, porTipo.get(k) || 0)).join(\\"\\") +\\n        (capas.length\\n          ? pt(COL_TIPO.paper, \\"paper\\", ps.length) +\\n            `<i>tama\\u00f1o: en un concepto, papers que lo declaran \\u00b7 en un paper, citas</i>`\\n          : \\"\\");\\n  }\\n  else if (colorPor === \\"vacio\\") {\\n    const c = cuenta(p => p.frase_vacio ? 1 : 0);\\n    h = pt(\\"#B8891C\\", \\"declara vac\\u00edo\\", c.get(1) || 0) + pt(\\"#C3CFCF\\", \\"no lo declara\\", c.get(0) || 0);\\n  }\\n  else {\\n    const ks = colorPor === \\"region\\" ? uni(\\"region\\") : [...new Set(D.papers.map(x=>x.decada))].sort();\\n    const c = cuenta(p => colorPor === \\"region\\" ? (p.region[0] || \\"\\u2014\\") : p.decada);\\n    h = ks.map((k,i) => c.get(k) ? pt(PAL[i%PAL.length], k, c.get(k)) : \\"\\").join(\\"\\");\\n    // los que no caen en ninguna categor\\u00eda se pintan grises: hay que contarlos\\n    // o las cifras de la leyenda no suman los papers que se ven\\n    const sin = ps.length - ks.reduce((s,k) => s + (c.get(k) || 0), 0);\\n    if (sin > 0) h += pt(\\"#C3CFCF\\", colorPor === \\"region\\" ? \\"sin regi\\u00f3n declarada\\" : \\"sin a\\u00f1o\\", sin);\\n  }\\n  $(\\"#leyenda\\").innerHTML = h; $(\\"#leyenda2\\").innerHTML = h;\\n}\\nfunction construye() {\\n  const prev = new Map(N.map(n => [n.k, n]));\\n  const vis = visibles(), ids = new Set(vis.map(p=>p.id));\\n  // Un paper se dibuja SOLO si cuelga de alguna capa encendida. Antes se\\n  // dibujaban siempre y los botones solo gobernaban a los conceptos: apagarlas\\n  // todas dejaba 1.196 puntos sueltos rebotando en vez de un lienzo vac\\u00edo.\\n  // Efecto secundario que se agradece: desaparece la periferia enga\\u00f1osa \\u2014 un\\n  // paper sin conceptos flotaba en el borde porque su posici\\u00f3n es el promedio\\n  // de sus vecinos y no ten\\u00eda ninguno. Los callados ya tienen su propia l\\u00e1mina,\\n  // as\\u00ed que el grafo no necesita cargar con ese trabajo.\\n  const activos = D.conceptos.filter(c => ver[c.tipo]);\\n  const conCapa = new Set();\\n  activos.forEach(c => c.papers.forEach(i => { if (ids.has(i)) conCapa.add(i); }));\\n  N = []; E = []; vecinos = new Map();\\n  const idx = new Map();\\n  vis.filter(p => conCapa.has(p.id)).forEach(p => { idx.set(\\"p\\"+p.id, N.length);\\n    N.push({k:\\"p\\"+p.id, tipo:\\"paper\\", et:p.t.slice(0,30), r:2.5+Math.min(8,Math.sqrt(p.cit)/2.4), id:p.id, p}); });\\n  activos.forEach(c => {\\n    const m\\u00edos = c.papers.filter(i => conCapa.has(i)); if (!m\\u00edos.length) return;\\n    idx.set(\\"c\\"+c.nombre, N.length);\\n    // ra\\u00edz cuadrada: si no, \\u00abEncuesta\\u00bb con 293 papers es una mancha que tapa todo\\n    N.push({k:\\"c\\"+c.nombre, tipo:c.tipo, et:c.nombre, r:5+Math.min(16,Math.sqrt(m\\u00edos.length)*1.5),\\n            nombre:c.nombre, grado:m\\u00edos.length});\\n    m\\u00edos.forEach(i => E.push([idx.get(\\"c\\"+c.nombre), idx.get(\\"p\\"+i)]));\\n  });\\n  E.forEach(([i,j]) => {\\n    if (!vecinos.has(i)) vecinos.set(i,new Set()); if (!vecinos.has(j)) vecinos.set(j,new Set());\\n    vecinos.get(i).add(j); vecinos.get(j).add(i);\\n  });\\n  const W = ancho(), H = alto();\\n  N.forEach((n,i) => {\\n    const v = prev.get(n.k);\\n    if (v) { n.x=v.x; n.y=v.y; n.vx=v.vx; n.vy=v.vy; }\\n    else { const a=(i/N.length)*Math.PI*2*7;\\n           n.x=W/2+Math.cos(a)*(n.tipo===\\"paper\\"?W*.34*(.4+(i%10)/14):W*.15);\\n           n.y=H/2+Math.sin(a)*(n.tipo===\\"paper\\"?H*.34*(.4+(i%10)/14):H*.15); n.vx=0; n.vy=0; }\\n  });\\n  leyenda(); alpha = 1;\\n  if (focoK && !N.some(n => n.k === focoK)) setFoco(null);   // ya no est\\u00e1 en la vista\\n}\\nconst grande = () => $(\\"#velo\\").classList.contains(\\"on\\");\\nconst cvs = () => grande() ? $(\\"#grafoBig\\") : $(\\"#grafo\\");\\nconst ancho = () => cvs().width / devicePixelRatio;\\nconst alto  = () => cvs().height / devicePixelRatio;\\n\\nfunction paso() {\\n  if (alpha < .004 && !arrastra) return;\\n  const W = ancho(), H = alto(), esc_ = grande() ? 1.7 : 1;\\n  const C = [];\\n  for (let i=0;i<N.length;i++) if (N[i].tipo !== \\"paper\\") C.push(i);\\n  for (let x=0;x<C.length;x++) for (let y=x+1;y<C.length;y++) {\\n    const a=N[C[x]], b=N[C[y]]; let dx=b.x-a.x, dy=b.y-a.y;\\n    const d2=dx*dx+dy*dy||.01, d=Math.sqrt(d2);\\n    const f=(11000*esc_*esc_)/d2, ux=dx/d, uy=dy/d;\\n    a.vx-=ux*f; a.vy-=uy*f; b.vx+=ux*f; b.vy+=uy*f;\\n  }\\n  const celda = 42*esc_, G = new Map();\\n  for (let i=0;i<N.length;i++) {\\n    const k = ((N[i].x/celda)|0) + \\":\\" + ((N[i].y/celda)|0);\\n    let a = G.get(k); if (!a) { a = []; G.set(k, a); } a.push(i);\\n  }\\n  for (let i=0;i<N.length;i++) {\\n    const a=N[i], gx=(a.x/celda)|0, gy=(a.y/celda)|0;\\n    for (let ox=-1;ox<=1;ox++) for (let oy=-1;oy<=1;oy++) {\\n      const arr = G.get((gx+ox)+\\":\\"+(gy+oy)); if (!arr) continue;\\n      for (let z=0;z<arr.length;z++) {\\n        const j = arr[z]; if (j <= i) continue;\\n        const b=N[j]; let dx=b.x-a.x, dy=b.y-a.y;\\n        const d2=dx*dx+dy*dy||.01, d=Math.sqrt(d2);\\n        const f=(620*esc_*esc_)/d2, ux=dx/d, uy=dy/d;\\n        a.vx-=ux*f; a.vy-=uy*f; b.vx+=ux*f; b.vy+=uy*f;\\n      }\\n    }\\n  }\\n  E.forEach(([i,j]) => {\\n    const a=N[i], b=N[j]; let dx=b.x-a.x, dy=b.y-a.y;\\n    const d=Math.sqrt(dx*dx+dy*dy)||.01, f=(d-70*esc_)*.0045, ux=dx/d, uy=dy/d;\\n    a.vx+=ux*f*d*.10; a.vy+=uy*f*d*.10; b.vx-=ux*f*d*.10; b.vy-=uy*f*d*.10;\\n  });\\n  N.forEach(n => {\\n    n.vx+=(W/2-n.x)*.0018; n.vy+=(H/2-n.y)*.0018;\\n    if (n===arrastra) { n.vx=n.vy=0; return; }\\n    n.vx*=.85; n.vy*=.85;\\n    n.x+=Math.max(-7,Math.min(7,n.vx)); n.y+=Math.max(-7,Math.min(7,n.vy));\\n    // Un concepto lleva r\\u00f3tulo encima: se le deja sitio para que no acabe\\n    // aplastado contra el borde superior. Un paper no lo lleva salvo al pasarle\\n    // el rat\\u00f3n, as\\u00ed que se conforma con su radio.\\n    const arr_ = n.tipo === \\"paper\\" ? n.r+2 : n.r+17;\\n    n.x=Math.max(n.r+2,Math.min(W-n.r-2,n.x)); n.y=Math.max(arr_,Math.min(H-n.r-2,n.y));\\n  });\\n  alpha *= .988;\\n}\\nfunction pinta() {\\n  const cv = cvs(), cx = cv.getContext(\\"2d\\"), W = ancho(), H = alto();\\n  cx.clearRect(0,0,W,H);\\n  // El lienzo vac\\u00edo tiene que INSTRUIR, no parecer roto: sin este letrero, el\\n  // arranque en blanco se lee como que el archivo no carg\\u00f3.\\n  if (!N.length) {\\n    const oscuro_ = grande();\\n    cx.textAlign = \\"center\\";\\n    cx.fillStyle = oscuro_ ? \\"#8FA6A3\\" : \\"#6E838C\\";\\n    cx.font = \'600 13px \\"Segoe UI\\",sans-serif\';\\n    cx.fillText(\\"El mapa se construye por capas.\\", W/2, H/2 - 8);\\n    cx.font = \'12px \\"Segoe UI\\",sans-serif\';\\n    cx.fillText(Object.values(ver).some(Boolean)\\n      ? \\"Ning\\u00fan paper del recorte actual declara esa capa.\\"\\n      : \\"Empieza encendiendo \\u00abmarco\\u00bb, arriba a la derecha.\\", W/2, H/2 + 12);\\n    return;\\n  }\\n  const foco = focoK ? N.findIndex(n => n.k === focoK) : -1;\\n  const cerca = foco >= 0 ? (vecinos.get(foco) || new Set()) : null;\\n  const oscuro = grande();\\n  cx.lineWidth = 1;\\n  E.forEach(([i,j]) => {\\n    const on = !cerca || i===foco || j===foco;\\n    if (!on && cerca) return;\\n    cx.strokeStyle = oscuro ? \\"rgba(180,205,205,.38)\\" : \\"rgba(110,131,140,.24)\\";\\n    cx.beginPath(); cx.moveTo(N[i].x,N[i].y); cx.lineTo(N[j].x,N[j].y); cx.stroke();\\n  });\\n  N.forEach((n,i) => {\\n    const on = !cerca || i === foco || cerca.has(i);\\n    cx.beginPath(); cx.arc(n.x,n.y,n.r,0,7);\\n    cx.fillStyle = colorDe(n);\\n    cx.globalAlpha = on ? (n.tipo===\\"paper\\"?.80:.95) : (oscuro ? .22 : .15);\\n    cx.fill(); cx.globalAlpha = 1;\\n    if (sel && n.k === \\"p\\"+sel) { cx.lineWidth=2.5; cx.strokeStyle=oscuro?\\"#EAF1EF\\":\\"#10222B\\"; cx.stroke(); cx.lineWidth=1; }\\n    if (on && (n.tipo !== \\"paper\\" || n === hover)) {\\n      cx.font = (n.tipo===\\"paper\\"?\\"10px \\":\\"600 11.5px \\") + \'\\"Segoe UI\\",sans-serif\';\\n      cx.fillStyle = oscuro ? \\"#DCE8E6\\" : (n.tipo===\\"paper\\"?\\"#3D5561\\":\\"#10222B\\");\\n      cx.textAlign = \\"center\\";\\n      const txt = n.tipo===\\"paper\\" ? n.et : n.et + (n===hover ? \\"  (\\"+mil(n.grado)+\\")\\" : \\"\\");\\n      // El r\\u00f3tulo va CENTRADO en el nodo y ENCIMA de \\u00e9l, as\\u00ed que un concepto\\n      // pegado al borde perd\\u00eda media palabra por el lado, o el r\\u00f3tulo entero por\\n      // arriba. En pantalla completa pasaba con varios a la vez. Se sujeta\\n      // dentro del ancho, y si arriba no cabe se dibuja debajo.\\n      const mitad = cx.measureText(txt).width/2 + 4;\\n      const arriba = n.y - n.r - 4;\\n      cx.fillText(txt, Math.max(mitad, Math.min(W - mitad, n.x)),\\n                  arriba < 12 ? n.y + n.r + 12 : arriba);\\n    }\\n  });\\n}\\nfunction bucle(){ paso(); pinta(); requestAnimationFrame(bucle); }\\nfunction ajusta() {\\n  [$(\\"#grafo\\"), $(\\"#grafoBig\\")].forEach(c => {\\n    const r = c.getBoundingClientRect();\\n    // Un lienzo oculto mide 0\\u00d70. Si se le hace caso, el m\\u00ednimo de 220\\u00d7150 se\\n    // convierte en la caja donde la simulaci\\u00f3n aplasta a todos los nodos, y al\\n    // volver a mostrarlo el mapa aparece descolocado. Mejor no tocarlo: se\\n    // queda con su \\u00faltimo tama\\u00f1o bueno y las posiciones se conservan.\\n    if (!r.width || !r.height) return;\\n    c.width = Math.max(220, r.width) * devicePixelRatio;\\n    c.height = Math.max(150, r.height) * devicePixelRatio;\\n    c.getContext(\\"2d\\").setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);\\n  });\\n}\\nfunction pos(ev){ const r = cvs().getBoundingClientRect(); return {x:ev.clientX-r.left, y:ev.clientY-r.top}; }\\nfunction nodoEn(p){\\n  for (let i=N.length-1;i>=0;i--) if (Math.hypot(N[i].x-p.x,N[i].y-p.y) < N[i].r+4) return i;\\n  return -1;\\n}\\n[$(\\"#grafo\\"), $(\\"#grafoBig\\")].forEach(c => {\\n  c.onmousedown = ev => { const i = nodoEn(pos(ev)); arrastra = i>=0?N[i]:null;\\n    setFoco(i>=0 ? N[i].k : null);\\n    alpha = Math.max(alpha,.3); c.style.cursor = arrastra?\\"grabbing\\":\\"grab\\"; };\\n  c.onmousemove = ev => { const p = pos(ev);\\n    if (arrastra) { arrastra.x=p.x; arrastra.y=p.y; return; }\\n    const i = nodoEn(p); hover = i>=0?N[i]:null; c.style.cursor = hover?\\"pointer\\":\\"grab\\"; };\\n  c.onmouseup = ev => {\\n    const i = nodoEn(pos(ev));\\n    if (i>=0 && N[i]===arrastra) {\\n      const n = N[i];\\n      if (n.tipo === \\"paper\\") { sel = n.id; panelPaper(D.papers.find(p=>p.id===n.id)); pintaTabla(false); }\\n      else panelConcepto(n.nombre);\\n    } else if (i < 0) { setFoco(null); }\\n    arrastra = null; c.style.cursor = \\"grab\\";\\n  };\\n});\\n$(\\"#btnAmp\\").onclick = () => { $(\\"#velo\\").classList.add(\\"on\\");\\n  $(\\"#veloN\\").textContent = mil(visibles().length) + \\" papers\\";\\n  setTimeout(()=>{ajusta(); alpha=1;}, 30); };\\n$(\\"#cerrar\\").onclick = () => { $(\\"#velo\\").classList.remove(\\"on\\"); setTimeout(()=>{ajusta(); alpha=1;}, 30); };\\naddEventListener(\\"keydown\\", e => {\\n  if (e.key !== \\"Escape\\") return;\\n  if (focoK) { setFoco(null); return; }          // primero suelta el foco\\n  if (grande()) { $(\\"#cerrar\\").click(); return; }   // y solo despu\\u00e9s cierra\\n  if ($(\\".tablero\\").classList.contains(\\"solo-abajo\\")) ampAbajo();  // y por \\u00faltimo, despliega\\n});\\n$(\\"#btnFoco\\").onclick = () => setFoco(null);\\n$(\\"#btnFoco2\\").onclick = () => setFoco(null);\\naddEventListener(\\"resize\\", () => { ajusta(); alpha = 1; });\\n\\n// El lienzo cambia de tama\\u00f1o por tres v\\u00edas: pantalla completa, el tirador y la\\n// ventana. Las dos primeras se resolv\\u00edan con un setTimeout de 30 ms, y en\\n// pantalla completa eso med\\u00eda el alto CON EL VELO A MEDIO ABRIR: la simulaci\\u00f3n\\n// se quedaba con un H peque\\u00f1o, apelotonaba el grafo contra el techo y dejaba\\n// media pantalla vac\\u00eda debajo. Un observador no depende de acertar el retardo.\\nif (window.ResizeObserver) {\\n  const ro = new ResizeObserver(() => { ajusta(); alpha = 1; });\\n  ro.observe($(\\"#grafo\\")); ro.observe($(\\"#grafoBig\\"));\\n}\\n\\najusta();\\n// Con todas las capas apagadas no se abre una ficha de concepto: nombrar\\u00eda algo\\n// que el mapa no est\\u00e1 dibujando, y la ficha quedar\\u00eda contradiciendo al lienzo.\\nconst _ini = D.conceptos.filter(c => ver[c.tipo]).sort((a,b)=>b.papers.length-a.papers.length)[0];\\nif (_ini) panelConcepto(_ini.nombre);\\nelse $(\\"#det\\").innerHTML =\\n  \'<span class=\\"rotulo\\">La ficha</span>\' +\\n  \'<div class=\\"meta\\">Aqu\\u00ed se lee un paper entero, o la p\\u00e1gina de un concepto con los papers \' +\\n  \'que lo declaran. Enciende una capa del mapa, o pulsa cualquier fila de la tabla.</div>\';\\npestana(\\"tabla\\");   // se abre SIEMPRE por la tabla, aunque arriba hubiera capas\\npintaTabla(true);\\nbucle();\\n</script></body></html>\\n"')
MARCA = "/*__DATOS__*/"



# para() ya está definida arriba, en la parte de matriz.py.


def _emitir():
    salida = _SALIDA
    datos = os.path.join(salida, "matriz_data.json")

    if not os.path.exists(datos):
        para("no está %s." % datos)

    d = json.load(io.open(datos, encoding="utf-8"))
    tpl = _PLANTILLA
    if MARCA not in tpl:
        para("la plantilla no trae la marca %s: no se puede incrustar nada." % MARCA)

    destino = os.path.join(salida, "matriz.html")
    with io.open(destino, "w", encoding="utf-8") as f:
        f.write(tpl.replace(MARCA, json.dumps(d, ensure_ascii=False)))
    print("escrito: %s  (%.0f KB)" % (destino, os.path.getsize(destino) / 1024))
    print("   %d papers · %d conceptos" % (len(d["papers"]), len(d["conceptos"])))
    if not d.get("citas", {}).get("hay"):
        print("   sin referencias en el export: la ficha va sin citas y no hay pestaña de canon")


# ══════════════════════════════════════════════════════════════════════════
#  La CLI del archivo único.
#  En el skill son dos comandos sobre un matriz.json; aquí es uno solo y las
#  rutas se descubren solas, porque quien corre esto lo hace en un chat.
# ══════════════════════════════════════════════════════════════════════════

_P_TXT = _P_JSON = _SALIDA = _RAIZ = None


def _descubrir(argv):
    """Encuentra el .txt y el retrato_data.json sin que haya que escribir rutas."""
    global _P_TXT, _P_JSON, _SALIDA, _RAIZ
    import glob

    opciones, sueltos = {}, []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            if i + 1 >= len(argv):
                para("a %s le falta el valor" % a)
            opciones[a[2:]] = argv[i + 1]
            i += 2
        else:
            sueltos.append(a)
            i += 1

    carpeta = opciones.get("carpeta") or (os.path.dirname(os.path.abspath(sueltos[0]))
                                          if sueltos else os.getcwd())

    # ── el .txt
    if sueltos:
        p_txt = os.path.abspath(sueltos[0])
    else:
        txts = sorted(glob.glob(os.path.join(carpeta, "*.txt")))
        if not txts:
            para("no encuentro ningún .txt en %s.\n"
                 "            Tiene que ser EL MISMO export que corrió el retrato." % carpeta)
        if len(txts) > 1:
            para("hay más de un .txt: %s\n"
                 "            Deja solo el que corrió el retrato."
                 % [os.path.basename(t) for t in txts])
        p_txt = txts[0]

    # ── el retrato
    if opciones.get("retrato"):
        p_json = os.path.abspath(opciones["retrato"])
    else:
        cand = (glob.glob(os.path.join(carpeta, "retrato_data.json"))
                + glob.glob(os.path.join(carpeta, "**", "retrato_data.json"),
                            recursive=True))
        if not cand:
            para("no encuentro retrato_data.json.\n"
                 "            Organizar lo que no se ha visto no es un servicio:\n"
                 "            corre primero el paso 1, el retrato.")
        p_json = os.path.abspath(cand[0])

    _P_TXT, _P_JSON = p_txt, p_json
    _RAIZ = carpeta
    _SALIDA = os.path.abspath(opciones.get("salida") or carpeta)
    if not os.path.isdir(_SALIDA):
        os.makedirs(_SALIDA)


def main():
    _descubrir(sys.argv)
    print("corpus  :", os.path.basename(_P_TXT),
          "·", round(os.path.getsize(_P_TXT) / 1024 / 1024, 1), "MB")
    print("retrato :", os.path.basename(_P_JSON))
    print("-" * 74)
    _calcular()
    _emitir()
    print()
    print("LISTO. matriz.html — ábrelo en el navegador.")
    print("   Arriba: la lámina de los papers callados y el grafo por capas.")
    print("   Abajo:  la tabla, la ficha de cada paper y el canon.")


if __name__ == "__main__":
    main()
