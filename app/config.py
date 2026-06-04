import json
import os
import sys
from pathlib import Path
from tkinter import filedialog, messagebox

APP_NAME = "PRT Welfare"


def _runtime_dirs():
    """
    Em desenvolvimento:
        raiz do projeto

    Compilado:
        pasta onde está o executável
    """
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
        return app_dir, app_dir

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base_dir, base_dir


APP_DIR, BASE_DIR = _runtime_dirs()
DOCS_DIR = os.path.join(BASE_DIR, "docs")
FAVICON_PATH = os.path.join(DOCS_DIR, "favico.ico")

# Configuração local fica junto ao executável/app local.
CONFIG_PATH = os.path.join(APP_DIR, "prt_welfare_config.json")
DB_FILENAME = "database.sqlite3"
DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)


def _ler_config_local():
    try:
        if not os.path.exists(CONFIG_PATH):
            return {}
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_config_local(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def set_db_path(caminho):
    global DB_PATH
    DB_PATH = os.path.abspath(caminho)
    return DB_PATH


def get_backup_dir():
    """
    A pasta db_backup fica sempre ao lado da base de dados.
    """
    return os.path.join(os.path.dirname(DB_PATH), "db_backup")


def garantir_base_dados_configurada(parent=None):
    """
    Garante que existe uma base de dados configurada localmente.
    Se não existir ou se o caminho guardado deixar de ser válido,
    pede ao utilizador para escolher o ficheiro database.sqlite3.
    """
    config = _ler_config_local()
    caminho_guardado = config.get("database_path")

    if caminho_guardado and os.path.exists(caminho_guardado):
        set_db_path(caminho_guardado)
        return True

    while True:
        messagebox.showinfo(
            "Base de dados",
            "Selecione a localização da base de dados database.sqlite3.",
            parent=parent,
        )

        caminho = filedialog.askopenfilename(
            parent=parent,
            title="Selecionar base de dados PRT Welfare",
            filetypes=[
                ("Base de dados SQLite", "*.sqlite3"),
                ("Todos os ficheiros", "*.*"),
            ],
        )

        if not caminho:
            return False

        if os.path.basename(caminho).lower() != DB_FILENAME.lower():
            continuar = messagebox.askyesno(
                "Confirmar base de dados",
                "O ficheiro selecionado não se chama database.sqlite3.\n\nQueres usar este ficheiro na mesma?",
                parent=parent,
            )
            if not continuar:
                continue

        if not os.path.exists(caminho):
            messagebox.showerror("Erro", "A base de dados selecionada não existe.", parent=parent)
            continue

        set_db_path(caminho)
        config["database_path"] = DB_PATH
        _guardar_config_local(config)
        return True



COR_PRINCIPAL = "#0b4b52"
COR_PRINCIPAL_ESCURO = "#083b41"
COR_WEEKEND = "#d8f1f4"
COR_FERIAS = "#78dafa"
COR_BRANCO = "#ffffff"
COR_LINHA = "#b7b7b7"
COR_LINHA_INTERNA = "#a6a6a6"
COR_AZUL_REFEICAO = "#1f73e8"
COR_EMENTA = "#008f3a"
COR_OBS = "#111111"
COR_VERMELHO = "#b90f12"
COR_CINZA = "#777777"

MASTER_NIM = "admin"
MASTER_PASSWORD = "Bangui123#"

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

REFEICOES = ["Almoço", "Jantar"]

POSTOS = [
    "OF-6", "OF-5", "OF-4", "OF-3", "OF-2", "OF-1",
    "OR-9", "OR-8", "OR-7", "OR-6", "OR-5", "OR-4", "OR-3", "OR-2", "OR-1"
]

TIPOS_ACESSO = [
    "Administrador",
    "Gestão Welfare Mensal",
    "Gestão Ementa",
    "Gestão Welfare Individual",
    "Leitura",
    "Pessoal/Gestão Férias",
]

TIPOS_WELFARE = {
    "Welfare": ["cooking.png"],
    "Welfare Livre": ["cooking.png", "star.png"],
    "Welfare Aniversário": ["cooking.png", "cake.png"],
    "Welfare Outros": ["cooking.png", "cookingtree-dots.png"],
}


TIPOS_ACESSO_DESCRICAO = {
    "Administrador": "Acesso total",
    "Gestão Welfare Mensal": "Elabora o plano mensal de Welfare.",
    "Gestão Ementa": "Adiciona a ementa ao plano mensal de Welfare.",
    "Gestão Welfare Individual": "Gere os Welfares Individuais do contingente.",
    "Leitura": "Acesso em modo de Leitura/Consulta.",
    "Pessoal/Gestão Férias": "Gere as férias do pessoal do contingente.",
}

ACESSOS_EDITAM_WELFARES_MENSAIS = {"Administrador", "Gestão Welfare Mensal"}
ACESSOS_APAGAM_WELFARES_MENSAIS = {"Administrador", "Gestão Welfare Mensal"}
ACESSOS_EDITAM_EMENTAS_MENSAIS = {"Administrador", "Gestão Welfare Mensal", "Gestão Ementa"}

ACESSOS_VEEM_BOTAO_EDITAR_WELFARES_MENSAIS = {"Administrador", "Gestão Welfare Mensal", "Gestão Ementa"}


ACESSOS_EDITAM_WELFARES_INDIVIDUAIS = {"Administrador", "Gestão Welfare Individual"}
ACESSOS_VEEM_WELFARES_INDIVIDUAIS = {"Administrador", "Gestão Welfare Individual", "Leitura"}
ACESSOS_GEREM_FERIAS = {"Administrador", "Pessoal/Gestão Férias"}
