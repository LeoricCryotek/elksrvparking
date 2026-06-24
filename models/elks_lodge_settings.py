from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ElksLodgeSettings(models.Model):
    _inherit = "elks.lodge.settings"

    rv_nightly_rate = fields.Float(
        string="RV Nightly Rate ($)",
        default=25.00,
        help="Suggested donation per night for RV parking.",
    )
    rv_income_account_id = fields.Many2one(
        "elks.account",
        string="RV Income Account",
        help="Elks GL account to credit when an RV parking donation is posted "
             "to the FRS journal (e.g. Miscellaneous Income).",
    )
    rv_total_spaces = fields.Integer(
        string="Total RV Spaces",
        default=10,
        help="Total number of RV parking spaces available at the lodge.",
    )
    rv_max_nights = fields.Integer(
        string="Max Consecutive Nights",
        default=7,
        help="Maximum number of consecutive nights a guest may stay. "
             "Set based on local zoning or lodge rules.",
    )
    rv_notification_email = fields.Char(
        string="Reservation Notification Email",
        help="Email address that receives notifications when a guest submits "
             "a reservation request from the website.",
    )
    rv_warning_threshold = fields.Integer(
        string="Limited Availability Threshold",
        default=2,
        help="When available spaces drop to this number or below, the "
             "calendar shows a yellow 'Limited' warning instead of green.",
    )
    rv_website_published = fields.Boolean(
        string="Show RV Parking in Website Menu",
        default=False,
        help="When enabled, an 'RV Parking' link appears in the public "
             "website navigation menu.",
    )

    # RV parking location (may differ from lodge address)
    rv_use_lodge_address = fields.Boolean(
        string="Same as Lodge Address",
        default=False,
        help="Check to copy the lodge address into the RV parking address fields.",
    )
    rv_address = fields.Char(
        string="RV Parking Address",
        help="Street address of the RV parking area, if different from "
             "the lodge address. Used for the Google Map on guest pages.",
    )
    rv_city = fields.Char(string="RV City")
    rv_state = fields.Selection([
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'),
        ('AR', 'Arkansas'), ('CA', 'California'), ('CO', 'Colorado'),
        ('CT', 'Connecticut'), ('DE', 'Delaware'), ('FL', 'Florida'),
        ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'),
        ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'),
        ('ME', 'Maine'), ('MD', 'Maryland'), ('MA', 'Massachusetts'),
        ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'),
        ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'),
        ('NM', 'New Mexico'), ('NY', 'New York'), ('NC', 'North Carolina'),
        ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'),
        ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'),
        ('TX', 'Texas'), ('UT', 'Utah'), ('VT', 'Vermont'),
        ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming'),
        ('DC', 'District of Columbia'),
        ('PR', 'Puerto Rico'), ('GU', 'Guam'), ('VI', 'U.S. Virgin Islands'),
    ], string="RV State")
    rv_zip = fields.Char(string="RV ZIP Code")

    rv_auto_checkout = fields.Boolean(
        string="Auto Check-Out at Scheduled End of Stay",
        default=True,
        help="When enabled, a daily cron job automatically checks out "
             "guests whose stay ends today. Runs at 3:00 PM lodge time.",
    )
    rv_checkout_hour = fields.Integer(
        string="Auto Check-Out Hour (24h)",
        default=15,
        help="Hour of day (0–23) when the auto-checkout cron runs. "
             "Default is 15 (3:00 PM).",
    )

    rv_slip_note = fields.Text(
        string="Registration Slip Note",
        help="Special note displayed on the thank-you page and printable "
             "guest registration slip (e.g. check-in instructions, "
             "rules, Wi-Fi info).",
    )

    # RV services / amenities (Water, Power, Sewer, etc.)
    rv_service_ids = fields.One2many(
        "elks.rv.service",
        "settings_id",
        string="RV Services & Amenities",
        help="Mark which services are available so they show on the public "
             "RV parking pages. For services that are not on-site, set them "
             "to 'Nearby' and enter the nearest location's address.",
    )

    @api.onchange("rv_use_lodge_address")
    def _onchange_rv_use_lodge_address(self):
        if self.rv_use_lodge_address:
            self.rv_address = self.lodge_address or ""
            self.rv_city = self.lodge_city or ""
            self.rv_state = self.lodge_state or False
            self.rv_zip = self.lodge_zip or ""

    @api.constrains("rv_warning_threshold", "rv_total_spaces")
    def _check_warning_threshold(self):
        for rec in self:
            if rec.rv_warning_threshold and rec.rv_total_spaces:
                if rec.rv_warning_threshold >= rec.rv_total_spaces:
                    raise ValidationError(
                        _("Limited Availability Threshold (%d) must be less "
                          "than Total RV Spaces (%d).")
                        % (rec.rv_warning_threshold, rec.rv_total_spaces)
                    )

    def write(self, vals):
        res = super().write(vals)
        if "rv_website_published" in vals:
            self._sync_rv_website_menu(vals["rv_website_published"])
        return res

    def _sync_rv_website_menu(self, published):
        """Create or remove the public website menu item for RV Parking."""
        Menu = self.env["website.menu"].sudo()
        website = self.env["website"].sudo().search([], limit=1)
        if not website:
            return
        existing = Menu.search([
            ("url", "=", "/rv-parking"),
            ("website_id", "=", website.id),
        ], limit=1)
        if published and not existing:
            # Find the top-level website menu to use as parent
            top_menu = Menu.search([
                ("parent_id", "=", False),
                ("website_id", "=", website.id),
            ], limit=1)
            Menu.create({
                "name": "RV Parking",
                "url": "/rv-parking",
                "parent_id": top_menu.id if top_menu else False,
                "website_id": website.id,
                "sequence": 60,
            })
        elif not published and existing:
            existing.unlink()

    # ------------------------------------------------------------------
    # RV services helpers
    # ------------------------------------------------------------------
    def get_website_rv_services(self):
        """Services to display on the public website (on-site or nearby)."""
        self.ensure_one()
        return self.rv_service_ids.filtered(
            lambda s: s.show_on_website
            and s.availability in ("onsite", "nearby")
        ).sorted(lambda s: (s.sequence, s.id))

    @api.model
    def _seed_default_rv_services(self):
        """Create the default set of RV services on the singleton settings
        record if it has none yet. Called from the module post-init hook."""
        settings = self.sudo().search([], limit=1)
        if settings and not settings.rv_service_ids:
            Service = self.env["elks.rv.service"].sudo()
            Service.create([
                dict(vals, settings_id=settings.id)
                for vals in Service._default_service_vals()
            ])
        return settings

    def action_load_default_rv_services(self):
        """Add any missing default services (by name) without duplicating
        ones the user already has."""
        self.ensure_one()
        Service = self.env["elks.rv.service"]
        existing = set(self.rv_service_ids.mapped("name"))
        to_create = [
            dict(vals, settings_id=self.id)
            for vals in Service._default_service_vals()
            if vals["name"] not in existing
        ]
        if to_create:
            Service.create(to_create)
        return True

    def action_open_rv_config(self):
        """Open the RV Parking configuration for the singleton settings record."""
        settings = self.sudo().search([], limit=1)
        if not settings:
            raise UserError(
                _("Please configure Lodge Settings in the FRS module first.")
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "elks.lodge.settings",
            "res_id": settings.id,
            "view_mode": "form",
            "view_id": self.env.ref("elksrvparking.view_rv_config_form").id,
            "target": "current",
        }
