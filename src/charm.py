#!/usr/bin/env python3
# Copyright 2022 Penny Gale
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Sample charm using the rolling ops library."""

import logging

from ops.charm import CharmBase
from ops.main import main
# from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class CharmRollingOpsCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.restart_action, self._on_restart_action)

    def _on_restart_action(self, event):
        """Fire off a rolling restart.
        """
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results({"restart": "Service {} restarted!.".format(
                self.model.config['service'])})


if __name__ == "__main__":
    main(CharmRollingOpsCharm)
