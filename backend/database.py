import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

db_name = os.getenv("DATABASE_NAME", "tenis_cleaner.db")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)

def get_db_connection():
    """Retorna uma conexão ativa com o banco SQLite com suporte a dicionários."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Cria as tabelas do sistema caso não existam e adiciona dados iniciais de demonstração."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabela de Clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Tabela de Pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        service_type TEXT NOT NULL DEFAULT 'Limpeza completa',
        pair_count INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Aguardando pagamento',
        payment_method TEXT,
        payment_status TEXT NOT NULL DEFAULT 'Pendente',
        payment_date TIMESTAMP,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completion_date TIMESTAMP,
        delivered_date TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
    );
    """)

    # Tabela de Itens do Pedido (Tênis individuais)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        brand TEXT NOT NULL,
        color_type TEXT NOT NULL, -- 'Branco' ou 'Colorido'
        details TEXT,
        before_image TEXT,
        after_image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    );
    """)

    # Tabela de Histórico e Auditoria de Pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        description TEXT,
        previous_data TEXT,
        new_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # Se a tabela de clientes estiver vazia, preencher com dados iniciais realistas
    cursor.execute("SELECT COUNT(*) as count FROM clients;")
    if cursor.fetchone()['count'] == 0:
        seed_sample_data(conn)

    conn.close()

def seed_sample_data(conn):
    """Insere dados de exemplo para demonstração e teste imediato."""
    cursor = conn.cursor()
    now = datetime.now()

    # Inserção de clientes
    clients_data = [
        ("Carlos Eduardo Silva", "67999881122"),
        ("Mariana Oliveira Santos", "67998123456"),
        ("Lucas Martins Pereira", "67997654321"),
        ("Fernanda Souza Costa", "67996549870")
    ]
    cursor.executemany("INSERT INTO clients (name, phone) VALUES (?, ?);", clients_data)
    conn.commit()

    # Pedido 1: 1 par, Lavando, Pendente (Carlos) - Iniciado hoje
    d_today = now.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO orders (client_id, service_type, pair_count, unit_price, total_price, status, payment_method, payment_status, created_at)
        VALUES (1, 'Limpeza completa', 1, 35.0, 35.0, 'Lavando', 'PIX', 'Pendente', ?);
    """, (d_today,))
    order1_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'Nike Air Force 1', 'Branco', 'Solado amarelado e couro com sujeira pesada');
    """, (order1_id,))

    # Pedido 2: 2 pares, Pronto para entrega, Pendente (Mariana) - Iniciado há 2 dias, concluído hoje
    d_two_days_ago = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO orders (client_id, service_type, pair_count, unit_price, total_price, status, payment_method, payment_status, created_at, completion_date)
        VALUES (2, 'Limpeza completa', 2, 30.0, 60.0, 'Pronto para entrega', 'PIX', 'Pendente', ?, ?);
    """, (d_two_days_ago, d_today))
    order2_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'Adidas Ultraboost', 'Colorido', 'Tecido primeknit com lama');
    """, (order2_id,))
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'Vans Old Skool', 'Branco', 'Camurça e lona encardida');
    """, (order2_id,))

    # Pedido 3: 1 par, Entregue, Pago em dinheiro (Lucas) - Finalizado e pago ontem
    d_yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO orders (client_id, service_type, pair_count, unit_price, total_price, status, payment_method, payment_status, payment_date, created_at, completion_date, delivered_date)
        VALUES (3, 'Limpeza completa', 1, 35.0, 35.0, 'Entregue', 'Dinheiro físico', 'Pago', ?, ?, ?, ?);
    """, (d_yesterday, d_two_days_ago, d_yesterday, d_yesterday))
    order3_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'Jordan 1 Retro High', 'Colorido', 'Biqueira suja e cadarços pretos');
    """, (order3_id,))

    # Pedido 4: 2 pares, Pagamento realizado, Pago via PIX hoje (Fernanda)
    cursor.execute("""
        INSERT INTO orders (client_id, service_type, pair_count, unit_price, total_price, status, payment_method, payment_status, payment_date, created_at)
        VALUES (4, 'Limpeza completa', 2, 30.0, 60.0, 'Pagamento realizado', 'PIX', 'Pago', ?, ?);
    """, (d_today, d_today))
    order4_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'Puma Suede', 'Colorido', 'Camurça azul desbotada');
    """, (order4_id,))
    cursor.execute("""
        INSERT INTO order_items (order_id, brand, color_type, details)
        VALUES (?, 'New Balance 574', 'Branco', 'Malha e entressola manchadas');
    """, (order4_id,))

    conn.commit()

if __name__ == '__main__':
    init_db()
    print("Banco de dados SQLite inicializado com sucesso!")
