import json
from datetime import datetime
from database import get_db_connection
from models.payment_model import PaymentModel

class OrderModel:
    ORDER_STATUSES = [
        'Aguardando pagamento',
        'Pagamento realizado',
        'Lavando',
        'Secando',
        'Pronto para entrega',
        'Entregue'
    ]

    @classmethod
    def create(cls, client_id: int, items: list, payment_method: str = 'PIX', payment_status: str = 'Pendente', notes: str = None, created_at: str = None):
        """
        Cria um novo pedido com um ou mais tênis (pares).
        Aplica a regra de precificação automática:
        - 1 par: R$ 35,00
        - 2 ou mais pares: R$ 30,00 por par
        """
        if not client_id:
            raise ValueError("O cliente é obrigatório para cadastrar o pedido.")

        try:
            client_id = int(client_id)
        except (ValueError, TypeError):
            raise ValueError("ID do cliente inválido.")

        if not items or len(items) == 0:
            raise ValueError("O pedido deve conter pelo menos 1 par de tênis.")

        sanitized_items = []
        for idx, item in enumerate(items):
            brand = (item.get('brand') or '').strip()
            if not brand:
                raise ValueError(f"A marca do tênis #{idx + 1} é obrigatória.")
            
            raw_color = str(item.get('color_type', 'Colorido')).strip().capitalize()
            color_type = 'Branco' if raw_color.lower() == 'branco' else 'Colorido'
            details = (item.get('details') or '').strip()

            sanitized_items.append({
                'brand': brand,
                'color_type': color_type,
                'details': details,
                'before_image': item.get('before_image', None),
                'after_image': item.get('after_image', None)
            })

        pair_count = len(sanitized_items)
        unit_price, total_price = PaymentModel.calculate_pricing(pair_count)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verificar se o cliente existe
        cursor.execute("SELECT id, name FROM clients WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        if not client:
            conn.close()
            raise ValueError("Cliente informado não foi encontrado no sistema.")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        order_created_at = created_at or now

        initial_status = 'Pagamento realizado' if payment_status == 'Pago' else 'Aguardando pagamento'
        payment_date = now if payment_status == 'Pago' else None

        cursor.execute("""
            INSERT INTO orders (
                client_id, service_type, pair_count, unit_price, total_price,
                status, payment_method, payment_status, payment_date, notes,
                created_at, updated_at
            ) VALUES (?, 'Limpeza completa', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id, pair_count, unit_price, total_price,
            initial_status, payment_method, payment_status, payment_date, notes or '',
            order_created_at, now
        ))
        order_id = cursor.lastrowid

        # Inserir itens de tênis
        for item in sanitized_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, brand, color_type, details, before_image, after_image, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                item['brand'],
                item['color_type'],
                item['details'],
                item['before_image'],
                item['after_image'],
                now
            ))

        # Registrar log no histórico
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, new_data, created_at)
            VALUES (?, 'Criação', ?, ?, ?)
        """, (
            order_id,
            f"Pedido criado com {pair_count} par(es) de tênis ({client['name']}). Total: R$ {total_price:.2f}",
            json.dumps({"pair_count": pair_count, "total": total_price, "status": initial_status}),
            now
        ))

        conn.commit()
        conn.close()

        return cls.get_by_id(order_id)

    @classmethod
    def get_all(cls, status=None, payment_status=None, client_id=None, search=None, start_date=None, end_date=None):
        """Lista pedidos com filtros opcionais de status, cliente, período e busca textual."""
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT o.*, 
                   c.name as client_name, 
                   c.phone as client_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND o.status = ?"
            params.append(status)

        if payment_status:
            query += " AND o.payment_status = ?"
            params.append(payment_status)

        if client_id:
            query += " AND o.client_id = ?"
            params.append(client_id)

        if search:
            search_term = f"%{search.strip()}%"
            query += " AND (c.name LIKE ? OR c.phone LIKE ? OR o.id LIKE ?)"
            params.extend([search_term, search_term, search_term])

        if start_date:
            query += " AND DATE(o.created_at) >= DATE(?)"
            params.append(start_date)

        if end_date:
            query += " AND DATE(o.created_at) <= DATE(?)"
            params.append(end_date)

        query += " ORDER BY o.id DESC"

        cursor.execute(query, params)
        orders = [dict(r) for r in cursor.fetchall()]

        # Buscar itens de tênis para cada pedido
        for o in orders:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (o['id'],))
            o['items'] = [dict(it) for it in cursor.fetchall()]

        conn.close()
        return orders

    @classmethod
    def get_by_id(cls, order_id: int):
        """Busca pedido detalhado por ID, com cliente, itens e histórico."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT o.*, 
                   c.name as client_name, 
                   c.phone as client_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE o.id = ?
        """, (order_id,))
        order_row = cursor.fetchone()
        if not order_row:
            conn.close()
            return None

        order = dict(order_row)

        # Buscar itens do pedido
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order_id,))
        order['items'] = [dict(r) for r in cursor.fetchall()]

        # Buscar histórico de auditoria
        cursor.execute("SELECT * FROM order_history WHERE order_id = ? ORDER BY created_at DESC", (order_id,))
        order['history'] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return order

    @classmethod
    def update_status(cls, order_id: int, new_status: str):
        """
        Atualiza o status no ciclo de vida do pedido.
        Regra fundamental:
        - A entrega do tênis está estritamente condicionada ao status 'Pago'.
        """
        if new_status not in cls.ORDER_STATUSES:
            raise ValueError(f"Status inválido. Permitidos: {cls.ORDER_STATUSES}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            raise ValueError("Pedido não encontrado.")

        old_status = order['status']

        # Validação da regra de negócio: Entrega condicionada a pagamento 'Pago'
        if new_status == 'Entregue' and order['payment_status'] != 'Pago':
            conn.close()
            raise ValueError(
                "A entrega do tênis está condicionada ao status 'Pago'. "
                "O pagamento deste pedido consta como Pendente. "
                "Por favor, confirme e registre o pagamento antes de realizar a entrega."
            )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        completion_date = order['completion_date']
        delivered_date = order['delivered_date']

        if new_status == 'Pronto para entrega' and not completion_date:
            completion_date = now

        if new_status == 'Entregue' and not delivered_date:
            delivered_date = now

        cursor.execute("""
            UPDATE orders 
            SET status = ?, 
                completion_date = ?, 
                delivered_date = ?, 
                updated_at = ?
            WHERE id = ?
        """, (new_status, completion_date, delivered_date, now, order_id))

        # Registro no histórico
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, previous_data, new_data, created_at)
            VALUES (?, 'Mudança de Status', ?, ?, ?, ?)
        """, (
            order_id,
            f"Status alterado de '{old_status}' para '{new_status}'",
            old_status,
            new_status,
            now
        ))

        conn.commit()
        conn.close()

        updated_order = cls.get_by_id(order_id)
        # Se mudou para 'Pronto para entrega', gerar informações do WhatsApp
        whatsapp_data = None
        if new_status == 'Pronto para entrega':
            whatsapp_data = PaymentModel.generate_whatsapp_info(order_id)

        return {
            "order": updated_order,
            "whatsapp_data": whatsapp_data
        }

    @classmethod
    def update_audit_full(cls, order_id: int, data: dict):
        """
        Permite modificar o histórico e campos de pedidos (auditoria/correção de erros).
        Modifica status, datas, observações, valores e itens, mantendo registro detalhado.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        old_order_row = cursor.fetchone()
        if not old_order_row:
            conn.close()
            raise ValueError("Pedido não encontrado.")

        old_order = dict(old_order_row)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Se houver mudança de status para 'Entregue', validar se está ou ficou 'Pago'
        new_status = data.get('status', old_order['status'])
        new_payment_status = data.get('payment_status', old_order['payment_status'])

        if new_status == 'Entregue' and new_payment_status != 'Pago':
            conn.close()
            raise ValueError("Não é possível definir como 'Entregue' com pagamento 'Pendente'.")

        new_payment_method = data.get('payment_method', old_order['payment_method'])
        new_created_at = data.get('created_at', old_order['created_at'])
        new_completion_date = data.get('completion_date', old_order['completion_date'])
        new_delivered_date = data.get('delivered_date', old_order['delivered_date'])
        new_notes = data.get('notes', old_order['notes'])

        # Se houver itens novos ou recalculados
        new_items = data.get('items', None)
        if new_items is not None and len(new_items) > 0:
            pair_count = len(new_items)
            unit_price, total_price = PaymentModel.calculate_pricing(pair_count)

            # Atualizar itens no banco
            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            for item in new_items:
                cursor.execute("""
                    INSERT INTO order_items (order_id, brand, color_type, details, before_image, after_image, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id,
                    item.get('brand', '').strip(),
                    item.get('color_type', 'Colorido'),
                    item.get('details', ''),
                    item.get('before_image', None),
                    item.get('after_image', None),
                    now
                ))
        else:
            pair_count = old_order['pair_count']
            unit_price = old_order['unit_price']
            total_price = data.get('total_price', old_order['total_price'])

        cursor.execute("""
            UPDATE orders 
            SET status = ?, 
                payment_status = ?, 
                payment_method = ?,
                pair_count = ?,
                unit_price = ?,
                total_price = ?,
                notes = ?,
                created_at = ?,
                completion_date = ?,
                delivered_date = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            new_status, new_payment_status, new_payment_method,
            pair_count, unit_price, total_price,
            new_notes, new_created_at, new_completion_date, new_delivered_date,
            now, order_id
        ))

        # Registrar log de auditoria
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, previous_data, new_data, created_at)
            VALUES (?, 'Auditoria / Correção Manual', ?, ?, ?, ?)
        """, (
            order_id,
            data.get('audit_reason', 'Correção de histórico de pedido'),
            json.dumps(old_order, default=str),
            json.dumps(data, default=str),
            now
        ))

        conn.commit()
        conn.close()

        return cls.get_by_id(order_id)

    @classmethod
    def save_item_images(cls, item_id: int, before_image: str = None, after_image: str = None):
        """Salva os caminhos das imagens Antes/Depois de um item de tênis."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM order_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        if not item:
            conn.close()
            raise ValueError("Item do pedido não encontrado.")

        new_before = before_image if before_image is not None else item['before_image']
        new_after = after_image if after_image is not None else item['after_image']

        cursor.execute("""
            UPDATE order_items 
            SET before_image = ?, after_image = ?
            WHERE id = ?
        """, (new_before, new_after, item_id))

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, created_at)
            VALUES (?, 'Upload de Fotos', ?, ?)
        """, (item['order_id'], f"Fotos Antes/Depois atualizadas para o item {item['brand']}", now))

        conn.commit()
        conn.close()

        return {"item_id": item_id, "before_image": new_before, "after_image": new_after}

    @classmethod
    def remove_item_photo(cls, item_id: int, photo_type: str):
        """Remove a foto de 'Antes' ou 'Depois' de um item de tênis."""
        if photo_type not in ['before', 'after']:
            raise ValueError("Tipo de foto inválido. Use 'before' ou 'after'.")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM order_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        if not item:
            conn.close()
            raise ValueError("Item do pedido não encontrado.")

        col = "before_image" if photo_type == "before" else "after_image"
        old_photo = item[col]

        cursor.execute(f"UPDATE order_items SET {col} = NULL WHERE id = ?", (item_id,))

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        label = "Antes" if photo_type == "before" else "Depois"
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, created_at)
            VALUES (?, 'Remoção de Foto', ?, ?)
        """, (item['order_id'], f"Foto '{label}' removida do item {item['brand']}", now))

        conn.commit()
        conn.close()

        return {"item_id": item_id, "removed": photo_type, "old_photo": old_photo}

    @classmethod
    def delete(cls, order_id: int):
        """Exclui um pedido e seus itens associados."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
        if not cursor.fetchone():
            conn.close()
            return False

        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        return True

    @classmethod
    def get_pipeline_counts(cls):
        """Retorna o número de pedidos em cada etapa do ciclo de vida."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM orders 
            GROUP BY status
        """)
        rows = cursor.fetchall()
        conn.close()

        counts = {s: 0 for s in cls.ORDER_STATUSES}
        for r in rows:
            if r['status'] in counts:
                counts[r['status']] = r['count']

        return counts
