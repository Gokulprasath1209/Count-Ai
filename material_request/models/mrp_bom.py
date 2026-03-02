from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    # Compute a dynamic running sequence/serial number for UI viewing
    s_no = fields.Integer(
        string='S.no',
        compute='_compute_s_no',
        store=False
    )

    @api.depends('sequence', 'bom_id.bom_line_ids')
    def _compute_s_no(self):
        for bom in self.mapped('bom_id'):
            # The lines are already ordered by sequence in standard Odoo
            for index, line in enumerate(bom.bom_line_ids.sorted('sequence'), start=1):
                line.s_no = index

    @api.constrains('product_id', 'bom_id')
    def _check_duplicate_component(self):
        """ Prevent duplicate products in the same Bill of Materials """
        for line in self:
            if line.bom_id and line.product_id:
                # Count occurrences of this product in the current BOM
                duplicate_count = self.search_count([
                    ('bom_id', '=', line.bom_id.id),
                    ('product_id', '=', line.product_id.id)
                ])
                if duplicate_count > 1:
                    raise ValidationError(_(
                        "Duplicate Component Detected: You cannot add '%s' more than once to this Bill of Materials."
                    ) % line.product_id.display_name)

    @api.constrains('product_qty')
    def _check_minimum_quantity(self):
        """ Prevent zero or negative quantities that break stock moves """
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(_(
                    "Invalid Quantity: The component '%s' has a quantity of %s. Component quantity must be strictly greater than 0."
                ) % (line.product_id.display_name, line.product_qty))
