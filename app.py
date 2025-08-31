# app.py - VERSÃO APRIMORADA

import os
import re
import fitz
import docx
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

# --- CONFIGURAÇÃO ---
app = Flask(__name__)
app.secret_key = 'super_secret_key' # Necessário para mensagens flash
UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated'
TEMPLATE_FOLDER = 'templates_docx'
DATABASE = 'database.db'
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    GENERATED_FOLDER=GENERATED_FOLDER,
    TEMPLATE_FOLDER=TEMPLATE_FOLDER
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(TEMPLATE_FOLDER, exist_ok=True)

# --- BANCO DE DADOS ---
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- LÓGICA DE SUBSTITUIÇÃO DE TEXTO (para manter a formatação) ---
def replace_text_in_paragraph(paragraph, key, value):
    # Esta função ajuda a manter a formatação da fonte ao substituir
    if key in paragraph.text:
        inline = paragraph.runs
        for i in range(len(inline)):
            if key in inline[i].text:
                text = inline[i].text.replace(key, value)
                inline[i].text = text

# --- LÓGICA PRINCIPAL ---
def processar_pdf(pdf_path):
    try:
        # --- MÉTODO DE EXTRAÇÃO APRIMORADO ---
        texto_extraido = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text_blocks = page.get_text("blocks")
                for block in text_blocks:
                    texto_extraido += block[4] + " "

        texto_limpo = re.sub(r'\s+', ' ', texto_extraido.replace('\n', ' '))

        # ---- LINHA DE DIAGNÓSTICO ADICIONADA ----
        print("--- TEXTO LIMPO PARA ANÁLISE REGEX ---")
        print(texto_limpo)
        print("-----------------------------------------")
        # -----------------------------------------

        dados_do_projeto = {}

        # --- Regex Refinadas (v3) ---
        padrao_tipo = r"(PROJETO DE LEI ORDINÁRIA|PROJETO DE LEI COMPLEMENTAR|PROJETO DE RESOLUÇÃO|PROJETO DE DECRETO LEGISLATIVO|PROPOSTA DE EMENDA À LEI ORGÂNICA MUNICIPAL)"
        padrao_numero = r"(?:N[º'q9]|n[oº9]|ne)\s*(\d+\s*[/]\s*\d{4})"
        padrao_data = r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})"
        padrao_ementa = r"\"\s*(Abre.*?Anual)\s*\""

        if (match := re.search(padrao_tipo, texto_limpo, re.IGNORECASE)):
            dados_do_projeto["TIPO_PROJETO"] = match.group(1).upper().strip()

        if (match := re.search(padrao_numero, texto_limpo, re.IGNORECASE)):
            dados_do_projeto["NUMERO_PROJETO"] = re.sub(r'\s', '', match.group(1))

        if (match := re.search(padrao_data, texto_limpo)):
            dados_do_projeto["DATA_PROJETO"] = match.group(1).strip()

        if (match := re.search(padrao_ementa, texto_limpo, re.IGNORECASE)):
             dados_do_projeto["EMENTA"] = f'"{match.group(1).strip()}"'

        return dados_do_projeto

    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        return {}

def gerar_docx_final(form_data, pdf_filename):
    arquivos_gerados = []
    db = get_db()
    comissoes_selecionadas = form_data.getlist('comissao_selecionada')

    for sigla in comissoes_selecionadas:
        template_path = os.path.join(app.config['TEMPLATE_FOLDER'], f"template_{sigla.lower()}.docx")
        if not os.path.exists(template_path): continue

        doc = docx.Document(template_path)
        comissao = db.execute('SELECT * FROM comissoes WHERE sigla = ?', (sigla,)).fetchone()
        membros = db.execute('SELECT * FROM membros WHERE comissao_id = ?', (comissao['id'],)).fetchall()
        relator = db.execute('SELECT * FROM membros WHERE id = ?', (form_data.get(f'relator_{sigla}'),)).fetchone()
        signatarios = [m for m in membros if m['id'] != relator['id']]

        data_parecer = datetime.strptime(form_data.get('data_parecer'), '%Y-%m-%d')

        contexto = {
            "{{TIPO_PROJETO}}": form_data.get("tipo_projeto"),
            "{{NUMERO_PROJETO}}": form_data.get("numero_projeto"),
            "{{DATA_PROJETO}}": form_data.get("data_projeto"),
            "{{EMENTA}}": form_data.get("ementa"),
            "{{AUTORIA}}": form_data.get("autoria"),
            "{{DATA_PROTOCOLO}}": datetime.strptime(form_data.get("data_protocolo"), '%Y-%m-%d').strftime('%d/%m/%Y'),
            "{{REGIME_URGENCIA}}": "EM REGIME DE URGÊNCIA," if 'regime_urgencia' in form_data else "",
            "{{TEXTO_APRESENTACAO}}": f" e apresentada como objeto de deliberação na sessão ordinária do dia {datetime.strptime(form_data.get('data_apresentacao'), '%Y-%m-%d').strftime('%d/%m/%Y')}" if 'incluir_apresentacao' in form_data and form_data.get('data_apresentacao') else ".",
            "{{NUMERO_PARECER}}": form_data.get(f'num_parecer_{sigla}'),
            "{{DATA_PARECER_EXTENSO}}": data_parecer.strftime('%d de %B de %Y').lower(),
            "{{NOME_DA_COMISSAO}}": comissao['nome'].upper(),
            "{{NOME_RELATOR}}": relator['nome'].upper(),
            "{{CARGO_RELATOR}}": relator['cargo'],
            "{{NOME_SIGNATARIO_1}}": signatarios[0]['nome'].upper() if len(signatarios) > 0 else "",
            "{{CARGO_SIGNATARIO_1}}": signatarios[0]['cargo'] if len(signatarios) > 0 else "",
            "{{NOME_SIGNATARIO_2}}": signatarios[1]['nome'].upper() if len(signatarios) > 1 else "",
            "{{CARGO_SIGNATARIO_2}}": signatarios[1]['cargo'] if len(signatarios) > 1 else "",
        }

        for p in doc.paragraphs:
            for key, value in contexto.items():
                replace_text_in_paragraph(p, key, value)
        
        nome_saida = f"Parecer_{sigla}_{form_data.get('numero_projeto', '00-0000').replace('/', '-')}.docx"
        caminho_saida = os.path.join(app.config['GENERATED_FOLDER'], nome_saida)
        doc.save(caminho_saida)
        arquivos_gerados.append(nome_saida)

        # Salva no histórico
        db.execute('INSERT INTO pareceres (pdf_name, docx_name, numero_projeto, data_geracao) VALUES (?, ?, ?, ?)',
                   (pdf_filename, nome_saida, form_data.get('numero_projeto'), datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        db.commit()

    return arquivos_gerados

# --- ROTAS ---
@app.route('/', methods=['GET'])
def index():
    db = get_db()
    historico = db.execute('SELECT * FROM pareceres ORDER BY id DESC').fetchall()
    return render_template('index.html', historico=historico)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))
    
    filename = file.filename
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(pdf_path)
    
    dados_pdf = processar_pdf(pdf_path)
    
    db = get_db()
    comissoes = db.execute('SELECT * FROM comissoes').fetchall()
    membros = db.execute('SELECT * FROM membros').fetchall()
    
    return render_template('revisar.html', dados=dados_pdf, comissoes=comissoes, membros=membros, filename=filename)

@app.route('/gerar', methods=['POST'])
def gerar():
    pdf_filename = request.form.get('pdf_filename')
    arquivos_gerados = gerar_docx_final(request.form, pdf_filename)
    return render_template('resultado.html', arquivos=arquivos_gerados)

# Rotas de download e init-db continuam as mesmas da versão anterior
@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename, as_attachment=True)

@app.cli.command('init-db')
def init_db_command():
    # ... (cole aqui a função init-db completa da mensagem anterior, com as 4 comissões)
    pass # A função completa está na mensagem anterior