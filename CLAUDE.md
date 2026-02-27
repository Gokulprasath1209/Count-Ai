# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Count-Ai is an Odoo 18 custom addon suite with 19 specialized business modules covering accounting, manufacturing, sales, inventory, and support. The working Odoo instance runs on port `1234` using the config at `/home/gowtham/workspace/odoo18/conf/count_ai.conf`.

## Common Commands

**Start Odoo server:**
```bash
python3 /home/gowtham/workspace/odoo18/odoo/odoo-bin -c /home/gowtham/workspace/odoo18/conf/count_ai.conf
```

**Update a specific module:**
```bash
python3 /home/gowtham/workspace/odoo18/odoo/odoo-bin -c /home/gowtham/workspace/odoo18/conf/count_ai.conf -u <module_name> --stop-after-init
```

**Run tests for a specific module:**
```bash
python3 /home/gowtham/workspace/odoo18/odoo/odoo-bin -c /home/gowtham/workspace/odoo18/conf/count_ai.conf --test-enable -u <module_name> --stop-after-init
```

**Run a single test class:**
```bash
python3 /home/gowtham/workspace/odoo18/odoo/odoo-bin -c /home/gowtham/workspace/odoo18/conf/count_ai.conf --test-enable --test-tags=TestClassName -u <module_name> --stop-after-init
```

**Install a new module:**
```bash
python3 /home/gowtham/workspace/odoo18/odoo/odoo-bin -c /home/gowtham/workspace/odoo18/conf/count_ai.conf -i <module_name> --stop-after-init
```

## Architecture

### Module Dependency Chain

The key internal dependency order matters for installation and understanding data flow:

```
base_account_budget
  └── base_accounting_kit
        └── dynamic_accounts_report

vendor_customer
  └── material_request  ←── (also depends on: mrp, stock, purchase_requisition, project)
        └── dashboard_ceo  ←── (also depends on: sale_extended)

sale_extended
  └── dashboard_ceo
```

`odoo_website_helpdesk`, `ica_web_responsive`, `web_login_styles`, `hide_menu_user`, `hide_delete_option`, and `purchase_cost_update` are independent of internal modules.

### Key Modules

**`material_request/`** — Core manufacturing workflow module. Implements a multi-level approval state machine for material requisitions:
- States: `draft → waiting_ceo_approval → waiting_for_purchase → onhand_approve/full_approve → approved → received`
- Models: `material.request`, `material.request.product.line`, `user.material.request`, `mrp.extended`
- Wizards: `purchase_request.py` (creates purchase requisitions), `backorder.py` (splits unfulfilled lines)
- Note: `purchae_request.xml` is a typo in the manifest for `wizard/purchase_request.xml`

**`dashboard_ceo/`** — Real-time executive dashboard aggregating data from sales, purchasing, stock, and approvals.
- `ceo_dashboard.py`: Creates composite DB indexes on `init()` for performance; uses timezone-aware date range queries
- `dashboard_analytics.py`: Caches computed analytics results
- Frontend: OWL component in `static/src/js/ceo_dashboard.js` + QWeb template in `static/src/xml/ceo_dashboard.xml`
- Depends on `material_request` and `sale_extended` for approval pipeline and revenue data

**`base_accounting_kit/`** — Largest module (56 Python files). Full accounting suite with asset depreciation, PDC checks, credit limits, follow-up automation, and multi-invoice layouts. Provides the foundation for `dynamic_accounts_report`.

**`dynamic_accounts_report/`** — Interactive financial reports (GL, Trial Balance, Balance Sheet, P&L, Cash Flow). Uses AJAX controllers + 11 JavaScript handlers for dynamic filtering.

**`odoo_website_helpdesk/`** — Customer-facing helpdesk with 17 models. Includes website portal, audio/video recording, ticket merging, and timesheet integration.

**`stock_quality/`** — Quality control layer over stock movements. Adds quality checks to `stock.move` and `product.template`.

**`sale_extended/`** — Extends sales orders for sales and spares workflows, with custom acknowledgement and report wizards.

### Standard Module Structure

All modules follow this Odoo convention:
```
module_name/
├── __manifest__.py      # name, version, depends, data files list
├── models/              # Business logic (inherit mail.thread for chatter)
├── views/               # Form/tree/search views + menus
├── wizard/              # Transient models for multi-step actions
├── security/            # ir.model.access.csv + record rules
├── data/                # Sequences, default data
├── static/src/          # JS (OWL), XML (QWeb), SCSS
├── report/              # QWeb PDF report templates
└── controllers/         # HTTP routes (AJAX endpoints)
```

### Frontend Stack

- OWL (Odoo Web Library) components for interactive widgets
- QWeb templates for views and PDF reports
- CDN assets used in some modules: `html2pdf.js` v0.10.1, `jsPDF` v3.0.2

### Testing

Tests use `odoo.tests.common.TransactionCase`. Only `purchase_cost_update` and `ica_web_responsive` have formal test suites. The `dashboard_ceo/` directory contains performance profiling scripts (`test_perf.py`, `test_profile.py`) that are standalone scripts, not Odoo test classes.

### Known Issues

- `material_request/__manifest__.py` references `wizard/purchae_request.xml` (typo — file is correctly named `purchase_request.xml` but listed with typo in manifest)
- `purchase_cost_update/tests/test_purchase_cost_update.py` has `from odoo import fields` at line 69 (after usage — move to top)
- `google_sheet_integration/` is an empty placeholder module with no implementation
