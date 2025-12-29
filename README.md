# 🚁 Sistema de Controle de Drone & Dashboard

Aplicação web completa para gerenciamento de operações de drones em segurança patrimonial. Permite o registro em tempo real de voos, rondas e eventos operacionais, além de oferecer um dashboard analítico robusto para tomada de decisão.

## 📋 Funcionalidades

### 🎮 Painel de Controle (Operacional)
- **Registro de Voos**: Controle de início e fim de voos com numeração automática.
- **Cronômetro de Rondas**: Monitoramento preciso do tempo de ronda por área (Perímetro, Estacionamento, etc.).
- **Eventos Operacionais**: Registro de paradas para troca de bateria ou refeição.
- **Justificativas**: Opção para justificar rondas não realizadas (ex: Chuva).

### 📊 Dashboard Analítico (Gerencial)
- **KPIs em Tempo Real**: Total de voos, horas de operação, média de tempo por ronda.
- **Evolução Temporal**: Gráficos de linha e área para volume de voos mensal e diário.
- **Mapa de Calor (Heatmap)**: Identificação visual de horários e dias de maior atividade.
- **Performance da Equipe**: Comparativo de produtividade entre operadores e Matriz de Eficiência (Volume x Velocidade).
- **Análise de Variabilidade**: Boxplot para identificar anomalias (outliers) nos tempos de ronda.
- **Data Storytelling**: Guias visuais explicativos em cada aba para facilitar a interpretação dos gráficos.

### 💾 Gerenciamento de Dados
- **Banco de Dados SQLite**: Armazenamento local seguro (`app_data.db`).
- **Backup & Restore**: Download e upload do banco de dados diretamente pela interface.
- **Exportação**: Download dos dados filtrados em CSV.
- **Importação**: Capacidade de importar dados legados via CSV.

### 🔐 Segurança
- **Autenticação**: Sistema de login para operadores e administrador.
- **Níveis de Acesso**: Apenas admin pode cadastrar novos usuários ou limpar o banco de dados.

## 🚀 Como Executar

### Pré-requisitos
- Python 3.8+
- Bibliotecas Python listadas abaixo.

### Instalação

1. Clone o repositório ou baixe os arquivos.
2. Instale as dependências necessárias:
   ```bash
   pip install streamlit pandas plotly
   ```
   *(Nota: O Python já inclui nativamente `sqlite3`, `hashlib`, `os`, `sys`, `random`, `time`, `threading`)*.

3. Execute a aplicação:
   ```bash
   streamlit run app_web_drone.py
   ```

## 📦 Criando Executável (Windows)

Para distribuir a aplicação sem necessidade de instalar Python em outras máquinas, você pode gerar um executável `.exe` usando o PyInstaller.

Execute o seguinte comando no terminal (dentro da pasta do projeto):

```bash
pyinstaller --name "DroneWebApp" --onefile --windowed --add-data "drone.png;." --add-data "app_data.db;." app_web_drone.py
```

*Certifique-se de ter o arquivo `drone.png` na pasta raiz antes de compilar.*

## 📂 Estrutura do Projeto

- `app_web_drone.py`: Código fonte principal da aplicação.
- `app_data.db`: Banco de dados SQLite (gerado automaticamente na primeira execução).
- `drone.png`: Logo/Ícone utilizado na interface.
- `README.md`: Documentação do projeto.

---
**Desenvolvido por Clayton S.Silva**
