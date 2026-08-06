import streamlit as st
import pandas as pd
import gspread
import requests
import unicodedata
import re
import json
from datetime import datetime, date
from collections import defaultdict
from pathlib import Path
from google.oauth2.service_account import Credentials
from streamlit_echarts import st_echarts, Map, JsCode

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dashboard de Juicios | Estudio Jurídico",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# IDENTIDAD VISUAL — PALETA Y ESTILOS
# ============================================================
COLOR_PRIMARY = "#0B2545"      # azul noche — encabezados, sidebar
COLOR_ACCENT = "#C9A24B"       # dorado — acentos, KPIs destacados
COLOR_BG_CARD = "#FFFFFF"
COLOR_PROBABLE = "#1F8A70"     # verde profesional
COLOR_POSIBLE = "#D9A441"      # dorado suave
COLOR_REMOTO = "#B23A48"       # rojo vino

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"]  {{
        font-family: 'Inter', sans-serif;
    }}

    /* Ocultar branding por defecto de Streamlit (menú hamburguesa y "Made with Streamlit") */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* ---------- Header / branding ---------- */
    .firm-header {{
        background: linear-gradient(135deg, {COLOR_PRIMARY} 0%, #163a63 100%);
        padding: 2rem 2.2rem;
        border-radius: 14px;
        margin-bottom: 1.6rem;
        box-shadow: 0 8px 24px rgba(11, 37, 69, 0.18);
    }}
    .firm-header h1 {{
        font-family: 'Playfair Display', serif;
        color: #FFFFFF;
        font-size: 2.1rem;
        margin: 0;
        letter-spacing: 0.3px;
    }}
    .firm-header p {{
        color: {COLOR_ACCENT};
        font-size: 0.95rem;
        margin: 0.35rem 0 0 0;
        font-weight: 500;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }}

    /* ---------- KPI cards ---------- */
    .kpi-card {{
        background: {COLOR_BG_CARD};
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        border: 1px solid #EAECEF;
        box-shadow: 0 2px 10px rgba(16, 24, 40, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        height: 100%;
    }}
    .kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 22px rgba(16, 24, 40, 0.10);
    }}
    .kpi-label {{
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #667085;
        margin-bottom: 0.35rem;
    }}
    .kpi-value {{
        font-size: 1.55rem;
        font-weight: 700;
        color: {COLOR_PRIMARY};
    }}
    .kpi-accent {{ border-left: 4px solid {COLOR_ACCENT}; }}
    .kpi-probable {{ border-left: 4px solid {COLOR_PROBABLE}; }}
    .kpi-posible {{ border-left: 4px solid {COLOR_POSIBLE}; }}
    .kpi-remoto {{ border-left: 4px solid {COLOR_REMOTO}; }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background-color: #F7F8FA;
        border-right: 1px solid #E4E7EC;
    }}
    section[data-testid="stSidebar"] h1 {{
        font-family: 'Playfair Display', serif;
        color: {COLOR_PRIMARY};
    }}

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #F1F3F6;
        border-radius: 8px 8px 0 0;
        padding: 0.6rem 1.1rem;
        font-weight: 600;
        color: #475467;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_PRIMARY} !important;
        color: #FFFFFF !important;
    }}

    /* ---------- Section subtitle ---------- */
    .section-sub {{
        color: #667085;
        font-size: 0.92rem;
        margin-top: -0.6rem;
        margin-bottom: 1rem;
    }}

    .footer-note {{
        text-align: center;
        color: #98A2B3;
        font-size: 0.8rem;
        padding-top: 1.5rem;
    }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================
# TEMA DE MARCA PARA ECHARTS + FORMATEADORES (JS)
# ============================================================
# El tema dict replica la identidad del estudio. Se pasa con theme= a todos los
# gráficos. backgroundColor transparente para integrarse con el fondo de la app.
BRAND_THEME = {
    "color": [
        COLOR_PROBABLE, COLOR_POSIBLE, COLOR_REMOTO,
        COLOR_ACCENT, COLOR_PRIMARY, "#2E86AB", "#7A6F9B", "#4C9F70",
    ],
    "backgroundColor": "transparent",
    "textStyle": {"fontFamily": "'Inter', sans-serif", "color": "#475467"},
    "categoryAxis": {
        "axisLine": {"lineStyle": {"color": "#D0D5DD"}},
        "axisLabel": {"color": "#667085"},
        "splitLine": {"lineStyle": {"color": "#EAECEF"}},
    },
    "valueAxis": {
        "axisLine": {"lineStyle": {"color": "#D0D5DD"}},
        "axisLabel": {"color": "#667085"},
        "splitLine": {"lineStyle": {"color": "#EAECEF"}},
    },
    "legend": {"textStyle": {"color": "#475467"}},
    "tooltip": {
        "backgroundColor": "#FFFFFF",
        "borderColor": "#E4E7EC",
        "textStyle": {"color": "#0B2545"},
    },
}

# Formateo de montos estilo ARG ($1.234.567) dentro de ECharts (lado navegador).
_FMT_JS = "function(v){ if (typeof v !== 'number') return v; return '$' + v.toLocaleString('es-AR'); }"
VAL_FMT = JsCode(_FMT_JS)   # tooltip valueFormatter
AX_FMT = JsCode(_FMT_JS)    # axisLabel / labels

TT_PROVINCIA = JsCode(
    "function(p){"
    "  var nm = (p.data && p.data.display) ? p.data.display : (p.name || '');"
    "  var v = (typeof p.value === 'number') ? '$' + Math.round(p.value).toLocaleString('es-AR') : '';"
    "  return '<b>' + nm + '</b><br/>' + v;"
    "}"
)

TT_RIESGO = JsCode(
    "function(p){"
    "  var d = p.data || {};"
    "  var dias = (d.value && d.value[0] != null) ? Math.round(d.value[0]) : '';"
    "  var v = (d.value && d.value[1] != null) ? '$' + Math.round(d.value[1]).toLocaleString('es-AR') : '';"
    "  return '<b>' + (d.caratula || '') + '</b><br/>'"
    "    + 'Juicio: ' + (d.numero || '') + '<br/>'"
    "    + 'Estado: ' + (d.estado || '') + '<br/>'"
    "    + 'Días: ' + dias + '<br/>'"
    "    + 'Exposición: ' + v;"
    "}"
)

# Gradientes declarativos (sin JavaScript): azul noche -> dorado.
GRAD_H = {"type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
          "colorStops": [{"offset": 0, "color": COLOR_PRIMARY},
                         {"offset": 1, "color": COLOR_ACCENT}]}
GRAD_V = {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
          "colorStops": [{"offset": 0, "color": "#2E86AB"},
                         {"offset": 1, "color": COLOR_PRIMARY}]}

# Renderer por defecto (canvas = más rápido; svg = mejor para imprimir).
_RENDERER = "canvas"

# ============================================================
# CONEXIÓN A GOOGLE SHEETS
# ============================================================
SPREADSHEET_NAME = "Ejemplo Juicios"
SHEET_JUICIOS = "Hoja1"
SHEET_INTERES = "Interes"
SHEET_COSTAS = "Costas"
SHEET_HONORARIOS = "Honoriarios"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@st.cache_data(ttl=300)
def cargar_desde_sheets():
    creds_json = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open(SPREADSHEET_NAME)

    def leer_hoja(nombre):
        try:
            ws = spreadsheet.worksheet(nombre)
            data = ws.get_all_values()
            if not data:
                return pd.DataFrame()
            # Buscamos la fila que contiene "Numero Juicio" para usarla como header
            header_idx = 0
            for i, row in enumerate(data):
                if any("numero" in str(c).lower() and "juicio" in str(c).lower() for c in row):
                    header_idx = i
                    break
            return pd.DataFrame(data[header_idx + 1:], columns=data[header_idx])
        except Exception as e:
            st.warning(f"No se pudo leer la hoja '{nombre}': {e}")
            return pd.DataFrame()

    return (
        leer_hoja(SHEET_JUICIOS),
        leer_hoja(SHEET_INTERES),
        leer_hoja(SHEET_COSTAS),
        leer_hoja(SHEET_HONORARIOS),
    )


@st.cache_data(ttl=300)
def procesar_datos_base(juicios_raw, interes_raw, costas_raw, honorarios_raw):
    """Limpieza y normalización de los datos que NO dependen de la fecha de corte.
    Separado de calcular_totales() para que cambiar la fecha de corte en el
    sidebar recalcule intereses/costas/honorarios sin tener que releer Sheets."""
    df = juicios_raw.copy()

    # 1. RECREAR LÓGICA DE ENCABEZADOS ÚNICOS
    raw_headers = df.columns.tolist()
    unique_headers = []
    header_counts = defaultdict(int)

    for header in raw_headers:
        original_header = str(header).strip()
        if original_header == "":
            original_header = "Unnamed_Column"

        if header_counts[original_header] == 0:
            unique_headers.append(original_header)
        else:
            unique_headers.append(f"{original_header}_{header_counts[original_header]}")
        header_counts[original_header] += 1

    df.columns = unique_headers

    # 2. RENOMBRAR COLUMNAS ESPECÍFICAS
    df = df.rename(
        columns={
            "Probable": "Demanda_Probable",
            "Posible": "Demanda_Posible",
            "Remoto": "Demanda_Remoto",
            "Probable_1": "Intereses_Probable",
            "Posible_1": "Intereses_Posible",
            "Remoto_1": "Intereses_Remoto",
            "Probable_2": "Costas_Probable",
            "Posible_2": "Costas_Posible",
            "Remoto_2": "Costas_Remoto",
            "Probable_3": "Honorarios_Probable",
            "Posible_3": "Honorarios_Posible",
            "Remoto_3": "Honorarios_Remoto",
            "Probable_4": "Totales_Probable",
            "Posible_4": "Totales_Posible",
            "Remoto_4": "Totales_Remoto",
        }
    )

    # 3. FILTRAR FILAS BASURA
    if "Numero Juicio" in df.columns:
        df = df[df["Numero Juicio"].astype(str).str.match(r"^\d+$", na=False)].copy()
        df["Numero Juicio"] = df["Numero Juicio"].astype(int)

    # 4. LIMPIAR Y CONVERTIR A NUMÉRICO LAS COLUMNAS DE MONTO
    def _es_columna_monetaria(nombre):
        if re.match(r"^Demanda($|_|\s)", nombre):
            return True
        return any(nombre.startswith(p) for p in ["Intereses", "Costas", "Honorarios", "Totales"])

    cols_monto = [c for c in df.columns if _es_columna_monetaria(c)]
    for col in cols_monto:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "").str.replace(" ", ""), errors="coerce"
        ).fillna(0.0)

    # 4b. Columnas de texto (rol de la parte, juzgado) — quedan como string limpio.
    for col in ["Demandante/Demandado", "Juzgado"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 5. FECHA DEL HECHO
    df["Fecha Hecho"] = pd.to_datetime(df["Fecha Hecho"], dayfirst=True, errors="coerce")

    # 6. MAPEAR TASAS POR JURISDICCIÓN
    def get_tasa_map(df_tasas):
        if df_tasas.empty:
            return {}
        try:
            col_jur = df_tasas.columns[0]
            col_pct = df_tasas.columns[1]
            return dict(
                zip(
                    df_tasas[col_jur].astype(str).str.strip(),
                    pd.to_numeric(df_tasas[col_pct].astype(str).str.replace("%", "").str.strip(), errors="coerce").fillna(0)
                    / 100.0,
                )
            )
        except Exception:
            return {}

    mapa_interes = get_tasa_map(interes_raw)
    mapa_costas = get_tasa_map(costas_raw)
    mapa_honorarios = get_tasa_map(honorarios_raw)

    df["Jurisdiccion"] = df["Jurisdiccion"].astype(str).str.strip()
    df["Tasa_interes"] = df["Jurisdiccion"].map(mapa_interes).fillna(0)
    df["Pct_Costas"] = df["Jurisdiccion"].map(mapa_costas).fillna(0)
    df["Pct_Honorarios"] = df["Jurisdiccion"].map(mapa_honorarios).fillna(0)

    for escenario in ["Probable", "Posible", "Remoto"]:
        col_dem = f"Demanda_{escenario}"
        if col_dem not in df.columns:
            df[col_dem] = 0.0

    return df


def calcular_totales(df_base, fecha_corte):
    """Recalcula días transcurridos, intereses, costas, honorarios y totales
    en función de la fecha de corte elegida en el sidebar."""
    df = df_base.copy()

    fecha_corte_ts = pd.Timestamp(fecha_corte)
    df["Dias_Transcurridos"] = (fecha_corte_ts - df["Fecha Hecho"]).dt.days.clip(lower=0)

    for escenario in ["Probable", "Posible", "Remoto"]:
        col_dem = f"Demanda_{escenario}"
        df[f"Intereses_{escenario}"] = (df["Dias_Transcurridos"] / 365.0) * df["Tasa_interes"] * df[col_dem]
        df[f"Costas_{escenario}"] = df["Pct_Costas"] * df[col_dem]
        df[f"Honorarios_{escenario}"] = df["Pct_Honorarios"] * df[col_dem]
        df[f"Totales_{escenario}"] = (
            df[col_dem] + df[f"Intereses_{escenario}"] + df[f"Costas_{escenario}"] + df[f"Honorarios_{escenario}"]
        )

    df["Totales_General"] = df["Totales_Probable"] + df["Totales_Posible"] + df["Totales_Remoto"]
    return df


# ============================================================
# HELPERS DE FORMATO
# ============================================================
def fmt_money(x, symbol="$"):
    """Formatea números al estilo es-AR: $1.234.567"""
    try:
        return f"{symbol}{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{symbol}0"


def kpi_card(label, value, css_class="kpi-accent"):
    st.markdown(
        f"""
        <div class="kpi-card {css_class}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MAPA POR PROVINCIA — NORMALIZACIÓN Y GEOJSON
# ============================================================
def normalizar_texto(s):
    """Mayúsculas y sin acentos, para poder comparar 'Córdoba' con 'CORDOBA'."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


# Alias para valores de "Jurisdiccion" que no coinciden textualmente con el
# nombre oficial de la provincia. Sumá acá las variantes que uses en la planilla.
ALIAS_PROVINCIAS = {
    "CABA": "Ciudad Autónoma de Buenos Aires",
    "CAPITAL FEDERAL": "Ciudad Autónoma de Buenos Aires",
    "CIUDAD DE BUENOS AIRES": "Ciudad Autónoma de Buenos Aires",
    "CAPITAL": "Ciudad Autónoma de Buenos Aires",
    "BS AS": "Buenos Aires",
    "BSAS": "Buenos Aires",
    "BS. AS.": "Buenos Aires",
    "PCIA DE BUENOS AIRES": "Buenos Aires",
    "PCIA BUENOS AIRES": "Buenos Aires",
    "PROVINCIA DE BUENOS AIRES": "Buenos Aires",
    "GBA": "Buenos Aires",
    "STA FE": "Santa Fe",
    "STGO DEL ESTERO": "Santiago del Estero",
    "TDF": "Tierra del Fuego",
}
ALIAS_PROVINCIAS_NORM = {normalizar_texto(k): normalizar_texto(v) for k, v in ALIAS_PROVINCIAS.items()}


def jurisdiccion_a_provincia(valor):
    clave = normalizar_texto(valor)
    return ALIAS_PROVINCIAS_NORM.get(clave, clave)


@st.cache_data(ttl=60 * 60 * 24)
def cargar_geojson_provincias():
    """Carga los límites provinciales: primero el archivo local
    argentina-provincias.geojson (GADM) y, si no existe, descarga desde la API
    oficial GeoRef (apis.datos.gob.ar). Normaliza e inyecta el campo `name`
    (necesario para que ECharts registre el mapa)."""
    local = Path(__file__).parent / "argentina-provincias.geojson"
    if local.exists():
        raw = local.read_bytes()
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            data = json.loads(raw.decode("latin-1"))
    else:
        url = "https://apis.datos.gob.ar/georef/api/provincias.geojson"
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()

    props_ejemplo = data["features"][0]["properties"]
    campo_nombre = next(
        (k for k in props_ejemplo if k in ("NAME_1", "name") or "nombre" in k.lower()),
        "name",
    )

    # El geojson GADM llama "Ciudad de Buenos Aires" a CABA; unificamos para que
    # coincida con la nomenclatura canónica del estudio (Ciudad Autónoma de Bs. As.).
    renombrar_gadm = {"CIUDAD DE BUENOS AIRES": "Ciudad Autónoma de Buenos Aires"}

    for feat in data["features"]:
        nombre_original = feat["properties"].get(campo_nombre, "")
        if campo_nombre == "NAME_1":
            nombre_original = renombrar_gadm.get(normalizar_texto(nombre_original), nombre_original)
        feat["properties"]["_nombre_display"] = nombre_original
        feat["properties"]["_nombre_norm"] = normalizar_texto(nombre_original)
        feat["properties"]["name"] = feat["properties"]["_nombre_norm"]

    return data


# ============================================================
# CROSS-FILTERING POR CLIC (on_select) — ESTADO Y HELPERS
# ============================================================
ESC_COL_A_ETIQUETA = {
    "Totales_Probable": "Probable",
    "Totales_Posible": "Posible",
    "Totales_Remoto": "Remoto",
}


def _nombres_seleccion(res):
    """Extrae los 'name' de los puntos seleccionados del resultado de st_echarts."""
    if res is None:
        return []
    sel = res.get("selection") if isinstance(res, dict) else getattr(res, "selection", None)
    if not isinstance(sel, dict):
        return []
    pts = sel.get("points") or []
    return [p.get("name") for p in pts if isinstance(p, dict) and p.get("name") is not None]


def _capturar_seleccion(clave_destino, key_chart):
    """Callback de on_select: guarda en session_state los items seleccionados
    del gráfico key_chart. Se ejecuta antes del cuerpo del script, así el
    dashboard se filtra sin quedar desactualizado."""
    st.session_state[clave_destino] = _nombres_seleccion(st.session_state.get(key_chart))


def _aplicar_selecciones_chart(df):
    """Aplica al DataFrame (ya filtrado por sidebar) las selecciones hechas por
    clic en los gráficos: jurisdicción, provincia y escenario dominante."""
    df2 = df.copy()

    s_jur = st.session_state.get("chart_sel_jurisdiccion") or []
    if s_jur:
        df2 = df2[df2["Jurisdiccion"].isin(s_jur)]

    s_prov = st.session_state.get("chart_sel_provincia") or []
    if s_prov:
        df2 = df2[df2["Jurisdiccion"].apply(jurisdiccion_a_provincia).isin(s_prov)]

    s_esc = st.session_state.get("chart_sel_escenario") or []
    if s_esc:
        esc_cols = list(ESC_COL_A_ETIQUETA.keys())
        dominante = df2[esc_cols].idxmax(axis=1).map(ESC_COL_A_ETIQUETA)
        df2 = df2[dominante.isin(s_esc)]

    return df2


# ============================================================
# CONSTRUCTORES DE OPCIONES ECHARTS
# ============================================================
def _opts_dona(df):
    data = [
        {"name": "Probable", "value": round(float(df["Totales_Probable"].sum()), 2)},
        {"name": "Posible", "value": round(float(df["Totales_Posible"].sum()), 2)},
        {"name": "Remoto", "value": round(float(df["Totales_Remoto"].sum()), 2)},
    ]
    return {
        "tooltip": {"trigger": "item", "valueFormatter": VAL_FMT},
        "legend": {"bottom": 0, "icon": "circle", "textStyle": {"color": "#475467"}},
        "series": [
            {
                "type": "pie",
                "radius": ["52%", "74%"],
                "center": ["50%", "45%"],
                "selectedMode": "single",
                "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2},
                "label": {"show": True, "formatter": "{b}\n{d}%", "color": "#475467"},
                "labelLine": {"length": 12, "length2": 8},
                "emphasis": {"scale": True, "scaleSize": 6},
                "data": data,
            }
        ],
    }


def _opts_jur(df, cats):
    tmp = df.groupby("Jurisdiccion")["Totales_General"].sum()
    data = [round(float(tmp.get(c, 0.0)), 2) for c in cats]
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "valueFormatter": VAL_FMT},
        "grid": {"left": 4, "right": 30, "top": 6, "bottom": 4, "containLabel": True},
        "xAxis": {"type": "value", "axisLabel": {"formatter": AX_FMT}},
        "yAxis": {"type": "category", "inverse": True, "data": cats},
        "series": [
            {
                "type": "bar",
                "data": data,
                "barWidth": 14,
                "itemStyle": {"color": GRAD_H, "borderRadius": [0, 4, 4, 0]},
                "label": {"show": True, "position": "right", "formatter": AX_FMT, "color": "#667085"},
            }
        ],
    }


def _opts_anio(df):
    df_a = df.dropna(subset=["Fecha Hecho"])
    if df_a.empty:
        return None
    por = df_a.groupby(df_a["Fecha Hecho"].dt.year)["Totales_General"].agg(["count", "sum"])
    anios = [int(a) for a in por.index.tolist()]
    counts = [int(c) for c in por["count"].tolist()]
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 4, "right": 12, "top": 24, "bottom": 4, "containLabel": True},
        "xAxis": {"type": "category", "data": [str(a) for a in anios]},
        "yAxis": {"type": "value"},
        "series": [
            {
                "type": "bar",
                "data": counts,
                "barWidth": "55%",
                "itemStyle": {"color": GRAD_V, "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top"},
            }
        ],
    }


def _opts_riesgo(df):
    cols = ["Dias_Transcurridos", "Totales_General", "Caratula", "Numero Juicio", "Estado", "Jurisdiccion"]
    sub = df[cols].dropna(subset=cols[:2])
    if sub.empty:
        return None
    data = [
        {
            "value": [float(dias), float(total)],
            "caratula": caratula,
            "numero": numero,
            "estado": estado,
            "jur": jur,
        }
        for dias, total, caratula, numero, estado, jur in sub.itertuples(index=False, name=None)
    ]
    vals = [d["value"][1] for d in data]
    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        vmax = vmin + 1
    return {
        "tooltip": {"trigger": "item", "formatter": TT_RIESGO},
        "grid": {"left": 4, "right": 40, "top": 24, "bottom": 4, "containLabel": True},
        "xAxis": {"type": "value", "name": "Días transcurridos", "nameTextStyle": {"color": "#667085"}},
        "yAxis": {
            "type": "value",
            "name": "Exposición total",
            "axisLabel": {"formatter": AX_FMT},
            "nameTextStyle": {"color": "#667085"},
        },
        "visualMap": {
            "dimension": 1,
            "min": vmin,
            "max": vmax,
            "right": 0,
            "bottom": 0,
            "calculable": True,
            "textStyle": {"color": "#667085"},
            "inRange": {"color": ["#EFF3F8", "#C9A24B", "#0B2545"]},
        },
        "series": [
            {
                "type": "scatter",
                "data": data,
                "symbolSize": JsCode("function(val){ return Math.max(6, Math.min(24, Math.sqrt(val[1]) / 12)); }"),
                "itemStyle": {"borderColor": "rgba(255,255,255,0.6)", "borderWidth": 1},
            }
        ],
    }


def _opts_estado(df):
    por = df.groupby("Estado")["Totales_General"].sum().sort_values(ascending=False)
    estados = [str(e) for e in por.index.tolist()]
    data = [round(float(v), 2) for v in por.values.tolist()]
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "valueFormatter": VAL_FMT},
        "grid": {"left": 4, "right": 24, "top": 20, "bottom": 4, "containLabel": True},
        "xAxis": {"type": "category", "data": estados},
        "yAxis": {"type": "value", "axisLabel": {"formatter": AX_FMT}},
        "series": [
            {
                "type": "bar",
                "data": data,
                "barWidth": "45%",
                "itemStyle": {"color": GRAD_V, "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top", "formatter": AX_FMT, "color": "#667085"},
            }
        ],
    }


def _opts_mapa(map_data, vmin, vmax):
    if vmin == vmax:
        vmax = vmin + 1
    return {
        "tooltip": {"trigger": "item", "formatter": TT_PROVINCIA},
        "visualMap": {
            "min": vmin,
            "max": vmax,
            "left": 16,
            "bottom": 16,
            "text": ["Alta", "Baja"],
            "textStyle": {"color": "#667085"},
            "inRange": {"color": ["#EFF3F8", "#C9A24B", "#0B2545"]},
        },
        "series": [
            {
                "type": "map",
                "map": "Argentina",
                "roam": True,
                "selectedMode": "single",
                "data": map_data,
                "label": {"show": False},
                "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 1, "areaColor": "#EFF3F8"},
                "emphasis": {
                    "label": {"show": True, "color": COLOR_PRIMARY},
                    "itemStyle": {"areaColor": COLOR_ACCENT},
                },
                "select": {
                    "label": {"show": True, "color": COLOR_PRIMARY},
                    "itemStyle": {"areaColor": COLOR_PRIMARY, "borderColor": "#FFFFFF"},
                },
            }
        ],
    }


def _opts_composicion(df):
    conceptos = ["Demanda", "Intereses", "Costas", "Honorarios"]
    series = []
    for esc, color in [("Probable", COLOR_PROBABLE), ("Posible", COLOR_POSIBLE), ("Remoto", COLOR_REMOTO)]:
        data = [round(float(df[f"{concepto}_{esc}"].sum()), 2) for concepto in conceptos]
        series.append(
            {
                "name": esc,
                "type": "bar",
                "stack": "total",
                "data": data,
                "itemStyle": {"color": color},
                "emphasis": {"focus": "series"},
            }
        )
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "valueFormatter": VAL_FMT},
        "legend": {"bottom": 0},
        "grid": {"left": 4, "right": 16, "top": 20, "bottom": 28, "containLabel": True},
        "xAxis": {"type": "category", "data": conceptos},
        "yAxis": {"type": "value", "axisLabel": {"formatter": AX_FMT}},
        "series": series,
    }


def _st_echarts(options, key, height="360px", on_select="ignore", selection_mode=("points",),
                map_obj=None, replace_merge=None):
    """Wrapper que aplica el tema de marca, el renderer elegido y una key estable
    (evita remounts y repite animaciones en cada rerun)."""
    kwargs = {}
    if map_obj is not None:
        kwargs["map"] = map_obj
    if replace_merge is not None:
        kwargs["replace_merge"] = replace_merge
    return st_echarts(
        options=options,
        theme=BRAND_THEME,
        height=height,
        renderer=_RENDERER,
        key=key,
        on_select=on_select,
        selection_mode=selection_mode,
        **kwargs,
    )


# ============================================================
# CARGA Y PROCESAMIENTO
# ============================================================
try:
    with st.spinner("Sincronizando información con Google Sheets…"):
        juicios_raw, interes_raw, costas_raw, honorarios_raw = cargar_desde_sheets()
        df_base = procesar_datos_base(juicios_raw, interes_raw, costas_raw, honorarios_raw)
except Exception as e:
    st.error(f"❌ Error crítico al conectar o procesar datos: {e}")
    st.stop()

if df_base.empty:
    st.warning("No se encontraron juicios cargados en la planilla. Verificá la fuente de datos.")
    st.stop()

# ============================================================
# SIDEBAR — BRANDING + FILTROS (100% en español)
# ============================================================
st.sidebar.markdown(
    """
    <div style="text-align:center; padding-bottom: 0.5rem;">
        <span style="font-size:2rem;">⚖️</span>
        <h1 style="font-size:1.3rem; margin:0.3rem 0 0 0;">Estudio Jurídico</h1>
        <p style="color:#667085; font-size:0.8rem; margin-top:0.1rem;">Panel de contingencias judiciales</p>
    </div>
    <hr style="margin: 0.6rem 0 1rem 0;">
    """,
    unsafe_allow_html=True,
)

st.sidebar.subheader("📅 Corte")
fecha_corte = st.sidebar.date_input("Fecha de corte", value=date.today(), format="DD/MM/YYYY")
st.sidebar.caption("Los intereses, costas y honorarios se recalculan según esta fecha.")

with st.sidebar.expander("🌎 Jurisdicción y tipo", expanded=True):
    jurisdicciones = sorted([str(x) for x in df_base["Jurisdiccion"].dropna().unique().tolist() if str(x).strip() != ""])
    jur_sel = st.multiselect("Jurisdicción", jurisdicciones, default=[], placeholder="Todas las jurisdicciones")

    tipos = sorted([str(x) for x in df_base["Tipo"].dropna().unique().tolist() if str(x).strip() != ""])
    tipo_sel = st.multiselect("Tipo de juicio", tipos, default=[], placeholder="Todos los tipos")

with st.sidebar.expander("🟢 Estado y rol", expanded=True):
    estados = sorted([str(x) for x in df_base["Estado"].dropna().unique().tolist() if str(x).strip() != ""])
    estado_sel = st.multiselect("Estado", estados, default=[], placeholder="Todos los estados")

    roles = sorted(
        [str(x) for x in df_base["Demandante/Demandado"].dropna().unique().tolist() if str(x).strip() != ""]
    )
    rol_sel = st.multiselect("Rol", roles, default=[], placeholder="Todos los roles")

juzgado_sel = []
if "Juzgado" in df_base.columns:
    with st.sidebar.expander("⚖️ Juzgado", expanded=True):
        def _orden_juzgado(valor):
            m = re.search(r"(\d+)$", valor)
            return (int(m.group(1)) if m else 10**9, valor)

        juzgados = sorted(
            [str(x) for x in df_base["Juzgado"].dropna().unique().tolist() if str(x).strip() != ""],
            key=_orden_juzgado,
        )
        juzgado_sel = st.multiselect("Juzgado", juzgados, default=[], placeholder="Todos los juzgados")

with st.sidebar.expander("🔍 Búsqueda", expanded=True):
    busqueda = st.text_input("Carátula o número de juicio", placeholder="Ej: 12345 o García c/ Pérez")

# ---------- Selección por clic en gráficos ----------
with st.sidebar.expander("🎯 Selección por clic", expanded=False):
    st.caption(
        "Hacé clic en la dona, el mapa o el gráfico de jurisdicciones para filtrar "
        "el resto del dashboard. Doble clic en un área vacía del gráfico limpia la selección."
    )
    s_jur = st.session_state.get("chart_sel_jurisdiccion") or []
    s_prov = st.session_state.get("chart_sel_provincia") or []
    s_esc = st.session_state.get("chart_sel_escenario") or []
    if s_jur or s_prov or s_esc:
        st.markdown("**Activos:**")
        if s_jur:
            st.write("• Jurisdicción: " + ", ".join(s_jur))
        if s_prov:
            st.write("• Provincia: " + ", ".join(s_prov))
        if s_esc:
            st.write("• Escenario dominante: " + ", ".join(s_esc))
        if st.button("🗑️ Limpiar selección"):
            for k in ["chart_sel_jurisdiccion", "chart_sel_provincia", "chart_sel_escenario"]:
                st.session_state[k] = []
            st.rerun()
    else:
        st.caption("Sin selección activa.")

# ---------- Renderer (canvas/svg) ----------
with st.sidebar.expander("🎨 Renderizado", expanded=False):
    renderer_sel = st.radio(
        "Renderer de los gráficos",
        ["canvas", "svg"],
        index=0,
        help="canvas: más rápido con muchos datos · svg: mejor para imprimir y exportar.",
    )
    _RENDERER = renderer_sel

st.sidebar.markdown("---")
st.sidebar.caption(f"🕒 Última actualización de datos: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ============================================================
# CÁLCULO DE TOTALES SEGÚN LA FECHA DE CORTE + APLICACIÓN DE FILTROS
# ============================================================
df = calcular_totales(df_base, fecha_corte)

mask = pd.Series(True, index=df.index)
if jur_sel:
    mask &= df["Jurisdiccion"].isin(jur_sel)
if tipo_sel:
    mask &= df["Tipo"].isin(tipo_sel)
if estado_sel:
    mask &= df["Estado"].isin(estado_sel)
if rol_sel:
    mask &= df["Demandante/Demandado"].isin(rol_sel)
if juzgado_sel:
    mask &= df["Juzgado"].isin(juzgado_sel)
if busqueda:
    mask &= (
        df["Caratula"].astype(str).str.contains(busqueda, case=False, na=False)
        | df["Numero Juicio"].astype(str).str.contains(busqueda, na=False)
    )

df_filtrado = df[mask].copy()

# Filtros por clic en gráficos (se aplican sobre lo ya filtrado por sidebar).
df_chart = _aplicar_selecciones_chart(df_filtrado)

# ============================================================
# ENCABEZADO
# ============================================================
st.markdown(
    f"""
    <div class="firm-header">
        <h1>⚖️ Dashboard de Juicios</h1>
        <p>Exposición contingente y proyección de pago · Corte al {fecha_corte.strftime('%d/%m/%Y')}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if df_filtrado.empty:
    st.info("No hay juicios que coincidan con los filtros seleccionados. Ajustá los criterios en la barra lateral.")
    st.stop()

if df_chart.empty:
    st.info(
        "⚠️ La selección por clic dejó sin causas a la vista. "
        "Limpiá la selección en la barra lateral (🎯 Selección por clic → Limpiar)."
    )

# ============================================================
# KPIs
# ============================================================
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("📁 Juicios activos", f"{len(df_chart):,}".replace(",", "."), "kpi-accent")
with c2:
    kpi_card("💰 Demanda total", fmt_money(df_chart["Demanda total"].sum()), "kpi-accent")
with c3:
    kpi_card("🟢 Escenario probable", fmt_money(df_chart["Totales_Probable"].sum()), "kpi-probable")
with c4:
    kpi_card("🟡 Escenario posible", fmt_money(df_chart["Totales_Posible"].sum()), "kpi-posible")
with c5:
    kpi_card("🔴 Escenario remoto", fmt_money(df_chart["Totales_Remoto"].sum()), "kpi-remoto")

st.write("")

# ============================================================
# TABS
# ============================================================
tab1, tab_mapa, tab2, tab3, tab4 = st.tabs(
    [
        "📊 Resumen ejecutivo",
        "🗺️ Mapa por provincia",
        "📈 Evolución y riesgo",
        "🔎 Detalle de causas",
        "💵 Proyección de pago",
    ]
)

# ---------- TAB 1: RESUMEN EJECUTIVO ----------
with tab1:
    st.markdown('<p class="section-sub">Visión consolidada de la exposición judicial del estudio.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.subheader("Exposición por escenario")
        _st_echarts(
            _opts_dona(df_filtrado),
            key="dona_escenarios",
            height="380px",
            on_select=lambda: _capturar_seleccion("chart_sel_escenario", "dona_escenarios"),
            selection_mode=("points",),
        )
        st.caption("Clic en un sector para filtrar por escenario dominante.")

    with col2:
        st.subheader("Exposición por jurisdicción")
        _st_echarts(
            _opts_jur(df_filtrado, jurisdicciones),
            key="jur_bar",
            height="380px",
            on_select=lambda: _capturar_seleccion("chart_sel_jurisdiccion", "jur_bar"),
            selection_mode=("points",),
            replace_merge="series",
        )
        st.caption("Clic en una barra para filtrar por jurisdicción.")

    st.subheader("Top 5 causas de mayor exposición")
    top5 = df_chart.sort_values("Totales_General", ascending=False).head(5)
    cols_top = ["Numero Juicio", "Caratula", "Jurisdiccion", "Juzgado", "Estado", "Totales_General"]
    cols_top = [c for c in cols_top if c in top5.columns]
    top5_show = top5[cols_top].copy()
    top5_show["Totales_General"] = top5_show["Totales_General"].apply(fmt_money)
    st.dataframe(top5_show.rename(columns={"Totales_General": "Exposición total"}), width="stretch", hide_index=True)

# ---------- TAB MAPA: MAPA POR PROVINCIA ----------
with tab_mapa:
    st.markdown(
        '<p class="section-sub">Distribución geográfica de la exposición judicial por provincia.</p>',
        unsafe_allow_html=True,
    )
    try:
        geojson_data = cargar_geojson_provincias()
        geo_nombres = {f["properties"]["name"] for f in geojson_data["features"]}
        geo_display = {f["properties"]["name"]: f["properties"]["_nombre_display"] for f in geojson_data["features"]}

        df_geo = df_filtrado.copy()
        df_geo["Provincia_norm"] = df_geo["Jurisdiccion"].apply(jurisdiccion_a_provincia)

        por_provincia = df_geo.groupby("Provincia_norm").agg(
            Cantidad_Causas=("Numero Juicio", "count"),
            Exposicion_Total=("Totales_General", "sum"),
        ).reset_index()

        map_data = []
        no_reconocidas = []
        for r in por_provincia.itertuples(index=False):
            nm = r.Provincia_norm
            if nm in geo_nombres:
                map_data.append(
                    {"name": nm, "value": round(float(r.Exposicion_Total), 2), "display": geo_display[nm]}
                )
            else:
                no_reconocidas.append({"Provincia_norm": nm, "Cantidad_Causas": int(r.Cantidad_Causas)})

        if map_data:
            valores = [m["value"] for m in map_data]
            mapa_arg = Map(map_name="Argentina", geo_json=geojson_data)
            _st_echarts(
                _opts_mapa(map_data, 0.0, float(max(valores))),
                key="mapa_provincias",
                height="560px",
                map_obj=mapa_arg,
                on_select=lambda: _capturar_seleccion("chart_sel_provincia", "mapa_provincias"),
                selection_mode=("points",),
            )
            st.caption(
                "Clic en una provincia para filtrar todo el dashboard. "
                "El mapa siempre muestra el panorama completo según el sidebar."
            )
        else:
            st.info(
                "Ninguno de los valores de 'Jurisdiccion' coincide todavía con una provincia argentina. "
                "Revisá el diccionario ALIAS_PROVINCIAS en el código para mapear los nombres usados en la planilla."
            )

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Ranking por provincia")
            df_prov = df_chart.copy()
            df_prov["Provincia_norm"] = df_prov["Jurisdiccion"].apply(jurisdiccion_a_provincia)
            tabla_prov = df_prov.groupby("Provincia_norm").agg(
                Cantidad_Causas=("Numero Juicio", "count"),
                Exposicion_Total=("Totales_General", "sum"),
            ).reset_index()
            if tabla_prov.empty:
                st.caption("Sin datos para el ranking con la selección actual.")
            else:
                tabla_prov["Provincia"] = tabla_prov["Provincia_norm"].map(geo_display).fillna(
                    tabla_prov["Provincia_norm"].str.title()
                )
                tabla_prov = tabla_prov.sort_values("Exposicion_Total", ascending=False)[
                    ["Provincia", "Cantidad_Causas", "Exposicion_Total"]
                ].copy()
                tabla_prov["Exposicion_Total"] = tabla_prov["Exposicion_Total"].apply(fmt_money)
                st.dataframe(
                    tabla_prov.rename(columns={"Cantidad_Causas": "Causas", "Exposicion_Total": "Exposición total"}),
                    width="stretch",
                    hide_index=True,
                )
        with col2:
            if no_reconocidas:
                with st.expander("⚠️ Jurisdicciones no identificadas", expanded=False):
                    st.caption(
                        "Estos valores de 'Jurisdiccion' no coinciden con ninguna provincia. "
                        "Sumalos al diccionario ALIAS_PROVINCIAS en el código."
                    )
                    st.dataframe(
                        pd.DataFrame(no_reconocidas).rename(columns={"Provincia_norm": "Valor en la planilla", "Cantidad_Causas": "Causas"}),
                        hide_index=True,
                        width="stretch",
                    )
    except requests.exceptions.RequestException:
        st.info(
            "No se pudo descargar el mapa de provincias (sin conexión al servicio GeoRef). "
            "El resto del dashboard sigue funcionando con normalidad."
        )
    except Exception as e:
        st.info(f"No se pudo generar el mapa por provincia en este momento. ({e})")

# ---------- TAB 2: EVOLUCIÓN Y RIESGO ----------
with tab2:
    st.markdown(
        '<p class="section-sub">Antigüedad de las causas y su relación con la exposición económica.</p>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Causas iniciadas por año")
        opts_anio = _opts_anio(df_chart)
        if opts_anio is not None:
            _st_echarts(opts_anio, key="anio_bar", height="360px", replace_merge="series")
        else:
            st.info("No hay fechas válidas para graficar la evolución temporal.")

    with col2:
        st.subheader("Matriz de riesgo: antigüedad vs. exposición")
        opts_riesgo = _opts_riesgo(df_chart)
        if opts_riesgo is not None:
            _st_echarts(opts_riesgo, key="riesgo_scatter", height="360px")
        else:
            st.info("No hay datos para graficar la matriz de riesgo.")

    st.subheader("Exposición por estado del proceso")
    if not df_chart.empty:
        _st_echarts(_opts_estado(df_chart), key="estado_bar", height="340px")
    else:
        st.info("Sin datos con la selección actual.")

# ---------- TAB 3: DETALLE ----------
with tab3:
    st.markdown('<p class="section-sub">Listado completo de causas según los filtros aplicados.</p>', unsafe_allow_html=True)

    cols_mostrar = [
        "Numero Juicio", "Caratula", "Estado", "Jurisdiccion", "Juzgado", "Tipo", "Demandante/Demandado",
        "Fecha Hecho", "Dias_Transcurridos", "Demanda total",
        "Totales_Probable", "Totales_Posible", "Totales_Remoto", "Totales_General",
    ]
    cols_existentes = [c for c in cols_mostrar if c in df_chart.columns]
    tabla = df_chart[cols_existentes].sort_values("Totales_General", ascending=False)
    st.dataframe(tabla, width="stretch", height=500)

    col_a, col_b = st.columns([1, 4])
    with col_a:
        csv = tabla.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar CSV filtrado", csv, file_name=f"juicios_{fecha_corte}.csv", mime="text/csv")

# ---------- TAB 4: PROYECCIÓN DE PAGO ----------
with tab4:
    st.markdown(
        f'<p class="section-sub">Desglose de conceptos por escenario, proyectado al {fecha_corte.strftime("%d/%m/%Y")}.</p>',
        unsafe_allow_html=True,
    )

    resumen = pd.DataFrame(
        {
            "Concepto": ["Demanda", "Intereses", "Costas", "Honorarios", "TOTAL A PAGAR"],
            "Probable": [
                df_chart["Demanda_Probable"].sum(),
                df_chart["Intereses_Probable"].sum(),
                df_chart["Costas_Probable"].sum(),
                df_chart["Honorarios_Probable"].sum(),
                df_chart["Totales_Probable"].sum(),
            ],
            "Posible": [
                df_chart["Demanda_Posible"].sum(),
                df_chart["Intereses_Posible"].sum(),
                df_chart["Costas_Posible"].sum(),
                df_chart["Honorarios_Posible"].sum(),
                df_chart["Totales_Posible"].sum(),
            ],
            "Remoto": [
                df_chart["Demanda_Remoto"].sum(),
                df_chart["Intereses_Remoto"].sum(),
                df_chart["Costas_Remoto"].sum(),
                df_chart["Honorarios_Remoto"].sum(),
                df_chart["Totales_Remoto"].sum(),
            ],
        }
    )
    resumen["Total"] = resumen["Probable"] + resumen["Posible"] + resumen["Remoto"]

    resumen_fmt = resumen.copy()
    for col in ["Probable", "Posible", "Remoto", "Total"]:
        resumen_fmt[col] = resumen_fmt[col].apply(fmt_money)

    st.dataframe(resumen_fmt, width="stretch", hide_index=True)

    st.subheader("Composición del total a pagar")
    if not df_chart.empty:
        _st_echarts(_opts_composicion(df_chart), key="comp_bar", height="380px")
    else:
        st.info("Sin datos con la selección actual.")

    col_x, col_y = st.columns([1, 4])
    with col_x:
        csv_resumen = resumen.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar proyección (CSV)", csv_resumen, file_name=f"proyeccion_pago_{fecha_corte}.csv", mime="text/csv")

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    f"""
    <div class="footer-note">
        Dashboard generado para uso interno del estudio · Datos sincronizados desde Google Sheets ·
        Corte al {fecha_corte.strftime('%d/%m/%Y')}
    </div>
    """,
    unsafe_allow_html=True,
)
