from odoo import _, api, fields, models


class RvOccupancyReportWizard(models.TransientModel):
    _name = "elks.rv.occupancy.report.wizard"
    _description = "RV Parking Occupancy Report Wizard"

    date_from = fields.Date(
        string="From", required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="To", required=True,
        default=fields.Date.today,
    )

    def action_print_report(self):
        """Preview the occupancy report (HTML)."""
        self.ensure_one()
        return self.env.ref(
            "elksrvparking.action_report_rv_occupancy"
        ).report_action(self)

    def action_download_pdf(self):
        """Download the occupancy report as PDF."""
        self.ensure_one()
        return self.env.ref(
            "elksrvparking.action_report_rv_occupancy_pdf"
        ).report_action(self)

    def _prepare_report_data(self):
        Reg = self.env["elks.rv.registration"]
        settings = self.env["elks.lodge.settings"].sudo().search([], limit=1)
        total_spaces = settings.rv_total_spaces if settings else 10

        # All non-cancelled registrations overlapping the date range
        regs = Reg.search([
            ("state", "!=", "cancelled"),
            ("check_in", "<=", self.date_to),
            ("check_out", ">=", self.date_from),
        ])

        total_regs = len(regs)
        total_nights = sum(r.nights for r in regs)
        total_suggested = sum(r.total_amount for r in regs)
        total_paid = sum(r.amount_paid or 0.0 for r in regs)

        staff_regs = regs.filtered(lambda r: r.booking_source == "staff")
        web_regs = regs.filtered(lambda r: r.booking_source == "website")

        # Occupancy calculation
        date_range_days = (self.date_to - self.date_from).days + 1
        total_capacity = total_spaces * date_range_days
        occupancy_pct = (
            (total_nights / total_capacity * 100) if total_capacity > 0 else 0
        )

        # Per-registration detail
        detail_lines = []
        for r in regs.sorted(key=lambda x: x.check_in):
            detail_lines.append({
                "name": r.name,
                "guest_name": r.guest_name or (
                    r.partner_id.name if r.partner_id else "Unknown"
                ),
                "check_in": r.check_in,
                "check_out": r.check_out,
                "nights": r.nights,
                "total_amount": r.total_amount,
                "amount_paid": r.amount_paid or 0.0,
                "booking_source": dict(
                    r._fields["booking_source"].selection
                ).get(r.booking_source, r.booking_source or "Staff"),
                "state": dict(
                    r._fields["state"].selection
                ).get(r.state, r.state),
                "payment_method": dict(
                    r._fields["payment_method"].selection
                ).get(r.payment_method, r.payment_method or ""),
            })

        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "lodge_name": settings.name if settings else "Elks Lodge",
            "lodge_number": settings.lodge_number if settings else "",
            "total_spaces": total_spaces,
            "date_range_days": date_range_days,
            "total_capacity": total_capacity,
            "total_regs": total_regs,
            "total_nights": total_nights,
            "total_suggested": total_suggested,
            "total_paid": total_paid,
            "occupancy_pct": round(occupancy_pct, 1),
            "staff_count": len(staff_regs),
            "staff_nights": sum(r.nights for r in staff_regs),
            "staff_paid": sum(r.amount_paid or 0.0 for r in staff_regs),
            "web_count": len(web_regs),
            "web_nights": sum(r.nights for r in web_regs),
            "web_paid": sum(r.amount_paid or 0.0 for r in web_regs),
            "lines": detail_lines,
        }
