import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import time
import os
import sys
import random
import sqlite3
import plotly.express as px
import threading

# --- Configuração de Caminhos (Robusto para Script e Executável) ---
if getattr(sys, 'frozen', False):
    # Se rodando como EXE (PyInstaller), o caminho base é onde o executável está
    application_path = os.path.dirname(sys.executable)
else:
    # Se rodando como script, o caminho base é a pasta do script
    application_path = os.path.dirname(os.path.abspath(__file__))

CAMINHO_IMG = os.path.join(application_path, "drone.png")
CAMINHO_GIF = os.path.join(application_path, "gif.gif")

# --- Configuração da Página ---
st.set_page_config(page_title="Controle de Drone Web", page_icon=CAMINHO_IMG, layout="wide")

# --- Constantes e Arquivos ---
DB_FILE = os.path.join(application_path, "app_data.db")

LISTA_RONDAS = [
    "Ronda Perímetro 01",
    "Ronda Estacionamento 02",
    "Ronda Talude 03",
    "Ronda Talude 05",
    
]

# --- Controle de Concorrência ---
# RLock permite que a mesma thread adquira o bloqueio várias vezes (ex: salvar chama carregar)
DATA_LOCK = threading.RLock()

# --- SQLite Functions ---
def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados SQLite."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
    return conn

def hash_senha(senha):
    """Cria um hash SHA256 para a senha fornecida."""
    # Adiciona um 'salt' fixo para aumentar a segurança contra tabelas pré-computadas
    salt = "drone_security_v1_" 
    return hashlib.sha256((salt + senha).encode()).hexdigest()


def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem."""
    with DATA_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create 'registros' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                Voo TEXT,
                Ronda_N INTEGER,
                Ronda TEXT,
                Inicio TEXT,
                Fim TEXT,
                Duracao_Formatada TEXT,
                Status TEXT,
                Data TEXT,
                Operador TEXT
            )
        """)
        
        # Create 'usuarios' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT UNIQUE,
                senha TEXT
            )
        """)
        
        # Insert default admin user if 'usuarios' table is empty
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            admin_senha_hash = hash_senha("123456")
            cursor.execute("INSERT INTO usuarios (usuario, senha) VALUES (?, ?)", ("admin", admin_senha_hash))
        
        conn.commit()
        conn.close()

# Call init_db once at the start
init_db()

# --- Funções Auxiliares ---
def carregar_dados(raise_on_error=False):
    with DATA_LOCK:
        colunas_esperadas = ["Voo", "Ronda_N", "Ronda", "Inicio", "Fim", "Duracao_Formatada", "Status", "Data", "Operador"]
        try:
            conn = get_db_connection()
            df = pd.read_sql_query("SELECT * FROM registros", conn)
            # Ensure all expected columns are present, adding if missing
            for col in colunas_esperadas:
                if col not in df.columns:
                    df[col] = None
            return df
        except pd.io.sql.DatabaseError as e:
            msg_erro = f"Erro crítico ao carregar dados do banco: {e}"
            if raise_on_error:
                raise Exception(msg_erro) from e
            st.error(msg_erro)
            df = pd.DataFrame(columns=colunas_esperadas)
            return df
        finally:
            conn.close()

# --- Cache para o Dashboard ---
# Isso evita ler o disco a cada clique nos filtros, melhorando muito a velocidade
@st.cache_data(ttl=60)  # Cache válido por 60 segundos
def carregar_dados_dashboard():
    return carregar_dados()

def salvar_registro(novo_dado):
    with DATA_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Converte o dicionário para uma tupla para inserção, garantindo a ordem correta
            data_tuple = (
                novo_dado.get("Voo"),
                novo_dado.get("Ronda_N"),
                novo_dado.get("Ronda"),
                novo_dado.get("Inicio"),
                novo_dado.get("Fim"),
                novo_dado.get("Duracao_Formatada"),
                novo_dado.get("Status"),
                novo_dado.get("Data"),
                novo_dado.get("Operador")
            )
            cursor.execute("""
                INSERT INTO registros (Voo, Ronda_N, Ronda, Inicio, Fim, Duracao_Formatada, Status, Data, Operador)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_tuple)
            conn.commit()
            carregar_dados_dashboard.clear() # Limpa o cache para refletir o novo dado
        except sqlite3.Error as e:
            st.error(f"Erro ao salvar registro no banco de dados: {e}")
        finally:
            conn.close()

def formatar_duracao(segundos):
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def safe_rerun():
    """Função auxiliar para compatibilidade entre versões do Streamlit"""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def show_success_message(message):
    """Exibe mensagem de sucesso de forma otimizada e não bloqueante."""
    if hasattr(st, "toast"):
        st.toast(message, icon="✅")
        time.sleep(0.5) # Pequena pausa apenas para garantir que o toast seja renderizado
    else:
        st.success(message)
        time.sleep(1)

def verificar_senha(senha_fornecida, senha_hash_armazenada):
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return hash_senha(senha_fornecida) == senha_hash_armazenada

def carregar_usuarios():
    """Carrega os usuários do banco de dados."""
    with DATA_LOCK:
        conn = get_db_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM usuarios", conn)
            return df
        except pd.io.sql.DatabaseError as e:
            st.error(f"Erro ao carregar usuários do banco de dados: {e}")
            return pd.DataFrame(columns=["usuario", "senha"])
        finally:
            conn.close()

def salvar_usuario(usuario, senha):
    """Salva um novo usuário no banco de dados, verificando se já existe."""
    with DATA_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (usuario, senha) VALUES (?, ?)", (usuario, hash_senha(senha)))
            conn.commit()
            return True
        except sqlite3.IntegrityError: # Handles UNIQUE constraint violation
            return False  # Usuário já existe
        except sqlite3.Error as e:
            st.error(f"Erro ao salvar usuário no banco de dados: {e}")
            return False
        finally:
            conn.close()

# --- Componente de Cronômetro (Fragmento) ---
if hasattr(st, "fragment"):
    @st.fragment(run_every=1)
    def exibir_cronometro_ativo():
        inicio = st.session_state.get('inicio_ronda')
        if inicio:
            try:
                agora = datetime.now()
                delta_segundos = (agora - inicio).total_seconds()
                st.metric(label="Tempo da Ronda", value=formatar_duracao(delta_segundos))
            except Exception: pass

    @st.fragment
    def exibir_cronometro_estatico():
        agora = datetime.now()
        delta_segundos = (agora - st.session_state['inicio_ronda']).total_seconds()
        st.metric(label="Tempo da Ronda", value=formatar_duracao(delta_segundos))
        if st.button("🔄 Atualizar Manualmente"):
            st.rerun()

    @st.fragment(run_every=1)
    def exibir_cronometro_evento():
        inicio = st.session_state.get('inicio_evento')
        if inicio:
            try:
                agora = datetime.now()
                delta_segundos = (agora - inicio).total_seconds()
                st.metric(label="Duração do Evento", value=formatar_duracao(delta_segundos))
            except Exception: pass

# --- Autenticação Simples ---
def tentar_login(usuario, senha):
    """Tenta realizar login e retorna True se sucesso."""
    usuarios_df = carregar_usuarios()
    # Busca o usuário ignorando maiúsculas/minúsculas
    registro_usuario = usuarios_df[usuarios_df['usuario'].str.lower() == usuario.lower().strip()]

    if not registro_usuario.empty:
        senha_hash_armazenada = registro_usuario.iloc[0]['senha']
        if verificar_senha(senha, senha_hash_armazenada):
            st.session_state['logged_in'] = True
            st.session_state['usuario'] = str(registro_usuario.iloc[0]['usuario'])
            st.session_state['pedir_backup_inicial'] = True
            show_success_message("Login realizado com sucesso!")
            safe_rerun()
            return True
    return False

def check_password():
    """Retorna True se o login for bem sucedido."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image(CAMINHO_IMG, width=150)
            st.title("🔐 Acesso ao Sistema")
            
            # Formulário de Login
            with st.form("login_form"):
                usuario = st.text_input("Usuário", key="login_main_user").strip() # Remove espaços acidentais
                senha = st.text_input("Senha", type="password", key="login_main_pwd")
                submitted = st.form_submit_button("Entrar")

                if submitted:
                    if not tentar_login(usuario, senha):
                        st.error("Usuário ou senha incorretos.")

            # Formulário de Cadastro
            with st.expander("Cadastrar Novo Operador"):
                with st.form("register_form"):
                    st.info("Apenas o usuário 'admin' pode cadastrar novos operadores.")
                    novo_usuario = st.text_input("Nome do Novo Operador", key="novo_user")
                    nova_senha = st.text_input("Senha para o Novo Operador", type="password", key="nova_senha")
                    senha_admin = st.text_input("Sua Senha de Administrador ('admin')", type="password", key="admin_senha_reg")
                    
                    register_submitted = st.form_submit_button("Cadastrar Operador")

                    if register_submitted:
                        if novo_usuario and nova_senha and senha_admin:
                            usuarios_df = carregar_usuarios()
                            admin_info = usuarios_df[usuarios_df['usuario'].str.lower() == 'admin']
                            
                            if not admin_info.empty and verificar_senha(senha_admin, admin_info.iloc[0]['senha']):
                                if salvar_usuario(novo_usuario, nova_senha):
                                    st.success(f"Operador '{novo_usuario}' cadastrado! Já pode fazer login.")
                                else:
                                    st.error(f"O usuário '{novo_usuario}' já existe.")
                            else:
                                st.error("Senha de administrador incorreta. Cadastro não autorizado.")
                        else:
                            st.warning("Preencha todos os campos para cadastrar.")
        return False
    return True

def alerta_backup_inicial():
    """Exibe um alerta e botão de download logo após o login."""
    if st.session_state.get('pedir_backup_inicial'):
        with st.container():
            st.warning("⚠️ **Backup de Segurança Automático (Sugerido)**")
            st.markdown("Para evitar perda de dados caso o servidor reinicie, **baixe o backup agora**.")
            try:
                with open(DB_FILE, "rb") as f:
                    st.download_button(
                        label="⬇️ BAIXAR BACKUP AGORA (app_data.db)",
                        data=f,
                        file_name=f"backup_auto_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                        mime="application/octet-stream",
                        use_container_width=True,
                        type="primary",
                        on_click=lambda: st.session_state.update({'pedir_backup_inicial': False})
                    )
            except Exception:
                pass
            st.divider()

# --- Funções de Interface (Refatoração) ---
def renderizar_area_importacao(expandido=False):
    if not st.session_state.get('logged_in', False):
        st.info("🔒 Faça login para importar ou gerenciar dados.")
        return

    # --- Backup e Restauração do Banco de Dados (.db) ---
    st.markdown("### 💾 Backup Completo (Banco de Dados)")
    st.info("💡 Dica: Baixe o arquivo `.db` regularmente. Se o servidor online reiniciar, basta enviar o arquivo aqui para restaurar tudo.")
    
    col_db1, col_db2 = st.columns(2)
    
    with col_db1:
        st.markdown("**1. Fazer Backup**")
        try:
            with open(DB_FILE, "rb") as f:
                st.download_button(
                    label="⬇️ Baixar app_data.db",
                    data=f,
                    file_name="app_data.db",
                    mime="application/octet-stream",
                    use_container_width=True
                )
        except Exception:
            st.warning("Banco de dados ainda não disponível.")

    with col_db2:
        st.markdown("**2. Restaurar Backup**")
        uploaded_db = st.file_uploader("Carregar arquivo .db", type=["db", "sqlite"], label_visibility="collapsed")
        if uploaded_db:
            if st.button("⚠️ Confirmar Restauração", type="primary", use_container_width=True):
                with DATA_LOCK:
                    try:
                        with open(DB_FILE, "wb") as f:
                            f.write(uploaded_db.getbuffer())
                        carregar_dados_dashboard.clear()
                        st.success("Banco restaurado com sucesso! Recarregando...")
                        time.sleep(1)
                        safe_rerun()
                    except Exception as e:
                        st.error(f"Erro ao restaurar: {e}")
    
    st.divider()

    with st.expander("📥 Importar / Restaurar Backup (CSV)", expanded=expandido):
        uploaded_file = st.file_uploader("Selecione o arquivo CSV", type=["csv"], key="upload_data")
        
        if uploaded_file:
            try:
                df_upload = pd.read_csv(uploaded_file)
                # Validação básica de colunas
                cols_req = ["Voo", "Ronda_N", "Ronda", "Inicio", "Fim", "Duracao_Formatada", "Status", "Data", "Operador"]
                
                if set(cols_req).issubset(df_upload.columns):
                    st.info(f"Arquivo carregado: {len(df_upload)} registros encontrados.")
                    c_imp1, c_imp2 = st.columns(2)
                    
                    if c_imp1.button("➕ Mesclar com Existentes", use_container_width=True):
                        with DATA_LOCK:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            
                            # Otimização: Prepara os dados e usa executemany para inserção em lote
                            dados_para_inserir = df_upload[cols_req].values.tolist()
                            cursor.executemany("""
                                INSERT INTO registros (Voo, Ronda_N, Ronda, Inicio, Fim, Duracao_Formatada, Status, Data, Operador)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, dados_para_inserir)
                            
                            conn.commit()
                            conn.close()
                            carregar_dados_dashboard.clear()
                        show_success_message("Dados mesclados com sucesso!")
                        safe_rerun()
                        
                    if c_imp2.button("⚠️ Substituir Base Completa", use_container_width=True, type="primary"):
                        with DATA_LOCK:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM registros") # Clear existing data
                            
                            # Otimização: Inserção em lote
                            dados_para_inserir = df_upload[cols_req].values.tolist()
                            cursor.executemany("""
                                INSERT INTO registros (Voo, Ronda_N, Ronda, Inicio, Fim, Duracao_Formatada, Status, Data, Operador)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, dados_para_inserir)
                            
                            conn.commit()
                            conn.close()
                            carregar_dados_dashboard.clear()
                        show_success_message("Base de dados substituída!")
                        safe_rerun()
                else:
                    st.error("O arquivo não possui a estrutura correta (colunas faltando).")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

    st.divider()

    with st.expander("🗑️ Zona de Perigo (Limpeza de Dados)", expanded=False):
        st.warning("⚠️ Esta ação apagará TODOS os registros de voos e rondas. Não pode ser desfeita.")
        
        senha_confirmacao = st.text_input("Digite a senha de ADMIN para confirmar:", type="password", key="senha_limpeza")
        
        if st.button("💣 LIMPAR BANCO DE DADOS", type="primary", use_container_width=True):
            if not senha_confirmacao:
                st.warning("Digite a senha de administrador.")
            else:
                # Verificar senha do admin
                usuarios_df = carregar_usuarios()
                # Busca admin de forma segura
                admin_user = usuarios_df[usuarios_df['usuario'].str.lower() == 'admin']
                
                if not admin_user.empty:
                    senha_hash_admin = admin_user.iloc[0]['senha']
                    if verificar_senha(senha_confirmacao, senha_hash_admin):
                        with DATA_LOCK:
                            try:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM registros")
                                conn.commit()
                                conn.close()
                                carregar_dados_dashboard.clear()
                                show_success_message("Banco de dados limpo com sucesso!")
                                time.sleep(1)
                                safe_rerun()
                            except Exception as e:
                                st.error(f"Erro ao limpar banco: {e}")
                    else:
                        st.error("Senha de administrador incorreta.")
                else:
                    st.error("Erro crítico: Usuário admin não encontrado.")

def renderizar_dashboard():
    st.title("📊 Dashboard de Performance Avançado ")
    
    # Usa a função com cache para leitura rápida
    df = carregar_dados_dashboard()
    
    if df.empty:
        st.warning("Nenhum dado registrado ainda.")
        st.subheader("Gerenciamento de Dados")
        # Mostra a importação expandida para facilitar o primeiro uso
        renderizar_area_importacao(expandido=True)
        return

    # --- Pré-processamento de Dados ---
    # Converter colunas de data e hora
    df['Data_Dt'] = pd.to_datetime(df['Data'], format="%d/%m/%Y", errors='coerce')
    # Criar coluna combinada para ordenação e extração
    df['Inicio_Dt'] = pd.to_datetime(df['Data'] + ' ' + df['Inicio'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    
    # Extrair componentes de tempo
    df['Ano'] = df['Data_Dt'].dt.year
    df['Mes_Num'] = df['Data_Dt'].dt.month
    df['Mes_Nome'] = df['Data_Dt'].dt.strftime('%B') # Nome do mês
    # Mapear dias da semana para Português
    dias_map = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Data_Dt'].dt.day_name().map(dias_map)
    df['Hora'] = df['Inicio_Dt'].dt.hour

    # Converter duração para minutos
    def duracao_para_minutos(str_duracao):
        try:
            if pd.isna(str_duracao): return 0
            h, m, s = map(int, str_duracao.split(':'))
            return h * 60 + m + s / 60
        except:
            return 0
    
    df['Duracao_Min'] = df['Duracao_Formatada'].apply(duracao_para_minutos)

    # --- Filtros Laterais ---
    st.sidebar.markdown("### 🔍 Filtros do Dashboard")
    
    # Filtro de Ano
    anos_disponiveis = sorted(df['Ano'].dropna().unique())
    anos_sel = st.sidebar.multiselect("Selecione o Ano", anos_disponiveis, default=anos_disponiveis)
    
    # Filtro de Operador
    ops_disponiveis = sorted(df['Operador'].dropna().unique())
    ops_sel = st.sidebar.multiselect("Selecione o Operador", ops_disponiveis, default=ops_disponiveis)

    # Aplicar Filtros
    df_filtered = df.copy()
    if anos_sel:
        df_filtered = df_filtered[df_filtered['Ano'].isin(anos_sel)]
    if ops_sel:
        df_filtered = df_filtered[df_filtered['Operador'].isin(ops_sel)]

    if df_filtered.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
        return

    # Botão de Exportação (Nova Funcionalidade)
    csv = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Dados (CSV)",
        data=csv,
        file_name="registro_voos_web.csv",
        mime="text/csv",
    )

    # --- KPIs Principais ---
    col1, col2, col3, col4 = st.columns(4)
    
    # Voos únicos (considerando que a coluna Voo é o ID)
    total_voos = pd.to_numeric(df_filtered['Voo'], errors='coerce').nunique()
    
    # Rondas (excluindo eventos operacionais)
    total_rondas = len(df_filtered[~df_filtered['Ronda'].str.contains("EVENTO", na=False)])
    
    # Tempo total
    tempo_total_min = df_filtered['Duracao_Min'].sum()
    horas_totais = int(tempo_total_min // 60)
    
    # Média de duração de ronda (apenas concluídas)
    media_ronda = df_filtered[(df_filtered['Status'] == 'Concluído') & (~df_filtered['Ronda'].str.contains("EVENTO", na=False))]['Duracao_Min'].mean()
    if pd.isna(media_ronda): media_ronda = 0

    col1.metric("Total de Voos", total_voos)
    col2.metric("Rondas Realizadas", total_rondas)
    col3.metric("Horas de Operação", f"{horas_totais}h")
    col4.metric("Média/Ronda (min)", f"{media_ronda:.1f}")

    st.divider()

    # Organização em Abas Expandida
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Evolução Temporal", 
        "👷 Performance Operadores", 
        "🛡️ Análise de Rondas",
        "🔋 Eventos & Pausas",
        " Dados Brutos"
    ])

    with tab1:
        st.subheader("Análise Temporal")
        c1, c2 = st.columns(2)
        
        with c1:
            # Voos por Mês (Linha do Tempo)
            # Agrupar por Ano e Mês para ordenar cronologicamente
            voos_mes = df_filtered.drop_duplicates(subset=['Voo']).groupby(['Ano', 'Mes_Num'])['Voo'].count().reset_index(name='Qtd')
            voos_mes['Periodo'] = voos_mes['Mes_Num'].astype(str).str.zfill(2) + '/' + voos_mes['Ano'].astype(str)
            
            fig_mes = px.line(voos_mes, x='Periodo', y='Qtd', markers=True, title="Evolução de Voos (Mensal)")
            st.plotly_chart(fig_mes, width="stretch")
            
            # Tendência Diária (Novo)
            st.markdown("#### Tendência Diária")
            voos_dia_especifico = df_filtered.groupby('Data_Dt')['Voo'].nunique().reset_index()
            fig_dia_trend = px.area(voos_dia_especifico, x='Data_Dt', y='Voo', title="Volume Diário de Voos", markers=True)
            fig_dia_trend.update_xaxes(title="Data")
            st.plotly_chart(fig_dia_trend, width="stretch")
            
        with c2:
            # Voos por Dia da Semana
            ordem_dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            voos_dia = df_filtered.drop_duplicates(subset=['Voo']).groupby('Dia_Semana')['Voo'].count().reindex(ordem_dias).reset_index()
            
            fig_sem = px.bar(voos_dia, x='Dia_Semana', y='Voo', title="Volume de Voos por Dia da Semana", color='Voo')
            st.plotly_chart(fig_sem, width="stretch")

        st.divider()
        st.subheader("Mapa de Calor Operacional")
        st.caption("Intensidade de operações por dia da semana e horário.")
        
        # Heatmap
        heatmap_data = df_filtered.groupby(['Dia_Semana', 'Hora']).size().reset_index(name='Atividades')
        # Garantir ordem dos dias no heatmap
        heatmap_data['Dia_Semana'] = pd.Categorical(heatmap_data['Dia_Semana'], categories=ordem_dias, ordered=True)
        heatmap_data = heatmap_data.sort_values('Dia_Semana')
        
        fig_heat = px.density_heatmap(
            heatmap_data, x='Hora', y='Dia_Semana', z='Atividades', 
            nbinsx=24, color_continuous_scale='Viridis'
        )
        fig_heat.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(fig_heat, width="stretch")

    with tab2:
        st.subheader("Produtividade da Equipe")
        c1, c2 = st.columns(2)
        
        with c1:
            # Total de Voos por Operador
            voos_op = df_filtered.drop_duplicates(subset=['Voo'])['Operador'].value_counts().reset_index()
            voos_op.columns = ['Operador', 'Voos']
            fig_op = px.bar(voos_op, x='Operador', y='Voos', color='Operador', text='Voos', title="Total de Voos por Operador")
            st.plotly_chart(fig_op, width="stretch")
            
        with c2:
            # Horas Totais por Operador
            horas_op = df_filtered.groupby('Operador')['Duracao_Min'].sum().reset_index()
            horas_op['Horas'] = round(horas_op['Duracao_Min'] / 60, 1)
            fig_horas = px.bar(horas_op, x='Operador', y='Horas', color='Operador', text='Horas', title="Horas Totais em Operação")
            st.plotly_chart(fig_horas, width="stretch")
            
        st.divider()
        st.subheader("Matriz de Eficiência (Volume x Velocidade)")
        # Agrupamento para Scatter Plot
        eff_df = df_filtered[~df_filtered['Ronda'].str.contains("EVENTO", na=False)].groupby('Operador').agg(
            Rondas=('Ronda', 'count'),
            Media_Min=('Duracao_Min', 'mean')
        ).reset_index()
        
        fig_scatter = px.scatter(eff_df, x='Rondas', y='Media_Min', color='Operador', size='Rondas', 
                                 text='Operador', title="Relação: Quantidade de Rondas vs Tempo Médio",
                                 labels={'Rondas': 'Total de Rondas Realizadas', 'Media_Min': 'Tempo Médio por Ronda (min)'})
        fig_scatter.update_traces(textposition='top center')
        st.plotly_chart(fig_scatter, width="stretch")

    with tab3:
        st.subheader("Detalhamento de Rondas")
        c1, c2 = st.columns(2)
        
        with c1:
            # Rondas mais realizadas (excluindo eventos)
            rondas_df = df_filtered[~df_filtered['Ronda'].str.contains("EVENTO", na=False)]
            rondas_count = rondas_df['Ronda'].value_counts().reset_index()
            rondas_count.columns = ['Ronda', 'Qtd']
            
            fig_ronda = px.bar(rondas_count, y='Ronda', x='Qtd', orientation='h', title="Rondas Mais Frequentes")
            fig_ronda.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_ronda, width="stretch")
            
        with c2:
            # Status das Rondas
            # Simplificar status
            df_filtered['Status_Simples'] = df_filtered['Status'].apply(lambda x: 'Justificado' if 'Justificado' in x else x)
            status_count = df_filtered['Status_Simples'].value_counts().reset_index()
            status_count.columns = ['Status', 'Qtd']
            
            fig_status = px.pie(status_count, names='Status', values='Qtd', hole=0.4, title="Taxa de Conclusão vs Justificativas")
            st.plotly_chart(fig_status, width="stretch")
            
        st.divider()
        st.subheader("Variabilidade de Tempo (Boxplot)")
        st.caption("Este gráfico ajuda a identificar anomalias. Pontos fora das caixas são rondas que demoraram muito mais ou muito menos que o normal.")
        # Boxplot para ver distribuição e outliers
        rondas_validas = df_filtered[(df_filtered['Duracao_Min'] > 0) & (~df_filtered['Ronda'].str.contains("EVENTO", na=False))]
        fig_box = px.box(rondas_validas, x='Ronda', y='Duracao_Min', color='Ronda', title="Distribuição de Tempo por Tipo de Ronda")
        st.plotly_chart(fig_box, width="stretch")

    with tab4:
        st.subheader("Eventos Operacionais")
        eventos_df = df_filtered[df_filtered['Ronda'] == "EVENTO OPERACIONAL"]
        
        if not eventos_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                ev_count = eventos_df['Status'].value_counts().reset_index()
                ev_count.columns = ['Tipo', 'Qtd']
                fig_ev = px.pie(ev_count, names='Tipo', values='Qtd', title="Distribuição de Eventos")
                st.plotly_chart(fig_ev, width="stretch")
            
            with c2:
                # Duração média por tipo de evento
                ev_dur = eventos_df.groupby('Status')['Duracao_Min'].mean().reset_index()
                ev_dur.columns = ['Tipo', 'Media_Min']
                fig_ev_dur = px.bar(ev_dur, x='Tipo', y='Media_Min', text_auto='.1f', title="Duração Média (Minutos)")
                st.plotly_chart(fig_ev_dur, width="stretch")
        else:
            st.info("Nenhum evento operacional (bateria/refeição) registrado no período.")

    with tab5:
        st.subheader("Gerenciamento de Dados")
        
        renderizar_area_importacao(expandido=False)

        st.divider()
        st.subheader("Visualização dos Dados (Filtrados)")
        st.dataframe(df_filtered)

# --- Interface Principal ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # Sidebar (Menu Lateral)
    if os.path.exists(CAMINHO_GIF):
        st.sidebar.image(CAMINHO_GIF)
    else:
        st.sidebar.image(CAMINHO_IMG)
    
    # Lógica de Exibição do Usuário e Login Rápido
    if st.session_state.get('logged_in', False):
        st.sidebar.title(f"Olá, {st.session_state.get('usuario', 'Operador')}")
    else:
        st.sidebar.title("Olá, Visitante")
        st.sidebar.markdown("---")
        with st.sidebar.expander("🔐 Login Rápido", expanded=True):
            with st.form("sidebar_login"):
                u_side = st.text_input("Usuário", key="login_side_user")
                p_side = st.text_input("Senha", type="password", key="login_side_pwd")
                if st.form_submit_button("Entrar"):
                    if not tentar_login(u_side, p_side):
                        st.error("Dados inválidos")

    menu = st.sidebar.radio("Navegação", ["Dashboard / Relatórios", "Painel de Controle"])
    
    if st.session_state['logged_in']:
        alerta_backup_inicial()

    if st.session_state['logged_in']:
        if st.sidebar.button("Sair"):
            st.session_state['logged_in'] = False
            st.session_state.pop('usuario', None) # Limpa o usuário da sessão
            safe_rerun()

        if st.sidebar.button("Encerrar Plantão"):
            st.session_state['voo_ativo'] = False
            st.session_state['numero_voo_atual'] = None
            st.session_state['contador_rondas_voo'] = 0
            st.session_state['ronda_ativa'] = False
            st.session_state['evento_ativo'] = False
            st.session_state['inicio_evento'] = None
            safe_rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("Desenvolvido por Clayton S.Silva")

    # --- Lógica do Painel de Controle ---
    if menu == "Painel de Controle":
        if not check_password():
            return

        st.title("Painel de Controle de Voos")
        
        # Inicializar estados da sessão
        if 'voo_ativo' not in st.session_state:
            st.session_state['voo_ativo'] = False
            st.session_state['numero_voo_atual'] = None
            st.session_state['contador_rondas_voo'] = 0
            st.session_state['ronda_ativa'] = False
            st.session_state['inicio_ronda'] = None
            st.session_state['ronda_selecionada'] = None
            st.session_state['evento_ativo'] = False
            st.session_state['inicio_evento'] = None
            st.session_state['tipo_evento_atual'] = None

        col_esq, col_dir = st.columns([1, 1])

        with col_esq:
            st.subheader("1. Controle de Voo")
            col_v1, col_v2 = st.columns(2)

            if col_v1.button("✈️ Iniciar Novo Voo", disabled=st.session_state['voo_ativo'], use_container_width=True, type="primary"):
                df = carregar_dados(raise_on_error=False) # Leitura segura para UI
                proximo_voo_num = 1
                if not df.empty and 'Voo' in df.columns:
                    # Converte a coluna 'Voo' para números, ignorando o que não for número
                    voos_numericos = pd.to_numeric(df['Voo'], errors='coerce')
                    if not voos_numericos.isnull().all():
                        proximo_voo_num = int(voos_numericos.max()) + 1

                st.session_state['voo_ativo'] = True
                st.session_state['numero_voo_atual'] = proximo_voo_num
                st.session_state['contador_rondas_voo'] = 0
                safe_rerun()

            if col_v2.button("🛑 Finalizar Voo", disabled=not st.session_state['voo_ativo'] or st.session_state['ronda_ativa'] or st.session_state['evento_ativo'], use_container_width=True):
                show_success_message(f"Voo {st.session_state['numero_voo_atual']:02d} finalizado com {st.session_state['contador_rondas_voo']} rondas.")
                st.session_state['voo_ativo'] = False
                st.session_state['numero_voo_atual'] = None
                st.session_state['contador_rondas_voo'] = 0
                safe_rerun()

            st.divider()

            # --- Controles de Ronda (só aparecem se um voo estiver ativo) ---
            if st.session_state['voo_ativo']:
                st.subheader("2. Registro de Ronda")
                ronda = st.selectbox(
                    "Selecione a Área de Ronda:", 
                    LISTA_RONDAS, 
                    disabled=st.session_state['ronda_ativa'] or st.session_state['evento_ativo']
                )

                col_r1, col_r2 = st.columns(2)
                
                if col_r1.button("🛫 Iniciar Ronda", disabled=st.session_state['ronda_ativa'] or st.session_state['evento_ativo'], use_container_width=True):
                    st.session_state['ronda_ativa'] = True
                    st.session_state['inicio_ronda'] = datetime.now()
                    st.session_state['ronda_selecionada'] = ronda
                    safe_rerun()

                if col_r2.button("🛬 Finalizar Ronda", disabled=not st.session_state['ronda_ativa'], use_container_width=True):
                    fim = datetime.now()
                    inicio = st.session_state['inicio_ronda']
                    duracao_segundos = (fim - inicio).total_seconds()
                    st.session_state['contador_rondas_voo'] += 1
                    
                    novo_registro = {
                        "Voo": f"{st.session_state['numero_voo_atual']:02d}",
                        "Ronda_N": st.session_state['contador_rondas_voo'],
                        "Ronda": st.session_state['ronda_selecionada'],
                        "Inicio": inicio.strftime("%H:%M:%S"),
                        "Fim": fim.strftime("%H:%M:%S"),
                        "Duracao_Formatada": formatar_duracao(duracao_segundos),
                        "Status": "Concluído",
                        "Data": inicio.strftime("%d/%m/%Y"),
                        "Operador": st.session_state['usuario']
                    }
                    salvar_registro(novo_registro)
                    
                    st.session_state['ronda_ativa'] = False
                    st.session_state['inicio_ronda'] = None
                    show_success_message(f"Ronda {st.session_state['contador_rondas_voo']} registrada!")
                    safe_rerun()

                with st.expander("Justificar Ausência de Ronda"):
                    motivo = st.text_input("Motivo da justificativa", key="motivo_just")
                    if st.button("Registrar Justificativa", disabled=st.session_state['ronda_ativa'] or st.session_state['evento_ativo']):
                        if motivo:
                            st.session_state['contador_rondas_voo'] += 1
                            agora = datetime.now()
                            novo_registro = {
                                "Voo": f"{st.session_state['numero_voo_atual']:02d}",
                                "Ronda_N": st.session_state['contador_rondas_voo'],
                                "Ronda": ronda,
                                "Inicio": "--:--:--",
                                "Fim": "--:--:--",
                                "Duracao_Formatada": "00:00:00",
                                "Status": f"Justificado: {motivo}",
                                "Data": agora.strftime("%d/%m/%Y"),
                                "Operador": st.session_state['usuario']
                            }
                            salvar_registro(novo_registro)
                            show_success_message("Justificativa salva.")
                            safe_rerun()
                        else:
                            st.warning("Digite um motivo.")

            # --- Eventos Operacionais (Novos Botões) ---
            if st.session_state['voo_ativo']:
                st.divider()
                st.subheader("3. Eventos Operacionais")
                col_ev1, col_ev2 = st.columns(2)

                if st.session_state['evento_ativo']:
                    st.warning(f"⚠️ {st.session_state['tipo_evento_atual']} em andamento...")
                    st.write(f"Início: {st.session_state['inicio_evento'].strftime('%H:%M:%S')}")
                    
                    if st.button("🏁 Finalizar Evento", use_container_width=True):
                        fim = datetime.now()
                        inicio = st.session_state['inicio_evento']
                        duracao_segundos = (fim - inicio).total_seconds()
                        st.session_state['contador_rondas_voo'] += 1
                        
                        novo_registro = {
                            "Voo": f"{st.session_state['numero_voo_atual']:02d}",
                            "Ronda_N": st.session_state['contador_rondas_voo'],
                            "Ronda": "EVENTO OPERACIONAL",
                            "Inicio": inicio.strftime("%H:%M:%S"),
                            "Fim": fim.strftime("%H:%M:%S"),
                            "Duracao_Formatada": formatar_duracao(duracao_segundos),
                            "Status": st.session_state['tipo_evento_atual'],
                            "Data": inicio.strftime("%d/%m/%Y"),
                            "Operador": st.session_state['usuario']
                        }
                        salvar_registro(novo_registro)
                        st.session_state['evento_ativo'] = False
                        st.session_state['inicio_evento'] = None
                        st.session_state['tipo_evento_atual'] = None
                        show_success_message("Evento registrado!")
                        safe_rerun()

                    if hasattr(st, "fragment"):
                        exibir_cronometro_evento()
                    else:
                        agora = datetime.now()
                        delta_segundos = (agora - st.session_state['inicio_evento']).total_seconds()
                        st.metric(label="Duração do Evento", value=formatar_duracao(delta_segundos))
                        time.sleep(1)
                        safe_rerun()
                else:
                    if col_ev1.button("🔋 Iniciar Troca de Bateria", use_container_width=True, disabled=st.session_state['ronda_ativa']):
                        st.session_state['evento_ativo'] = True
                        st.session_state['tipo_evento_atual'] = "Troca de Bateria"
                        st.session_state['inicio_evento'] = datetime.now()
                        safe_rerun()
                    
                    if col_ev2.button("🍽️ Iniciar Intervalo Refeição", use_container_width=True, disabled=st.session_state['ronda_ativa']):
                        st.session_state['evento_ativo'] = True
                        st.session_state['tipo_evento_atual'] = "Intervalo Refeição"
                        st.session_state['inicio_evento'] = datetime.now()
                        safe_rerun()

        with col_dir:
            st.subheader("Status Atual")
            if st.session_state['voo_ativo']:
                st.info(f"✈️ VOO ATUAL: {st.session_state['numero_voo_atual']:02d}")
                st.metric("Rondas neste Voo", st.session_state['contador_rondas_voo'])

                if st.session_state['ronda_ativa']:
                    st.warning(f"🔴 EM RONDA: {st.session_state['ronda_selecionada']}")
                    st.write(f"Início da Ronda: {st.session_state['inicio_ronda'].strftime('%H:%M:%S')}")
                    
                    # Controle de atualização
                    auto_refresh = st.checkbox("⏱️ Atualização Automática", value=True, key="chk_auto_refresh")

                    if hasattr(st, "fragment"):
                        if auto_refresh:
                            exibir_cronometro_ativo()
                        else:
                            exibir_cronometro_estatico()
                    else:
                        # Fallback para versões antigas do Streamlit
                        agora = datetime.now()
                        delta_segundos = (agora - st.session_state['inicio_ronda']).total_seconds()
                        st.metric(label="Tempo da Ronda", value=formatar_duracao(delta_segundos))
                        
                        if auto_refresh:
                            time.sleep(1)
                            safe_rerun()
                        elif st.button("🔄 Atualizar Manualmente"):
                            safe_rerun()
                else:
                    st.success("🟢 Aguardando nova ronda...")
                    st.metric(label="Tempo da Ronda", value="0:00:00")
            else:
                st.info("Nenhum voo ativo. Clique em 'Iniciar Novo Voo' para começar.")

        # Tabela Recente
        st.divider()
        st.subheader("Registros Recentes")
        df = carregar_dados()
        if not df.empty:
            # Mostrar os últimos 10, invertido
            st.dataframe(df.tail(10).iloc[::-1])

    # --- Lógica do Dashboard ---
    elif menu == "Dashboard / Relatórios":
        renderizar_dashboard()

def run_streamlit_server():
    """Inicia o servidor Streamlit programaticamente para o executável."""
    from streamlit.web import cli as stcli
    # Simula a linha de comando: streamlit run app_web_drone.py
    sys.argv = ["streamlit", "run", __file__, "--server.port=8501", "--server.headless=true"]
    stcli.main()

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # Se estiver rodando como um executável PyInstaller
        # Verifica se já estamos rodando dentro do processo do Streamlit para evitar loop infinito
        if os.environ.get("STREAMLIT_RUNNING_PROCESS"):
            main()
        else:
            os.environ["STREAMLIT_RUNNING_PROCESS"] = "true"
            run_streamlit_server()
    else:
        # Execução normal (streamlit run app_web_drone.py)
        main()


#  pyinstaller --name "DroneWebApp" --onefile --windowed --add-data "drone.png;." --add-data "app_data.db;." app_web_drone.py




