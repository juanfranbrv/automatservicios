import streamlit as st

# Configuración de la página
st.set_page_config(page_title="💻 Gestión de Facturas", layout="wide")

# Título principal
st.title("💻 Gestión de Facturas de Servicios")

# Widgets en la barra lateral
st.sidebar.header("Sube tus facturas")
luz_file = st.sidebar.file_uploader("Factura de Luz", type="pdf", key="luz")
agua_file = st.sidebar.file_uploader("Factura de Agua", type="pdf", key="agua")
internet_file = st.sidebar.file_uploader("Factura de Internet", type="pdf", key="internet")
gas_file = st.sidebar.file_uploader("Factura de Gas", type="pdf", key="gas")

# Mostrar mensaje de confirmación para cada archivo subido
if luz_file:
    st.sidebar.success("Factura de Luz subida correctamente.")
if agua_file:
    st.sidebar.success("Factura de Agua subida correctamente.")
if internet_file:
    st.sidebar.success("Factura de Internet subida correctamente.")
if gas_file:
    st.sidebar.success("Factura de Gas subida correctamente.")

# Visualización de archivos subidos en el cuerpo principal
st.header("Resumen de archivos subidos")
uploaded_files = {
    "Luz": luz_file,
    "Agua": agua_file,
    "Internet": internet_file,
    "Gas": gas_file
}

for service, file in uploaded_files.items():
    if file:
        st.write(f"**{service}:** {file.name} subido correctamente.")
    else:
        st.write(f"**{service}:** No se ha subido ninguna factura.")

