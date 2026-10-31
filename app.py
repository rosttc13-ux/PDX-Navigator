import streamlit as st
import pandas as pd
import os
from google import genai
from google.genai import types

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Asistente de Validación - Lyreco",
    page_icon="✅",
    layout="wide"
)

# --- CARGA Y ESTRUCTURACIÓN DE LA DOCUMENTACIÓN (MOCK UP) ---
MOCK_UP_PATH = '/content/MOCK UP_Final v21.04.2026 up to 3 languages.xlsm'

@st.cache_data(show_spinner="Cargando base de conocimiento del negocio...")
def load_knowledge_base(file_path):
    knowledge = {}
    try:
        if os.path.exists(file_path):
            # 1. AT INSTRUCTION
            df_inst = pd.read_excel(file_path, sheet_name="AT INSTRUCTION")
            df_inst.columns = df_inst.columns.str.strip()
            inst_text = ""
            for _, row in df_inst.dropna(subset=['Column']).head(50).iterrows():
                tab_info = f" (Pestaña: {row['Tab']})" if pd.notna(row['Tab']) else ""
                inst_text += f"- Atributo/Columna: {row['Column']}{tab_info}. Instrucción: {row['Comments']}
"
            knowledge['instructions'] = inst_text

            # 2. AT NECESSARY FOR ALL PRODUCTS
            df_nec = pd.read_excel(file_path, sheet_name="AT NECESSARY FOR ALL PRODUCTS")
            df_nec.columns = df_nec.columns.str.strip()
            nec_text = ""
            cols_to_use = ['Attribute ID', 'Attribute Name (EN)', 'TYPE', 'Definition & Completion advice (EN)']
            cols_present = [c for c in cols_to_use if c in df_nec.columns]
            for _, row in df_nec.dropna(subset=['Attribute ID']).head(60).iterrows():
                details = ", ".join([f"{c}: {row[c]}" for c in cols_present if pd.notna(row[c])])
                nec_text += f"- {details}
"
            knowledge['necessary'] = nec_text

            # 3. LOV_Values
            df_lov = pd.read_excel(file_path, sheet_name="LOV_Values")
            df_lov.columns = df_lov.columns.str.strip()
            lov_text = ""
            sample_lovs = df_lov.dropna(subset=['Attribute LOV ID', 'Value Name (EN)']).head(100)
            for lov_id, group in sample_lovs.groupby('Attribute LOV ID'):
                vals = ", ".join(group['Value Name (EN)'].astype(str).unique())
                lov_text += f"- {lov_id}: Valores permitidos -> [{vals}]
"
            knowledge['lovs'] = lov_text

            # 4. Bible
            df_bible = pd.read_excel(file_path, sheet_name="Bible")
            df_bible.columns = df_bible.columns.str.strip()
            bible_text = ""
            for _, row in df_bible.dropna(subset=['SAP Code']).head(15).iterrows():
                bible_text += f"- SAP Code: {row['SAP Code']} | Producto: {row.get('Group Description 40', 'N/A')} | Proveedor: {row.get('Supplier Name', 'N/A')}
"
            knowledge['bible'] = bible_text

            return knowledge
        else:
            st.warning("⚠️ No se encontró el archivo de documentación Excel en la ruta especificada.")
            return None
    except Exception as e:
        st.error(f"Error procesando la base de conocimiento: {e}")
        return None

# Cargar base de conocimiento
kb = load_knowledge_base(MOCK_UP_PATH)

# --- GENERACIÓN DEL SYSTEM PROMPT ENRIQUECIDO ---
def build_system_instruction(kb):
    base_prompt = (
        "Eres un asistente experto de validación de datos y catálogos de productos para Lyreco.
"
        "Tu rol es ayudar a los proveedores y analistas a resolver dudas de negocio, validar formatos y explicar errores.

"
        "IMPORTANTE: Responde a las consultas de los usuarios basándose prioritariamente en la documentación oficial "
        "del negocio provista a continuación. Si la información no está aquí, utiliza tus capacidades cognitivas indicando "
        "claramente que es una recomendación basada en estándares generales.

"
    )

    if kb:
        base_prompt += "=== REGLAS MAESTRAS DE PRODUCTOS (HOJA BIBLE) ===
"
        base_prompt += kb.get('bible', 'No disponible') + "

"

        base_prompt += "=== REGLAS DE OBLIGATORIEDAD (HOJA AT NECESSARY FOR ALL PRODUCTS) ===
"
        base_prompt += kb.get('necessary', 'No disponible') + "

"

        base_prompt += "=== VALORES PERMITIDOS LOV (HOJA LOV_Values) ===
"
        base_prompt += kb.get('lovs', 'No disponible') + "

"

        base_prompt += "=== INSTRUCCIONES DE ATRIBUTOS (HOJA AT INSTRUCTION) ===
"
        base_prompt += kb.get('instructions', 'No disponible') + "

"

    return base_prompt

system_instruction = build_system_instruction(kb)

# --- CLIENTE DE GEMINI (st.secrets) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error("⚠️ No se pudo iniciar el cliente de Gemini. Por favor configure su 'GEMINI_API_KEY' en st.secrets.")
    client = None

# --- INTERFAZ DE USUARIO ---
st.title("✅ Asistente de Masterdata & Validación Inteligente")
st.write("Realiza consultas inteligentes basadas directamente en el Mock Up de negocio, valida plantillas Excel o interactúa con el modelo.")

tab1, tab2 = st.tabs(["⁉ Chat de Soporte de Negocio", "🔍 Validador de Plantilla Excel"])

with tab1:
    st.subheader("¡Conversa con Gemini sobre la regulación de atributos!")
    st.info("El modelo responderá utilizando información real sobre atributos obligatorios, instrucciones del proveedor y valores LOV cargados del Excel.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("¿Cómo rellenar el campo FSC? ¿Qué valores están permitidos?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if client:
                try:
                    contents = []
                    for msg in st.session_state.messages:
                        contents.append(
                            types.Content(
                                role="user" if msg["role"] == "user" else "model",
                                parts=[types.Part.from_text(text=msg["content"])]
                            )
                        )

                    response = client.models.generate_content(
                        model='gemini-2.5-flash-lite',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2
                        )
                    )
                    assistant_response = response.text
                    st.markdown(assistant_response)
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                except Exception as ex:
                    st.error(f"Error al generar respuesta de Gemini: {ex}")
            else:
                st.warning("Servicio de IA no configurado.")

with tab2:
    st.subheader("Validación de estructura de datos de usuario")
    uploaded_file = st.file_uploader("Sube tu archivo de datos para pre-validar contra las reglas del negocio", type=["xlsx", "xlsm", "csv"])
    if uploaded_file:
        try:
            user_df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
            st.success("¡Archivo cargado correctamente!")
            st.write("**Vista previa de tus datos:**")
            st.dataframe(user_df.head(10))

            if kb and 'necessary' in kb:
                st.markdown("### 🔍 Diagnóstico de campos obligatorios detectados")
                expected_mandatory = ['FSC', 'Brand', 'Supplier Name', 'SAP code']
                found_missing = [col for col in expected_mandatory if col not in user_df.columns]
                if found_missing:
                    st.warning(f"⚠️ Faltan los siguientes campos críticos en tu plantilla: {', '.join(found_missing)}")
                else:
                    st.success("✅ ¡Tu archivo contiene todas las columnas de control requeridas para la validación!")
        except Exception as e:
            st.error(f"No se pudo procesar tu archivo de validación: {e}")
