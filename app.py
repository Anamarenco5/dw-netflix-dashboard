"""
Dashboard del DW Netflix (Paso 5 - Explotación).
Lee el modelo estrella dw_netflix alojado en Clever Cloud (MySQL)
y responde las 7 preguntas del Paso 1.

Regla de cálculo: la tabla de hechos tiene granularidad
título x país x género x director, así que los conteos siempre
son COUNT(DISTINCT show_id) y los promedios se hacen sobre títulos
distintos (nunca SUM(frecuencia) ni AVG directo sobre las filas).
"""
import os

import numpy as np
import pandas as pd
import plotly.express as px
import pymysql
import streamlit as st

st.set_page_config(page_title="DW Netflix", layout="wide")

# Colores fijos: el mismo significado tiene siempre el mismo color
COLOR_TIPO = {"Movie": "#E50914", "TV Show": "#3D3D3D"}
COLOR_GRUPO = {"Antiguo": "#9E9E9E", "Reciente": "#E50914"}


# ---------------------------------------------------------------------
# Conexión: Clever Cloud expone las credenciales como MYSQL_ADDON_*.
# En Render se cargan esas mismas variables en "Environment".
# ---------------------------------------------------------------------
def _env(*names, default=None):
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


DB = dict(
    host=_env("MYSQL_ADDON_HOST", "DB_HOST", default="localhost"),
    port=int(_env("MYSQL_ADDON_PORT", "DB_PORT", default="3306")),
    user=_env("MYSQL_ADDON_USER", "DB_USER", default="root"),
    password=_env("MYSQL_ADDON_PASSWORD", "DB_PASSWORD", default=""),
    database=_env("MYSQL_ADDON_DB", "DB_NAME", default="dw_netflix"),
)


@st.cache_data(ttl=3600, show_spinner="Consultando el DW...")
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = pymysql.connect(**DB, charset="utf8mb4", connect_timeout=15)
    try:
        with con.cursor() as cur:
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        con.close()


def num(df, *cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c])
    return df


# Join reutilizable con los atributos de una fila de hechos
BASE = """
FROM hechos_catalogo h
JOIN dim_tipo_contenido tc ON tc.id_tipo = h.id_tipo
JOIN dim_pais p            ON p.id_pais = h.id_pais
JOIN dim_genero g          ON g.id_genero = h.id_genero
JOIN dim_director d        ON d.id_director = h.id_director
JOIN dim_clasificacion c   ON c.id_clasificacion = h.id_clasificacion
JOIN dim_duracion du       ON du.id_duracion = h.id_duracion
JOIN dim_tiempo ti         ON ti.id_tiempo = h.id_tiempo_incorporacion
JOIN dim_tiempo tl         ON tl.id_tiempo = h.id_tiempo_lanzamiento
"""

# ---------------------------------------------------------------------
# Encabezado y filtros globales
# ---------------------------------------------------------------------
st.title("Catálogo de Netflix — Data Warehouse")
st.caption("Garciarena, Lupica, Marenco y Mas (A2) · Modelo estrella `dw_netflix` en Clever Cloud")

try:
    kpi = q(f"""
        SELECT COUNT(DISTINCT h.show_id) AS titulos,
               COUNT(DISTINCT CASE WHEN tc.tipo_contenido='Movie' THEN h.show_id END) AS peliculas,
               COUNT(DISTINCT CASE WHEN tc.tipo_contenido='TV Show' THEN h.show_id END) AS series,
               COUNT(DISTINCT NULLIF(h.id_pais,1)) AS paises,
               COUNT(DISTINCT NULLIF(h.id_genero,1)) AS generos,
               MIN(ti.anio) AS desde, MAX(ti.anio) AS hasta
        {BASE}""")
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudo conectar a la base: {e}")
    st.info("Revisar las variables MYSQL_ADDON_HOST/PORT/DB/USER/PASSWORD en Render.")
    st.stop()

k = kpi.iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Títulos", f"{int(k.titulos):,}".replace(",", "."))
c2.metric("Películas", f"{int(k.peliculas):,}".replace(",", "."))
c3.metric("Series", f"{int(k.series):,}".replace(",", "."))
c4.metric("Países", int(k.paises))
c5.metric("Géneros", int(k.generos))

with st.sidebar:
    st.header("Filtros")
    tipos = st.multiselect("Tipo de contenido", ["Movie", "TV Show"], default=["Movie", "TV Show"])
    anio_min, anio_max = int(k.desde), int(k.hasta)
    rango = st.slider("Año de incorporación a Netflix", anio_min, anio_max, (anio_min, anio_max))
    st.caption("Los filtros se aplican a todas las preguntas salvo que se indique otra cosa. "
               "Si se acota el año de incorporación quedan afuera los 10 títulos sin fecha de alta.")

if not tipos:
    st.warning("Elegí al menos un tipo de contenido.")
    st.stop()

ph_tipos = ",".join(["%s"] * len(tipos))
# Si el rango de años queda completo no se filtra por año, así no se
# pierden los 10 títulos sin fecha de incorporación (id_tiempo = 1).
FILTRO_7 = f" WHERE tc.tipo_contenido IN ({ph_tipos}) AND ti.anio BETWEEN %s AND %s "
if rango == (anio_min, anio_max):
    FILTRO = f" WHERE tc.tipo_contenido IN ({ph_tipos}) "
    PARAMS = tuple(tipos)
else:
    FILTRO = FILTRO_7
    PARAMS = (*tipos, rango[0], rango[1])

tabs = st.tabs([
    "1 · Países", "2 · Lanzamiento vs incorporación", "3 · País × género × tipo",
    "4 · Antiguo vs reciente", "5 · Directores", "6 · Diversidad de géneros",
    "7 · Perfil de lo reciente",
])

# ---------------------------------------------------------------------
# 1) Países con mayor presencia según el rango de fecha
# ---------------------------------------------------------------------
with tabs[0]:
    st.subheader("¿Qué países tienen mayor presencia en el catálogo según el rango de fecha?")
    top_n = st.slider("Cantidad de países", 5, 25, 10, key="p1n")
    df = num(q(f"""
        SELECT p.nombre_pais AS pais, tc.tipo_contenido AS tipo,
               COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY p.nombre_pais, tc.tipo_contenido""", PARAMS), "titulos")
    tot = df.groupby("pais").titulos.sum().nlargest(top_n)
    df = df[df.pais.isin(tot.index)]
    fig = px.bar(df, x="titulos", y="pais", color="tipo", color_discrete_map=COLOR_TIPO, orientation="h",
                 category_orders={"pais": list(tot.index)},
                 labels={"titulos": "Títulos", "pais": "", "tipo": "Tipo"})
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Evolución por año de incorporación (top 5 del período)**")
    ev = num(q(f"""
        SELECT ti.anio AS anio, p.nombre_pais AS pais, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY ti.anio, p.nombre_pais""", PARAMS), "titulos", "anio")
    ev = ev[ev.pais.isin(tot.index[:5])]
    st.plotly_chart(px.line(ev, x="anio", y="titulos", color="pais", markers=True,
                            labels={"anio": "Año de incorporación", "titulos": "Títulos", "pais": "País"}),
                    width="stretch")
    st.caption("Un título con coproducción cuenta para cada uno de sus países. Se excluyen títulos sin país.")

# ---------------------------------------------------------------------
# 2) Año de lanzamiento vs tiempo hasta incorporarse
# ---------------------------------------------------------------------
with tabs[1]:
    st.subheader("¿Hay relación entre el año de lanzamiento y el tiempo que tardó en llegar a Netflix?")
    t = num(q(f"""
        SELECT DISTINCT h.show_id, tl.anio AS lanzamiento, tl.decada,
               tc.tipo_contenido AS tipo, h.anios_hasta_incorporacion AS anios
        {BASE} {FILTRO} AND h.anios_hasta_incorporacion IS NOT NULL""", PARAMS),
        "lanzamiento", "decada", "anios")
    r = t.lanzamiento.corr(t.anios)
    m1, m2, m3 = st.columns(3)
    m1.metric("Títulos analizados", f"{len(t):,}".replace(",", "."))
    m2.metric("Promedio de años hasta incorporación", f"{t.anios.mean():.2f}")
    m3.metric("Correlación (Pearson)", f"{r:.2f}")
    por_anio = (t[t.lanzamiento >= 1990]
                .groupby(["lanzamiento", "tipo"]).anios.mean().reset_index())
    st.plotly_chart(px.line(por_anio, x="lanzamiento", y="anios", color="tipo", markers=True,
                            color_discrete_map=COLOR_TIPO,
                            labels={"lanzamiento": "Año de lanzamiento",
                                    "anios": "Años promedio hasta incorporarse", "tipo": "Tipo"},
                            title="Años promedio hasta llegar a Netflix (lanzamientos desde 1990)"),
                    width="stretch")
    dec = t.groupby(["decada", "tipo"]).anios.mean().round(1).unstack()
    dec.index = dec.index.astype(int).astype(str) + "s"
    st.markdown("**Años promedio hasta la incorporación, por década de lanzamiento**")
    st.dataframe(dec.astype(object).where(dec.notna(), "—"), width="stretch")
    st.caption(f"Una correlación de {r:.2f} indica una relación {'fuerte' if abs(r) > .6 else 'moderada' if abs(r) > .3 else 'débil'} "
               f"y {'negativa' if r < 0 else 'positiva'}: {'cuanto más reciente es el título, antes llega al catálogo' if r < 0 else 'los títulos más recientes tardan más'}. "
               "Parte de esa relación es esperable por construcción: como todas las altas ocurren entre 2008 y 2021, "
               "un título de 1960 no puede tardar menos de ~48 años. Por eso conviene leer también el promedio por década y por tipo.")

# ---------------------------------------------------------------------
# 3) País x género x tipo
# ---------------------------------------------------------------------
with tabs[2]:
    st.subheader("¿Cómo se relacionan el país de producción, el género y el tipo de contenido?")
    total = q(f"SELECT COUNT(DISTINCT h.show_id) AS n {BASE} {FILTRO}", PARAMS).n.iloc[0]
    comb = num(q(f"""
        SELECT p.nombre_pais AS pais, g.nombre_genero AS genero, tc.tipo_contenido AS tipo,
               COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY p.nombre_pais, g.nombre_genero, tc.tipo_contenido
        ORDER BY titulos DESC LIMIT 20""", PARAMS), "titulos")
    comb["% participación"] = (comb.titulos / float(total) * 100).round(2)
    st.markdown(f"**Top 20 combinaciones** (participación sobre {int(total):,} títulos del filtro)".replace(",", "."))
    st.dataframe(comb, width="stretch", hide_index=True)

    hm = num(q(f"""
        SELECT p.nombre_pais AS pais, g.nombre_genero AS genero, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY p.nombre_pais, g.nombre_genero""", PARAMS), "titulos")
    top_p = hm.groupby("pais").titulos.sum().nlargest(10).index
    top_g = hm.groupby("genero").titulos.sum().nlargest(12).index
    piv = hm[hm.pais.isin(top_p) & hm.genero.isin(top_g)].pivot(index="pais", columns="genero", values="titulos").fillna(0)
    piv = piv.loc[top_p, top_g]
    st.plotly_chart(px.imshow(piv, text_auto=True, aspect="auto", color_continuous_scale="Reds",
                              labels={"color": "Títulos", "x": "", "y": ""}),
                    width="stretch")
    st.caption("Mapa de calor: 10 países y 12 géneros con más títulos. Los porcentajes no suman 100 % porque un título puede tener varios países y géneros.")

# ---------------------------------------------------------------------
# 4) Antiguo vs reciente
# ---------------------------------------------------------------------
with tabs[3]:
    st.subheader("¿Qué distingue al contenido antiguo del reciente?")
    corte = st.slider("Año de lanzamiento que separa 'antiguo' de 'reciente'", 1990, 2020, 2010, key="corte")
    st.caption(f"Antiguo: lanzado antes de {corte}. Reciente: lanzado en {corte} o después. "
               "Se usa el año de lanzamiento (no el de incorporación).")
    GRUPO = "CASE WHEN tl.anio < %s THEN 'Antiguo' ELSE 'Reciente' END"

    base_t = num(q(f"""
        SELECT DISTINCT h.show_id, {GRUPO} AS grupo, tc.tipo_contenido AS tipo,
               c.codigo_rating AS rating, h.duracion_num AS duracion
        {BASE} {FILTRO}""", (corte, *PARAMS)), "duracion")
    n_grupo = base_t.groupby("grupo").show_id.nunique()

    a, b = st.columns(2)
    dur = base_t.groupby(["grupo", "tipo"]).duracion.mean().round(1).unstack()
    dur.columns = [f"{col} ({'min' if col == 'Movie' else 'temporadas'})" for col in dur.columns]
    dur.insert(0, "títulos", n_grupo)
    a.markdown("**Cantidad de títulos y duración promedio**")
    a.dataframe(dur, width="stretch")

    rat = base_t.groupby(["grupo", "rating"]).show_id.nunique().reset_index(name="titulos")
    rat["%"] = rat.titulos / rat.grupo.map(n_grupo) * 100
    b.plotly_chart(px.bar(rat, x="rating", y="%", color="grupo", color_discrete_map=COLOR_GRUPO, barmode="group",
                          labels={"rating": "Clasificación", "%": "% de títulos del grupo", "grupo": ""},
                          title="Clasificación"), width="stretch")

    for campo, etiqueta, extra in (("g.nombre_genero", "Género", ""), ("p.nombre_pais", "País", "AND h.id_pais > 1")):
        df = num(q(f"""
            SELECT {GRUPO} AS grupo, {campo} AS valor, COUNT(DISTINCT h.show_id) AS titulos
            {BASE} {FILTRO} {extra}
            GROUP BY grupo, valor""", (corte, *PARAMS)), "titulos")
        df["%"] = df.titulos / df.grupo.map(n_grupo) * 100
        top = df.groupby("valor")["%"].max().nlargest(10).index
        st.plotly_chart(px.bar(df[df.valor.isin(top)], x="%", y="valor", color="grupo",
                               category_orders={"valor": list(top), "grupo": ["Antiguo", "Reciente"]}, color_discrete_map=COLOR_GRUPO, barmode="group",
                               orientation="h", labels={"valor": "", "%": "% de títulos del grupo", "grupo": ""},
                               title=f"{etiqueta}: top 10"), width="stretch")

# ---------------------------------------------------------------------
# 5) Directores más frecuentes
# ---------------------------------------------------------------------
with tabs[4]:
    st.subheader("¿Qué directores aparecen más y en qué géneros y tipos participan?")
    n_dir = st.slider("Cantidad de directores", 5, 30, 15, key="dn")
    top = num(q(f"""
        SELECT d.id_director, d.nombre_director AS director, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_director > 1
        GROUP BY d.id_director, d.nombre_director
        ORDER BY titulos DESC, director LIMIT %s""", (*PARAMS, n_dir)), "titulos")
    ids = tuple(int(i) for i in top.id_director)
    ph = ",".join(["%s"] * len(ids))
    det = num(q(f"""
        SELECT d.nombre_director AS director, tc.tipo_contenido AS tipo, g.nombre_genero AS genero,
               COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_director IN ({ph})
        GROUP BY d.nombre_director, tc.tipo_contenido, g.nombre_genero""", (*PARAMS, *ids)), "titulos")
    tipo_real = num(q(f"""
        SELECT d.nombre_director AS director, tc.tipo_contenido AS tipo, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_director IN ({ph})
        GROUP BY d.nombre_director, tc.tipo_contenido""", (*PARAMS, *ids)), "titulos")
    st.plotly_chart(px.bar(tipo_real, x="titulos", y="director", color="tipo", color_discrete_map=COLOR_TIPO, orientation="h",
                           category_orders={"director": list(top.director)},
                           labels={"titulos": "Títulos", "director": "", "tipo": "Tipo"}),
                    width="stretch")
    resumen = (det.sort_values("titulos", ascending=False)
                  .groupby("director")
                  .apply(lambda x: ", ".join(f"{g} ({n})" for g, n in zip(x.genero.head(3), x.titulos.head(3))),
                         include_groups=False)
                  .rename("géneros principales (títulos)"))
    tabla = top.set_index("director")[["titulos"]].join(resumen)
    st.dataframe(tabla, width="stretch")
    st.caption("Se excluyen los 2.634 títulos sin director informado.")

# ---------------------------------------------------------------------
# 6) Volumen vs diversidad de géneros
# ---------------------------------------------------------------------
with tabs[5]:
    st.subheader("¿Los países que más producen también tienen mayor diversidad de géneros?")
    minimo = st.slider("Mínimo de títulos por país", 1, 100, 20, key="min6")
    dist = num(q(f"""
        SELECT p.nombre_pais AS pais, g.nombre_genero AS genero, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY p.nombre_pais, g.nombre_genero""", PARAMS), "titulos")
    tit = num(q(f"""
        SELECT p.nombre_pais AS pais, COUNT(DISTINCT h.show_id) AS titulos,
               COUNT(DISTINCT h.id_genero) AS generos_distintos
        {BASE} {FILTRO} AND h.id_pais > 1
        GROUP BY p.nombre_pais""", PARAMS), "titulos", "generos_distintos")

    # Índice de Shannon normalizado (0 = un solo género, 1 = reparto parejo)
    def shannon(x):
        p_ = x / x.sum()
        return float(-(p_ * np.log(p_)).sum() / np.log(len(x))) if len(x) > 1 else 0.0
    sh = dist.groupby("pais").titulos.apply(shannon).rename("indice_shannon")
    paises = tit.set_index("pais").join(sh).reset_index()
    paises = paises[paises.titulos >= minimo]
    rho_g = paises.titulos.rank().corr(paises.generos_distintos.rank())
    rho_s = paises.titulos.rank().corr(paises.indice_shannon.rank())
    m1, m2, m3 = st.columns(3)
    m1.metric("Países analizados", len(paises))
    m2.metric("Spearman: títulos vs géneros distintos", f"{rho_g:.2f}")
    m3.metric("Spearman: títulos vs índice de Shannon", f"{rho_s:.2f}")
    top_lbl = set(paises.nlargest(8, "titulos").pais)
    paises["etiqueta"] = paises.pais.where(paises.pais.isin(top_lbl), "")
    st.plotly_chart(px.scatter(paises, x="titulos", y="generos_distintos", hover_name="pais", text="etiqueta",
                               color="indice_shannon", log_x=True, color_continuous_scale="Viridis",
                               labels={"titulos": "Títulos (escala log)", "generos_distintos": "Géneros distintos",
                                       "indice_shannon": "Shannon"})
                    .update_traces(textposition="top center", marker_size=10),
                    width="stretch")
    st.dataframe(paises.drop(columns="etiqueta").sort_values("titulos", ascending=False).round(3), width="stretch", hide_index=True)
    st.caption("Géneros distintos mide amplitud; el índice de Shannon normalizado mide qué tan parejo se reparten los títulos entre géneros.")

# ---------------------------------------------------------------------
# 7) Perfil del contenido más reciente
# ---------------------------------------------------------------------
with tabs[6]:
    st.subheader("¿Qué combinación de tipo, género, clasificación y país caracteriza lo más reciente?")
    desde = st.slider("Incorporados desde el año", anio_min, anio_max, max(anio_min, anio_max - 2), key="rec")
    st.caption("Esta pestaña usa su propio corte de fecha (ignora el rango de la barra lateral).")
    p7 = (*tipos, desde, anio_max)
    total7 = q(f"SELECT COUNT(DISTINCT h.show_id) AS n {BASE} {FILTRO_7}", p7).n.iloc[0]
    comb7 = num(q(f"""
        SELECT tc.tipo_contenido AS tipo, g.nombre_genero AS genero, c.codigo_rating AS clasificacion,
               p.nombre_pais AS pais, COUNT(DISTINCT h.show_id) AS titulos
        {BASE} {FILTRO_7} AND h.id_pais > 1
        GROUP BY tc.tipo_contenido, g.nombre_genero, c.codigo_rating, p.nombre_pais
        ORDER BY titulos DESC LIMIT 15""", p7), "titulos")
    comb7["% de lo reciente"] = (comb7.titulos / float(total7) * 100).round(2)
    st.markdown(f"**Top 15 combinaciones entre {int(total7):,} títulos incorporados desde {desde}**".replace(",", "."))
    st.dataframe(comb7, width="stretch", hide_index=True)
    comb7["combinación"] = comb7.tipo + " · " + comb7.genero + " · " + comb7.clasificacion + " · " + comb7.pais
    st.plotly_chart(px.bar(comb7, x="titulos", y="combinación", orientation="h",
                           category_orders={"combinación": list(comb7["combinación"])},
                           labels={"titulos": "Títulos", "combinación": ""}),
                    width="stretch")
