from . import controllers
from . import models
from . import wizard


def _post_init_seed_rv_services(env):
    """Seed the default RV services on the singleton lodge settings record."""
    env["elks.lodge.settings"]._seed_default_rv_services()
