/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class HelpdeskDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            stats: {},
            loading: true,
            currentView: 'dashboard', // dashboard or all_tickets
            tickets: [],
            filterData: {
                mills: [],
                teams: [],
                stages: [],
                categories: []
            },
            ticketsFilter: {
                search: "",
                category: "all",
                mill: "all",
                status: "all",
                team: "all",
                date_range: {
                    start: "",
                    end: ""
                }
            },
            showDateRange: false,
            filter: {
                searchQuery: "",
                period: "all", // all, daily, weekly, monthly, custom
                dateStart: "",
                dateEnd: "",
            }
        });

        onWillStart(async () => {
            await this.loadDashboardData();
            await this.loadFilterOptions();
        });
    }

    async loadFilterOptions() {
        const data = await this.orm.call("ticket.helpdesk", "get_filter_data", []);
        this.state.filterOptions = data;
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const dateFilter = this.state.filter.period === 'custom'
                ? { start: this.state.filter.dateStart, end: this.state.filter.dateEnd }
                : this.state.filter.period === 'all' ? null : this.state.filter.period;

            const data = await this.orm.call("ticket.helpdesk", "get_dashboard_stats", [], {
                search_query: this.state.filter.searchQuery,
                date_filter: dateFilter,
            });
            this.state.stats = data;
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async loadTicketsData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("ticket.helpdesk", "get_tickets_data", [], {
                filters: this.state.ticketsFilter
            });
            this.state.tickets = data;
        } catch (error) {
            console.error("Failed to load tickets data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    // Dashboard search
    searchTimeout = null;
    onSearchInput(ev) {
        this.state.filter.searchQuery = ev.target.value;
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.loadDashboardData();
        }, 500);
    }

    // All Tickets search
    ticketsSearchTimeout = null;
    onTicketsSearchInput(ev) {
        this.state.ticketsFilter.search = ev.target.value;
        if (this.ticketsSearchTimeout) {
            clearTimeout(this.ticketsSearchTimeout);
        }
        this.ticketsSearchTimeout = setTimeout(() => {
            this.loadTicketsData();
        }, 500);
    }

    onFilterChange() {
        this.loadTicketsData();
    }

    setPeriod(period) {
        this.state.filter.period = period;
        if (period !== 'custom') {
            this.loadDashboardData();
        }
    }

    onCustomDateChange() {
        if (this.state.filter.dateStart || this.state.filter.dateEnd) {
            this.loadDashboardData();
        }
    }

    toggleDateRange() {
        this.state.showDateRange = !this.state.showDateRange;
    }

    switchToDashboard() {
        this.state.currentView = 'dashboard';
        this.loadDashboardData();
    }

    async onViewAllTickets() {
        this.state.currentView = 'all_tickets';
        await this.loadTicketsData();
    }

    exportTickets() {
        // Implementation for export if needed
        console.log("Exporting tickets...");
    }

    async openFilteredListView(category = null, isOpenOnly = false) {
        // If we want to stay in the dashboard and use our custom table instead of Odoo's list view
        this.state.currentView = 'all_tickets';
        this.state.ticketsFilter.category = category || 'all';
        // Reset other filters or keep them? Resetting for specific KPI clicks usually makes sense
        this.state.ticketsFilter.mill = 'all';
        this.state.ticketsFilter.status = 'all';
        this.state.ticketsFilter.team = 'all';
        await this.loadTicketsData();
    }

    onCreateTicket() {
        this.action.doAction({
            name: "Create Ticket",
            type: "ir.actions.act_window",
            res_model: "ticket.helpdesk",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTicket(ticketId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ticket.helpdesk",
            view_mode: "form",
            res_id: ticketId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

HelpdeskDashboard.template = "odoo_website_helpdesk.HelpdeskDashboard";
HelpdeskDashboard.components = { Layout };

registry.category("actions").add("helpdesk_dashboard_action", HelpdeskDashboard);
