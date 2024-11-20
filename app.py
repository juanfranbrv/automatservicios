import streamlit as st
import pdfplumber
import pandas as pd
import json
import re
from io import BytesIO
from groq import Groq  # Importamos el cliente de Groq

# Configuración de la página
st.set_page_config(page_title="Extracción de Facturas con Groq", layout="wide")

# Leer la clave API de secrets.toml
groq_api_key = st.secrets["GROQ_API_KEY"]

# Inicializar el cliente de Groq
groq_client = Groq(api_key=groq_api_key)

# Widgets en la barra lateral para subir archivos con íconos delante
st.sidebar.header("Sube tus facturas")
luz_file = st.sidebar.file_uploader("💡 Factura de Luz", type="pdf", key="luz")
agua_file = st.sidebar.file_uploader("🚿 Factura de Agua", type="pdf", key="agua")
internet_file = st.sidebar.file_uploader("🌐 Factura de Internet", type="pdf", key="internet")
gas_file = st.sidebar.file_uploader("🔥 Factura de Gas", type="pdf", key="gas")

# Inicializar el estado para los resultados
if "results" not in st.session_state:
    st.session_state.results = {}

# Función para extraer el texto del primer tercio del PDF usando pdfplumber
def extract_text_from_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            total_pages = len(pdf.pages)
            limit_pages = max(1, total_pages // 3)  # Calculamos el primer tercio, con al menos una página

            text = ""
            for page_num in range(limit_pages):
                page_text = pdf.pages[page_num].extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()  # Eliminamos espacios extra
    except Exception as e:
        st.error(f"Error al extraer texto con pdfplumber: {e}")
        return ""

# Función para enviar el texto a la API de Groq usando el modelo "Gemma"
def extract_data_with_groq(text, service_type):
    try:
        # Crear el prompt para la factura
        prompt = f"""
        Eres un asistente que analiza facturas. Aquí tienes el texto de una factura de {service_type}.
        Por favor, identifica y devuelve esta información en formato JSON:
        - 'amount': El monto total a pagar (incluye el símbolo € si aparece).
        - 'start_date': La fecha de inicio del periodo facturado (formato DD/MM/YYYY).
        - 'end_date': La fecha de fin del periodo facturado (formato DD/MM/YYYY).
        
        Devuelve exclusivamente un JSON sin ningún texto adicional.

        Texto de la factura:
        {text}
        """

        # Llamada a la API de Groq usando el modelo "Gemma" y streaming
        response = groq_client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True,
            stop=None,
        )

        # Concatenar las partes de la respuesta
        result = ""
        for chunk in response:
            result += chunk.choices[0].delta.content or ""
        
        return result
    except Exception as e:
        st.error(f"Error al llamar a la API de Groq: {e}")
        return None

# Función para intentar extraer un JSON válido de la respuesta
def extract_json_from_response(response):
    try:
        # Usar una expresión regular para buscar el primer objeto JSON válido en la respuesta
        json_match = re.search(r"\{.*?\}", response, re.DOTALL)
        if json_match:
            return json_match.group(0)
        else:
            return None
    except Exception as e:
        st.error(f"Error al intentar extraer JSON de la respuesta: {e}")
        return None

# Procesar archivos al hacer clic en el botón
if st.button("Procesar Facturas"):
    # Inicializar la variable total_amount
    total_amount = 0.0

    # Recorrer los archivos subidos
    uploaded_files = {
        "Luz": luz_file,
        "Agua": agua_file,
        "Internet": internet_file,
        "Gas": gas_file
    }

    for service, file in uploaded_files.items():
        if file:
            # Extraer el texto del archivo
            text = extract_text_from_pdf(file)
            
            if text.strip():  # Comprobar si el texto no está vacío
                # Enviar el texto a Groq
                with st.spinner(f"Analizando la factura de {service} con Groq..."):
                    result = extract_data_with_groq(text, service)
                    if result:
                        # Intentar extraer solo el JSON de la respuesta
                        json_string = extract_json_from_response(result)
                        if json_string:
                            try:
                                # Intentar parsear la respuesta como JSON
                                result_json = json.loads(json_string)
                                
                                # Normalizar fechas y montos si es necesario
                                if "start_date" in result_json:
                                    result_json["start_date"] = result_json["start_date"].replace(".", "/")
                                if "end_date" in result_json:
                                    result_json["end_date"] = result_json["end_date"].replace(".", "/")
                                
                                # Guardar los resultados en el estado de la sesión
                                st.session_state.results[service] = result_json

                            except json.JSONDecodeError:
                                st.error(f"No se pudo extraer información válida de la factura de {service}. La respuesta no es un JSON válido.")
                        else:
                            st.error(f"No se pudo encontrar un JSON válido en la respuesta para la factura de {service}.")
                    else:
                        st.error(f"No se pudo extraer información de la factura de {service}.")
            else:
                st.warning(f"No se pudo extraer texto de la factura de {service}. Intente con otro archivo.")

# Mostrar los resultados almacenados en session_state
if st.session_state.results:
    total_amount = 0.0  # Inicializamos de nuevo la suma total para el cálculo al mostrar los resultados
    for service, result in st.session_state.results.items():
        # Extraer el importe sin agregar el símbolo de euro
        amount = result.get('amount', 'N/A').replace(",", ".").replace("€", "").strip()
        if amount != "N/A":
            amount = float(amount)
            total_amount += amount

        # Mostrar los datos
        st.markdown(f"#### {service}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Inicio", result.get('start_date', 'N/A'))
        col2.metric("Fin", result.get('end_date', 'N/A'))
        col3.metric("Importe (€)", f"{amount:.2f} €")
        st.divider()

    # Crear el archivo Excel para descarga sin formato adicional ni símbolo de euro
    data = []
    for service, result in st.session_state.results.items():
        # Convertir el importe a número sin formato ni símbolos
        amount = result.get("amount", "N/A")
        if amount != "N/A":
            amount = float(amount.replace(",", ".").replace("€", "").strip())  # Convertir a float para asegurar el formato numérico

        data.append({
            "Concepto": service,
            "Inicio": result.get('start_date', 'N/A'),
            "Final": result.get('end_date', 'N/A'),
            "Importe": amount
        })
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados")
    output.seek(0)

    # Botón de descarga
    st.download_button(
        label="Descargar Resultados en Excel",
        data=output,
        file_name="facturas_procesadas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Mostrar la suma total de importes en pantalla alineada a la derecha, siempre debajo de los resultados
    st.markdown(
        f"<div style='text-align: right; font-size: 40px; font-weight: bold;'>Total: {total_amount:.2f} €</div>",
        unsafe_allow_html=True
    )
