import streamlit as st
from processor import processar_pdfs, LEGISLACOES

st.set_page_config(page_title="Comparador de Laudos Ambientais", layout="wide")

st.title("📊 Comparador de Laudos Ambientais")

legislacao = st.selectbox(
    "Selecione a legislação:",
    list(LEGISLACOES.keys())
)

limites_ativos = LEGISLACOES[legislacao]

pdfs = st.file_uploader(
    "Envie DOIS laudos em PDF",
    type=["pdf"],
    accept_multiple_files=True
)

if pdfs and len(pdfs) == 2:
    if st.button("🔍 Processar"):
        with st.spinner("Processando laudos..."):
            df_final = processar_pdfs(
                pdfs,
                limites_ativos,
                legislacao
            )

        st.success("Processamento concluído!")
        st.dataframe(df_final, use_container_width=True)

        st.download_button(
            "📥 Baixar Excel",
            data=df_final.to_excel(index=False, engine="openpyxl"),
            file_name="comparativo_laudos.xlsx"
        )
else:
    st.info("Envie exatamente DOIS arquivos PDF.")
