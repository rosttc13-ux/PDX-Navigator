
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

# Configuración de la página
st.set_page_config(
    page_title="Asistente de carga de productos",
    page_icon="📦",
    layout="centered"
)

# Título y Descripción
st.title("Asistente de carga de productos 📦")
st.markdown(
    "Consulta dudas sobre atributos, formatos y errores de validación en ficheros de carga de productos. "
    "Sube tu archivo Excel para comenzar el proceso de validación."
)

# Inicialización exclusiva con st.secrets["GEMINI_API_KEY"]
api_key = st.secrets.get("GEMINI_API_KEY", None)
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("⚠️ Error: No se pudo cargar 'GEMINI_API_KEY' desde st.secrets. Verifica tu configuración en Streamlit Cloud.")
    client = None

# ---------------------------------------------------------------------
# FUNCIONALIDAD: Revisar un fichero de carga (Validación Inicial)
# ---------------------------------------------------------------------
st.header("📤 1. Cargar y Revisar Fichero de Productos")
uploaded_file = st.file_uploader(
    "Selecciona tu archivo de carga (.xlsx o .xlsm)",
    type=["xlsx", "xlsm"]
)

df_context = ""
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"✅ Archivo '{uploaded_file.name}' cargado correctamente.")

        # Reporte de revisión de fichero
        st.subheader("📊 Reporte de Revisión")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Filas", len(df))
        col2.metric("Total Columnas", len(df.columns))

        # Detección básica de inconsistencias
        null_counts = df.isnull().sum().sum()
        col3.metric("Celdas Vacías", null_counts)

        # Guardar lista de columnas como contexto para el asistente
        columns_list = list(df.columns)
        df_context = f" El archivo cargado por el usuario contiene las siguientes columnas: {columns_list}."

        with st.expander("🔍 Ver vista previa de las columnas cargadas"):
            st.dataframe(df.head(5))

    except Exception as e:
        st.error(f"❌ Error al leer y revisar el archivo Excel: {e}")

# ---------------------------------------------------------------------
# FUNCIONALIDAD: Resolver dudas sobre atributos y Explicar errores de validación
# ---------------------------------------------------------------------
st.header("💬 2. Asistente de Consultas")
st.write("Pregunta al asistente sobre el significado de atributos específicos, formatos válidos o pega un error de validación para interpretarlo.")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_query := st.chat_input("Ej: ¿Qué formato debe tener el atributo EAN o cómo soluciono un error de longitud máxima?"):

    st.session_state["messages"].append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    if client is not None:
        with st.chat_message("assistant"):
            with st.spinner("Analizando consulta..."):
                try:
                    system_instruction = (
                        "Actúas como un asistente experto para proveedores de comercio electrónico. "
                        "Tu único objetivo es resolver dudas sobre atributos de productos, formatos de carga y explicar errores de validación. "
                        "Reglas de comportamiento:\n"
                        "- Responde estrictamente en español.\n"
                        "- Utiliza un lenguaje muy claro, sencillo y profesional.\n"
                        "- Explica el significado de los atributos consultados y cómo resolver errores de validación paso a paso.\n"
                        "- Proporciona consejos para completar correctamente las plantillas de carga.\n"
                        "- NO inventes información. Si no tienes suficiente información, indícalo claramente.\n"
                        "- NO completes atributos por el usuario ni intentes modificar el archivo Excel.\n"
                        "- No asumas formatos específicos de plataformas ajenas a menos que el usuario lo mencione.\n"
                    )

                    if df_context:
                        system_instruction += df_context

                    contents = []
                    for m in st.session_state["messages"]:
                        role_name = "user" if m["role"] == "user" else "model"
                        contents.append(types.Content(
                            role=role_name,
                            parts=[types.Part.from_text(text=m["content"])]
                        ))

                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2
                        )
                    )

                    assistant_response = response.text
                    st.markdown(assistant_response)
                    st.session_state["messages"].append({"role": "assistant", "content": assistant_response})

                except Exception as e:
                    st.error(f"❌ Error al generar la respuesta: {e}")
    else:
        st.warning("⚠️ El asistente está inactivo porque no se configuró 'GEMINI_API_KEY' en st.secrets.")
