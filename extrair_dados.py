import io
import re
import base64
import pandas as pd
import pdfplumber
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

PALAVRAS_IGNORAR = [
    "Referente", "Unidade", "Rua", "CEP", "CNPJ",
    "Vencimento", "Total", "Boleto", "Detalhe:"
]

padrao = r'(.+?)\s*\.+\s*([\d]+\,[\d]{2})$|(.+?)\s+([\d]+\,[\d]{2})$'


def get_service(gmail_token: str = None):
    import json as _json
    if gmail_token:
        creds = Credentials.from_authorized_user_info(_json.loads(gmail_token), SCOPES)
    else:
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except FileNotFoundError:
            import streamlit as st
            creds = Credentials.from_authorized_user_info(
                _json.loads(st.secrets["GOOGLE_TOKEN"]), SCOPES
            )
    return build('gmail', 'v1', credentials=creds)


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    texto = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    return texto


def extrair_itens(texto: str, ano_mes: str) -> list:
    dados = []
    linhas = texto.split("\n")
    dentro_detalhamento = False
    processar_linha = False

    for linha in linhas:
        linha_original = linha.strip()

        if "Detalhamento da Fatura" in linha_original:
            dentro_detalhamento = True
            processar_linha = True
            continue

        if dentro_detalhamento or processar_linha:
            if (
                "SICOOB" in linha_original or
                "Não Receber" in linha_original or
                linha_original.startswith("Endereço:") or
                ("CNPJ" in linha_original and len(linha_original) > 50) or
                "Referente à Unidade" in linha_original
            ):
                processar_linha = False
                dentro_detalhamento = False
                continue

        if len(linha_original) == 0 or linha_original.startswith("---") or linha_original.startswith("==="):
            continue

        if not (dentro_detalhamento or processar_linha):
            continue

        if any(palavra in linha_original for palavra in PALAVRAS_IGNORAR):
            continue

        match = re.search(padrao, linha_original)
        if match:
            if match.group(1):
                item = match.group(1).strip()
                valor_str = match.group(2)
            else:
                item = match.group(3).strip()
                valor_str = match.group(4)

            item = re.sub(r'\.+', '', item)
            item = " ".join(item.split())

            if re.match(r'^[\d\s/]+[A-Z]*[\d\s/]*$', item) or len(item) > 50:
                continue
            if len(item) < 3 or not re.search(r'[a-zA-ZÀ-ÿ]{3,}', item):
                continue

            valor = float(valor_str.replace(",", "."))
            dados.append({"mes": ano_mes, "item": item, "valor": valor})

    return dados


def buscar_e_extrair(gmail_token: str = None):
    service = get_service(gmail_token)

    results = service.users().messages().list(
        userId='me',
        q='subject:Boleto'
    ).execute()

    mensagens = results.get('messages', [])
    if not mensagens:
        print("Nenhum email encontrado.")
        return []

    todos_dados = []

    for msg in mensagens:
        detalhe = service.users().messages().get(userId='me', id=msg['id']).execute()

        headers = detalhe['payload']['headers']
        remetente_valido = any(
            h['name'] == 'From' and "mettacondominios" in h['value']
            for h in headers
        )
        if not remetente_valido:
            continue

        data_email = datetime.fromtimestamp(int(detalhe['internalDate']) / 1000)
        ano_mes = data_email.strftime("%Y_%m")

        parts = detalhe['payload'].get('parts', [])
        for part in parts:
            filename = part.get('filename', '')
            if not filename.lower().endswith('.pdf'):
                continue

            attachment_id = part['body'].get('attachmentId')
            if not attachment_id:
                continue

            # 🔑 Busca o PDF direto em memória, sem salvar no disco
            attachment = service.users().messages().attachments().get(
                userId='me',
                messageId=msg['id'],
                id=attachment_id
            ).execute()

            pdf_bytes = base64.urlsafe_b64decode(attachment['data'])
            print(f"Processando {ano_mes} - {filename} ({len(pdf_bytes)//1024}KB) em memória...")

            texto = extrair_texto_pdf(pdf_bytes)
            itens = extrair_itens(texto, ano_mes)
            todos_dados.extend(itens)
            print(f"  → {len(itens)} itens extraídos")

    return todos_dados


if __name__ == "__main__":
    dados = buscar_e_extrair()

    if dados:
        df = pd.DataFrame(dados)
        df = df[df["item"].str.len() < 100]
        df = df[~df["item"].str.match(r'^[\d\s/R$]+$')]
        df.to_csv("dados_condominio.csv", index=False)
        print(f"\n✅ {len(df)} registros salvos em dados_condominio.csv")
    else:
        print("Nenhum dado extraído.")
