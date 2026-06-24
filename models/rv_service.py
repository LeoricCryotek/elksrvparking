from urllib.parse import quote_plus

from odoo import api, fields, models


class RvService(models.Model):
    """A single RV service / amenity (Water, Power, Sewer, etc.).

    Attached to the singleton lodge settings record. Lodge staff mark each
    service as on-site, nearby (off-site), or not available, and the
    available ones are shown on the public website pages. For services that
    are not on-site, staff can record the nearest location's name, address,
    and a map link (e.g. nearest sewer dump station, water fill, power).
    """

    _name = "elks.rv.service"
    _description = "RV Parking Service / Amenity"
    _order = "sequence, id"

    settings_id = fields.Many2one(
        "elks.lodge.settings",
        string="Lodge Settings",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string="Service",
        required=True,
        help="Name of the service or amenity (e.g. Water Hookup, "
             "Power / Electric, Sewer Hookup, Dump Station, WiFi).",
    )
    icon = fields.Char(
        string="Icon",
        default="fa-check",
        help="Optional Font Awesome icon class shown on the website "
             "(e.g. fa-tint, fa-bolt, fa-wifi). Leave as fa-check if unsure.",
    )
    availability = fields.Selection(
        [
            ("onsite", "On-site"),
            ("nearby", "Nearby (off-site)"),
            ("unavailable", "Not available"),
        ],
        string="Availability",
        default="onsite",
        required=True,
        help="On-site: available at the RV lot. Nearby: not on-site, but "
             "available at a nearby location (enter the address below). "
             "Not available: hidden from the website.",
    )
    detail = fields.Char(
        string="Detail",
        help="Optional detail shown next to the service "
             "(e.g. '30/50 amp', 'Potable', 'Free').",
    )
    location_name = fields.Char(
        string="Nearest Location Name",
        help="For nearby (off-site) services: the name of the nearest place "
             "that offers it (e.g. 'Flying J Travel Center', "
             "'City RV Dump Station').",
    )
    location_address = fields.Char(
        string="Nearest Location Address",
        help="For nearby (off-site) services: the address guests should go to "
             "(e.g. sewer dumping address, water fill, power). Shown on the "
             "website with a map link.",
    )
    show_on_website = fields.Boolean(
        string="Show on Website",
        default=True,
        help="When enabled (and availability is On-site or Nearby), this "
             "service appears on the public RV parking pages.",
    )
    map_query = fields.Char(
        string="Map Query",
        compute="_compute_map_query",
        help="URL-encoded query used to build the Google Maps link for "
             "nearby services.",
    )

    @api.depends("location_name", "location_address")
    def _compute_map_query(self):
        for rec in self:
            parts = [p for p in (rec.location_name, rec.location_address) if p]
            rec.map_query = quote_plus(", ".join(parts)) if parts else ""

    @api.model
    def _default_service_vals(self):
        """Common RV services seeded on install / via the config button."""
        return [
            {"sequence": 10, "name": "Water Hookup", "icon": "fa-tint",
             "availability": "onsite"},
            {"sequence": 20, "name": "Power / Electric", "icon": "fa-bolt",
             "availability": "onsite", "detail": "30/50 amp"},
            {"sequence": 30, "name": "Sewer Hookup", "icon": "fa-recycle",
             "availability": "onsite"},
            {"sequence": 40, "name": "Dump Station", "icon": "fa-trash",
             "availability": "onsite"},
            {"sequence": 50, "name": "WiFi", "icon": "fa-wifi",
             "availability": "onsite"},
            {"sequence": 60, "name": "Restrooms", "icon": "fa-bath",
             "availability": "onsite"},
            {"sequence": 70, "name": "Showers", "icon": "fa-bath",
             "availability": "onsite"},
            {"sequence": 80, "name": "Trash Disposal", "icon": "fa-trash",
             "availability": "onsite"},
        ]
