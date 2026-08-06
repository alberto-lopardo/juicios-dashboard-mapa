# ⚖️ Dashboard de Juicios — versión ECharts

Dashboard interactivo de contingencias judiciales para el estudio, construido con
**Streamlit** + **Apache ECharts** (v6, vía `streamlit-echarts`) y alimentado desde
**Google Sheets**.

## ✨ Características

- **KPIs de exposición** según la fecha de corte (los intereses, costas y honorarios se recalculan dinámicamente).
- **Cross-filtering por clic**: hacer clic en la dona de escenarios, en el mapa o en las barras de jurisdicción filtra el resto del dashboard (KPIs, tablas y demás gráficos) sin JavaScript.
- **Mapa choropleth de provincias** con GeoJSON local (`argentina-provincias.geojson`) y fallback a la API oficial GeoRef.
- **Tema de marca** personalizado (azul noche + dorado) aplicado a todos los gráficos.
- **Animaciones suaves** entre estados gracias a `key` estables y `replace_merge`.
- **Renderer Canvas/SVG** seleccionable desde la barra lateral (SVG ideal para imprimir/exportar).
- **Filtros por sidebar**: jurisdicción, tipo, estado, rol, juzgado y búsqueda por carátula o número.
- Descarga de **CSV filtrado** y de la **proyección de pago**.

## 📁 Estructura del proyecto

```
Con Mapa/
├── app.py                       # Aplicación principal
├── requirements.txt             # Dependencias
├── argentina-provincias.geojson # Límites provinciales (GADM) — local-first
└── .streamlit/
    ├── config.toml              # Tema de Streamlit
    └── secrets.toml             # Credenciales del Service Account (solo local)
```

## ✅ Requisitos

- Python **≥ 3.10** (requerido por `streamlit-echarts`).
- Un spreadsheet de Google llamado **`Ejemplo Juicios`** con las hojas:
  - `Hoja1` (juicios), `Interes`, `Costas`, `Honoriarios`.
- Un **Service Account** de Google Cloud con acceso de lectura al spreadsheet.

## 🚀 Instalación y ejecución local

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
streamlit run app.py
```

> Para que `st.secrets` funcione localmente, el archivo
> `.streamlit/secrets.toml` debe contener el Service Account bajo `[gcp_service_account]`.

## 🔐 Configuración de Google Sheets

1. Creá un Service Account en [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts).
2. En la pestaña **Keys → Add Key → JSON**, descargá el archivo de credenciales.
3. Compartí el spreadsheet `Ejemplo Juicios` con el `client_email` de ese Service Account en modo **Lector** (o Editor si querés escribir desde la app).
4. El contenido del JSON es exactamente lo que va como secret.

## 🔑 Secrets para Streamlit Cloud

En Community Cloud abrí tu app → **⋮ → Settings → Secrets** y pegá el contenido
del JSON del Service Account bajo el encabezado `[gcp_service_account]`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "tu-proyecto"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "tu-cuenta@tu-proyecto.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/tu-cuenta..."
```

No hay otros secretos necesarios: ECharts y el geojson se sirven desde el repo.

## 🌍 Deploy en Streamlit Community Cloud

1. Subí el proyecto (incluido `argentina-provincias.geojson`) a un repositorio de GitHub.
2. Entrá a [share.streamlit.io](https://share.streamlit.io) → **Create app** → conectá el repo.
3. Elegí `Con Mapa/app.py` como archivo principal (o `app.py` si subís solo esta carpeta como raíz).
4. Pegá los Secrets como se indica arriba y hacé **Deploy**.

## 🗺️ Mapa de provincias

- El app busca primero `argentina-provincias.geojson` junto a `app.py` (funciona offline y es más rápido).
- Si el archivo no existe, descarga los límites desde `https://apis.datos.gob.ar/georef/api/provincias.geojson` (GeoRef) y los cachea por 24 h.
- Los valores de la columna **Jurisdiccion** se normalizan (mayúsculas, sin acentos) y se mapean a provincias con el diccionario `ALIAS_PROVINCIAS` en el código. Si tu planilla usa nombres propios (ej. "CABA", "Capital", "BS AS"), asegurate de que estén en ese diccionario.

## 🎯 Interactividad

- **Clic** en la dona de escenarios, en el mapa o en las barras de jurisdicción → filtra el resto del dashboard.
- **Doble clic** en un área vacía del gráfico → limpia esa selección.
- Botón **🗑️ Limpiar selección** en la barra lateral → resetea todo el filtrado por clic.
- **🎨 Renderizado**: cambiar entre `canvas` (más rápido) y `svg` (mejor para imprimir).

## 🎨 Personalización

- Paleta del estudio: variables `COLOR_*` al inicio de `app.py`.
- Tema de los gráficos: diccionario `BRAND_THEME` (se pasa como `theme=` a todos los ECharts).
- Estilos generales (header, tarjetas KPI, tabs): bloque `CUSTOM_CSS`.
