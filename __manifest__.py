{
    "name": "Elks RV Parking",
    "version": "19.0.2.0",
    "category": "Elks Lodge/Services",
    "summary": "RV parking registration, receipts, public availability, and FRS journal posting.",
    "description": """
Elks RV Parking
================

First-come-first-serve RV parking registration for visiting Elks members.

Features
--------
* Register visiting members with RV parking
* Configurable nightly suggested-donation rate and space count
* Calendar view showing occupancy on the Registrations page
* Public website: availability calendar with live occupancy counter
* Online reservation request form with email notifications
* Print filled registration receipts or blank hand-write slips
* Optional posting to the Elks FRS journal system
* Tear-off guest receipt stub on blank slips
""",
    "author": "Danny Santiago",
    "website": "https://dannysantiago.info",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "website",
        "elksfrs",
        "elkssecretary",
    ],
    "data": [
        "security/elksrvparking_groups.xml",
        "security/ir.model.access.csv",
        "data/rv_sequence.xml",
        "data/rv_cron.xml",
        "report/rv_receipt_report.xml",
        "report/rv_blank_slip_report.xml",
        "report/rv_occupancy_report.xml",
        "wizard/rv_quick_register_wizard_views.xml",
        "wizard/rv_occupancy_report_wizard_views.xml",
        "wizard/rv_extend_stay_wizard_views.xml",
        "views/rv_registration_views.xml",
        "views/lodge_settings_views.xml",
        "views/rv_website_templates.xml",
        "views/elksrvparking_menus.xml",
    ],
    "installable": True,
    "application": True,
    "post_init_hook": "_post_init_seed_rv_services",
}
