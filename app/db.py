import calendar
import sqlite3

from app.config import DB_PATH, MASTER_NIM, MASTER_PASSWORD, TIPOS_ACESSO
from app.security import hash_password, verificar_password


def _connect():
    """Ligação SQLite com timeout maior para uso em pasta partilhada.

    Não muda o formato da base de dados. Apenas evita falhas/esperas curtas
    quando outro posto está temporariamente a escrever.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error:
        pass
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS welfares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            refeicao TEXT NOT NULL,
            tipo TEXT NOT NULL,
            prato TEXT,
            sobremesa TEXT,
            observacao TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(data, refeicao)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS utilizadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nim TEXT NOT NULL UNIQUE,
            posto TEXT,
            nome TEXT,
            sobrenome TEXT,
            data_chegada TEXT,
            data_partida TEXT,
            antiguidade TEXT,
            snr INTEGER DEFAULT 0,
            telemovel_servico TEXT,
            responsavel_welfare INTEGER DEFAULT 0,
            tipo_acesso TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            master INTEGER DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migração automática para bases de dados criadas antes do campo antiguidade.
    cur.execute("PRAGMA table_info(utilizadores)")
    colunas_utilizadores = {row[1] for row in cur.fetchall()}
    if "antiguidade" not in colunas_utilizadores:
        cur.execute("ALTER TABLE utilizadores ADD COLUMN antiguidade TEXT")
    if "snr" not in colunas_utilizadores:
        cur.execute("ALTER TABLE utilizadores ADD COLUMN snr INTEGER DEFAULT 0")
    if "telemovel_servico" not in colunas_utilizadores:
        cur.execute("ALTER TABLE utilizadores ADD COLUMN telemovel_servico TEXT")
    if "responsavel_welfare" not in colunas_utilizadores:
        cur.execute("ALTER TABLE utilizadores ADD COLUMN responsavel_welfare INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS utilizadores_acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilizador_id INTEGER NOT NULL,
            tipo_acesso TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(utilizador_id, tipo_acesso),
            FOREIGN KEY(utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
        )
    """)

    # Migração dos nomes antigos dos tipos de acesso para os nomes atuais.
    acessos_migracao = {
        "Escrita 1": "Gestão Welfare Mensal",
        "Escrita 2": "Gestão Ementa",
        "Escrita 3": "Gestão Welfare Individual",
        "Leitura 1": "Leitura",
        "Leitura 2": "Leitura",
    }
    for antigo, novo in acessos_migracao.items():
        cur.execute("SELECT utilizador_id FROM utilizadores_acessos WHERE tipo_acesso = ?", (antigo,))
        for (utilizador_id,) in cur.fetchall():
            cur.execute("""
                INSERT OR IGNORE INTO utilizadores_acessos (utilizador_id, tipo_acesso)
                VALUES (?, ?)
            """, (utilizador_id, novo))
        cur.execute("DELETE FROM utilizadores_acessos WHERE tipo_acesso = ?", (antigo,))
        cur.execute(
            "UPDATE utilizadores SET tipo_acesso = REPLACE(tipo_acesso, ?, ?)",
            (antigo, novo)
        )


    cur.execute("""
        CREATE TABLE IF NOT EXISTS welfares_individuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilizador_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            refeicao TEXT NOT NULL,
            marcado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(utilizador_id, data, refeicao),
            FOREIGN KEY(utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            chave TEXT PRIMARY KEY,
            valor TEXT,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS day_offs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            observacao TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ferias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilizador_id INTEGER NOT NULL,
            data_hora_inicio TEXT NOT NULL,
            data_hora_fim TEXT NOT NULL,
            observacao TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
        )
    """)



    cur.execute("""
        CREATE TABLE IF NOT EXISTS meses_trancados (
            mes TEXT PRIMARY KEY,
            trancado INTEGER NOT NULL DEFAULT 0,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Índices para acelerar leituras mensais em SQLite, sobretudo em pasta partilhada.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_welfares_data ON welfares(data)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_welfares_individuais_mes ON welfares_individuais(data)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_welfares_individuais_user_data ON welfares_individuais(utilizador_id, data)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ferias_periodo ON ferias(data_hora_inicio, data_hora_fim)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ferias_user ON ferias(utilizador_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_utilizadores_partida ON utilizadores(data_partida)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_utilizadores_ordenacao ON utilizadores(posto, antiguidade, sobrenome, nome)")

    salt, pwd_hash = hash_password(MASTER_PASSWORD)

    cur.execute("""
        INSERT OR IGNORE INTO utilizadores (
            nim, posto, nome, sobrenome, data_chegada, data_partida, antiguidade, snr,
            telemovel_servico, responsavel_welfare,
            tipo_acesso, password_salt, password_hash, master
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        MASTER_NIM,
        "",
        "Administrador",
        "Mestre",
        "",
        "",
        "",
        0,
        "",
        0,
        "Administrador",
        salt,
        pwd_hash,
    ))

    # Migração automática: copia o antigo campo tipo_acesso para a nova tabela multi-acesso.
    cur.execute("SELECT id, tipo_acesso, master FROM utilizadores")
    for user_id, tipo_acesso, master in cur.fetchall():
        if master:
            cur.execute("""
                INSERT OR IGNORE INTO utilizadores_acessos (utilizador_id, tipo_acesso)
                VALUES (?, ?)
            """, (user_id, "Administrador"))
        elif tipo_acesso:
            for acesso in str(tipo_acesso).split(","):
                acesso = acesso.strip()
                if acesso in TIPOS_ACESSO:
                    cur.execute("""
                        INSERT OR IGNORE INTO utilizadores_acessos (utilizador_id, tipo_acesso)
                        VALUES (?, ?)
                    """, (user_id, acesso))

    conn.commit()
    conn.close()


def db_rows(query, params=()):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def db_one(query, params=()):
    rows = db_rows(query, params)
    return rows[0] if rows else None


def db_execute(query, params=()):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()


def db_execute_return_id(query, params=()):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_utilizador_acessos(utilizador_id):
    rows = db_rows("""
        SELECT tipo_acesso
        FROM utilizadores_acessos
        WHERE utilizador_id = ?
        ORDER BY
            CASE tipo_acesso
                WHEN 'Administrador' THEN 1
                WHEN 'Gestão Welfare Mensal' THEN 2
                WHEN 'Gestão Ementa' THEN 3
                WHEN 'Gestão Welfare Individual' THEN 4
                WHEN 'Leitura' THEN 5
                WHEN 'Gestão Férias' THEN 6
                ELSE 99
            END
    """, (utilizador_id,))
    return [row["tipo_acesso"] for row in rows]


def set_utilizador_acessos(utilizador_id, acessos):
    acessos_validos = [a for a in acessos if a in TIPOS_ACESSO]

    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM utilizadores_acessos WHERE utilizador_id = ?", (utilizador_id,))

    for acesso in acessos_validos:
        cur.execute("""
            INSERT OR IGNORE INTO utilizadores_acessos (utilizador_id, tipo_acesso)
            VALUES (?, ?)
        """, (utilizador_id, acesso))

    tipo_legacy = ", ".join(acessos_validos) if acessos_validos else "Leitura"
    cur.execute("UPDATE utilizadores SET tipo_acesso = ? WHERE id = ?", (tipo_legacy, utilizador_id))

    conn.commit()
    conn.close()


def atualizar_password_utilizador(utilizador_id, password):
    salt, pwd_hash = hash_password(password)
    db_execute("""
        UPDATE utilizadores
        SET password_salt = ?, password_hash = ?
        WHERE id = ?
    """, (salt, pwd_hash, utilizador_id))


def enriquecer_user_com_acessos(user):
    if not user:
        return None

    acessos = get_utilizador_acessos(user["id"])

    if user.get("master") and "Administrador" not in acessos:
        acessos.insert(0, "Administrador")

    if not acessos and user.get("tipo_acesso"):
        acessos = [a.strip() for a in str(user["tipo_acesso"]).split(",") if a.strip()]

    user["acessos"] = acessos
    user["tipo_acesso"] = ", ".join(acessos) if acessos else user.get("tipo_acesso", "")
    return user


def autenticar_utilizador(nim, password):
    user = db_one("SELECT * FROM utilizadores WHERE nim = ?", (nim.strip(),))

    if not user:
        return None

    if verificar_password(password, user["password_salt"], user["password_hash"]):
        return enriquecer_user_com_acessos(user)

    return None



def get_snr_utilizadores():
    """Devolve todos os utilizadores marcados como SNR/Sénior, excluindo o utilizador mestre."""
    return db_rows("""
        SELECT *
        FROM utilizadores
        WHERE master = 0 AND COALESCE(snr, 0) = 1
        ORDER BY
            CASE posto
                WHEN 'OF-6' THEN 1
                WHEN 'OF-5' THEN 2
                WHEN 'OF-4' THEN 3
                WHEN 'OF-3' THEN 4
                WHEN 'OF-2' THEN 5
                WHEN 'OF-1' THEN 6
                WHEN 'OR-9' THEN 7
                WHEN 'OR-8' THEN 8
                WHEN 'OR-7' THEN 9
                WHEN 'OR-6' THEN 10
                WHEN 'OR-5' THEN 11
                WHEN 'OR-4' THEN 12
                WHEN 'OR-3' THEN 13
                WHEN 'OR-2' THEN 14
                WHEN 'OR-1' THEN 15
                ELSE 99
            END,
            CASE
                WHEN antiguidade IS NULL OR TRIM(antiguidade) = '' THEN '9999-12-31'
                ELSE SUBSTR(antiguidade, 1, 10)
            END ASC,
            sobrenome COLLATE NOCASE,
            nome COLLATE NOCASE
    """)


def _ativo_hoje_sql_condicao(alias=""):
    prefixo = f"{alias}." if alias else ""
    return f"({prefixo}data_partida IS NULL OR TRIM({prefixo}data_partida) = '' OR SUBSTR({prefixo}data_partida, 1, 10) >= ?)"


def get_snr_utilizadores_ativos():
    """Devolve SNR ativos hoje, excluindo mestre, ordenados por posto e antiguidade."""
    from datetime import date
    hoje = date.today().isoformat()
    return db_rows("""
        SELECT *
        FROM utilizadores
        WHERE master = 0
          AND COALESCE(snr, 0) = 1
          AND (data_partida IS NULL OR TRIM(data_partida) = '' OR SUBSTR(data_partida, 1, 10) >= ?)
        ORDER BY
            CASE posto
                WHEN 'OF-6' THEN 1
                WHEN 'OF-5' THEN 2
                WHEN 'OF-4' THEN 3
                WHEN 'OF-3' THEN 4
                WHEN 'OF-2' THEN 5
                WHEN 'OF-1' THEN 6
                WHEN 'OR-9' THEN 7
                WHEN 'OR-8' THEN 8
                WHEN 'OR-7' THEN 9
                WHEN 'OR-6' THEN 10
                WHEN 'OR-5' THEN 11
                WHEN 'OR-4' THEN 12
                WHEN 'OR-3' THEN 13
                WHEN 'OR-2' THEN 14
                WHEN 'OR-1' THEN 15
                ELSE 99
            END,
            CASE
                WHEN antiguidade IS NULL OR TRIM(antiguidade) = '' THEN '9999-12-31'
                ELSE SUBSTR(antiguidade, 1, 10)
            END ASC,
            sobrenome COLLATE NOCASE,
            nome COLLATE NOCASE
    """, (hoje,))


def get_snr_unico_ativo_para_assinatura():
    seniors = get_snr_utilizadores_ativos()
    return seniors[0] if len(seniors) == 1 else None


def get_responsaveis_welfare_ativos():
    """Devolve responsáveis Welfare ativos hoje, excluindo mestre, ordenados por posto e antiguidade."""
    from datetime import date
    hoje = date.today().isoformat()
    return db_rows("""
        SELECT *
        FROM utilizadores
        WHERE master = 0
          AND COALESCE(responsavel_welfare, 0) = 1
          AND (data_partida IS NULL OR TRIM(data_partida) = '' OR SUBSTR(data_partida, 1, 10) >= ?)
        ORDER BY
            CASE posto
                WHEN 'OF-6' THEN 1
                WHEN 'OF-5' THEN 2
                WHEN 'OF-4' THEN 3
                WHEN 'OF-3' THEN 4
                WHEN 'OF-2' THEN 5
                WHEN 'OF-1' THEN 6
                WHEN 'OR-9' THEN 7
                WHEN 'OR-8' THEN 8
                WHEN 'OR-7' THEN 9
                WHEN 'OR-6' THEN 10
                WHEN 'OR-5' THEN 11
                WHEN 'OR-4' THEN 12
                WHEN 'OR-3' THEN 13
                WHEN 'OR-2' THEN 14
                WHEN 'OR-1' THEN 15
                ELSE 99
            END,
            CASE
                WHEN antiguidade IS NULL OR TRIM(antiguidade) = '' THEN '9999-12-31'
                ELSE SUBSTR(antiguidade, 1, 10)
            END ASC,
            sobrenome COLLATE NOCASE,
            nome COLLATE NOCASE
    """, (hoje,))


def get_responsavel_welfare_mais_antigo_ativo():
    responsaveis = get_responsaveis_welfare_ativos()
    return responsaveis[0] if responsaveis else None

def get_snr_unico_para_assinatura():
    # Compatibilidade: agora só considera SNR ativos hoje.
    return get_snr_unico_ativo_para_assinatura()

def get_welfares_mes(ano, mes):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = f"{ano}-{mes:02d}-01"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    rows = db_rows("""
        SELECT *
        FROM welfares
        WHERE data BETWEEN ? AND ?
        ORDER BY data,
            CASE refeicao
                WHEN 'Almoço' THEN 1
                WHEN 'Jantar' THEN 2
                ELSE 3
            END
    """, (inicio, fim))

    dados = {}
    for row in rows:
        dados.setdefault(row["data"], []).append(row)

    return dados


def get_welfare(data_str, refeicao):
    return db_one("""
        SELECT *
        FROM welfares
        WHERE data = ? AND refeicao = ?
    """, (data_str, refeicao))


def guardar_welfare(data_str, refeicao, tipo, prato, sobremesa, observacao):
    db_execute("""
        INSERT INTO welfares (
            data, refeicao, tipo, prato, sobremesa, observacao
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(data, refeicao)
        DO UPDATE SET
            tipo = excluded.tipo,
            prato = excluded.prato,
            sobremesa = excluded.sobremesa,
            observacao = excluded.observacao
    """, (
        data_str,
        refeicao,
        tipo,
        prato,
        sobremesa,
        observacao,
    ))


def eliminar_welfare(data_str, refeicao):
    db_execute("""
        DELETE FROM welfares
        WHERE data = ? AND refeicao = ?
    """, (data_str, refeicao))


def get_utilizadores_ativos_para_welfare_individual():
    """
    Devolve utilizadores ativos para a grelha de Welfare Individual.
    Exclui o utilizador mestre.
    Ativo = sem data de partida ou data de partida >= hoje.
    """
    from datetime import date

    hoje = date.today().isoformat()

    return db_rows("""
        SELECT *
        FROM utilizadores
        WHERE master = 0
          AND (
                data_partida IS NULL
                OR TRIM(data_partida) = ''
                OR data_partida >= ?
          )
        ORDER BY
            CASE posto
                WHEN 'OF-6' THEN 1
                WHEN 'OF-5' THEN 2
                WHEN 'OF-4' THEN 3
                WHEN 'OF-3' THEN 4
                WHEN 'OF-2' THEN 5
                WHEN 'OF-1' THEN 6
                WHEN 'OR-9' THEN 7
                WHEN 'OR-8' THEN 8
                WHEN 'OR-7' THEN 9
                WHEN 'OR-6' THEN 10
                WHEN 'OR-5' THEN 11
                WHEN 'OR-4' THEN 12
                WHEN 'OR-3' THEN 13
                WHEN 'OR-2' THEN 14
                WHEN 'OR-1' THEN 15
                ELSE 99
            END,
            CASE
                WHEN antiguidade IS NULL OR TRIM(antiguidade) = '' THEN '9999-12-31'
                ELSE SUBSTR(antiguidade, 1, 10)
            END ASC,
            sobrenome COLLATE NOCASE,
            nome COLLATE NOCASE
    """, (hoje,))


def get_welfares_individuais_mes(ano, mes):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = f"{ano}-{mes:02d}-01"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    rows = db_rows("""
        SELECT utilizador_id, data, refeicao, marcado
        FROM welfares_individuais
        WHERE data BETWEEN ? AND ?
    """, (inicio, fim))

    dados = {}
    for row in rows:
        dados[(row["utilizador_id"], row["data"], row["refeicao"])] = int(row["marcado"])

    return dados


def set_welfare_individual(utilizador_id, data_str, refeicao, marcado):
    db_execute("""
        INSERT INTO welfares_individuais (
            utilizador_id, data, refeicao, marcado, atualizado_em
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(utilizador_id, data, refeicao)
        DO UPDATE SET
            marcado = excluded.marcado,
            atualizado_em = CURRENT_TIMESTAMP
    """, (
        utilizador_id,
        data_str,
        refeicao,
        1 if marcado else 0,
    ))



def reset_welfares_individuais_mes(ano, mes):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = f"{ano}-{mes:02d}-01"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    db_execute("""
        DELETE FROM welfares_individuais
        WHERE data BETWEEN ? AND ?
    """, (inicio, fim))


def get_setting(chave, default=""):
    row = db_one("SELECT valor FROM app_settings WHERE chave = ?", (chave,))
    if not row:
        return default
    return row.get("valor") if row.get("valor") is not None else default


def set_setting(chave, valor):
    db_execute("""
        INSERT INTO app_settings (chave, valor, atualizado_em)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chave)
        DO UPDATE SET
            valor = excluded.valor,
            atualizado_em = CURRENT_TIMESTAMP
    """, (chave, str(valor)))


def get_valor_welfare():
    return get_setting("valor_welfare", "")


def set_valor_welfare(valor):
    set_setting("valor_welfare", valor)


def get_day_offs(mostrar_todos=False):
    from datetime import date

    hoje = date.today().isoformat()

    if mostrar_todos:
        return db_rows("""
            SELECT *
            FROM day_offs
            ORDER BY data DESC
        """)

    return db_rows("""
        SELECT *
        FROM day_offs
        WHERE data >= ?
        ORDER BY data DESC
    """, (hoje,))


def get_day_off(day_off_id):
    return db_one("SELECT * FROM day_offs WHERE id = ?", (day_off_id,))


def guardar_day_off(data_str, observacao="", day_off_id=None):
    if day_off_id:
        db_execute("""
            UPDATE day_offs
            SET data = ?, observacao = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (data_str, observacao, day_off_id))
    else:
        db_execute("""
            INSERT INTO day_offs (data, observacao, atualizado_em)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(data)
            DO UPDATE SET
                observacao = excluded.observacao,
                atualizado_em = CURRENT_TIMESTAMP
        """, (data_str, observacao))


def eliminar_day_off(day_off_id):
    db_execute("DELETE FROM day_offs WHERE id = ?", (day_off_id,))


def get_day_offs_mes(ano, mes):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = f"{ano}-{mes:02d}-01"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    rows = db_rows("""
        SELECT data
        FROM day_offs
        WHERE data BETWEEN ? AND ?
    """, (inicio, fim))

    return {row["data"] for row in rows}


def get_nome_cos():
    return get_setting("nome_cos", "")

def set_nome_cos(nome):
    set_setting("nome_cos", nome)


def get_inicio_semana():
    return get_setting("inicio_semana", "")


def set_inicio_semana(data_str):
    set_setting("inicio_semana", data_str or "")


def get_lingua():
    return get_setting("lingua", "pt")


def set_lingua(valor):
    valor = valor if valor in ("pt", "en") else "pt"
    set_setting("lingua", valor)



def get_ferias(mostrar_todas=False):
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d %H:%M")
    if mostrar_todas:
        return db_rows("""
            SELECT f.*, u.posto, u.nome, u.sobrenome, u.antiguidade
            FROM ferias f
            JOIN utilizadores u ON u.id = f.utilizador_id
            ORDER BY f.data_hora_inicio DESC
        """)
    return db_rows("""
        SELECT f.*, u.posto, u.nome, u.sobrenome, u.antiguidade
        FROM ferias f
        JOIN utilizadores u ON u.id = f.utilizador_id
        WHERE f.data_hora_fim >= ?
        ORDER BY f.data_hora_inicio DESC
    """, (hoje,))


def get_feria(feria_id):
    return db_one("""
        SELECT f.*, u.posto, u.nome, u.sobrenome
        FROM ferias f
        JOIN utilizadores u ON u.id = f.utilizador_id
        WHERE f.id = ?
    """, (feria_id,))


def guardar_feria(utilizador_id, data_hora_inicio, data_hora_fim, observacao="", feria_id=None):
    if feria_id:
        db_execute("""
            UPDATE ferias
            SET utilizador_id = ?, data_hora_inicio = ?, data_hora_fim = ?,
                observacao = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (utilizador_id, data_hora_inicio, data_hora_fim, observacao, feria_id))
    else:
        db_execute("""
            INSERT INTO ferias (utilizador_id, data_hora_inicio, data_hora_fim, observacao, atualizado_em)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (utilizador_id, data_hora_inicio, data_hora_fim, observacao))


def eliminar_feria(feria_id):
    db_execute("DELETE FROM ferias WHERE id = ?", (feria_id,))


def get_ferias_mes(ano, mes):
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = f"{ano}-{mes:02d}-01 00:00"
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d} 23:59"
    rows = db_rows("""
        SELECT *
        FROM ferias
        WHERE data_hora_inicio <= ? AND data_hora_fim >= ?
        ORDER BY utilizador_id, data_hora_inicio
    """, (fim, inicio))
    dados = {}
    for row in rows:
        dados.setdefault(row["utilizador_id"], []).append(row)
    return dados


def normalizar_mes_chave(ano, mes):
    return f"{int(ano):04d}-{int(mes):02d}"


def is_mes_trancado(ano, mes):
    chave = normalizar_mes_chave(ano, mes)
    row = db_one("SELECT trancado FROM meses_trancados WHERE mes = ?", (chave,))
    return bool(row and int(row.get("trancado") or 0) == 1)


def set_mes_trancado(ano, mes, trancado):
    chave = normalizar_mes_chave(ano, mes)
    db_execute("""
        INSERT INTO meses_trancados (mes, trancado, atualizado_em)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(mes)
        DO UPDATE SET
            trancado = excluded.trancado,
            atualizado_em = CURRENT_TIMESTAMP
    """, (chave, 1 if trancado else 0))
