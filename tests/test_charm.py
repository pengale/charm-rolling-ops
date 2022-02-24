# Copyright 2022 Penny Gale
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock

from charm import CharmRollingOpsCharm
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(CharmRollingOpsCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_action(self):
        # the harness doesn't (yet!) help much with actions themselves
        action_event = Mock(params={"fail": ""})
        self.harness.charm._on_restart_action(action_event)

        self.assertTrue(action_event.set_results.called)

    def test_action_fail(self):
        action_event = Mock(params={"fail": "fail this"})
        self.harness.charm._on_restart_action(action_event)

        self.assertEqual(action_event.fail.call_args, [("fail this",)])
