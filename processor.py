import pdfplumber
import re
import pandas as pd
import unicodedata


# =========================
# LEGISLAÇÕES
# =========================
LIMITES_DN_COPAM = {
    "Demanda Bioquímica de Oxigênio": 60.0,
    "Demanda Química de Oxigênio": 180.0,
    "Sólidos Suspensos Totais": 100.0,
    "Sólidos Sedimentáveis": 1.0,
    "Óleos e Graxas": 20.0,
    "Fósforo total": 0.1,
    "Nitrogênio Amoniacal Total": 3.7,
    "Surfactantes Aniônicos": 0.5,
    "pH": (5.0, 9.0),
    "Temperatura da Amostra": 40.0
}

LIMITES_CONAMA_430 = {
    "Demanda Bioquímica de Oxigênio": 120.0,
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
# FUNÇÕES BÁSICAS
# =========================
def ler_linhas(pdf):
    linhas = []
    with pdfplumber.open(pdf) as p:
        for page in p.pages:
            texto = page.extract_text()
            if texto:
                linhas.extend(texto.split("\n"))
    return linhas


def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt


def extrair_amostra_tipo(linhas):
    amostra = None
    tipo = None

    for l in linhas:
        m = re.search(r'(?:Nº )?Amostra:\s*(\d+)-', l)
        if m:
            amostra = m.group(1)

        if "Saída" in l:
            tipo = "Saída"
        elif "Entrada" in l:
            tipo = "Entrada"

    return amostra, tipo


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

        if rx_ph.match(l):
            m = rx_ph.match(l)
            dados.append({
                "Analise": "pH",
                "Resultado": float(m.group(2).replace(",", ".")),
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

    return pd.DataFrame(dados).drop_duplicates()


# =========================
# AVALIAÇÕES
# =========================
def buscar_limite(analise, limites):
    nome = normalizar(analise)
    for chave, limite in limites.items():
        if normalizar(chave) in nome or nome in normalizar(chave):
            return limite
    return None


def avaliar_conformidade(analise, valor, limites):
    limite = buscar_limite(analise, limites)

    if limite is None or valor is None:
        return None, "Avaliar"

    try:
        v = float(str(valor).replace("<", "").replace(",", "."))

        if isinstance(limite, tuple):
            return limite, "Conforme" if limite[0] <= v <= limite[1] else "Não Conforme"

        return limite, "Conforme" if v <= limite else "Não Conforme"

    except:
        return limite, "Avaliar"


def calcular_remocao(df, parametro, limite_percentual):
    entrada = None
    saida = None

    for _, row in df.iterrows():
        if parametro in row["Analise"]:
            for col in df.columns:
                if "Entrada" in col:
                    entrada = row[col]
                elif "Saída" in col:
                    saida = row[col]

    try:
        entrada = float(str(entrada).replace("<", "").replace(",", "."))
        saida = float(str(saida).replace("<", "").replace(",", "."))

        if entrada <= 0:
            return None, None, "Avaliar"

        remocao = ((entrada - saida) / entrada) * 100
        situacao = "Conforme" if remocao >= limite_percentual else "Não Conforme"

        return round(remocao, 2), limite_percentual, situacao

    except:
        return None, None, "Avaliar"


# =========================
# FUNÇÃO PRINCIPAL
# =========================
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

    saida_col = next((c for c in df_final.columns if "Saída" in c), None)

    limites_legais = []
    situacoes = []

    for _, row in df_final.iterrows():
        valor = row[saida_col] if saida_col else None
        limite, sit = avaliar_conformidade(row["Analise"], valor, limites)
        limites_legais.append(limite)
        situacoes.append(sit)

    df_final["Limite Legal"] = limites_legais
    df_final["Situação"] = situacoes
    df_final["Legislação"] = nome_legislacao


    # =========================
    # EFICIÊNCIAS (%)
    # =========================
    eficiencias = [
        ("Eficiência de Remoção de DBO", "Demanda Bioquímica de Oxigênio", 75.0),
        ("Eficiência de Remoção de DQO", "Demanda Química de Oxigênio", 80.0),
    ]

    for nome, parametro, limite in eficiencias:
        valor, lim, sit = calcular_remocao(df_final, parametro, limite)

        if valor is not None:
            linha = {
                "Analise": nome,
                "Unidade": "%",
                "Limite Legal": lim,
                "Situação": sit,
                "Legislação": nome_legislacao
            }

            for col in df_final.columns:
                if col.startswith("Amostra"):
                    linha[col] = ""

            col_valor = next(c for c in df_final.columns if c.startswith("Amostra"))
            linha[col_valor] = valor

            df_final = pd.concat(
                [df_final, pd.DataFrame([linha])],
                ignore_index=True
            )

    return df_final


