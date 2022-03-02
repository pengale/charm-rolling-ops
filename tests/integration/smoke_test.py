#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import unittest
from subprocess import check_output
import uuid

from juju import jasyncio
from juju.model import Model, Controller


CHARM_FILE="./rolling-ops_ubuntu-20.04-amd64.charm"

logging.basicConfig(level=logging.INFO)

ws_logger = logging.getLogger('websockets.protocol')
ws_logger.setLevel(logging.INFO)


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
        await self.model.block_until(lambda: app.status in ('error', 'blocked', 'active'))

        self.assertEqual(app.status, 'active')

        # Add some units, and run a rolling restart.
        count = 2
        for i in range(0, count):
            await self.model.add_machine()
        await app.add_units(count=count)

        for unit in app.units:
            action = await unit.run_action('restart')
            # logging.debug("Action results: %s", action.results) # TODO assert

        await self.model.block_until(lambda: app.status in ('error', 'blocked', 'active'))
        self.assertEqual(app.status, 'active')

    async def asyncTearDown(self):
        """Destroy the test model, and disconnect from the controller.

        If we wanted to allow tests to share a model, we'd need to do something clever in
        order to run this once, after all tests have completed (tearDownClass doesn't have
        an async equivalent).

        """
        await self.controller.destroy_model(self.model.info.uuid)
        await self.controller.disconnect()
