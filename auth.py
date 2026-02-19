from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def autenticar():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES
    )

    creds = flow.run_local_server(
        host='127.0.0.1',
        port=8080,
        open_browser=True
    )

    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    print("Autenticado com sucesso!")

if __name__ == '__main__':
    autenticar()
