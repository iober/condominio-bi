import pdfplumber

pdf = pdfplumber.open('pdfs/2026_01_Boleto.pdf')
print(f'Total de páginas: {len(pdf.pages)}')

for i, pagina in enumerate(pdf.pages):
    texto = pagina.extract_text()
    if 'Taxa' in texto or 'Corsan' in texto or 'Consumo' in texto:
        print(f'\n=== Página {i} ===')
        linhas = [l for l in texto.split('\n') if 'Taxa' in l or 'Corsan' in l or 'Consumo' in l or 'Água' in l or 'água' in l or 'Agua' in l]
        for linha in linhas[:15]:
            print(repr(linha))
