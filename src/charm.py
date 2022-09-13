#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Sample charm using the rolling ops library."""

import logging
import time

from charms.rolling_ops.v0.rollingops import RollingOpsManager
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class CharmRollingOpsCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.restart_manager = RollingOpsManager(
            charm=self, relation="restart", callback=self._restart
        )

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.restart_action, self._on_restart_action)
        self.framework.observe(self.on.custom_restart_action, self._on_custom_restart_action)

        # Sentinel for testing (omit from production charms)
        self._stored.set_default(restarted=False)
        self._stored.set_default(delay=None)

    def _restart(self, event):
        # In a production charm, we'd perhaps import the systemd library, and run
        # systemd.restart_service.  Here, we just set a sentinal in our stored state, so
        # that we can run our tests.
        if self._stored.delay:
            time.sleep(int(self._stored.delay))
        self._stored.restarted = True
        self.model.get_relation(self.name).data[self.unit].update({"restart-type": "restart"})

    def _custom_restart(self, event):
        # In a production charm, we'd perhaps import the systemd library, and run
        # systemd.restart_service.  Here, we just set a sentinal in our stored state, so
        # that we can run our tests.
        if self._stored.delay:
            time.sleep(int(self._stored.delay))
        self._stored.custom_restarted = True
        self.model.get_relation(self.name).data[self.unit].update(
            {"restart-type": "custom-restart"}
        )

    def _on_install(self, event):
        self.unit.status = ActiveStatus()

    def _on_restart_action(self, event):
        self._stored.delay = event.params.get("delay")
        self.on[self.restart_manager.name].acquire_lock.emit()

    def _on_custom_restart_action(self, event):
        self._stored.delay = event.params.get("delay")
        self.on[self.restart_manager.name].acquire_lock.emit(callback_override="_custom_restart")


if __name__ == "__main__":
    main(CharmRollingOpsCharm)
