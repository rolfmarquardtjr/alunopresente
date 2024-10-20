import os
import streamlit as st
import sqlite3
import pandas as pd
import pywhatkit
import io
from datetime import datetime
import base64
import time
from PIL import Image
from io import BytesIO

# Configuração da página Streamlit
st.set_page_config(page_title="Sistema de Presença")

# Função para inicializar o banco de dados e criar tabelas se não existirem
def inicializar_banco_de_dados():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    # Criar tabela de usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Criar tabela de configuração
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_template TEXT NOT NULL
        )
    ''')

    # Criar tabela de logs de presença
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno TEXT NOT NULL,
            serie TEXT NOT NULL,
            data TEXT NOT NULL,
            responsavel TEXT,
            numero TEXT,
            status TEXT NOT NULL,
            resposta TEXT
        )
    ''')

    # Inserir usuários admin padrão se eles não existirem
    c.execute("SELECT * FROM users WHERE username='Marcelo'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES ('Marcelo', 'Edu2024')")
        c.execute("INSERT INTO users (username, password) VALUES ('Simone', '300190')")
        conn.commit()

    # Inserir um modelo de mensagem padrão se ele não existir
    c.execute("SELECT * FROM config WHERE id=1")
    if not c.fetchone():
        c.execute("INSERT INTO config (message_template) VALUES ('Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje.')")
        conn.commit()

    conn.close()

# Inicializa o banco de dados
inicializar_banco_de_dados()

# Função para melhorar o layout
def set_page_style():
    st.markdown(
        """
        <style>
        .reportview-container {
            background: #f4f4f4;
        }
        .sidebar .sidebar-content {
            background: #004466;
            color: white;
        }
        h1 {
            color: #004466;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Função para enviar mensagens em lote via PyWhatKit
from time import sleep

def enviar_mensagens_lote(mensagens):
    intervalo = 10  # Intervalo fixo de 10 segundos entre os envios
    try:
        for i, msg in enumerate(mensagens):
            st.info(f"Enviando mensagem para {msg['numero']} ({i + 1}/{len(mensagens)})...")
            try:
                # Enviar mensagem usando pywhatkit
                pywhatkit.sendwhatmsg_instantly(f"+{msg['numero']}", msg['mensagem'], wait_time=10, tab_close=True, close_time=5)
                st.success(f"Mensagem enviada para {msg['numero']} com sucesso!")
                sleep(intervalo)  # Intervalo definido pelo backend para garantir que a mensagem seja enviada antes da próxima
            except Exception as e:
                st.error(f"Erro ao enviar mensagem para {msg['numero']}: {e}")
        return {'status': 'sucesso', 'mensagem': 'Todas as mensagens foram enviadas com sucesso'}
    except Exception as e:
        return {'status': 'erro', 'mensagem': f'Erro ao enviar mensagens: {e}'}

# Conexão ao banco de dados SQLite usando "with" para garantir que a conexão seja fechada corretamente
def registrar_presenca(aluno, serie, data, responsavel, numero, status):
    try:
        with sqlite3.connect('attendance.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO attendance_log (aluno, serie, data, responsavel, numero, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (aluno, serie, data, responsavel, numero, status))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Erro ao registrar presença: {e}")

# Função principal do Streamlit para rodar a interface
def run_streamlit():
    set_page_style()
    st.title("Sistema de Presença e Mensagens Automáticas")

    # Página de Login
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.header("Login")
        username = st.text_input("Usuário", placeholder="Digite seu usuário")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        if st.button("Entrar"):
            with sqlite3.connect('attendance.db') as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
                user = c.fetchone()
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(f"Bem-vindo, {username}!")
                else:
                    st.error("Usuário ou senha inválidos")
    else:
        st.sidebar.header(f"Bem-vindo, {st.session_state['username']}")

        # Adicionar botão de logout no sidebar
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

        # Menu lateral para navegação
        page = st.sidebar.selectbox("Escolha a página", ["Página Principal", "Configurações", "Exportar/Importar Alunos", "Exportar Logs", "Mensagens Recebidas", "Editar Aluno"])

        if page == "Página Principal":
            # Página principal com calendário e série
            st.header("Registro de Presença")

            current_date = st.date_input("Selecione a data", datetime.now())
            if current_date.weekday() in (5, 6):
                st.error("Finais de semana não são permitidos.")
            else:
                # Carregar e exibir séries e alunos
                file_path = 'alunos_atualizados.xlsx'
                df = pd.read_excel(file_path)
                series = df['série'].unique()
                selected_series = st.selectbox("Selecione a série", series)
                selected_students = df[df['série'] == selected_series]

                st.subheader(f"Alunos da Série {selected_series}")
                attendance = {}
                for i, row in selected_students.iterrows():
                    responsavel = row['responsavel'] if not pd.isna(row['responsavel']) else 'N/A'
                    attendance[row['Nome do Aluno']] = st.checkbox(f"{row['Nome do Aluno']} - Responsável: {responsavel}")

                if st.button("Enviar Mensagens"):
                    # Pegar mensagem template do banco
                    with sqlite3.connect('attendance.db') as conn:
                        c = conn.cursor()
                        c.execute("SELECT message_template FROM config WHERE id=1")
                        template = c.fetchone()
                        if template:
                            template = template[0]
                        else:
                            template = "Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje."

                    # Criar lista de mensagens para enviar
                    mensagens = []
                    for aluno, faltou in attendance.items():
                        if faltou:
                            responsavel = selected_students[selected_students['Nome do Aluno'] == aluno]['responsavel'].values[0]
                            numero = selected_students[selected_students['Nome do Aluno'] == aluno]['Celular responsável'].values[0]
                            if pd.isna(numero):
                                st.warning(f"Mensagem não enviada para {aluno}. Número de telefone faltando.")
                            else:
                                try:
                                    numero = str(int(numero))  # Converte o número para string sem ponto decimal
                                    mensagem = template.replace("{nome_aluno}", aluno).replace("{nome_responsavel}", responsavel)
                                    mensagens.append({'numero': numero, 'mensagem': mensagem})
                                except ValueError:
                                    st.warning(f"Número de telefone inválido para {aluno}. Não foi possível preparar a mensagem.")

                    # Enviar todas as mensagens em lote
                    if mensagens:
                        resultado = enviar_mensagens_lote(mensagens)
                        if resultado['status'] == 'sucesso':
                            st.success("Todas as mensagens foram enviadas com sucesso!")
                            # Registrar log de presença no banco de dados
                            for msg in mensagens:
                                registrar_presenca(msg['mensagem'].split(' ')[-2], selected_series, str(current_date), msg['mensagem'].split(' ')[1], msg['numero'], "Mensagem enviada")
                        else:
                            st.error(f"Erro ao enviar mensagens: {resultado['mensagem']}")

        elif page == "Configurações":
            # Página de configuração
            st.header("Configurações de Mensagens")

            # Carregar o modelo de mensagem atual
            with sqlite3.connect('attendance.db') as conn:
                c = conn.cursor()
                c.execute("SELECT message_template FROM config WHERE id=1")
                template = c.fetchone()

            # Verificar se o template já existe
            if template:
                template = template[0]
            else:
                template = "Prezado {nome_responsavel}, informamos que o aluno {nome_aluno} esteve ausente na data de hoje."

            # Exibir área para editar a mensagem
            new_template = st.text_area("Modelo de mensagem", template)

            # Salvar o modelo de mensagem atualizado
            if st.button("Salvar Modelo"):
                with sqlite3.connect('attendance.db') as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM config WHERE id=1")
                    if c.fetchone():
                        c.execute("UPDATE config SET message_template = ? WHERE id = 1", (new_template,))
                    else:
                        c.execute("INSERT INTO config (message_template) VALUES (?)", (new_template,))
                    conn.commit()
                st.success("Modelo de mensagem atualizado com sucesso!")

        elif page == "Exportar/Importar Alunos":
            # Página para exportar ou importar planilhas
            st.header("Exportar ou Importar Alunos")
            file_path = 'alunos_atualizados.xlsx'

            if st.button("Exportar Planilha de Alunos"):
                df = pd.read_excel(file_path)
                df.to_excel('alunos_exportados.xlsx', index=False)
                st.success("Planilha exportada com sucesso.")

            uploaded_file = st.file_uploader("Importar nova planilha de alunos", type="xlsx")
            if uploaded_file:
                df_new = pd.read_excel(uploaded_file)
                df_new.to_excel(file_path, index=False)
                st.success("Nova planilha importada com sucesso!")

        elif page == "Exportar Logs":
            # Página para exportar logs de presença
            st.header("Exportar Logs de Presença")

            selected_date = st.date_input("Selecione a data dos logs", datetime.now())
            selected_series = st.text_input("Digite a série (ex: 1A, 2B)")

            if st.button("Exportar Logs"):
                with sqlite3.connect('attendance.db') as conn:
                    query = "SELECT * FROM attendance_log WHERE data = ? AND serie = ?"
                    logs = pd.read_sql_query(query, conn, params=(str(selected_date), selected_series))

                if logs.empty:
                    st.warning("Nenhum log encontrado para a data e série selecionada.")
                else:
                    # Gerar o arquivo Excel para download
                    log_file = io.BytesIO()
                    logs.to_excel(log_file, index=False)
                    log_file.seek(0)

                    st.download_button(
                        label="Baixar Logs",
                        data=log_file,
                        file_name=f'logs_{selected_series}_{selected_date}.xlsx',
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success(f"Logs exportados com sucesso.")

        elif page == "Mensagens Recebidas":
            # Página para exibir mensagens recebidas
            st.header("Mensagens Recebidas")

            # Certifique-se de abrir a conexão com o banco de dados
           
