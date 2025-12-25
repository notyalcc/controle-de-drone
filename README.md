# 🚁 Controle de Drone Web

Sistema de gestão operacional para equipes de segurança com drones. O aplicativo permite o registro de voos, cronometragem de rondas e análise de performance dos operadores através de dashboards interativos.

## 📋 Funcionalidades

- **Controle de Voo:** Registro de início e fim de voos e rondas.
- **Cronômetro:** Monitoramento em tempo real da duração das rondas.
- **Gestão de Ocorrências:** Registro de pausas (bateria, refeição) e justificativas.
- **Dashboard:** Gráficos interativos (Plotly) para análise de produtividade e tendências.
- **Autenticação:** Sistema de login para operadores e admin.
- **Banco de Dados:** Armazenamento local em SQLite com suporte a backup/restore.

## 🛠️ Tecnologias Utilizadas

- Python 3
- Streamlit (Interface Web)
- Pandas (Manipulação de Dados)
- Plotly (Gráficos)
- SQLite (Banco de Dados)

## 🚀 Como Rodar Localmente

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
