/**
 * dashboard.js - Lógica do Dashboard Financeiro e Indicadores Visuais
 * SneakerClean - Gestão de Limpeza de Tênis
 */

const Dashboard = {
    metrics: null,

    async init() {
        await this.loadMetrics();
    },

    async loadMetrics() {
        try {
            const data = await API.getDashboardMetrics();
            this.metrics = data;
            this.renderKPIs(data.financial);
            this.renderChart(data.financial.daily_chart);
            this.renderPipelineProgress(data.pipeline);
            this.renderSneakerStats(data.sneaker_stats);
            this.renderRecentOrders(data.recent_orders);
        } catch (err) {
            console.error("Erro ao carregar dados do dashboard:", err);
            Utils.showToast("Falha ao atualizar dados do dashboard.", "danger");
        }
    },

    renderKPIs(fin) {
        if (!fin) return;

        // Faturamento do Dia
        const elRevDay = document.getElementById('kpi-rev-day');
        if (elRevDay) elRevDay.textContent = Utils.formatCurrency(fin.revenue_day);

        const elOrdersDay = document.getElementById('kpi-orders-day');
        if (elOrdersDay) elOrdersDay.textContent = `${fin.orders_paid_day} pedido(s) pago(s) hoje`;

        // Faturamento da Semana
        const elRevWeek = document.getElementById('kpi-rev-week');
        if (elRevWeek) elRevWeek.textContent = Utils.formatCurrency(fin.revenue_week);

        const elOrdersWeek = document.getElementById('kpi-orders-week');
        if (elOrdersWeek) elOrdersWeek.textContent = `${fin.orders_paid_week} pedido(s) nos últimos 7 dias`;

        // Faturamento do Mês
        const elRevMonth = document.getElementById('kpi-rev-month');
        if (elRevMonth) elRevMonth.textContent = Utils.formatCurrency(fin.revenue_month);

        const elOrdersMonth = document.getElementById('kpi-orders-month');
        if (elOrdersMonth) elOrdersMonth.textContent = `${fin.orders_paid_month} pedido(s) • ${fin.pairs_cleaned_month} par(es)`;

        // Total a Receber (Pendente)
        const elPending = document.getElementById('kpi-pending-total');
        if (elPending) elPending.textContent = Utils.formatCurrency(fin.pending_total);

        const elPendingCount = document.getElementById('kpi-pending-count');
        if (elPendingCount) elPendingCount.textContent = `${fin.pending_count} pedido(s) aguardando pagamento`;
    },

    renderChart(dailyData) {
        const container = document.getElementById('dashboard-bar-chart');
        if (!container || !dailyData || dailyData.length === 0) return;

        const maxVal = Math.max(...dailyData.map(d => d.amount), 50);

        container.innerHTML = dailyData.map(d => {
            const heightPercent = Math.max(5, Math.round((d.amount / maxVal) * 100));
            return `
                <div class="bar-col">
                    <div class="bar-tooltip">
                        <strong>${Utils.formatCurrency(d.amount)}</strong><br>
                        ${d.orders_count} pedido(s)
                    </div>
                    <div class="bar-pill" style="height: ${heightPercent}%;"></div>
                    <span class="bar-label">${d.label}</span>
                </div>
            `;
        }).join('');
    },

    renderPipelineProgress(pipe) {
        const container = document.getElementById('pipeline-progress-container');
        if (!container || !pipe) return;

        const totalActive = Object.values(pipe).reduce((a, b) => a + b, 0) || 1;

        const stages = [
            { key: 'Aguardando pagamento', color: '#D97706', label: 'Aguardando Pagamento' },
            { key: 'Pagamento realizado', color: '#059669', label: 'Pagamento Realizado' },
            { key: 'Lavando', color: '#2563EB', label: 'Lavando' },
            { key: 'Secando', color: '#7C3AED', label: 'Secando' },
            { key: 'Pronto para entrega', color: '#10B981', label: 'Pronto para Entrega' },
            { key: 'Entregue', color: '#475569', label: 'Entregue' }
        ];

        container.innerHTML = stages.map(st => {
            const count = pipe[st.key] || 0;
            const percent = Math.round((count / totalActive) * 100);
            return `
                <div class="pipe-row">
                    <div class="pipe-info">
                        <span style="color: ${st.color}; font-weight: 700;">${st.label}</span>
                        <span><strong>${count}</strong> (${percent}%)</span>
                    </div>
                    <div class="pipe-track">
                        <div class="pipe-fill" style="width: ${percent}%; background-color: ${st.color};"></div>
                    </div>
                </div>
            `;
        }).join('');
    },

    renderSneakerStats(stats) {
        const colorContainer = document.getElementById('color-distribution-container');
        if (colorContainer && stats && stats.colors) {
            const totalPairs = stats.colors.reduce((sum, c) => sum + c.count, 0) || 1;
            colorContainer.innerHTML = stats.colors.map(c => {
                const pct = Math.round((c.count / totalPairs) * 100);
                const isBranco = c.color_type === 'Branco';
                return `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px dashed var(--border-subtle);">
                        <span style="font-weight: 600;">👟 Tênis ${c.color_type}</span>
                        <span style="background: ${isBranco ? '#E2E8F0' : '#DBEAFE'}; color: ${isBranco ? '#1E293B' : '#1E40AF'}; padding: 0.2rem 0.6rem; border-radius: var(--radius-full); font-size: 0.8rem; font-weight: 700;">
                            ${c.count} par(es) (${pct}%)
                        </span>
                    </div>
                `;
            }).join('');
        }

        const brandsContainer = document.getElementById('top-brands-container');
        if (brandsContainer && stats && stats.top_brands) {
            brandsContainer.innerHTML = stats.top_brands.map((b, idx) => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0;">
                    <span style="font-size: 0.88rem; font-weight: 600;">${idx + 1}. ${b.brand}</span>
                    <strong style="color: var(--blue-marine); font-size: 0.88rem;">${b.count} un.</strong>
                </div>
            `).join('');
        }
    },

    renderRecentOrders(recent) {
        const tbody = document.getElementById('recent-orders-tbody');
        if (!tbody) return;

        if (!recent || recent.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nenhum pedido recente registrado.</td></tr>`;
            return;
        }

        tbody.innerHTML = recent.map(o => `
            <tr>
                <td><strong>#${o.id}</strong></td>
                <td><strong>${o.client_name}</strong></td>
                <td>${o.pair_count} par(es)</td>
                <td><strong>${Utils.formatCurrency(o.total_price)}</strong></td>
                <td>
                    <span class="badge-payment ${o.payment_status.toLowerCase()}">${o.payment_status}</span>
                </td>
                <td>
                    <span class="status-pill ${this.getStatusClass(o.status)}">${o.status}</span>
                </td>
            </tr>
        `).join('');
    },

    getStatusClass(status) {
        switch (status) {
            case 'Aguardando pagamento': return 'aguardando';
            case 'Pagamento realizado': return 'pago';
            case 'Lavando': return 'lavando';
            case 'Secando': return 'secando';
            case 'Pronto para entrega': return 'pronto';
            case 'Entregue': return 'entregue';
            default: return '';
        }
    }
};

window.Dashboard = Dashboard;
