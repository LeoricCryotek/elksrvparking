from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RvExtendStayWizard(models.TransientModel):
    _name = "elks.rv.extend.stay.wizard"
    _description = "Extend RV Stay"

    registration_id = fields.Many2one(
        "elks.rv.registration", string="Registration",
        required=True, readonly=True,
    )
    current_nights = fields.Integer(
        string="Current Nights", readonly=True,
    )
    max_nights = fields.Integer(
        string="Max Consecutive Nights", readonly=True,
    )
    extra_nights = fields.Integer(
        string="Add Nights", default=1, required=True,
    )
    new_total = fields.Integer(
        string="New Total Nights",
        compute="_compute_new_total",
    )

    @api.depends("current_nights", "extra_nights")
    def _compute_new_total(self):
        for rec in self:
            rec.new_total = (rec.current_nights or 0) + (rec.extra_nights or 0)

    def action_extend(self):
        self.ensure_one()
        reg = self.registration_id
        if reg.state not in ("draft", "registered"):
            raise UserError(
                _("Only draft or registered stays can be extended.")
            )
        if self.extra_nights < 1:
            raise UserError(_("Please enter at least 1 extra night."))
        # Staff may extend beyond the usual maximum; log it as an override
        # rather than blocking.
        over_max = bool(self.max_nights and self.new_total > self.max_nights)
        reg.nights = self.new_total
        reg.message_post(
            body=_(
                "<b>Stay Extended</b> — added %d night(s), "
                "now %d total (check-out %s).%s",
                self.extra_nights, self.new_total, reg.check_out,
                (_(" Staff override: above the usual maximum of %d nights.")
                 % self.max_nights) if over_max else "",
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {"type": "ir.actions.act_window_close"}
