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
                    start_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
                    end_date: new Date().toISOString().split('T')[0],
                    project_id: false,
                    customer_id: false,
                    vendor_id: false,
                    location_id: false,
                    category_id: false,
                    project_name: 'All Projects',
                    customer_name: 'All Customers',
                    vendor_name: 'All Vendors',
                    location_name: 'All Locations',
                    category_name: 'All Categories'
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
                        cards: [],
                        shortages: { total_at_risk: 0, items: [] },
                        cash_requirement: 0
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

    async loadData() {
        const filters = this.state.data.filters;
        const data = await this.orm.call("ceo.dashboard", "get_dashboard_data", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
            project_id: filters.project_id,
            customer_id: filters.customer_id,
            vendor_id: filters.vendor_id,
            location_id: filters.location_id,
            category_id: filters.category_id
        });
        this.state.data = { ...this.state.data, ...data };
    }

    async loadFilterOptions() {
        const options = await this.orm.call("ceo.dashboard", "get_filter_options", []);
        this.state.data.filterOptions = options;
    }

    async applyFilters() {
        await this.loadData();
        this.renderCharts();
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
            this.renderCharts();
        }
    }

    async rejectRecord(model, resId) {
        const reason = prompt("Please enter the reason for rejection:");
        if (reason !== null) {
            await this.orm.call("ceo.dashboard", "action_reject_record", [], {
                model: model,
                res_id: resId,
                reason: reason
            });
            await this.loadData();
            this.renderCharts();
        }
    }

    async onRevenueClick() {
        const filters = this.state.data.filters;
        const domain = [
            ['state', 'in', ['sale', 'done']]
        ];

        if (filters.start_date) domain.push(['date_order', '>=', filters.start_date + ' 00:00:00']);
        if (filters.end_date) domain.push(['date_order', '<=', filters.end_date + ' 23:59:59']);
        if (filters.customer_id) domain.push(['partner_id', '=', filters.customer_id]);

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Revenue (Sales Orders)',
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onSpendClick() {
        const today = new Date();
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 30);

        const dateStr = thirtyDaysAgo.toISOString().split('T')[0];

        const domain = [
            ['state', 'in', ['purchase', 'done']],
            ['date_order', '>=', dateStr]
        ];

        if (this.state.data.filters.vendor_id) {
            domain.push(['partner_id', '=', this.state.data.filters.vendor_id]);
        }

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Purchase Orders (Last 30 Days)',
            res_model: 'purchase.order',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onOutwardSpendClick() {
        const todayStr = new Date().toISOString().split('T')[0];
        const domain = [
            ['picking_type_id.code', '=', 'outgoing'],
            ['state', '=', 'done'],
            ['date_done', '>=', todayStr + ' 00:00:00'],
            ['date_done', '<=', todayStr + ' 23:59:59']
        ];

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Daily Outward Spend (Today)',
            res_model: 'stock.picking',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onInwardPurchaseClick() {
        const todayStr = new Date().toISOString().split('T')[0];
        const domain = [
            ['picking_type_id.code', '=', 'incoming'],
            ['state', '=', 'done'],
            ['date_done', '>=', todayStr + ' 00:00:00'],
            ['date_done', '<=', todayStr + ' 23:59:59']
        ];

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Daily Inward Purchase (Today)',
            res_model: 'stock.picking',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    async onPayablesClick() {
        const domain = [
            ['move_type', '=', 'in_invoice'],
            ['state', '=', 'posted'],
            ['payment_state', 'in', ['not_paid', 'partial']]
        ];

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Total Payables Pending',
            res_model: 'account.move',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }

    onInventoryClick() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Inventory Value',
            res_model: 'stock.quant',
            views: [[false, 'list'], [false, 'form']],
            domain: [['location_id.usage', '=', 'internal']],
            context: { 'search_default_internal_loc': 1, 'search_default_groupby_product': 1 },
            target: 'current',
        });
    }

    onProjectsClick() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Active Projects',
            res_model: 'project.project',
            views: [[false, 'list'], [false, 'form']],
            domain: [['active', '=', true]],
            target: 'current',
        });
    }

    openPendingRecords() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Pending Approvals (Sales/Spares)',
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['state', '=', 'waiting_ceo_approval']],
            context: { create: false }
        });
    }

    openApprovedRecords() {
        this.action.doAction('dashboard_ceo.action_spare_order_approval_history');
    }

    openRejectedRecords() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Rejected Records',
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['state', '=', 'rejected']],
            context: { create: false }
        });
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

    resetFilters() {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
        this.state.data.filters = {
            start_date: firstDay.toISOString().split('T')[0],
            end_date: today.toISOString().split('T')[0],
            project_id: false,
            customer_id: false,
            vendor_id: false,
            location_id: false,
            category_id: false,
            project_name: 'All Projects',
            customer_name: 'All Customers',
            vendor_name: 'All Vendors',
            location_name: 'All Locations',
            category_name: 'All Categories'
        };
        this.state.data.activeFilter = null;
        this.applyFilters();
    }

    formatCompact(value) {
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

        this.charts.foc = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'FOC Cost',
                        data: data.foc_costs,
                        borderColor: '#ef4444',
                        backgroundColor: '#ef4444',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.4,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Revenue',
                        data: data.revenue,
                        borderColor: '#10b981',
                        backgroundColor: '#10b981',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.4,
                        yAxisID: 'y1'
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
                    legend: { display: true, position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const val = context.raw;
                                return ` ${context.dataset.label} : ₹${val.toLocaleString()}`;
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
                        ticks: {
                            callback: (value) => value >= 1000 ? (value / 1000) + 'K' : value
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value >= 100000 ? (value / 100000) + 'L' : value
                        },
                        grid: { drawOnChartArea: false }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    renderMachineChart() {
        if (!this.focChartRef.el) return;
        const ctx = this.focChartRef.el.getContext('2d');
        const data = this.state.data.foc_page.machines;

        if (this.charts.foc) this.charts.foc.destroy();

        this.charts.foc = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(m => m.name),
                datasets: [{
                    label: 'FOC Cost',
                    data: data.map(m => m.value),
                    backgroundColor: '#ef4444',
                    borderRadius: 4,
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
                            label: (context) => ` FOC Cost: ₹${context.raw.toLocaleString()}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => '₹' + (value / 1000) + 'K'
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    x: { grid: { display: false } }
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

    renderForecastChart() {
        if (!this.forecastChartRef.el) return;
        const ctx = this.forecastChartRef.el.getContext('2d');
        const projection = this.state.data.inventory_page.forecast.daily_projection || [];

        if (this.charts.forecast) this.charts.forecast.destroy();

        if (projection.length === 0) return;

        this.charts.forecast = new Chart(ctx, {
            type: 'line',
            data: {
                labels: projection.map(d => d.label),
                datasets: [
                    {
                        label: 'Projected Stock Value',
                        data: projection.map(d => d.stock_value),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        borderWidth: 2,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Predicted Purchase Spend',
                        data: projection.map(d => d.spend),
                        borderColor: '#ef4444',
                        backgroundColor: '#ef4444',
                        type: 'bar',
                        barThickness: 5,
                        yAxisID: 'y1'
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
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const val = context.raw;
                                if (context.datasetIndex === 0) {
                                    return ` Stock Value: ₹${this.formatCurrency(val)}`;
                                } else {
                                    return ` Spend: ₹${this.formatCurrency(val)}`;
                                }
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
                        title: { display: true, text: 'Stock Value' },
                        ticks: {
                            callback: (value) => this.formatCurrency(value)
                        },
                        grid: { borderDash: [5, 5], color: '#e2e8f0' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        title: { display: true, text: 'Purchase Spend' },
                        ticks: {
                            callback: (value) => this.formatCurrency(value)
                        },
                        grid: { drawOnChartArea: false }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            autoSkip: true,
                            maxRotation: 0,
                            callback: function (val, index) {
                                return index % 10 === 0 ? this.getLabelForValue(val) : '';
                            }
                        }
                    }
                }
            }
        });
    }

    async onActiveProjectsClick() {
        const filters = this.state.data.filters;
        const action = await this.orm.call("ceo.dashboard", "get_active_projects_action", [], {
            start_date: filters.start_date,
            end_date: filters.end_date,
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
            customer_id: filters.customer_id,
        });
        this.action.doAction(action);
    }

    async onProjectSpendClick() {
        const todayStr = new Date().toISOString().split('T')[0];
        const action = await this.orm.call("ceo.dashboard", "get_project_spend_po_action", [], {
            start_date: todayStr,
            end_date: todayStr,
            project_id: this.state.data.filters.project_id,
        });
        this.action.doAction(action);
    }

    async onShortageClick() {
        const domain = [
            ['qty_available', '<', 1], // Or use a field that stores forecast but easier to use a dynamic search
        ];

        // Better: Open product list with a context that highlights shortages
        // For Odoo 18, we can use the reordering rules view or a filtered product list
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Material Shortages (ROP)',
            res_model: 'stock.warehouse.orderpoint',
            views: [[false, 'list'], [false, 'form']],
            domain: [['qty_to_order', '>', 0]],
            target: 'current',
        });
    }

    onProductClick(productName) {
        // Find product ID by name if needed, but easier to just use search
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Product Forecast',
            res_model: 'product.product',
            views: [[false, 'form']],
            domain: [['display_name', '=', productName]],
            target: 'current',
            context: { 'search_default_filter_to_sell': 1 }
        });

        // Actually, Odoo has a specific "Forecasted" report.
        // We can navigate to it if we have the ID.
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
                                    return context.label + ': ' + context.parsed + '%';
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
