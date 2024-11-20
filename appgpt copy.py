import streamlit as st
import pdfplumber
from openai import OpenAI
import pandas as pd
from io import BytesIO

key = st.secrets["OPENAI_API_KEY"]

# Verificar si la clave API está presente
if not key:
    st.error("API Key no encontrada. Asegúrate de tener una variable 'OPENAI_API_KEY' en tu archivo .env")
    st.stop()

# Configura tu API key directamente
openai_client = OpenAI(api_key=key)

# Configuración de la página
st.set_page_config(page_title="Extracción de Facturas con GPT", layout="wide")

# Widgets en la barra lateral para subir archivos
st.sidebar.header("Sube tus facturas")
luz_file = st.sidebar.file_uploader("Factura de Luz", type="pdf", key="luz")
agua_file = st.sidebar.file_uploader("Factura de Agua", type="pdf", key="agua")
internet_file = st.sidebar.file_uploader("Factura de Internet", type="pdf", key="internet")
gas_file = st.sidebar.file_uploader("Factura de Gas", type="pdf", key="gas")

# Inicializar el estado para los resultados
if "results" not in st.session_state:
    st.session_state.results = {}

# Función para extraer texto del PDF usando pdfplumber
def extract_text_from_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()  # Eliminamos espacios extra
    except Exception as e:
        st.error(f"Error al extraer texto con pdfplumber: {e}")
        return ""

# Función para enviar el texto a ChatGPT
def extract_data_with_gpt(text, service_type):
    prompt = f"""
    Eres un asistente que analiza facturas. Aquí tienes el texto de una factura de {service_type}.
    Por favor, identifica y devuelve esta información en formato JSON:
    - 'amount': El monto total a pagar (incluye el símbolo € si aparece).
    - 'start_date': La fecha de inicio del periodo facturado (formato DD/MM/YYYY).
    - 'end_date': La fecha de fin del periodo facturado (formato DD/MM/YYYY).

    Texto de la factura:
    {text}
    """
    try:
        # Usar la nueva API del cliente OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un extractor de datos de facturas."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error al llamar a la API de ChatGPT: {e}")
        return None

# Procesar archivos al hacer clic en el botón
if st.button("Procesar Facturas"):
    # Recorrer los archivos subidos
    uploaded_files = {
        "Luz": luz_file,
        "Agua": agua_file,
        "Internet": internet_file,
        "Gas": gas_file
    }

    for service, file in uploaded_files.items():
        if file:
            st.header(f"Procesando factura de {service}")
            
            # Extraer el texto del archivo
            text = extract_text_from_pdf(file)
            
            if text.strip():  # Comprobar si el texto no está vacío
                st.text_area(f"Texto extraído de {service}:", text, height=300)
                
                # Enviar el texto a ChatGPT
                with st.spinner(f"Analizando la factura de {service} con ChatGPT..."):
                    result = extract_data_with_gpt(text, service)
                    if result:
                        st.success(f"Datos extraídos de la factura de {service}:")
                        st.json(result)  # Mostrar los datos extraídos en formato JSON
                        st.session_state.results[service] = result
                    else:
                        st.error(f"No se pudo extraer información de la factura de {service}.")
            else:
                st.warning(f"No se pudo extraer texto de la factura de {service}. Intente con otro archivo.")

# Crear el archivo Excel para descarga con formato personalizado
if st.session_state.results:
    # Crear un DataFrame con los resultados
    data = []
    for service, result in st.session_state.results.items():
        result_json = eval(result)  # Convertir string a JSON
        data.append({
            "Concepto": service,
            "Inicio": result_json.get('start_date', 'N/A'),
            "Final": result_json.get('end_date', 'N/A'),
            "Importe": result_json.get("amount", "N/A")
        })
    df = pd.DataFrame(data)
    
    # Añadir la suma final al DataFrame
    try:
        df["Importe"] = df["Importe"].str.replace("€", "").str.replace(",", ".").astype(float)
        total = df["Importe"].sum()
    except ValueError:
        total = "Error al calcular"
    
    # Guardar el archivo Excel en memoria con formato personalizado
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados")
        workbook = writer.book
        worksheet = writer.sheets["Resultados"]

        # Formato para encabezados
        header_format = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": "#4F81BD",
            "border": 1,
            "align": "center"
        })

        # Formato para datos
        cell_format = workbook.add_format({
            "border": 1,
            "align": "center",
        })

        # Formato para la suma final
        total_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9E1F2",
            "border": 1,
            "align": "center"
        })

        # Aplicar formato a los encabezados
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)

        # Aplicar formato a las celdas
        for row_num in range(1, len(df) + 1):
            for col_num in range(len(df.columns)):
                worksheet.write(row_num, col_num, df.iloc[row_num - 1, col_num], cell_format)

        # Agregar suma final al final de la columna "Importe"
        worksheet.write(len(df), 2, "TOTAL", total_format)
        worksheet.write(len(df), 3, total, total_format)

    output.seek(0)

    # Botón de descarga
    st.download_button(
        label="Descargar Resultados en Excel",
        data=output,
        file_name="facturas_procesadas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
