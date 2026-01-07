import streamlit as st
import pandas as pd
from io import BytesIO

from processor import processar_pdfs, LEGISLACOES


# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Comparador de Laudos Ambientais",
    layout="wide"
)

st.title("📊 Comparador de Laudos Ambientais")


# =========================
# SELEÇÃO DA LEGISLAÇÃO
# =========================
st.subheader("📜 Legislação")

legislacao = st.selectbox(
    "Selecione a legislação aplicável:",
    list(LEGISLACOES.keys())
)

limites_ativos = LEGISLACOES[legislacao]


# =========================
# UPLOAD DOS PDFs
# =========================
st.subheader("📂 Upload dos Laudos")

pdfs = st.file_uploader(
    "Envie EXATAMENTE DOIS laudos em PDF",
    type=["pdf"],
    accept_multiple_files=True
)


# =========================
# FUNÇÃO PARA GERAR EXCEL
# =========================
def gerar_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Comparativo")
    buffer.seek(0)
    return buffer


# =========================
# PROCESSAMENTO
# =========================
if pdfs and len(pdfs) == 2:

    if st.button("🔍 Processar laudos"):

        with st.spinner("Processando laudos, aguarde..."):
            df_final = processar_pdfs(
                pdfs,
                limites_ativos,
                legislacao
            )

        st.success("✅ Processamento concluído")

        # =========================
        # EXIBIÇÃO DA TABELA
        # =========================
        st.subheader("📊 Resultado da Comparação")
        st.dataframe(df_final, use_container_width=True)

        # =========================
        # DOWNLOAD EXCEL
        # =========================
        excel_bytes = gerar_excel(df_final)

        st.download_button(
            label="📥 Baixar comparativo em Excel",
            data=excel_bytes,
            file_name="comparativo_laudos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("ℹ️ Envie exatamente DOIS arquivos PDF para iniciar a comparação.")
