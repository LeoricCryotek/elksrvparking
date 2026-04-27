from odoo import _, api, fields, models


class RvQuickRegisterWizard(models.TransientModel):
    _name = "elks.rv.quick.register.wizard"
    _description = "Quick RV Registration"

    guest_name = fields.Char(string="Guest Name (optional)")
    member_number = fields.Char(string="Member # (optional)")
    home_lodge_number = fields.Char(string="Home Lodge # (optional)")
    home_lodge_name = fields.Char(string="Home Lodge Name (optional)")
    contact_phone = fields.Char(string="Contact Phone (optional)")
    nights = fields.Integer(string="Nights", default=1, required=True)
    nightly_rate = fields.Float(
        string="Nightly Rate ($)", digits=(10, 2), required=True,
    )
    total_amount = fields.Float(
        string="Total ($)", digits=(10, 2),
        compute="_compute_total_amount", store=True, readonly=False,
    )
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("check", "Check"),
            ("card", "Card"),
            ("other", "Other"),
        ],
        string="Payment Method", default="cash", required=True,
    )
    notes = fields.Text(string="Notes (optional)")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        if settings and "nightly_rate" in fields_list:
            res["nightly_rate"] = settings.rv_nightly_rate or 25.0
        return res

    @api.depends("nights", "nightly_rate")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = (rec.nights or 0) * (rec.nightly_rate or 0.0)

    def action_register(self):
        """Create the registration and immediately mark it as registered."""
        self.ensure_one()
        Registration = self.env["elks.rv.registration"]
        vals = {
            "guest_name": self.guest_name or _("Walk-in"),
            "member_number": self.member_number,
            "home_lodge_number": self.home_lodge_number,
            "home_lodge_name": self.home_lodge_name,
            "contact_phone": self.contact_phone,
            "check_in": fields.Date.context_today(self),
            "nights": self.nights,
            "nightly_rate": self.nightly_rate,
            "total_amount": self.total_amount,
            "payment_method": self.payment_method,
            "notes": self.notes,
        }
        reg = Registration.create(vals)
        reg.action_register()
        return {
            "type": "ir.actions.act_window",
            "res_model": "elks.rv.registration",
            "res_id": reg.id,
            "view_mode": "form",
            "target": "current",
        }
