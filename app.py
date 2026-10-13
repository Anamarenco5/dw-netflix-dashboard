"""
Dashboard del DW Netflix - Paso 5
Garciarena, Lupica, Marenco y Mas (A2)

Cada pregunta (1, 2, 4, 5 y 6) tiene UNA consulta SQL (diccionario CONSULTAS).
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

# Las 5 consultas, una por pregunta (las preguntas 3 y 7 se eliminaron)
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

pestanas = st.tabs(["Pregunta 1", "Pregunta 2", "Pregunta 4", "Pregunta 5", "Pregunta 6"])

# ---------------------------------------------------------------------
with pestanas[0]:
    st.subheader("¿Qué países tienen una mayor presencia en el catálogo de Netflix según el rango de fecha?")
    datos = consultar(1)
    desde, hasta = st.slider("Años de incorporación", 2008, 2021, (2015, 2021))
    datos = datos[(datos.anio_incorporacion >= desde) & (datos.anio_incorporacion <= hasta)]

    top5 = datos.groupby("pais").titulos.sum().nlargest(5).index
    por_anio = datos[datos.pais.isin(top5)].groupby(["anio_incorporacion", "pais"], as_index=False).titulos.sum()
    st.plotly_chart(px.line(por_anio, x="anio_incorporacion", y="titulos", color="pais", markers=True,
                            category_orders={"pais": list(top5)},
                            labels={"anio_incorporacion": "Año de incorporación", "titulos": "Títulos"},
                            title=f"Títulos incorporados por año – Top 5 países ({desde}-{hasta})"))

    tabla = por_anio.pivot(index="pais", columns="anio_incorporacion", values="titulos").fillna(0).astype(int)
    tabla["Total"] = tabla.sum(axis=1)
    tabla = tabla.sort_values("Total", ascending=False)
    tabla.columns = [str(c) for c in tabla.columns]
    st.dataframe(tabla)

    st.info("Estados Unidos es el país con más títulos incorporados en 2015–2021 (3633), seguido por India (1046) "
            "y Reino Unido (800). El pico de Estados Unidos fue en 2019 con 856 títulos. Se observa un gran dominio "
            "por parte del país en cuanto al control y presencia en el catálogo de la plataforma (triplica la "
            "cantidad de producciones que su principal competencia).")

# ---------------------------------------------------------------------
with pestanas[1]:
    st.subheader("¿Existe una relación entre el año de lanzamiento de un contenido y el tiempo que tardó en "
                 "incorporarse al catálogo de Netflix?")
    datos = consultar(2)
    rangos = ["0 (mismo año)", "1 año", "2 a 5 años", "6 a 10 años", "11 a 20 años", "Más de 20 años"]
    datos["rango"] = pd.cut(datos.anios, bins=[-100, 0, 1, 5, 10, 20, 1000], labels=rangos)

    por_rango = datos.groupby(["rango", "tipo"], observed=False).show_id.count().reset_index(name="titulos")
    st.plotly_chart(px.bar(por_rango, x="rango", y="titulos", color="tipo", barmode="group",
                           color_discrete_map=COLORES, category_orders={"rango": rangos},
                           labels={"rango": "Años hasta incorporarse", "titulos": "Títulos"},
                           title="Años entre lanzamiento e incorporación a Netflix"))

    tabla = por_rango.pivot(index="rango", columns="tipo", values="titulos").reindex(rangos)
    tabla["Total"] = tabla.sum(axis=1)
    st.dataframe(tabla)

    mismo_anio = (datos.anios <= 0).mean()
    hasta_un_anio = (datos.anios <= 1).mean()
    st.info(f"El {mismo_anio:.0%} de los títulos se incorporó el mismo año de su lanzamiento "
            f"({hasta_un_anio:.0%} si se suma el año siguiente). Como observamos en el gráfico, muchas de las "
            "producciones se incorporan el mismo año que se lanzaron, aunque también hay una gran parte que tardan "
            "hasta 5 años en incorporarse. Dentro de esto, podemos decir que las series se incorporan más rápido, "
            "mientras que las películas tienen una cola larga de títulos antiguos (si bien en el mismo año tienen "
            "un buen número de incorporaciones, en los otros rangos de fechas son muchas más películas que series).")

# ---------------------------------------------------------------------
with pestanas[2]:
    st.subheader("¿Qué características distinguen al contenido más antiguo del reciente en términos de "
                 "género y duración?")
    datos = consultar(4)

    # Tipo y duracion: una fila por titulo
    titulos = datos.drop_duplicates("show_id")
    tabla = titulos.groupby(["grupo", "tipo"], as_index=False).agg(titulos=("show_id", "count"),
                                                                   duracion_promedio=("duracion", "mean"))
    tabla["duracion_promedio"] = tabla.duracion_promedio.round(1)
    tabla["% dentro del grupo"] = (tabla.titulos / tabla.groupby("grupo").titulos.transform("sum") * 100).round(1)
    tabla["unidad duración"] = tabla.tipo.map({"Movie": "minutos", "TV Show": "temporadas"})
    st.dataframe(tabla, hide_index=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(tabla, x="grupo", y="% dentro del grupo", color="tipo", color_discrete_map=COLORES,
                           title="Composición por tipo (%)"))
    c2.plotly_chart(px.bar(tabla[tabla.tipo == "Movie"], x="grupo", y="duracion_promedio", text="duracion_promedio",
                           color="grupo", color_discrete_map=COLORES,
                           labels={"duracion_promedio": "Minutos"}, title="Duración promedio de películas (min)"))

    # Top 3 generos por grupo (grafico nuevo)
    generos = datos.groupby(["grupo", "genero"], as_index=False).show_id.nunique().rename(columns={"show_id": "titulos"})
    top3 = generos.sort_values("titulos", ascending=False).groupby("grupo").head(3)
    top3["tipo"] = top3.genero.map(lambda g: "TV Show" if "TV" in g else "Movie")
    fig = px.bar(top3, x="genero", y="titulos", color="tipo", facet_col="grupo", text="titulos",
                 color_discrete_map=COLORES, category_orders={"grupo": ["Antiguo", "Reciente"]},
                 labels={"genero": "", "titulos": "Cantidad de títulos"},
                 title="Top 3 géneros: contenido antiguo (< 2010) vs. reciente (≥ 2010)")
    fig.update_xaxes(matches=None, categoryorder="total descending")
    st.plotly_chart(fig)
    st.dataframe(top3[["grupo", "genero", "titulos"]], hide_index=True)

    st.info("El contenido antiguo es mayormente películas (86.4%), mientras que en el reciente las series aumentan "
            "su porcentaje, pero no lo superan ni igualan (33.4%). Las películas antiguas duran en promedio 113.3 min "
            "contra 96.4 min de las recientes. En el caso de las series, antes, en promedio, presentaban 2.3 "
            "temporadas, mientras que ahora presentan 1.7 en promedio (disminución en la producción). En cuanto al "
            "género, antiguamente el principal era Drama (484), mientras que en el reciente es Películas "
            "Internacionales (2303).")

# ---------------------------------------------------------------------
with pestanas[3]:
    st.subheader("¿Qué directores aparecen con mayor frecuencia en el catálogo y en qué tipos de contenido "
                 "participan principalmente?")
    datos = consultar(5)
    top = datos.groupby("director").show_id.nunique().nlargest(10).index
    datos = datos[datos.director.isin(top)]

    por_tipo = datos.groupby(["director", "tipo"], as_index=False).show_id.nunique()
    st.plotly_chart(px.bar(por_tipo, x="show_id", y="director", color="tipo", orientation="h",
                           color_discrete_map=COLORES, category_orders={"director": list(top)},
                           labels={"show_id": "Títulos"}, title="Top 10 directores por cantidad de títulos"))

    tabla = por_tipo.pivot(index="director", columns="tipo", values="show_id").fillna(0).astype(int)
    tabla = tabla.reindex(columns=["Movie", "TV Show"], fill_value=0).rename(columns={"Movie": "peliculas", "TV Show": "series"})
    tabla.insert(0, "titulos", tabla.sum(axis=1))
    st.dataframe(tabla.reindex(top))

    st.info("El director con más títulos es Rajiv Chilaka (22 títulos). De los 10 principales (excepto Marcus "
            "Raboy), todos dirigen únicamente películas, lo que muestra que la dirección se especializa "
            "frecuentemente en películas.")

# ---------------------------------------------------------------------
with pestanas[4]:
    st.subheader("¿Los países que producen mayor cantidad de contenido también presentan una mayor diversidad "
                 "de géneros?")
    datos = consultar(6)
    st.plotly_chart(px.scatter(datos, x="titulos", y="generos_distintos", hover_name="pais", log_x=True,
                               labels={"titulos": "Títulos (escala logarítmica)", "generos_distintos": "Géneros distintos"},
                               title="Diversidad de géneros vs. cantidad de títulos por país (≥ 20 títulos)"))
    st.dataframe(datos.sort_values(["generos_distintos", "titulos"], ascending=False).head(15), hide_index=True)

    st.info("Estados Unidos es el país con mayor diversidad (42 géneros distintos en 3690 títulos). La diversidad "
            "crece con el volumen de títulos, aunque hay países con catálogos chicos y muy variados. Podemos decir "
            "que los países dominantes en el catálogo presentan mucha variedad en género.")
