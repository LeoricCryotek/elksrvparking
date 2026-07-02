from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RvRegistration(models.Model):
    _name = "elks.rv.registration"
    _description = "RV Parking Registration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "check_in desc, id desc"

    # ------------------------------------------------------------------
    # Sequence / reference
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Registration #", readonly=True, copy=False,
        default=lambda self: _("New"),
    )

    # ------------------------------------------------------------------
    # Guest info
    # ------------------------------------------------------------------
    is_unknown_member = fields.Boolean(
        string="Unknown Member", default=False, tracking=True,
        help="Toggle on if the guest's identity is not known.",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Member", tracking=True, index=True,
        domain="[('x_is_member', '=', True)]",
        help="Select an existing contact or leave blank for walk-ins.",
    )
    guest_name = fields.Char(
        string="Guest Name", tracking=True,
        help="Name as written if not linked to a contact.",
    )
    member_number = fields.Char(
        string="Member #", required=True, tracking=True,
    )
    home_lodge_number = fields.Char(
        string="Home Lodge #", tracking=True,
    )
    home_lodge_name = fields.Char(
        string="Home Lodge Name", tracking=True,
    )
    home_lodge_state = fields.Selection(
        [
            ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"),
            ("AR", "Arkansas"), ("CA", "California"), ("CO", "Colorado"),
            ("CT", "Connecticut"), ("DE", "Delaware"), ("FL", "Florida"),
            ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"),
            ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
            ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"),
            ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"),
            ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
            ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
            ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"),
            ("NM", "New Mexico"), ("NY", "New York"), ("NC", "North Carolina"),
            ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
            ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"),
            ("SC", "South Carolina"), ("SD", "South Dakota"),
            ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"),
            ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"),
            ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
            ("DC", "District of Columbia"), ("PR", "Puerto Rico"),
            ("GU", "Guam"), ("VI", "U.S. Virgin Islands"),
        ],
        string="Home Lodge State", tracking=True,
    )
    contact_phone = fields.Char(
        string="Contact Phone", tracking=True,
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    registration_date = fields.Date(
        string="Registered On", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Date this registration was created (e.g. when a reservation "
             "call came in). Auto-filled on creation.",
    )
    check_in = fields.Date(
        string="Check-In", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Planned or actual arrival date.",
    )
    check_out = fields.Date(
        string="Check-Out", tracking=True,
        compute="_compute_check_out", store=True, readonly=False,
        help="Computed from Check-In + Nights, or set manually.",
    )
    nights = fields.Integer(
        string="Nights", default=1, required=True, tracking=True,
    )

    # ------------------------------------------------------------------
    # Occupancy
    # ------------------------------------------------------------------
    space_number = fields.Char(
        string="Space #", tracking=True, index=True,
        help="RV lot space assigned to this guest (e.g. 5, A-2, Back Row 3).",
    )
    num_occupants = fields.Integer(
        string="People", default=1, tracking=True,
        help="Number of people staying in the RV.",
    )
    num_pets = fields.Integer(
        string="Pets", default=0, tracking=True,
        help="Number of pets staying with the guest.",
    )

    # ------------------------------------------------------------------
    # Rates / totals
    # ------------------------------------------------------------------
    nightly_rate = fields.Float(
        string="Nightly Rate ($)", digits=(10, 2), tracking=True,
    )
    total_amount = fields.Float(
        string="Suggested Total ($)", digits=(10, 2),
        compute="_compute_total_amount", store=True, readonly=False,
        tracking=True,
        help="Nights × Nightly Rate. This is the suggested donation amount.",
    )
    amount_paid = fields.Float(
        string="Amount Paid ($)", digits=(10, 2), tracking=True,
        help="Actual amount the guest paid. May differ from the suggested "
             "total if the guest chose to donate more or less.",
    )

    # ------------------------------------------------------------------
    # Booking source
    # ------------------------------------------------------------------
    booking_source = fields.Selection(
        [
            ("staff", "Staff"),
            ("website", "Website"),
        ],
        string="Booked Via", default="staff", tracking=True,
        help="How the reservation was created: by lodge staff or self-booked "
             "through the public website.",
    )

    # ------------------------------------------------------------------
    # Payment / accounting
    # ------------------------------------------------------------------
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("check", "Check"),
            ("card", "Card"),
            ("other", "Other"),
        ],
        string="Payment Method", default="cash", tracking=True,
    )
    post_to_frs = fields.Boolean(
        string="Post to FRS Journal", default=False,
        help="If checked, a journal entry will be created in the Elks FRS "
             "when this registration is confirmed.",
    )
    payment_account_id = fields.Many2one(
        "elks.account", string="Cash/Bank Account",
        domain="[('account_type', 'in', ['bank', 'asset'])]",
        tracking=True,
        help="Elks COA cash or bank account that received the donation.",
    )
    journal_entry_id = fields.Many2one(
        "elks.journal.entry", string="Journal Entry",
        readonly=True, copy=False,
    )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("registered", "Registered"),
            ("checked_out", "Checked Out"),
            ("cancelled", "Cancelled"),
        ],
        string="Status", default="draft", required=True,
        tracking=True, index=True,
    )
    notes = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends("check_in", "nights")
    def _compute_check_out(self):
        for rec in self:
            if rec.check_in and rec.nights and rec.nights > 0:
                rec.check_out = fields.Date.add(rec.check_in, days=rec.nights)
            elif not rec.check_out:
                rec.check_out = False

    @api.depends("nights", "nightly_rate")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = (rec.nights or 0) * (rec.nightly_rate or 0.0)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("nights")
    def _check_max_nights(self):
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        max_nights = settings.rv_max_nights if settings else 7
        for rec in self:
            if rec.nights and rec.nights > max_nights:
                raise ValidationError(
                    _(
                        "%(nights)d nights exceeds the maximum consecutive "
                        "stay of %(max)d nights.",
                        nights=rec.nights,
                        max=max_nights,
                    )
                )

    # ------------------------------------------------------------------
    # Defaults from Lodge Settings
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("elks.rv.registration")
                    or _("New")
                )
            if not vals.get("nightly_rate") and settings:
                vals["nightly_rate"] = settings.rv_nightly_rate or 25.0
        return super().create(vals_list)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Auto-fill guest fields from linked contact."""
        if self.partner_id:
            p = self.partner_id
            if not self.guest_name:
                self.guest_name = p.name
            if not self.member_number and hasattr(p, "x_detail_member_num"):
                self.member_number = p.x_detail_member_num
            if not self.home_lodge_number and hasattr(p, "x_detail_lodge_num"):
                self.home_lodge_number = p.x_detail_lodge_num
            if not self.home_lodge_name and hasattr(p, "x_lodge_report_lodge_name"):
                self.home_lodge_name = p.x_lodge_report_lodge_name
            if not self.contact_phone:
                self.contact_phone = p.phone or getattr(p, 'mobile', '') or ""

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def action_register(self):
        """Confirm the registration."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft registrations can be confirmed."))
            rec.state = "registered"
            if rec.post_to_frs and not rec.journal_entry_id:
                rec._create_journal_entry()
            rec.message_post(
                body=_(
                    "<b>Registered</b> — %s checked in for %d night(s). "
                    "Donation: $%.2f",
                    ("Unknown Member" if rec.is_unknown_member
                     else rec.guest_name or rec.partner_id.name or "Guest"),
                    rec.nights, rec.total_amount,
                ),
                subtype_xmlid="mail.mt_note",
            )

    def action_check_out(self):
        for rec in self:
            if rec.state != "registered":
                raise UserError(_("Only registered guests can be checked out."))
            if not rec.check_out:
                rec.check_out = fields.Date.context_today(self)
            rec.state = "checked_out"
            rec.message_post(
                body=_("<b>Checked Out</b> on %s.", rec.check_out),
                subtype_xmlid="mail.mt_note",
            )

    def action_cancel(self):
        for rec in self:
            if rec.state in ("checked_out",):
                raise UserError(
                    _("Cannot cancel a registration that is already checked out.")
                )
            rec.state = "cancelled"
            rec.message_post(
                body=_("<b>Cancelled</b> by %s.", self.env.user.name),
                subtype_xmlid="mail.mt_note",
            )

    def action_reset_to_draft(self):
        """Send a registration back to draft so it can be edited.

        Allowed from registered, checked out, or cancelled. Any posted FRS
        journal entry is left in place (a note is logged) so accounting is
        not silently changed."""
        for rec in self:
            if rec.state == "draft":
                raise UserError(_("This registration is already in draft."))
            if rec.journal_entry_id:
                rec.message_post(
                    body=_(
                        "<b>Reset to Draft</b> by %s. Note: FRS journal "
                        "entry <b>%s</b> is already posted and was left "
                        "unchanged — adjust it manually if the reservation "
                        "amount changes.",
                        self.env.user.name,
                        rec.journal_entry_id.display_name,
                    ),
                    subtype_xmlid="mail.mt_note",
                )
            else:
                rec.message_post(
                    body=_("<b>Reset to Draft</b> by %s.", self.env.user.name),
                    subtype_xmlid="mail.mt_note",
                )
            rec.state = "draft"

    # ------------------------------------------------------------------
    # FRS Journal Entry
    # ------------------------------------------------------------------
    def _create_journal_entry(self):
        self.ensure_one()
        if self.journal_entry_id:
            raise UserError(
                _("A journal entry already exists for this registration.")
            )
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        income_account = settings.rv_income_account_id if settings else False
        if not income_account:
            raise UserError(
                _(
                    "Please set an RV Income Account in Lodge Settings before "
                    "posting to the FRS journal."
                )
            )
        if not self.payment_account_id:
            raise UserError(
                _("Please select a Cash/Bank Account before posting.")
            )
        guest_label = (
            "Unknown Member" if self.is_unknown_member
            else self.guest_name or (self.partner_id.name if self.partner_id else "Guest")
        )
        memo = "RV Parking %s — %s (%d night(s))" % (
            self.name, guest_label, self.nights,
        )
        JE = self.env["elks.journal.entry"]
        entry = JE.create({
            "date": fields.Date.context_today(self),
            "memo": memo,
            "line_ids": [
                (0, 0, {
                    "account_id": self.payment_account_id.id,
                    "debit": self.amount_paid or self.total_amount,
                    "credit": 0.0,
                    "memo": "RV Parking %s" % self.name,
                }),
                (0, 0, {
                    "account_id": income_account.id,
                    "debit": 0.0,
                    "credit": self.amount_paid or self.total_amount,
                    "memo": "RV Parking %s" % self.name,
                }),
            ],
        })
        entry.action_post()
        self.journal_entry_id = entry.id

    # ------------------------------------------------------------------
    # Extend stay
    # ------------------------------------------------------------------
    def action_extend_stay(self):
        """Open wizard to add nights to an active or future registration."""
        self.ensure_one()
        if self.state not in ("draft", "registered"):
            raise UserError(
                _("Only draft or registered stays can be extended.")
            )
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        max_nights = settings.rv_max_nights if settings else 7
        return {
            "type": "ir.actions.act_window",
            "name": _("Extend Stay"),
            "res_model": "elks.rv.extend.stay.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_registration_id": self.id,
                "default_current_nights": self.nights,
                "default_max_nights": max_nights,
            },
        }

    # ------------------------------------------------------------------
    # Auto Check-Out Cron
    # ------------------------------------------------------------------
    @api.model
    def cron_auto_checkout(self):
        """Automatically check out guests whose stay ends today.

        Runs daily (default 3 PM).  Finds all 'registered' records
        whose check_out date is today or earlier and transitions them
        to 'checked_out'.
        """
        today = fields.Date.context_today(self)
        due = self.search([
            ("state", "=", "registered"),
            ("check_out", "<=", today),
            ("check_out", "!=", False),
        ])
        for rec in due:
            rec.state = "checked_out"
            rec.message_post(
                body=_(
                    "<b>Auto Checked Out</b> on %s "
                    "(scheduled end of stay).",
                    rec.check_out,
                ),
                subtype_xmlid="mail.mt_note",
            )
        if due:
            import logging
            logging.getLogger(__name__).info(
                "RV Park auto-checkout: %d guest(s) checked out.", len(due),
            )

    # ------------------------------------------------------------------
    # Print actions
    # ------------------------------------------------------------------
    def action_print_receipt(self):
        """Preview the RV receipt (HTML)."""
        return self.env.ref(
            "elksrvparking.action_report_rv_receipt"
        ).report_action(self)

    def action_download_receipt_pdf(self):
        """Download the RV receipt as PDF."""
        return self.env.ref(
            "elksrvparking.action_report_rv_receipt_pdf"
        ).report_action(self)

    def action_print_blank_slip(self):
        """Preview the blank registration slip (HTML)."""
        return self.env.ref(
            "elksrvparking.action_report_rv_blank_slip"
        ).report_action(self)

    def action_download_blank_slip_pdf(self):
        """Download the blank registration slip as PDF."""
        return self.env.ref(
            "elksrvparking.action_report_rv_blank_slip_pdf"
        ).report_action(self)
