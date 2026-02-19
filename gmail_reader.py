from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64
import os
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_service():
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('gmail', 'v1', credentials=creds)


def baixar_pdfs():
    service = get_service()

    query = 'subject:Boleto'

    results = service.users().messages().list(
        userId='me',
        q=query
    ).execute()

    mensagens = results.get('messages', [])

    if not mensagens:
        print("Nenhum email encontrado.")
        return

    if not os.path.exists('pdfs'):
        os.makedirs('pdfs')

    for msg in mensagens:
        detalhe = service.users().messages().get(
            userId='me',
            id=msg['id']
        ).execute()

        headers = detalhe['payload']['headers']

        remetente_valido = False
        for header in headers:
            if header['name'] == 'From' and "mettacondominios" in header['value']:
                remetente_valido = True
                break

        if not remetente_valido:
            continue

        # 📅 Pega data do email
        data_email = datetime.fromtimestamp(int(detalhe['internalDate']) / 1000)
        ano_mes = data_email.strftime("%Y_%m")

        parts = detalhe['payload'].get('parts', [])
        if not parts:
            continue

        for part in parts:
            filename = part.get('filename')

            if filename and filename.lower().endswith('.pdf'):
                attachment_id = part['body'].get('attachmentId')
                if not attachment_id:
                    continue

                attachment = service.users().messages().attachments().get(
                    userId='me',
                    messageId=msg['id'],
                    id=attachment_id
                ).execute()

                file_data = base64.urlsafe_b64decode(attachment['data'])

                novo_nome = f"{ano_mes}_Boleto.pdf"
                path = os.path.join('pdfs', novo_nome)

                with open(path, 'wb') as f:
                    f.write(file_data)

                print("PDF salvo:", novo_nome)


if __name__ == "__main__":
    baixar_pdfs()
