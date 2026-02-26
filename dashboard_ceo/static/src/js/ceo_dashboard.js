/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
const { Component, onWillStart, onMounted, useState, useRef, useExternalListener } = owl;

export class CEODashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            activeTab: 'summary',
            data: {
                revenue: 0,
                spend: 0,
                margin: 0,
                margin_pct: 0,
                inventory: 0,
                projects: { on_track: 0, at_risk: 0, over_budget: 0 },
                approvals: { pending: 0, approved: 0, rejected: 0, blocked_value: 0 },
                bottlenecks: [],
                trends: [],
                top_vendors: [],
                last_updated: "",
                dropdownOpen: false,
                spendView: 'timeline',
                inventoryView: 'split',
                focView: 'trend',
                activeFilter: null, // To track which dropdown is open
                filters: {
                    start_date: (() => {
                        let d = new Date();
                        return new Date(d.getFullYear(), d.getMonth(), 1).toLocaleDateString('en-CA');
                    })(),
                    end_date: new Date().toLocaleDateString('en-CA'),
                    project_id: false,
                    customer_id: false,
                    vendor_id: false,
                    location_id: false,
                    category_id: false,
                    project_name: 'All Projects',
                    customer_name: 'All Customers',
                    vendor_name: 'All Vendors',
                    location_name: 'All Locations',
                    category_name: 'All Categories',
                    is_custom_date: false
                },
                filterOptions: {
                    projects: [],
                    customers: [],
                    vendors: [],
                    locations: [],
                    categories: []
                },
                filterSearchTerms: {
                    project: '',
                    customer: '',
                    vendor: '',
                    location: '',
                    category: ''
                },
                money_flow: {
                    outward_spend: { value: 0, trend: 0 },
                    inward_purchase: { value: 0, trend: 0 },
                    payables_pending: { value: 0, trend: 0 },
                    project_spend: { value: 0, trend: 0 },
                    foc_cost: { value: 0, trend: 0 },
                    inventory_value: { value: 0, trend: 0 }
                },
                spend_view_data: {
                    timeline: { labels: [], data: [] },
                    category: { labels: [], data: [] }
                },
                projects_page: {
                    active_projects: 0,
                    total_budget: 0,
                    total_spent: 0,
                    project_list: [],
                    approvals: {
                        pending: 0,
                        approved: 0,
                        rejected: 0,
                        blocked_value: 0,
                        bottlenecks: []
                    }
                },
                inventory_page: {
                    total_value: 0,
                    split: [],
                    aging_data: [],
                    forecast: {
                        cash_required_30d: 0,
                        cards: [{ label: '', forecasted: 0, committed: 0, pending: 0 }],
                        shortages: { total_at_risk: 0, items: [] },
                        cash_requirement: 0,
                        daily_projection: []
                    }
                },
                foc_page: {
                    mtd_cost: 0,
                    ytd_cost: 0,
                    revenue_pct: 0,
                    top_client: '',
                    trend: { labels: [], foc_costs: [], revenue: [] },
                    clients: [],
                    machines: []
                },
                forecast_page: {
                    labels: [],
                    revenue: [],
                    target: []
                }
            }
        });





        this.trendChartRef = useRef("trendChart");
        this.spendChartRef = useRef("spendChart");
        this.vendorChartRef = useRef("vendorChart");
        this.inventoryChartRef = useRef("inventoryChart");
        this.forecastChartRef = useRef("forecastChart");
        this.focChartRef = useRef("focChart");
        this.businessForecastChartRef = useRef("businessForecastChart");
        this.charts = {};
        useExternalListener(window, 'resize', () => this.renderCharts());

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadFilterOptions();
            await this.loadData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    // Deep merge helper: recursively merges source into target without wiping nested defaults
    _deepMerge(target, source) {
        if (!source || typeof source !== 'object') return target;
        const result = { ...target };
        for (const key of Object.keys(source)) {
            if (
                source[key] !== null &&
                typeof source[key] === 'object' &&
                !Array.isArray(source[key]) &&
                target[key] !== null &&
                typeof target[key] === 'object' &&
                !Array.isArray(target[key])
            ) {
                result[key] = this._deepMerge(target[key], source[key]);
            } else {
                result[key] = source[key];
            }
        }
        return result;
    }

    async loadData() {
        const filters = this.state.data.filters;
        const filter_params = {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
            vendor_id: filters.vendor_id,
            location_id: filters.location_id,
            category_id: filters.category_id,
            is_custom_date: filters.is_custom_date
        };

        // 1. Fetch lightweight aggregated KPI data instantly (does NOT overwrite nested defaults)
        const kpi_data = await this.orm.call("dashboard.analytics.service", "get_kpi_data", [], filter_params);
        this.state.data = this._deepMerge(this.state.data, kpi_data);

        // 2. Trigger asynchronous heavy graph loading in the background
        this.loadGraphDataAsync(filter_params);
    }

    async loadGraphDataAsync(filter_params) {
        const graph_data = await this.orm.call("dashboard.analytics.service", "get_graph_data", [], filter_params);
        this.state.data = this._deepMerge(this.state.data, graph_data);
        this.renderCharts();
    }

    async loadFilterOptions() {
        const options = await this.orm.call("ceo.dashboard", "get_filter_options", []);
        this.state.data.filterOptions = options;
    }

    async onApplyFilters() {
        this.state.data.filters.is_custom_date = true;
        await this.applyFilters();
    }

    async applyFilters() {
        // Calling loadData handles KPI and kicks off Graph re-rendering via async
        await this.loadData();
    }

    toggleDropdown() {
        this.state.data.dropdownOpen = !this.state.data.dropdownOpen;
    }

    toggleSpendView(view) {
        if (this.state.data.spendView !== view) {
            this.state.data.spendView = view;
            setTimeout(() => this.renderSpendChart(), 0);
        }
    }

    switchInventoryView(view) {
        if (this.state.data.inventoryView !== view) {
            this.state.data.inventoryView = view;
            this.renderCharts();
        }
    }

    switchFocView(view) {
        if (this.state.data.focView !== view) {
            this.state.data.focView = view;
            setTimeout(() => this.renderCharts(), 0);
        }
    }

    switchTab(tab) {
        this.state.activeTab = tab;
        setTimeout(() => this.renderCharts(), 0);
    }

    toggleFilterDropdown(filterType) {
        if (this.state.data.activeFilter === filterType) {
            this.state.data.activeFilter = null;
        } else {
            this.state.data.activeFilter = filterType;
            // Clear search when opening
            if (this.state.data.filterSearchTerms[filterType] !== undefined) {
                this.state.data.filterSearchTerms[filterType] = '';
            }
        }
    }

    onSearchInput(ev, type) {
        this.state.data.filterSearchTerms[type] = ev.target.value;
    }

    getFilteredOptions(type) {
        const optionsMap = {
            'project': 'projects',
            'customer': 'customers',
            'vendor': 'vendors',
            'location': 'locations',
            'category': 'categories'
        };
        const options = this.state.data.filterOptions[optionsMap[type]] || [];
        const term = this.state.data.filterSearchTerms[type] || '';
        if (!term) return options;
        return options.filter(opt => opt.name.toLowerCase().includes(term.toLowerCase()));
    }

    setFilter(type, value) {
        // value is an object with {id, name}
        if (type === 'project') {
            this.state.data.filters.project_id = value.id;
            this.state.data.filters.project_name = value.name;
        } else if (type === 'customer') {
            this.state.data.filters.customer_id = value.id;
            this.state.data.filters.customer_name = value.name;
        } else if (type === 'vendor') {
            this.state.data.filters.vendor_id = value.id;
            this.state.data.filters.vendor_name = value.name;
        } else if (type === 'location') {
            this.state.data.filters.location_id = value.id;
            this.state.data.filters.location_name = value.name;
        } else if (type === 'category') {
            this.state.data.filters.category_id = value.id;
            this.state.data.filters.category_name = value.name;
        }
        this.state.data.activeFilter = null;
        this.applyFilters();
    }

    async approveRecord(model, resId) {
        if (confirm("Are you sure you want to approve this record?")) {
            await this.orm.call("ceo.dashboard", "action_approve_record", [], {
                model: model,
                res_id: resId
            });
            await this.loadData();
            // Data re-renders graphs implicitly on completion anyway
        }
    }

    async rejectRecord(model, resId) {
        if (confirm("Are you sure you want to reject this record?")) {
            await this.orm.call("ceo.dashboard", "action_reject_record", [], {
                model: model,
                res_id: resId
            });
            await this.loadData();
            this.renderCharts();
        }
    }

    async onRevenueClick() {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_active_mos_action", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
        });

        action.name = "Manufacturing Orders Cost Analysis";
        this.action.doAction(action);
    }

    async onSpendClick() {
        const filters = this.state.data.filters;
        const domain = [
            ['state', 'in', ['purchase', 'done']]
        ];

        if (filters.start_date) {
            domain.push(['date_order', '>=', filters.start_date + ' 00:00:00']);
        } else {
            // Default to last 30 days if no filter
            const today = new Date();
            const thirtyDaysAgo = new Date(today);
            thirtyDaysAgo.setDate(today.getDate() - 30);
            domain.push(['date_order', '>=', thirtyDaysAgo.toISOString().split('T')[0]]);
        }

        if (filters.end_date) {
            domain.push(['date_order', '<=', filters.end_date + ' 23:59:59']);
        }

        if (filters.vendor_id) {
            domain.push(['partner_id', '=', filters.vendor_id]);
        }
        if (filters.project_id) {
            domain.push(['project_id', '=', filters.project_id]);
        }
        if (filters.category_id) {
            domain.push(['order_line.product_id.categ_id', 'child_of', filters.category_id]);
        }
        if (filters.location_id) {
            domain.push(['picking_type_id.default_location_dest_id', 'child_of', filters.location_id]);
        }

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Purchase Orders',
            res_model: 'purchase.order',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onOutwardSpendClick() {
        const filters = this.state.data.filters;
        const domain = [
            ['picking_type_id.code', '=', 'outgoing'],
            ['state', '=', 'done']
        ];

        let start = filters.start_date;
        let end = filters.end_date;
        if (!filters.is_custom_date) {
            const todayObj = new Date();
            const yesterdayObj = new Date();
            yesterdayObj.setDate(todayObj.getDate() - 1);

            start = yesterdayObj.toISOString().split('T')[0];
            end = todayObj.toISOString().split('T')[0];
        }

        if (start) domain.push(['date_done', '>=', start + ' 00:00:00']);
        if (end) domain.push(['date_done', '<=', end + ' 23:59:59']);
        if (filters.location_id) domain.push(['location_id', 'child_of', filters.location_id]);
        if (filters.category_id) domain.push(['move_ids_without_package.product_id.categ_id', 'child_of', filters.category_id]);

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Outward Spend (' + (start || 'All') + ' to ' + (end || 'All') + ')',
            res_model: 'stock.picking',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onInwardPurchaseClick() {
        const filters = this.state.data.filters;
        const domain = [
            ['picking_type_id.code', '=', 'incoming'],
            ['state', '=', 'done']
        ];

        let start = filters.start_date;
        let end = filters.end_date;
        if (!filters.is_custom_date) {
            const todayObj = new Date();
            const yesterdayObj = new Date();
            yesterdayObj.setDate(todayObj.getDate() - 1);

            start = yesterdayObj.toISOString().split('T')[0];
            end = todayObj.toISOString().split('T')[0];
        }

        if (start) domain.push(['date_done', '>=', start + ' 00:00:00']);
        if (end) domain.push(['date_done', '<=', end + ' 23:59:59']);
        if (filters.location_id) domain.push(['location_dest_id', 'child_of', filters.location_id]);
        if (filters.category_id) domain.push(['move_ids_without_package.product_id.categ_id', 'child_of', filters.category_id]);

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Inward Purchase (' + (start || 'All') + ' to ' + (end || 'All') + ')',
            res_model: 'stock.picking',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onPayablesClick() {
        const filters = this.state.data.filters;
        const domain = [
            ['move_type', '=', 'in_invoice'],
            ['state', '=', 'posted'],
            ['payment_state', 'in', ['not_paid', 'partial']]
        ];

        let start = filters.start_date;
        let end = filters.end_date;
        if (!filters.is_custom_date) {
            const todayObj = new Date();
            const yesterdayObj = new Date();
            yesterdayObj.setDate(todayObj.getDate() - 1);

            start = yesterdayObj.toISOString().split('T')[0];
            end = todayObj.toISOString().split('T')[0];
        }

        if (start) domain.push(['invoice_date', '>=', start]);
        if (end) domain.push(['invoice_date', '<=', end]);

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Total Payables Pending',
            res_model: 'account.move',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    onInventoryClick(categoryId, categoryName) {
        const filters = this.state.data.filters;
        const domain = [['quantity', '>', 0], ['location_id.usage', '=', 'internal']];

        if (filters.location_id) {
            domain.push(['location_id', 'child_of', filters.location_id]);
        } else {
            // Match backend default filtering for CW/Store locations
            domain.push('|', ['location_id.complete_name', 'ilike', 'CW'], ['location_id.complete_name', 'ilike', 'Store']);
        }

        const catId = categoryId || filters.category_id;
        if (catId && !isNaN(catId)) {
            domain.push(['product_id.categ_id', 'child_of', parseInt(catId)]);
        }

        const title = categoryName ? `Inventory Value - ${categoryName}` : 'Inventory Value';

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: title,
            res_model: 'stock.quant',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            context: { 'search_default_internal_loc': 1, 'search_default_groupby_product': 1 },
            target: 'current',
        });
    }

    onProjectsClick() {
        const filters = this.state.data.filters;
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Active Projects',
            res_model: 'project.project',
            views: [[false, 'list'], [false, 'form']],
            domain: filters.project_id ? [['id', '=', filters.project_id]] : [['active', '=', true]],
            target: 'current',
        });
    }

    onProjectHealthClick(statusType) {
        if (!this.state.data.projects) {
            return;
        }

        const ids = this.state.data.projects[`${statusType}_ids`] || [];
        let name = "Projects";

        if (statusType === 'on_track') name = "On Track Projects";
        if (statusType === 'at_risk') name = "At Risk Projects";
        if (statusType === 'over_budget') name = "Over Budget Projects";

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['id', 'in', ids]],
            target: 'current',
        });
    }

    openPendingRecords() {
        this.onApprovalClick('pending');
    }

    openApprovedRecords() {
        this.onApprovalClick('approved');
    }

    openRejectedRecords() {
        this.onApprovalClick('rejected');
    }

    openRecord(model, resId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            res_id: resId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    onMaterialRequestClick() {
        this.openPendingRecords();
    }

    async onFocCostClick(period) {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_foc_drilldown_action", [], {
            period: period,
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
            vendor_id: filters.vendor_id,
            location_id: filters.location_id,
            category_id: filters.category_id
        });
        this.action.doAction(action);
    }

    async onFocClientClick(partnerId) {
        const action = await this.orm.call("ceo.dashboard", "get_foc_drilldown_action", [], {
            period: 'mtd', // Default to month-to-date for individual client clicks
            start_date: this.state.data.filters.start_date,
            end_date: this.state.data.filters.end_date,
            customer_id: partnerId,
        });
        this.action.doAction(action);
    }

    resetFilters() {
        const today = new Date().toLocaleDateString('en-CA');
        const monthStart = (() => {
            let d = new Date();
            return new Date(d.getFullYear(), d.getMonth(), 1).toLocaleDateString('en-CA');
        })();
        this.state.data.filters = {
            start_date: monthStart,
            end_date: today,
            project_id: false,
            customer_id: false,
            vendor_id: false,
            location_id: false,
            category_id: false,
            project_name: 'All Projects',
            customer_name: 'All Customers',
            vendor_name: 'All Vendors',
            location_name: 'All Locations',
            category_name: 'All Categories',
            is_custom_date: false
        };
        this.state.data.activeFilter = null;
        this.applyFilters();
    }

    formatCompact(value) {
        if (value === false || value === undefined || value === null || isNaN(value)) {
            return "0K";
        }
        if (value >= 10000000) {
            return (value / 10000000).toFixed(1) + "Cr";
        }
        return (value / 1000).toFixed(0) + "K";
    }

    formatCurrency(value) {
        if (value === false || value === undefined || value === null || isNaN(value)) {
            return "0";
        }
        if (value >= 10000000) {
            return (value / 10000000).toFixed(2) + "Cr";
        } else if (value >= 100000) {
            return (value / 100000).toFixed(2) + "L";
        } else if (value >= 1000) {
            return (value / 1000).toFixed(1) + "K";
        }
        return value.toString();
    }

    renderCharts() {
        setTimeout(() => {
            if (this.state.activeTab === 'money_flow' || this.state.activeTab === 'summary') {
                this.renderTrendChart();
                this.renderSpendChart();
                this.renderVendorChart();
            } else if (this.state.activeTab === 'inventory') {
                if (this.state.data.inventoryView === 'split') {
                    this.renderInventoryChart();
                } else {
                    this.renderAgingChart();
                }
                this.renderForecastChart();
            } else if (this.state.activeTab === 'foc') {
                if (this.state.data.focView === 'trend') {
                    this.renderFocChart();
                } else if (this.state.data.focView === 'machine') {
                    this.renderMachineChart();
                } else if (this.state.data.focView === 'client') {
                    this.renderClientChart();
                }
            } else if (this.state.activeTab === 'forecast') {
                this.renderForecastChart();
            }
        }, 50);
    }

    renderFocChart() {
        if (!this.focChartRef.el) return;
        const ctx = this.focChartRef.el.getContext('2d');
        const data = this.state.data.foc_page.trend;

        if (this.charts.foc) this.charts.foc.destroy();

        // Teal gradient for FOC Cost
        const gradientFOC = ctx.createLinearGradient(0, 0, 0, 400);
        gradientFOC.addColorStop(0, 'rgba(0, 210, 190, 0.45)');
        gradientFOC.addColorStop(1, 'rgba(0, 210, 190, 0.05)');

        this.charts.foc = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'FOC Cost',
                        data: data.foc_costs,
                        borderColor: '#00d2be',
                        backgroundColor: gradientFOC,
                        borderWidth: 3,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointBackgroundColor: '#00d2be',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        fill: true,
                        tension: 0.35
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            color: '#94a3b8',
                            font: { size: 12, family: "'Inter', sans-serif" },
                            padding: 24
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        borderColor: 'rgba(148, 163, 184, 0.2)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: (context) => {
                                const val = context.raw;
                                return `  ${context.dataset.label}: ₹${this.formatCurrency(val)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        border: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
                            callback: (value) => '₹' + this.formatCurrency(value)
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.08)',
                            borderDash: [5, 5]
                        }
                    },
                    x: {
                        border: { display: false },
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 }
                        }
                    }
                },
                animation: {
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderMachineChart() {
        if (!this.focChartRef.el) return;
        const ctx = this.focChartRef.el.getContext('2d');
        const data = this.state.data.foc_page.machines || [];

        if (this.charts.foc) this.charts.foc.destroy();

        this.charts.foc = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(m => m.name),
                datasets: [{
                    label: 'FOC Cost',
                    data: data.map(m => m.value),
                    backgroundColor: 'rgba(0, 210, 190, 0.7)',
                    hoverBackgroundColor: '#00d2be',
                    borderRadius: 6,
                    borderWidth: 0,
                    barThickness: 45,
                    maxBarThickness: 60
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { size: 12 },
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        padding: 12,
                        callbacks: {
                            label: (context) => ` FOC Cost: ₹${this.formatCurrency(context.raw)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        border: { display: false },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.08)',
                            borderDash: [5, 5]
                        },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
                            callback: (value) => '₹' + this.formatCurrency(value)
                        }
                    },
                    x: {
                        border: { display: false },
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 }
                        }
                    }
                },
                animation: {
                    duration: 1000,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderBusinessForecastChart() {
        if (!this.businessForecastChartRef.el) return;
        const ctx = this.businessForecastChartRef.el.getContext('2d');
        const data = this.state.data.forecast_page;

        if (this.charts.businessForecast) this.charts.businessForecast.destroy();

        this.charts.businessForecast = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Projected Revenue',
                        data: data.revenue,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Budget Target',
                        data: data.target,
                        borderColor: '#94a3b8',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'bottom' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => '₹' + (value / 100000) + 'L'
                        }
                    }
                }
            }
        });
    }

    renderClientChart() {
        if (!this.focChartRef.el) return;
        const ctx = this.focChartRef.el.getContext('2d');
        const data = this.state.data.foc_page.clients || [];

        if (this.charts.foc) this.charts.foc.destroy();

        this.charts.foc = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(c => c.name),
                datasets: [{
                    label: 'FOC Cost',
                    data: data.map(c => c.value),
                    backgroundColor: 'rgba(96, 165, 250, 0.7)',
                    hoverBackgroundColor: '#60a5fa',
                    borderRadius: 6,
                    borderWidth: 0,
                    barThickness: 45,
                    maxBarThickness: 60
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { size: 12 },
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        padding: 12,
                        callbacks: {
                            label: (context) => ` FOC Cost: ₹${this.formatCurrency(context.raw)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        border: { display: false },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.08)',
                            borderDash: [5, 5]
                        },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
                            callback: (value) => '₹' + this.formatCurrency(value)
                        }
                    },
                    x: {
                        border: { display: false },
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 }
                        }
                    }
                },
                animation: {
                    duration: 1000,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    renderForecastChart() {
        if (!this.forecastChartRef.el) return;
        const ctx = this.forecastChartRef.el.getContext('2d');
        const projection = this.state.data.inventory_page.forecast.daily_projection || [];

        if (this.charts.forecast) this.charts.forecast.destroy();
        if (projection.length === 0) return;

        const labels = projection.map(d => d.label);
        const forecastData = projection.map(d => d.forecasted);
        const committedData = projection.map(d => d.committed);

        // Teal gradient fill for Forecast Purchase area
        const gradForecast = ctx.createLinearGradient(0, 0, 0, 300);
        gradForecast.addColorStop(0, 'rgba(0, 210, 190, 0.55)');
        gradForecast.addColorStop(1, 'rgba(0, 210, 190, 0.02)');

        this.charts.forecast = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Forecast Purchase',
                        data: forecastData,
                        borderColor: '#00d2be',
                        backgroundColor: gradForecast,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointBackgroundColor: '#00d2be',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        borderWidth: 2.5,
                        order: 2
                    },
                    {
                        label: 'Committed Orders',
                        data: committedData,
                        borderColor: '#60a5fa',
                        backgroundColor: 'transparent',
                        fill: false,
                        tension: 0.35,
                        borderDash: [6, 4],
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        pointBackgroundColor: '#60a5fa',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        borderWidth: 2,
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            color: '#94a3b8',
                            font: { size: 12, family: "'Inter', sans-serif" },
                            padding: 24,
                            boxWidth: 10,
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        borderColor: 'rgba(148, 163, 184, 0.15)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: (context) => `  ${context.dataset.label}: ₹${this.formatCurrency(context.raw)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.10)',
                            borderDash: [4, 4]
                        },
                        border: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
                            callback: (value) => '₹' + this.formatCurrency(value)
                        }
                    },
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 }
                        }
                    }
                },
                animation: {
                    duration: 900,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }


    async onActiveMOsClick() {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_active_mos_action", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
        });
        this.action.doAction(action);
    }

    async onMOSpendClick() {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_mo_spend_action", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
        });
        this.action.doAction(action);
    }

    onProjectRowClick(resId) {
        if (!resId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'sale.order',
            res_id: resId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async onApprovalClick(statusType) {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_approval_action", [statusType], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
            vendor_id: filters.vendor_id,
            location_id: filters.location_id,
            category_id: filters.category_id,
        });
        this.action.doAction(action);
    }

    async onProjectSpendClick(projectId) {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_project_spend_po_action", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: projectId || filters.project_id,
        });
        this.action.doAction(action);
    }

    async onForecastClick() {
        const filters = this.state.data.filters || {};
        let items = [];
        try {
            items = await this.orm.call('ceo.dashboard', 'get_forecast_shortage_drilldown', [], {
                project_id: filters.project_id || false,
                customer_id: filters.customer_id || false,
                location_id: filters.location_id || false,
                category_id: filters.category_id || false,
            });
        } catch (e) {
            items = [];
        }
        this.state.data.drilldownItems = items;
        this.state.data.showForecastModal = true;
    }

    onShortageClick() {
        this.onForecastClick();
    }

    closeForecastModal() {
        this.state.data.showForecastModal = false;
    }

    openDrilldownRecord(model, resId) {
        if (!model || !resId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            res_id: parseInt(resId),
            views: [[false, 'form']],
            target: 'current',
        });
    }

    onProductClick(productId) {
        if (!productId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Product Details',
            res_model: 'product.template',
            res_id: parseInt(productId),
            views: [[false, 'form']],
            target: 'current',
        });
    }

    renderAgingChart() {
        if (!this.inventoryChartRef.el) return;
        const ctx = this.inventoryChartRef.el.getContext('2d');
        const data = this.state.data.inventory_page.aging_data;

        if (this.charts.inventory) this.charts.inventory.destroy();

        this.charts.inventory = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    label: 'Inventory Value',
                    data: data.map(d => d.value),
                    backgroundColor: data.map(d => d.color),
                    borderRadius: 5,
                    barThickness: 150
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const val = context.raw;
                                return ` Inventory Value : ₹${(val / 100000).toFixed(2)}L`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => '₹' + (value / 100000) + 'L'
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    renderInventoryChart() {
        if (!this.inventoryChartRef.el) return;
        const ctx = this.inventoryChartRef.el.getContext('2d');
        const data = this.state.data.inventory_page.split;

        if (this.charts.inventory) this.charts.inventory.destroy();

        this.charts.inventory = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    data: data.map(d => d.value),
                    backgroundColor: data.map(d => d.color),
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const item = this.state.data.inventory_page.split[index];
                        if (item) {
                            this.onInventoryClick(item.id, item.label);
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const val = context.raw;
                                return ` ₹${(val / 100000).toFixed(2)}L (${((val / this.state.data.inventory_page.total_value) * 100).toFixed(1)}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    renderTrendChart() {
        if (!this.trendChartRef.el) return;
        if (this.charts.trend) this.charts.trend.destroy();
        const ctx = this.trendChartRef.el.getContext('2d');
        const labels = this.state.data.trends.map(t => t.month);
        const revenueData = this.state.data.trends.map(t => t.revenue);
        const spendData = this.state.data.trends.map(t => t.spend);

        this.charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'revenue',
                        data: revenueData,
                        borderColor: '#2ecc71',
                        backgroundColor: 'rgba(46, 204, 113, 0.4)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#2ecc71',
                        pointRadius: 4
                    },
                    {
                        label: 'spend',
                        data: spendData,
                        borderColor: '#e28169',
                        backgroundColor: 'rgba(226, 129, 105, 0.6)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#e28169',
                        pointRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: (context) => {
                                let label = context.dataset.label || '';
                                if (label) { label += ' : '; }
                                label += '₹' + this.formatCurrency(context.parsed.y);
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value > 0 ? '₹' + this.formatCompact(value) : '₹0K'
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    renderSpendChart() {
        if (!this.spendChartRef.el) return;
        const ctx = this.spendChartRef.el.getContext('2d');

        // Destroy existing chart if it exists
        if (this.charts.spend) {
            this.charts.spend.destroy();
        }

        if (this.state.data.spendView === 'timeline') {
            const labels = this.state.data.spend_view_data.timeline.labels;
            const data = this.state.data.spend_view_data.timeline.data;

            this.charts.spend = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Spend Amount',
                        data: data,
                        backgroundColor: '#3b82f6',
                        borderRadius: 6,
                        barThickness: 45
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const timeline = this.state.data.spend_view_data.timeline;
                            const date = timeline.full_dates[index];
                            const model = timeline.model;

                            let domain = [];
                            let name = 'Spend Details';

                            if (model === 'stock.picking') {
                                // Material Spend - Show Delivery Orders (Outgoing Pickings)
                                domain = [
                                    ['picking_type_code', '=', 'outgoing'],
                                    ['state', '=', 'done'],
                                    ['date_done', '>=', date + ' 00:00:00'],
                                    ['date_done', '<=', date + ' 23:59:59']
                                ];
                                name = 'Delivery Orders (' + date + ')';

                                this.action.doAction({
                                    type: 'ir.actions.act_window',
                                    name: name,
                                    res_model: 'stock.picking',
                                    views: [[false, 'list'], [false, 'form']],
                                    domain: domain,
                                    target: 'current',
                                });
                            } else {
                                // Bills Spend (account.move)
                                domain = [
                                    ['invoice_date', '=', date],
                                    ['move_type', '=', 'in_invoice'],
                                    ['state', '=', 'posted']
                                ];
                                name = 'Bill Spend (' + date + ')';

                                this.action.doAction({
                                    type: 'ir.actions.act_window',
                                    name: name,
                                    res_model: model,
                                    views: [[false, 'list'], [false, 'form']],
                                    domain: domain,
                                    target: 'current',
                                });
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                pointStyle: 'rect',
                                padding: 20
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => 'Spend Amount: ₹' + this.formatCurrency(context.parsed.y)
                            }
                        }
                    },
                    scales: {
                        y: {
                            display: true,
                            beginAtZero: true,
                            ticks: {
                                callback: (value) => '₹' + this.formatCompact(value)
                            },
                            grid: { borderDash: [5, 5], color: '#e2e8f0' }
                        },
                        x: { display: true, grid: { display: false } }
                    }
                }
            });
        } else {
            // Category View (Pie Chart)
            const labels = this.state.data.spend_view_data.category.labels;
            const data = this.state.data.spend_view_data.category.data;
            const colors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981']; // Blue, Purple, Cyan, Green matching the image style

            this.charts.spend = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const catData = this.state.data.spend_view_data.category;
                            const catId = catData.ids ? catData.ids[index] : null;
                            const catLabel = catData.labels ? catData.labels[index] : 'Unknown';
                            if (catId) {
                                this.onInventoryClick(catId, catLabel);
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'right',
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: { size: 12 }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    const value = context.parsed;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${context.label}: ₹${this.formatCurrency(value)} (${percentage}%)`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: { display: false },
                        x: { display: false }
                    }
                }
            });
        }
    }

    renderVendorChart() {
        if (!this.vendorChartRef.el) return;
        const ctx = this.vendorChartRef.el.getContext('2d');
        const labels = this.state.data.top_vendors.map(v => v.name);
        const data = this.state.data.top_vendors.map(v => v.value);

        if (this.charts.vendor) this.charts.vendor.destroy();

        this.charts.vendor = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Purchase Value',
                    data: data,
                    backgroundColor: '#8b5cf6',
                    borderRadius: 6,
                    barThickness: 25
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'rect',
                            padding: 20
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => 'Purchase Value: ₹' + this.formatCurrency(context.raw)
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const vendor = this.state.data.top_vendors[index];
                        if (vendor && vendor.partner_id) {
                            const model = vendor.model || 'account.move';
                            let domain = [];
                            let name = `Purchases from ${vendor.name}`;

                            if (model === 'account.move') {
                                domain = [
                                    ['partner_id', '=', vendor.partner_id],
                                    ['move_type', '=', 'in_invoice'],
                                    ['state', '=', 'posted']
                                ];
                            } else {
                                domain = [
                                    ['partner_id', '=', vendor.partner_id],
                                    ['state', 'in', ['purchase', 'done']]
                                ];
                            }

                            // Add date range filter
                            if (this.state.data.filters.start_date) {
                                const dateField = model === 'account.move' ? 'invoice_date' : 'date_order';
                                domain.push([dateField, '>=', this.state.data.filters.start_date]);
                            }
                            if (this.state.data.filters.end_date) {
                                const dateField = model === 'account.move' ? 'invoice_date' : 'date_order';
                                domain.push([dateField, '<=', this.state.data.filters.end_date]);
                            }

                            this.action.doAction({
                                type: 'ir.actions.act_window',
                                name: name,
                                res_model: model,
                                views: [[false, 'list'], [false, 'form']],
                                domain: domain,
                                target: 'current',
                            });
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => '₹' + this.formatCurrency(value)
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    y: { grid: { display: false } }
                }
            }
        });
    }
}

CEODashboard.template = "dashboard_ceo.Main";
registry.category("actions").add("dashboard_ceo.main", CEODashboard);
