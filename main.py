import os
import shutil
from datetime import datetime
from pathlib import Path
import tkinter as tk

import app.config as config
from app.utils import aplicar_icone
from pathlib import Path
import sys

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DOCS_DIR = BASE_DIR / "docs"


def criar_backup_base_dados(max_backups=20):
    """
    Cria backup da base de dados após login, mantendo no máximo max_backups pastas.
    A pasta db_backup fica sempre na mesma localização da base de dados partilhada.
    """
    try:
        origem = Path(config.DB_PATH)
        if not origem.exists():
            return

        pasta_backup = Path(config.get_backup_dir())
        pasta_backup.mkdir(parents=True, exist_ok=True)

        nome_pasta = datetime.now().strftime("%d%m%Y_%H%M%S")
        destino_dir = pasta_backup / nome_pasta
        destino_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(origem, destino_dir / "database.sqlite3")

        backups = [p for p in pasta_backup.iterdir() if p.is_dir()]
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for antigo in backups[max_backups:]:
            shutil.rmtree(antigo, ignore_errors=True)

    except Exception as exc:
        # O backup não deve impedir a entrada na aplicação.
        print(f"Erro ao criar backup da base de dados: {exc}")


def main():
    os.makedirs(config.DOCS_DIR, exist_ok=True)

    root = tk.Tk()
    aplicar_icone(root)
    root.withdraw()

    # Antes do login, garante que existe uma base de dados válida configurada.
    # Na primeira utilização, ou se o caminho deixar de existir, abre o Explorador do Windows.
    if not config.garantir_base_dados_configurada(root):
        root.destroy()
        return

    # Importar só depois de a DB_PATH estar definida.
    from app.db import init_db
    from app.login import LoginDialog
    from app.main_app import PRTWelfareApp

    init_db()

    login = LoginDialog(root)
    root.wait_window(login)

    if login.user:
        criar_backup_base_dados()
        root.deiconify()
        try:
            root.state("zoomed")
        except tk.TclError:
            root.attributes("-zoomed", True)
        app = PRTWelfareApp(root, login.user)
        root.mainloop()


if __name__ == "__main__":
    main()
