#!/usr/bin/env python3
# Copyright 2022 Penny Gale
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Sample charm using the rolling ops library."""

import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.model import ActiveStatus
from ops.main import main
from charms.rolling_ops.v0.rollingops import RollingOpsManager, RollingEvents

logger = logging.getLogger(__name__)


class CharmRollingOpsCharm(CharmBase):
    """Charm the service."""

    on = RollingEvents()
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.restart = RollingOpsManager(self, 'restart', self._restart, self.on.restart_action)
        self.framework.observe(self.on.install, self._on_install)

        # Sentinal for testing (omit from production charms)

        self._stored.set_default(restarted=False)

    def _restart(self, event):
        # In a production charm, we'd perhaps import the systemd library, and run systemd.restart_service.
        # Here, we just set a sentinal in our stored state, so that we can run our tests.
        self._stored.restarted = True

    def _on_install(self, event):
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(CharmRollingOpsCharm)
