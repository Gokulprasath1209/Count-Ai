{
    "name": "Spare Orders (Sale Engine)",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Spare Orders using full Sale module functionality",
    "description": """
Spare Orders Module
==================
This module provides Spare Orders using the complete Sale module engine.
All Sale features like quotations, orders, invoices, delivery, reports,
dashboards, activities, and chatter are reused without duplication.
""",
    "author": "Your Company",
    "depends": [
        "sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sapre_views.xml",
        "views/spare_sequences.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
