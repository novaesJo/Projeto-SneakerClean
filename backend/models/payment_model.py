import os
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import get_db_connection

# Carregar variáveis do arquivo .env
load_dotenv()

class PaymentModel:
    ALLOWED_METHODS = ['PIX', 'Dinheiro físico']
    ALLOWED_STATUSES = ['Pendente', 'Pago']
    # Lê do .env — se não encontrar, usa os valores padrão como fallback
    PIX_KEY = os.getenv("PIX_KEY", "67998570731")
    PIX_HOLDER = os.getenv("PIX_HOLDER", "João Ricardo Albuquerque Novaes")

    @staticmethod
    def calculate_pricing(pair_count: int):
        """
        Regra de Precificação (Promoção):
        - 1 par de tênis custa R$ 35,00.
        - Pedidos com 2 ou mais pares custam R$ 30,00 cada par.
        """
        pair_count = max(1, int(pair_count))
        if pair_count == 1:
            unit_price = 35.0
        else:
            unit_price = 30.0
        total_price = pair_count * unit_price
        return unit_price, total_price

    @classmethod
    def register_payment(cls, order_id: int, payment_method: str, payment_status: str = 'Pago'):
        """Registra ou atualiza o status de pagamento de um pedido."""
        if payment_status not in cls.ALLOWED_STATUSES:
            raise ValueError(f"Status de pagamento inválido. Permitidos: {cls.ALLOWED_STATUSES}")

        if payment_method and payment_method not in cls.ALLOWED_METHODS:
            raise ValueError(f"Forma de pagamento inválida. Permitidas: {cls.ALLOWED_METHODS}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            raise ValueError("Pedido não encontrado.")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payment_date = now if payment_status == 'Pago' else None

        cursor.execute("""
            UPDATE orders 
            SET payment_status = ?, 
                payment_method = COALESCE(?, payment_method),
                payment_date = COALESCE(?, payment_date),
                updated_at = ?
            WHERE id = ?
        """, (payment_status, payment_method, payment_date, now, order_id))

        # Registrar no histórico de auditoria
        cursor.execute("""
            INSERT INTO order_history (order_id, action, description, previous_data, new_data, created_at)
            VALUES (?, 'Atualização de Pagamento', ?, ?, ?, ?)
        """, (
            order_id,
            f"Pagamento alterado para {payment_status} ({payment_method or order['payment_method']})",
            f"Status: {order['payment_status']}, Método: {order['payment_method']}",
            f"Status: {payment_status}, Método: {payment_method or order['payment_method']}",
            now
        ))

        conn.commit()
        conn.close()
        return True

    @classmethod
    def validate_delivery_eligibility(cls, order_id: int):
        """
        Regra de Negócio:
        A entrega do tênis está estritamente condicionada ao status 'Pago'.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False, "Pedido não encontrado."

        if row['payment_status'] != 'Pago':
            return False, "A entrega do tênis está condicionada ao status 'Pago'. O pagamento atual está Pendente."

        return True, "Liberado para entrega."

    @classmethod
    def generate_whatsapp_info(cls, order_id: int):
        """
        Gera o texto e o link do WhatsApp para notificação do cliente:
        - Se o status de pagamento for "Pendente", a mensagem gerada deve ser exatamente:
          Olá, seus tênis estão prontos, aguardando pagamento
          Chave pix: 67998570731
          Nome: João Ricardo
          Valor: R$ {valor_total_do_pedido}
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT o.*, c.name as client_name, c.phone as client_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            WHERE o.id = ?
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            conn.close()
            raise ValueError("Pedido não encontrado.")

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = [dict(r) for r in cursor.fetchall()]
        conn.close()

        total_fmt = f"{order['total_price']:.2f}".replace('.', ',')

        if order['payment_status'] == 'Pendente':
            # Mensagem automática de cobrança / aguardando pagamento
            message = (
                f"✨Olá, seus tênis estão prontos, aguardando o pagamento!\n\n"
                f"💰 Valor: R$ {total_fmt}\n"
                f"🔑 Chave pix: {cls.PIX_KEY}\n"
                f"👤 Nome: {cls.PIX_HOLDER}"
            )
        else:
            # Mensagem quando já está pago
            message = (
                f"✨ Olá, seus tênis estão prontos para entrega/retirada!\n\n"
                f"💰 Valor: R$ {total_fmt}\n"
                f"🔑 Chave pix: {cls.PIX_KEY}\n"
                f"👤 Nome: {cls.PIX_HOLDER}"
            )

        # Montar link wa.me
        phone_clean = re_sub = "".join(filter(str.isdigit, str(order['client_phone'])))
        if not phone_clean.startswith('55') and len(phone_clean) in (10, 11):
            phone_clean = '55' + phone_clean

        encoded_text = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{phone_clean}?text={encoded_text}"

        return {
            "order_id": order_id,
            "client_name": order['client_name'],
            "client_phone": order['client_phone'],
            "formatted_phone": phone_clean,
            "payment_status": order['payment_status'],
            "total_price": order['total_price'],
            "total_formatted": total_fmt,
            "message": message,
            "whatsapp_url": whatsapp_url,
            "pix_key": cls.PIX_KEY,
            "pix_holder": cls.PIX_HOLDER,
            "items": items
        }

    @classmethod
    def get_financial_metrics(cls):
        """
        Dashboard Financeiro:
        Cálculo e exibição visual dos orçamentos/faturamentos periódicos:
        - Faturamento do Dia
        - Faturamento da Semana (últimos 7 dias)
        - Faturamento do Mês (mês corrente)
        - Métricas complementares (pendente, ticket médio, etc.)
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        week_ago_str = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
        first_day_month_str = now.strftime('%Y-%m-01 00:00:00')

        # Faturamento do Dia (pedidos pagos hoje por payment_date ou created_at se pago)
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count
            FROM orders
            WHERE payment_status = 'Pago'
              AND (
                DATE(payment_date) = DATE(?)
                OR (payment_date IS NULL AND DATE(created_at) = DATE(?))
              );
        """, (today_str, today_str))
        day_row = cursor.fetchone()
        revenue_day = float(day_row['total'])
        orders_paid_day = int(day_row['count'])

        # Faturamento da Semana (últimos 7 dias)
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count
            FROM orders
            WHERE payment_status = 'Pago'
              AND (
                payment_date >= ?
                OR (payment_date IS NULL AND created_at >= ?)
              );
        """, (week_ago_str, week_ago_str))
        week_row = cursor.fetchone()
        revenue_week = float(week_row['total'])
        orders_paid_week = int(week_row['count'])

        # Faturamento do Mês (mês atual)
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count, COALESCE(SUM(pair_count), 0) as pairs
            FROM orders
            WHERE payment_status = 'Pago'
              AND (
                payment_date >= ?
                OR (payment_date IS NULL AND created_at >= ?)
              );
        """, (first_day_month_str, first_day_month_str))
        month_row = cursor.fetchone()
        revenue_month = float(month_row['total'])
        orders_paid_month = int(month_row['count'])
        pairs_cleaned_month = int(month_row['pairs'])

        # Total a Receber (Pendente)
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count
            FROM orders
            WHERE payment_status = 'Pendente';
        """)
        pending_row = cursor.fetchone()
        pending_total = float(pending_row['total'])
        pending_count = int(pending_row['count'])

        # Total Geral Histórico Pago
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count, COALESCE(SUM(pair_count), 0) as pairs
            FROM orders
            WHERE payment_status = 'Pago';
        """)
        total_hist = cursor.fetchone()
        revenue_total = float(total_hist['total'])
        orders_total_paid = int(total_hist['count'])
        pairs_total_cleaned = int(total_hist['pairs'])

        # Breakdown por forma de pagamento
        cursor.execute("""
            SELECT payment_method, COALESCE(SUM(total_price), 0) as total, COUNT(*) as count
            FROM orders
            WHERE payment_status = 'Pago' AND payment_method IS NOT NULL
            GROUP BY payment_method;
        """)
        payment_methods_breakdown = [dict(r) for r in cursor.fetchall()]

        # Faturamento diário nos últimos 7 dias para gráfico
        daily_chart = []
        for i in range(6, -1, -1):
            day_target = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COALESCE(SUM(total_price), 0) as total, COUNT(*) as count
                FROM orders
                WHERE payment_status = 'Pago'
                  AND (
                    DATE(payment_date) = ?
                    OR (payment_date IS NULL AND DATE(created_at) = ?)
                  );
            """, (day_target, day_target))
            r = cursor.fetchone()
            # Formatar dia para 'DD/MM'
            day_label = (now - timedelta(days=i)).strftime('%d/%m')
            daily_chart.append({
                "date": day_target,
                "label": day_label,
                "amount": float(r['total']),
                "orders_count": int(r['count'])
            })

        conn.close()

        # Ticket Médio
        ticket_medio = (revenue_total / orders_total_paid) if orders_total_paid > 0 else 0.0

        return {
            "revenue_day": revenue_day,
            "orders_paid_day": orders_paid_day,
            "revenue_week": revenue_week,
            "orders_paid_week": orders_paid_week,
            "revenue_month": revenue_month,
            "orders_paid_month": orders_paid_month,
            "pairs_cleaned_month": pairs_cleaned_month,
            "pending_total": pending_total,
            "pending_count": pending_count,
            "revenue_total": revenue_total,
            "ticket_medio": round(ticket_medio, 2),
            "payment_methods_breakdown": payment_methods_breakdown,
            "daily_chart": daily_chart
        }
