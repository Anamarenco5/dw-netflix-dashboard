"""
Dashboard del DW Netflix - Paso 5
Garciarena, Lupica, Marenco y Mas (A2)

Cada pregunta tiene UNA consulta SQL (diccionario CONSULTAS).
El resultado de la consulta se carga en una tabla de pandas y
con esa tabla se arma el grafico.

Importante: la tabla de hechos tiene una fila por titulo x pais x
genero x director, asi que para contar titulos usamos
COUNT(DISTINCT show_id) y no COUNT(*).
"""
import os

import pandas as pd
import plotly.express as px
import pymysql
import streamlit as st

st.set_page_config(page_title="DW Netflix", layout="wide")

# Las 7 consultas, una por pregunta
CONSULTAS = {
    1: """
SELECT p.nombre_pais     AS pais,
       ti.anio           AS anio_incorporacion,
       t.tipo_contenido  AS tipo,
       COUNT(DISTINCT h.show_id) AS titulos
FROM hechos_catalogo h
JOIN dim_pais p           ON h.id_pais = p.id_pais
JOIN dim_tiempo ti        ON h.id_tiempo_incorporacion = ti.id_tiempo
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
WHERE p.nombre_pais <> 'Sin dato'
  AND ti.anio IS NOT NULL
GROUP BY p.nombre_pais, ti.anio, t.tipo_contenido
ORDER BY titulos DESC;
""",
    2: """
SELECT DISTINCT h.show_id,
       tl.anio            AS anio_lanzamiento,
       t.tipo_contenido   AS tipo,
       h.anios_hasta_incorporacion AS anios
FROM hechos_catalogo h
JOIN dim_tiempo tl        ON h.id_tiempo_lanzamiento = tl.id_tiempo
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
WHERE h.anios_hasta_incorporacion IS NOT NULL;
""",
    3: """
SELECT p.nombre_pais     AS pais,
       g.nombre_genero   AS genero,
       t.tipo_contenido  AS tipo,
       COUNT(DISTINCT h.show_id) AS titulos,
       ROUND(COUNT(DISTINCT h.show_id) * 100 /
             (SELECT COUNT(DISTINCT show_id) FROM hechos_catalogo), 2) AS porcentaje
FROM hechos_catalogo h
JOIN dim_pais p           ON h.id_pais = p.id_pais
JOIN dim_genero g         ON h.id_genero = g.id_genero
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
WHERE p.nombre_pais <> 'Sin dato'
GROUP BY p.nombre_pais, g.nombre_genero, t.tipo_contenido
ORDER BY titulos DESC;
""",
    4: """
SELECT DISTINCT h.show_id,
       CASE WHEN tl.anio < 2010 THEN 'Antiguo' ELSE 'Reciente' END AS grupo,
       t.tipo_contenido   AS tipo,
       g.nombre_genero    AS genero,
       c.codigo_rating    AS clasificacion,
       p.nombre_pais      AS pais,
       h.duracion_num     AS duracion
FROM hechos_catalogo h
JOIN dim_tiempo tl        ON h.id_tiempo_lanzamiento = tl.id_tiempo
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
JOIN dim_genero g         ON h.id_genero = g.id_genero
JOIN dim_clasificacion c  ON h.id_clasificacion = c.id_clasificacion
JOIN dim_pais p           ON h.id_pais = p.id_pais;
""",
    5: """
SELECT d.nombre_director  AS director,
       t.tipo_contenido   AS tipo,
       g.nombre_genero    AS genero,
       h.show_id
FROM hechos_catalogo h
JOIN dim_director d       ON h.id_director = d.id_director
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
JOIN dim_genero g         ON h.id_genero = g.id_genero
WHERE d.nombre_director <> 'Sin dato';
""",
    6: """
SELECT p.nombre_pais  AS pais,
       COUNT(DISTINCT h.show_id)   AS titulos,
       COUNT(DISTINCT h.id_genero) AS generos_distintos
FROM hechos_catalogo h
JOIN dim_pais p ON h.id_pais = p.id_pais
WHERE p.nombre_pais <> 'Sin dato'
GROUP BY p.nombre_pais
HAVING COUNT(DISTINCT h.show_id) >= 20
ORDER BY titulos DESC;
""",
    7: """
SELECT t.tipo_contenido  AS tipo,
       g.nombre_genero   AS genero,
       c.codigo_rating   AS clasificacion,
       p.nombre_pais     AS pais,
       COUNT(DISTINCT h.show_id) AS titulos
FROM hechos_catalogo h
JOIN dim_tipo_contenido t ON h.id_tipo = t.id_tipo
JOIN dim_genero g         ON h.id_genero = g.id_genero
JOIN dim_clasificacion c  ON h.id_clasificacion = c.id_clasificacion
JOIN dim_pais p           ON h.id_pais = p.id_pais
JOIN dim_tiempo ti        ON h.id_tiempo_incorporacion = ti.id_tiempo
WHERE ti.anio >= 2019
  AND p.nombre_pais <> 'Sin dato'
GROUP BY t.tipo_contenido, g.nombre_genero, c.codigo_rating, p.nombre_pais
ORDER BY titulos DESC
LIMIT 15;
""",
}


# Conexion a la base (los datos estan en las variables de entorno de Render)
@st.cache_data(ttl=3600)
def consultar(numero):
    conexion = pymysql.connect(
        host=os.getenv("MYSQL_ADDON_HOST", "localhost"),
        port=int(os.getenv("MYSQL_ADDON_PORT", "3306")),
        user=os.getenv("MYSQL_ADDON_USER", "root"),
        password=os.getenv("MYSQL_ADDON_PASSWORD", ""),
        database=os.getenv("MYSQL_ADDON_DB", "dw_netflix"),
        charset="utf8mb4",
    )
    tabla = pd.read_sql(CONSULTAS[numero], conexion)
    conexion.close()
    return tabla


COLORES = {"Movie": "#E50914", "TV Show": "#3D3D3D",
           "Antiguo": "#9E9E9E", "Reciente": "#E50914"}

st.title("Catálogo de Netflix — Data Warehouse")
st.caption("Garciarena, Lupica, Marenco y Mas (A2)")

pestanas = st.tabs(["Pregunta 1", "Pregunta 2", "Pregunta 3", "Pregunta 4",
                    "Pregunta 5", "Pregunta 6", "Pregunta 7"])

# ---------------------------------------------------------------------
with pestanas[0]:
    st.subheader("¿Qué países tienen mayor presencia en el catálogo según el rango de fecha?")
    datos = consultar(1)
    desde, hasta = st.slider("Años de incorporación", 2008, 2021, (2008, 2021))
    datos = datos[(datos.anio_incorporacion >= desde) & (datos.anio_incorporacion <= hasta)]

    por_pais = datos.groupby(["pais", "tipo"], as_index=False).titulos.sum()
    top10 = datos.groupby("pais").titulos.sum().nlargest(10).index
    fig = px.bar(por_pais[por_pais.pais.isin(top10)], x="titulos", y="pais", color="tipo",
                 orientation="h", color_discrete_map=COLORES,
                 category_orders={"pais": list(top10)},
                 title=f"Top 10 países ({desde}-{hasta})")
    st.plotly_chart(fig)

    por_anio = datos[datos.pais.isin(top10[:5])].groupby(["anio_incorporacion", "pais"], as_index=False).titulos.sum()
    st.plotly_chart(px.line(por_anio, x="anio_incorporacion", y="titulos", color="pais",
                            markers=True, title="Evolución por año (top 5)"))

# ---------------------------------------------------------------------
with pestanas[1]:
    st.subheader("¿Existe relación entre el año de lanzamiento y el tiempo que tardó en incorporarse?")
    datos = consultar(2)
    c1, c2, c3 = st.columns(3)
    c1.metric("Promedio general (años)", round(datos.anios.mean(), 2))
    c2.metric("Promedio películas", round(datos[datos.tipo == "Movie"].anios.mean(), 2))
    c3.metric("Promedio series", round(datos[datos.tipo == "TV Show"].anios.mean(), 2))

    promedio = datos.groupby(["anio_lanzamiento", "tipo"], as_index=False).anios.mean()
    fig = px.line(promedio[promedio.anio_lanzamiento >= 1990], x="anio_lanzamiento", y="anios",
                  color="tipo", markers=True, color_discrete_map=COLORES,
                  labels={"anios": "Años promedio hasta incorporarse",
                          "anio_lanzamiento": "Año de lanzamiento"},
                  title="Años promedio hasta llegar a Netflix (lanzamientos desde 1990)")
    st.plotly_chart(fig)
    correlacion = datos.anio_lanzamiento.corr(datos.anios)
    st.write(f"Correlación entre año de lanzamiento y años hasta incorporarse: **{correlacion:.2f}**")

# ---------------------------------------------------------------------
with pestanas[2]:
    st.subheader("¿Cómo se relacionan el país de producción, el género y el tipo de contenido?")
    datos = consultar(3)
    st.write("Las 20 combinaciones más frecuentes")
    st.dataframe(datos.head(20), hide_index=True)

    paises = datos.groupby("pais").titulos.sum().nlargest(10).index
    generos = datos.groupby("genero").titulos.sum().nlargest(10).index
    mapa = datos[datos.pais.isin(paises) & datos.genero.isin(generos)]
    mapa = mapa.pivot_table(index="pais", columns="genero", values="titulos", aggfunc="sum", fill_value=0)
    st.plotly_chart(px.imshow(mapa, text_auto=True, aspect="auto", color_continuous_scale="Reds",
                              title="Títulos por país y género"))

# ---------------------------------------------------------------------
with pestanas[3]:
    st.subheader("¿Qué distingue al contenido antiguo (antes de 2010) del reciente?")
    datos = consultar(4)

    # Duracion promedio: una fila por titulo
    titulos = datos.drop_duplicates("show_id")
    duracion = titulos.groupby(["grupo", "tipo"], as_index=False).duracion.mean().round(1)
    st.write("Duración promedio (películas en minutos, series en temporadas)")
    st.dataframe(duracion, hide_index=True)

    total_grupo = titulos.groupby("grupo").show_id.count()
    for columna in ["genero", "clasificacion", "pais"]:
        tabla = datos.groupby(["grupo", columna], as_index=False).show_id.nunique()
        tabla["porcentaje"] = tabla.show_id / tabla.grupo.map(total_grupo) * 100
        if columna == "pais":
            tabla = tabla[tabla.pais != "Sin dato"]
        top = tabla.groupby(columna).porcentaje.max().nlargest(8).index
        st.plotly_chart(px.bar(tabla[tabla[columna].isin(top)], x=columna, y="porcentaje",
                               color="grupo", barmode="group", color_discrete_map=COLORES,
                               title=f"% de títulos de cada grupo por {columna}"))

# ---------------------------------------------------------------------
with pestanas[4]:
    st.subheader("¿Qué directores aparecen más y en qué géneros y tipos participan?")
    datos = consultar(5)
    top = datos.groupby("director").show_id.nunique().nlargest(10).index
    datos = datos[datos.director.isin(top)]

    por_tipo = datos.groupby(["director", "tipo"], as_index=False).show_id.nunique()
    st.plotly_chart(px.bar(por_tipo, x="show_id", y="director", color="tipo", orientation="h",
                           color_discrete_map=COLORES, category_orders={"director": list(top)},
                           labels={"show_id": "Títulos"}, title="Top 10 directores"))

    por_genero = datos.groupby(["director", "genero"], as_index=False).show_id.nunique()
    st.plotly_chart(px.bar(por_genero, x="show_id", y="director", color="genero", orientation="h",
                           category_orders={"director": list(top)},
                           labels={"show_id": "Títulos"}, title="Géneros de cada director"))
    st.caption("Un título puede tener varios géneros, por eso esta barra puede ser más larga que la de arriba.")

# ---------------------------------------------------------------------
with pestanas[5]:
    st.subheader("¿Los países que más producen tienen mayor diversidad de géneros?")
    datos = consultar(6)
    st.plotly_chart(px.scatter(datos, x="titulos", y="generos_distintos", hover_name="pais",
                               log_x=True, title="Títulos vs géneros distintos (países con 20 títulos o más)"))
    correlacion = datos.titulos.corr(datos.generos_distintos, method="spearman")
    st.write(f"Correlación entre cantidad de títulos y géneros distintos: **{correlacion:.2f}**")
    st.dataframe(datos, hide_index=True)

# ---------------------------------------------------------------------
with pestanas[6]:
    st.subheader("¿Qué combinación caracteriza a lo incorporado desde 2019?")
    datos = consultar(7)
    datos["combinacion"] = datos.tipo + " · " + datos.genero + " · " + datos.clasificacion + " · " + datos.pais
    st.plotly_chart(px.bar(datos, x="titulos", y="combinacion", orientation="h",
                           category_orders={"combinacion": list(datos.combinacion)},
                           title="Las 15 combinaciones más frecuentes"))
    st.dataframe(datos.drop(columns="combinacion"), hide_index=True)
