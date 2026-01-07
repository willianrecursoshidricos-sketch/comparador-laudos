from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import io

from processor import processar_pdfs, LEGISLACOES

app = FastAPI(
    title="API – Comparador de Laudos Ambientais",
    version="1.0.0"
)

@app.post("/processar")
async def processar_laudos(
    legislacao: str = Form(...),
    pdfs: list[UploadFile] = File(...)
):
    if len(pdfs) != 2:
        return {"erro": "Envie exatamente 2 arquivos PDF."}

    if legislacao not in LEGISLACOES:
        return {"erro": "Legislação inválida."}

    arquivos = []
    for pdf in pdfs:
        conteudo = await pdf.read()
        caminho = pdf.filename
        with open(caminho, "wb") as f:
            f.write(conteudo)
        arquivos.append(caminho)

    df = processar_pdfs(
        arquivos,
        LEGISLACOES[legislacao],
        legislacao
    )

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=comparativo_laudos.xlsx"}
    )
