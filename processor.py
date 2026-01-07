import pdfplumber
import re
import pandas as pd
import unicodedata

# =========================
# LEGISLAÇÕES
# =========================
LIMITES_DN_COPAM = {
    "Demanda Bioquímica de Oxigênio (DBO)": 60.0,
    "Demanda Química de Oxigênio (DQO)": 180.0,
    "Sólidos Suspensos Totais": 100.0,
    "Sólidos Sedimentáveis": 1.0,
    "Óleos e Graxas": 20.0,
    "Fósforo total": 0.1,
    "Nitrogênio Amoniacal Total": 3.7,
    "Surfactantes Aniônicos (Detergentes)": 0.5,
    "pH": (5.0, 9.0),
    "Temperatura da Amostra": 40.0
}

LIMITES_CONAMA_430 = {
    "Demanda Bioquímica de Oxigênio (DBO)": 120.0,
    "Sólidos Suspensos Totais": 100.0,
    "Sólidos Sedimentáveis": 1.0,
    "Óleos e Graxas": 100.0,
    "pH": (5.0, 9.0),
    "Temperatura da Amostra": 40.0
}

LEGISLACOES = {
    "DN COPAM (MG)": LIMITES_DN_COPAM,
    "CONAMA 430/2011": LIMITES_CONAMA_430
}

# =========================
# FUNÇÕES AUXILIARES
# =========================
def ler_linhas(pdf):
    linhas = []
    with pdfplumber.open(pdf) as p:
        for page in p.pages:
            texto = page.extract_text()
            if texto:
                linhas.extend(texto.split("\n"))
    return linhas


def extrair_amostra_tipo(linhas):
    for l in linhas:
        m = re.search(r'(?:Nº )?Amostra:\s*(\d+)-\d+/\d+\.\d+', l)
        if m:
            amostra = m.group(1)
            tipo = "Saída" if "Saída" in l else "Entrada" if "Entrada" in l else None
            return amostra, tipo
    return None, None


def extrair_resultados(linhas):
    dados = []

    rx_geral = re.compile(
        r'^(?P<analise>.+?)\s+'
        r'(?P<resultado><\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*'
        r'(?P<unidade>mg/L|mL/L|ºC)\b',
        re.IGNORECASE
    )

    rx_ph = re.compile(r'^(pH)\s+(\d+(?:[.,]\d+)?)', re.IGNORECASE)

    for l in linhas:
        l = l.strip()
        if not l:
            continue

        m_ph = rx_ph.match(l)
        if m_ph:
            dados.append({
                "Analise": "pH",
                "Resultado": float(m_ph.group(2).replace(",", ".")),
                "Unidade": "-"
            })
            continue

        m = rx_geral.match(l)
        if m:
            dados.append({
                "Analise": m.group("analise").strip(),
                "Resultado": m.group("resultado").replace(",", ".").replace(" ", ""),
                "Unidade": m.group("unidade")
            })

    return pd.DataFrame(dados).drop_duplicates(subset=["Analise", "Unidade"])


def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt


def buscar_limite_legal(analise, limites):
    nome = normalizar(analise)

    for chave, limite in limites.items():
        chave_norm = normalizar(chave)

        # Correspondência flexível (contém OU é contido)
        if chave_norm in nome or nome in chave_norm:
            return limite

    return None

def avaliar_conformidade(analise, valor, limites):
    limite = buscar_limite_legal(analise, limites)

    if limite is None or valor is None:
        return None, "Avaliar"

    try:
        v = float(str(valor).replace(",", ".").replace("<", ""))
        if isinstance(limite, tuple):
            return limite, "Conforme" if limite[0] <= v <= limite[1] else "Não Conforme"
        return limite, "Conforme" if v <= limite else "Não Conforme"
    except:
        return limite, "Avaliar"


def processar_pdfs(pdfs, limites, nome_legislacao):
    dfs = []

    for pdf in pdfs:
        linhas = ler_linhas(pdf)
        amostra, tipo = extrair_amostra_tipo(linhas)
        df = extrair_resultados(linhas)

        col = f"Amostra {amostra} ({tipo})"
        df[col] = df["Resultado"]
        df = df.drop(columns=["Resultado"])
        dfs.append(df)

    df_final = dfs[0]
    for df in dfs[1:]:
        df_final = pd.merge(df_final, df, on=["Analise", "Unidade"], how="outer")

    limites_col = []
    situacoes = []

    saida_col = next((c for c in df_final.columns if "Saída" in c), None)

    for _, row in df_final.iterrows():
        valor = row[saida_col] if saida_col else None
        limite, sit = avaliar_conformidade(row["Analise"], valor, limites)
        limites_col.append(limite)
        situacoes.append(sit)

    df_final["Limite Legal"] = limites_col
    df_final["Situação"] = situacoes
    df_final["Legislação"] = nome_legislacao

    return df_final

