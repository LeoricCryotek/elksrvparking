import json
from datetime import date, timedelta
from urllib.parse import quote_plus

from odoo import http
from odoo.http import request


class RvParkingWebsite(http.Controller):
    """Public website pages for RV parking availability and reservation."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_settings(self):
        return request.env["elks.lodge.settings"].sudo().search([], limit=1)

    def _get_map_address(self, settings):
        """Build a one-line address for Google Maps, preferring RV-specific
        address fields and falling back to the lodge address."""
        if not settings:
            return ""
        # Prefer RV parking address if set
        if settings.rv_address:
            parts = [settings.rv_address]
            csz = []
            if settings.rv_city:
                csz.append(settings.rv_city)
            if settings.rv_state:
                csz.append(settings.rv_state)
            if csz:
                parts.append(", ".join(csz))
            if settings.rv_zip:
                parts[-1] = parts[-1] + " " + settings.rv_zip if parts else settings.rv_zip
            return ", ".join(parts)
        # Fall back to lodge address
        parts = []
        if settings.lodge_address:
            parts.append(settings.lodge_address)
        csz = []
        if settings.lodge_city:
            csz.append(settings.lodge_city)
        if settings.lodge_state:
            csz.append(settings.lodge_state)
        if csz:
            parts.append(", ".join(csz))
        if settings.lodge_zip:
            parts[-1] = parts[-1] + " " + settings.lodge_zip if parts else settings.lodge_zip
        return ", ".join(parts)

    def _occupancy_on_date(self, target_date):
        """Return count of registrations occupying a space on *target_date*.

        A registration occupies a space when:
          check_in <= target_date < check_out  (check-out day is free)
        Only draft and registered states count (not cancelled/checked_out).
        """
        return request.env["elks.rv.registration"].sudo().search_count([
            ("state", "in", ("draft", "registered")),
            ("check_in", "<=", target_date),
            ("check_out", ">", target_date),
        ])

    def _month_calendar(self, year, month, total_spaces):
        """Build a list-of-weeks structure for the template calendar grid."""
        import calendar
        cal = calendar.Calendar(firstweekday=6)  # Sunday start
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            days = []
            for d in week:
                if d.month == month:
                    occ = self._occupancy_on_date(d)
                    days.append({
                        "date": d,
                        "day": d.day,
                        "occupied": occ,
                        "available": max(total_spaces - occ, 0),
                        "full": occ >= total_spaces,
                        "in_month": True,
                    })
                else:
                    days.append({"date": d, "day": d.day, "in_month": False})
            weeks.append(days)
        return weeks

    # ------------------------------------------------------------------
    # Public availability page
    # ------------------------------------------------------------------
    @http.route("/rv-parking", type="http", auth="public", website=True,
                sitemap=True)
    def rv_availability(self, month=None, year=None, **kw):
        settings = self._get_settings()
        total_spaces = settings.rv_total_spaces if settings else 10
        nightly_rate = settings.rv_nightly_rate if settings else 25.0

        today = date.today()
        try:
            year = int(year) if year else today.year
            month = int(month) if month else today.month
        except (ValueError, TypeError):
            year, month = today.year, today.month

        # Clamp to valid month
        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1

        warning_threshold = settings.rv_warning_threshold if settings else 2

        current_occupancy = self._occupancy_on_date(today)
        weeks = self._month_calendar(year, month, total_spaces)

        # Previous / next month links
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1

        import calendar
        month_name = calendar.month_name[month]

        lodge_name = settings.name if settings else "Elks Lodge"
        lodge_number = settings.lodge_number if settings else ""

        return request.render("elksrvparking.rv_availability_page", {
            "settings": settings,
            "lodge_name": lodge_name,
            "lodge_number": lodge_number,
            "total_spaces": total_spaces,
            "nightly_rate": nightly_rate,
            "current_occupancy": current_occupancy,
            "spaces_available": max(total_spaces - current_occupancy, 0),
            "weeks": weeks,
            "month": month,
            "year": year,
            "month_name": month_name,
            "today": today,
            "prev_month": prev_month,
            "prev_year": prev_year,
            "next_month": next_month,
            "next_year": next_year,
            "warning_threshold": warning_threshold,
        })

    # ------------------------------------------------------------------
    # JSON availability check for date range
    # ------------------------------------------------------------------
    @http.route("/rv-parking/check", type="jsonrpc", auth="public",
                methods=["POST"], csrf=False)
    def rv_check_availability(self, check_in=None, nights=1, **kw):
        settings = self._get_settings()
        total_spaces = settings.rv_total_spaces if settings else 10

        try:
            ci = date.fromisoformat(check_in)
            nights = max(int(nights), 1)
        except (ValueError, TypeError):
            return {"error": "Invalid date or nights value."}

        results = []
        for i in range(nights):
            d = ci + timedelta(days=i)
            occ = self._occupancy_on_date(d)
            results.append({
                "date": d.isoformat(),
                "occupied": occ,
                "available": max(total_spaces - occ, 0),
                "full": occ >= total_spaces,
            })

        all_available = all(not r["full"] for r in results)
        return {
            "available": all_available,
            "total_spaces": total_spaces,
            "nights": results,
        }

    # ------------------------------------------------------------------
    # Reservation request form (GET = show form, POST = submit)
    # ------------------------------------------------------------------
    @http.route("/rv-parking/request", type="http", auth="public",
                website=True, methods=["GET"], sitemap=True)
    def rv_request_form(self, check_in=None, nights=1, **kw):
        settings = self._get_settings()
        nightly_rate = settings.rv_nightly_rate if settings else 25.0
        total_spaces = settings.rv_total_spaces if settings else 10
        max_nights = settings.rv_max_nights if settings else 7
        today = date.today()

        return request.render("elksrvparking.rv_request_page", {
            "settings": settings,
            "nightly_rate": nightly_rate,
            "total_spaces": total_spaces,
            "max_nights": max_nights or 30,
            "today": today.isoformat(),
            "check_in": check_in or today.isoformat(),
            "nights": int(nights) if nights else 1,
            "lodge_name": settings.name if settings else "Elks Lodge",
            "lodge_number": settings.lodge_number if settings else "",
            # Defaults so template t-att-value expressions don't error
            "error": False,
            "guest_name": "",
            "member_number": "",
            "home_lodge_number": "",
            "home_lodge_name": "",
            "home_lodge_state": "",
            "contact_phone": "",
        })

    @http.route("/rv-parking/request", type="http", auth="public",
                website=True, methods=["POST"], csrf=True)
    def rv_request_submit(self, **post):
        settings = self._get_settings()

        guest_name = (post.get("guest_name") or "").strip()
        member_number = (post.get("member_number") or "").strip()
        home_lodge_number = (post.get("home_lodge_number") or "").strip()
        home_lodge_name = (post.get("home_lodge_name") or "").strip()
        home_lodge_state = (post.get("home_lodge_state") or "").strip() or False
        contact_phone = (post.get("contact_phone") or "").strip()
        check_in_str = post.get("check_in", "")
        nights = max(int(post.get("nights", 1) or 1), 1)
        max_nights = settings.rv_max_nights if settings else 7
        if max_nights and nights > max_nights:
            nights = max_nights

        try:
            check_in_date = date.fromisoformat(check_in_str)
        except (ValueError, TypeError):
            check_in_date = date.today()

        # --- Availability check: reject if any night in the stay is full ---
        total_spaces = settings.rv_total_spaces if settings else 10
        full_dates = []
        for i in range(nights):
            d = check_in_date + timedelta(days=i)
            if self._occupancy_on_date(d) >= total_spaces:
                full_dates.append(d.strftime("%m/%d/%Y"))

        if full_dates:
            nightly_rate = settings.rv_nightly_rate if settings else 25.0
            error_msg = (
                "Sorry, the RV lot is fully booked on the following date(s): "
                + ", ".join(full_dates)
                + ". Please choose different dates."
            )
            return request.render("elksrvparking.rv_request_page", {
                "settings": settings,
                "nightly_rate": nightly_rate,
                "total_spaces": total_spaces,
                "max_nights": max_nights or 30,
                "today": date.today().isoformat(),
                "check_in": check_in_str,
                "nights": nights,
                "lodge_name": settings.name if settings else "Elks Lodge",
                "lodge_number": settings.lodge_number if settings else "",
                "error": error_msg,
                "guest_name": guest_name,
                "member_number": member_number,
                "home_lodge_number": home_lodge_number,
                "home_lodge_name": home_lodge_name,
                "home_lodge_state": home_lodge_state,
                "contact_phone": contact_phone,
            })

        # Create draft registration
        Registration = request.env["elks.rv.registration"].sudo()
        reg = Registration.create({
            "guest_name": guest_name or "Website Request",
            "member_number": member_number,
            "home_lodge_number": home_lodge_number,
            "home_lodge_name": home_lodge_name,
            "home_lodge_state": home_lodge_state,
            "contact_phone": contact_phone,
            "check_in": check_in_date,
            "nights": nights,
            "state": "draft",
            "booking_source": "website",
        })

        # Send email notification
        notify_email = settings.rv_notification_email if settings else False
        if notify_email:
            nightly_rate = settings.rv_nightly_rate if settings else 25.0
            total = nights * nightly_rate
            body = (
                "<h3>New RV Parking Reservation Request</h3>"
                "<p><b>Registration:</b> %s</p>"
                "<p><b>Guest:</b> %s</p>"
                "<p><b>Member #:</b> %s</p>"
                "<p><b>Home Lodge:</b> #%s %s</p>"
                "<p><b>Phone:</b> %s</p>"
                "<p><b>Check-In:</b> %s</p>"
                "<p><b>Nights:</b> %d</p>"
                "<p><b>Estimated Donation:</b> $%.2f</p>"
                "<p>Please review and confirm this reservation in the "
                "RV Parking module.</p>"
            ) % (
                reg.name, guest_name, member_number,
                home_lodge_number, home_lodge_name,
                contact_phone, check_in_date.strftime("%m/%d/%Y"),
                nights, total,
            )
            try:
                mail = request.env["mail.mail"].sudo().create({
                    "subject": "RV Reservation Request — %s" % reg.name,
                    "body_html": body,
                    "email_from": (
                        request.env.company.email
                        or "noreply@localhost"
                    ),
                    "email_to": notify_email,
                    "auto_delete": True,
                })
                mail.send()
            except Exception:
                pass  # Don't break the user flow if email fails

        lodge_name = settings.name if settings else "Elks Lodge"
        map_address = self._get_map_address(settings)
        rv_slip_note = settings.rv_slip_note if settings else ""
        return request.render("elksrvparking.rv_request_thanks", {
            "reg": reg,
            "lodge_name": lodge_name,
            "map_address": map_address,
            "map_query": quote_plus(map_address) if map_address else "",
            "rv_slip_note": rv_slip_note,
        })

    # ------------------------------------------------------------------
    # Printable guest registration slip (public)
    # ------------------------------------------------------------------
    @http.route("/rv-parking/receipt/<int:reg_id>", type="http",
                auth="public", website=True)
    def rv_guest_receipt(self, reg_id, **kw):
        reg = request.env["elks.rv.registration"].sudo().browse(reg_id)
        if not reg.exists():
            return request.redirect("/rv-parking")
        settings = self._get_settings()
        lodge_name = settings.name if settings else "Elks Lodge"
        lodge_number = settings.lodge_number if settings else ""
        # Build formatted address line
        addr_parts = []
        if settings and settings.lodge_address:
            addr_parts.append(settings.lodge_address)
        city_state_zip = []
        if settings and settings.lodge_city:
            city_state_zip.append(settings.lodge_city)
        if settings and settings.lodge_state:
            city_state_zip.append(settings.lodge_state)
        if city_state_zip:
            addr_parts.append(", ".join(city_state_zip))
        if settings and settings.lodge_zip:
            addr_parts[-1] = addr_parts[-1] + " " + settings.lodge_zip if addr_parts else settings.lodge_zip
        lodge_address = ", ".join(addr_parts) if addr_parts else ""
        lodge_phone = settings.lodge_phone if settings else ""
        map_address = self._get_map_address(settings)
        map_query = quote_plus(map_address) if map_address else ""
        rv_slip_note = settings.rv_slip_note if settings else ""
        # QR code: free API, always available — links to Google Maps directions
        qr_url = ""
        if map_query:
            maps_url = "https://www.google.com/maps/dir/?api=1&destination=%s" % map_query
            qr_url = (
                "https://api.qrserver.com/v1/create-qr-code/"
                "?size=150x150&data=%s" % quote_plus(maps_url)
            )
        return request.render("elksrvparking.rv_guest_receipt_page", {
            "reg": reg,
            "settings": settings,
            "lodge_name": lodge_name,
            "lodge_number": lodge_number,
            "lodge_address": lodge_address,
            "lodge_phone": lodge_phone,
            "map_address": map_address,
            "map_query": map_query,
            "rv_slip_note": rv_slip_note,
            "qr_url": qr_url,
        })
