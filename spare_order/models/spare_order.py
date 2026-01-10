from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_or_spare = fields.Selection(
        [
            ("sale", "Sale"),
            ("spare", "Spare"),
        ],
        string="Order Type",
        default="sale",
        required=True,
        tracking=True,
    )

    @api.model
    def create(self, vals):
        """
        Use Spare sequence for spare orders.
        Sale orders continue using default Sale sequence.
        """
        if vals.get("sale_or_spare") == "spare":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "sale.order.spare"
            ) or "New"
        return super().create(vals)
