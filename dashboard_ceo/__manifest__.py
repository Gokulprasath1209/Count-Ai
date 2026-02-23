{
    'name': 'CEO Super Dashboard',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Premium Dashboard for CEO with real-time analytics',
    'description': """
        Real-time business intelligence & analytics for CEO.
        Features:
        - Executive Summary
        - Revenue vs Spend Trend
        - Project Health Overview
        - Approval Bottlenecks
        - Top Vendors Analysis
    """,
    'author': 'Gokulprasath',
    'depends': ['base', 'web', 'project', 'account', 'stock', 'material_request', 'sale_extended'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/stock_picking_views.xml',
        'views/approval_records_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dashboard_ceo/static/src/scss/ceo_dashboard.scss',
            'dashboard_ceo/static/src/js/ceo_dashboard.js',
            'dashboard_ceo/static/src/xml/ceo_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
