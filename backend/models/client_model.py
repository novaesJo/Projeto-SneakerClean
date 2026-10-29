import re
from datetime import datetime
from database import get_db_connection

class ClientModel:
    @staticmethod
    def _clean_phone(phone):
        """Remove caracteres não numéricos do telefone."""
        if not phone:
            return ""
        return re.sub(r'\D', '', str(phone))

    @classmethod
    def create(cls, name, phone):
        """Cria um novo cliente no banco."""
        name = (name or "").strip()
        phone_clean = cls._clean_phone(phone)

        if not name:
            raise ValueError("O nome do cliente é obrigatório.")
        if len(phone_clean) < 10:
            raise ValueError("O telefone/WhatsApp deve conter pelo menos 10 dígitos (DDD + número).")

        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            "INSERT INTO clients (name, phone, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, phone_clean, now, now)
        )
        conn.commit()
        client_id = cursor.lastrowid
        conn.close()

        return cls.get_by_id(client_id)

    @classmethod
    def get_all(cls, search=None):
        """Lista todos os clientes com suporte a busca por nome ou telefone e resumo de pedidos."""
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT c.*, 
                   COUNT(o.id) as total_orders,
                   COALESCE(SUM(CASE WHEN o.payment_status = 'Pago' THEN o.total_price ELSE 0 END), 0) as total_spent,
                   COALESCE(SUM(CASE WHEN o.payment_status = 'Pendente' THEN o.total_price ELSE 0 END), 0) as pending_amount
            FROM clients c
            LEFT JOIN orders o ON c.id = o.client_id
        """
        params = []

        if search:
            search_term = f"%{search.strip()}%"
            query += " WHERE c.name LIKE ? OR c.phone LIKE ?"
            params.extend([search_term, search_term])

        query += " GROUP BY c.id ORDER BY c.name ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        clients = [dict(row) for row in rows]
        conn.close()
        return clients

    @classmethod
    def get_by_id(cls, client_id):
        """Recupera um cliente específico pelo ID com seu histórico de pedidos."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        client = dict(row)

        # Buscar pedidos deste cliente
        cursor.execute("""
            SELECT id, service_type, pair_count, total_price, status, payment_status, payment_method, created_at, completion_date
            FROM orders
            WHERE client_id = ?
            ORDER BY created_at DESC
        """, (client_id,))
        client['orders'] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return client

    @classmethod
    def update(cls, client_id, name, phone):
        """Atualiza nome e telefone de um cliente."""
        name = (name or "").strip()
        phone_clean = cls._clean_phone(phone)

        if not name:
            raise ValueError("O nome do cliente é obrigatório.")
        if len(phone_clean) < 10:
            raise ValueError("O telefone/WhatsApp deve conter pelo menos 10 dígitos (DDD + número).")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM clients WHERE id = ?", (client_id,))
        if not cursor.fetchone():
            conn.close()
            return None

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "UPDATE clients SET name = ?, phone = ?, updated_at = ? WHERE id = ?",
            (name, phone_clean, now, client_id)
        )
        conn.commit()
        conn.close()

        return cls.get_by_id(client_id)

    @classmethod
    def delete(cls, client_id):
        """Exclui um cliente e seus pedidos associados."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM clients WHERE id = ?", (client_id,))
        if not cursor.fetchone():
            conn.close()
            return False

        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        conn.close()
        return True
