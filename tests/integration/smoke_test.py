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
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json
import logging
import subprocess
import unittest
import uuid
from typing import Tuple

from juju.model import Controller
from juju.unit import Unit

CHARM_FILE = "./rolling-ops_ubuntu-20.04-amd64.charm"

logging.basicConfig(level=logging.INFO)

ws_logger = logging.getLogger("websockets.protocol")
ws_logger.setLevel(logging.INFO)


def get_restart_type(unit: Unit, model_name: str) -> str:
    show_unit_json = subprocess.check_output(
        f"JUJU_MODEL={model_name} juju show-unit {unit.name} --format json",
        stderr=subprocess.PIPE,
        shell=True,
        universal_newlines=True,
    )
    show_unit_dict = json.loads(show_unit_json)
    restart_type = show_unit_dict[unit.name]["relation-info"][0]["local-unit"]["data"][
        "restart-type"
    ]

    return restart_type


class TestSmoke(unittest.IsolatedAsyncioTestCase):
    """Integration test class.

    Inherits from IsolatedAsyncioTestCase, which is lovely, though it does (as of this
    writing) use the deprecated loop method to run its coroutines.

    # TODO: see if we can patch in jasyncio.

    """

    model = None  # An instance of Model from pylibjuju, representing the current model.
    controller = None  # An instance of Controller.

    async def asyncSetUp(self):
        """Connect to the controller, and create a new model, with a unique uuid.

        This means that each test will run on a fresh model, meaning that there will be no
        artifacts left from previous tests.

        The downside is that we will be deploying our charm and performing other lengthy
        operations multiple times in a row.

        """
        model_name = "test-rolling-{}".format(uuid.uuid4())

        self.controller = Controller()
        await self.controller.connect()

        self.model = await self.controller.add_model(model_name)

    async def test_smoke(self):
        """Basic smoke test.

        Verify that we can deploy, and seem to be able to run a rolling op.
        """
        # Deploy, and verify deployment
        app = await self.model.deploy(CHARM_FILE)
        await app.add_units(count=2)
        await self.model.block_until(lambda: app.status in ("error", "blocked", "active"))

        self.assertEqual(app.status, "active")

        # Run the restart, with a delay to alleviate timing issues.
        for unit in app.units:
            # TODO: check action status.
            await unit.run_action("restart", delay="1")

        await self.model.block_until(lambda: app.status in ("maintenance", "error"))
        self.assertFalse(app.status == "error")
        await self.model.block_until(lambda: app.status in ("error", "blocked", "active"))
        self.assertEqual(app.status, "active")

    async def test_smoke_single_unit(self):
        """Basic smoke test, on a single unit.

        Verify that deployment and rolling ops suceed for a single unit.
        """
        # Grab the application
        app = await self.model.deploy(CHARM_FILE)

        # Scale down to one unit
        app.scale(scale=1)

        # wait for unit to be ready
        await self.model.block_until(lambda: app.status in ("error", "blocked", "active"))
        self.assertEqual(app.status, "active")

        # Run the restart, with a delay to alleviate timing issues.
        # TODO: check action status.
        await app.units[0].run_action("restart", delay="1")

        await self.model.block_until(lambda: app.status in ("maintenance", "error"))
        self.assertFalse(app.status == "error")
        await self.model.block_until(lambda: app.status in ("error", "blocked", "active"))
        self.assertEqual(app.status, "active")

    async def asyncTearDown(self):
        """Destroy the test model, and disconnect from the controller.

        If we wanted to allow tests to share a model, we'd need to do something clever in
        order to run this once, after all tests have completed (tearDownClass doesn't have
        an async equivalent).

        """
        await self.controller.destroy_model(self.model.info.uuid)
        await self.controller.disconnect()
