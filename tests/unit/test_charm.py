# Copyright 2022 Penny Gale
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock

from charm import CharmRollingOpsCharm
from charms.rolling_ops.v0.rollingops import RunWithLock
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(CharmRollingOpsCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin_with_initial_hooks()
        # self.harness.begin()

    def test_restart(self):
        # Verify that our _restart handler gets called when we call RunWithLock
        self.harness.charm.on.run_with_lock.emit(name="restart")
        self.assertTrue(self.harness.charm._stored.restarted)

    def test_wrong_restart(self):
        # Verify that our _restart handler gets called when we call RunWithLock with the
        # wrong name.
        self.harness.charm.on.run_with_lock.emit(name="foo")
        self.assertFalse(self.harness.charm._stored.restarted)

    def test_acquire(self):
        # A human operator runs the "restart" action.
        action_event = Mock()
        action_event.params = dict(name="restart")
        self.harness.charm.restart._on_acquire_lock(action_event)

        data = self.harness.charm.model.relations["restart"][0].data

        # The result should be that we set a lock request on our relation data.
        self.assertEqual(data[self.harness.model.unit]["status"], "acquire")

    def test_peers(self):

        # Set unit 0 as the leader.
        # Add a peer relation to a unit 1.
        self.harness.set_leader(True)
        self.harness.add_relation_unit(0, "rolling-ops/1")
        self.harness.update_relation_data(0, "rolling-ops/0", {"status": "acquire"})
        self.harness.update_relation_data(0, "rolling-ops/1", {"status": "acquire"})

        unit_0 = self.harness.charm.model.get_unit("rolling-ops/0")
        unit_1 = self.harness.charm.model.get_unit("rolling-ops/1")
        rel_data = self.harness.charm.model.relations["restart"][0].data

        # Unit 1 should have requested the lock, and been granted the lock.
        self.assertEqual(rel_data[unit_1]["status"], "acquire")
        self.assertEqual(rel_data[self.harness.model.app][str(unit_1)], "granted")

        # Unit 0 should have requested the lock, but not yet granted the lock to itself.
        self.assertEqual(rel_data[unit_0]["status"], "acquire")

        # Now we simulate unit 1 processing and releasing the lock.
        self.harness.update_relation_data(0, "rolling-ops/1", {"status": "release"})

        # This should result in unit 0 granting itself the lock, and executing.
        # Both units should end up in the "release" and "idle" state.
        rel_data = self.harness.charm.model.relations["restart"][0].data
        self.assertEqual(rel_data[unit_1]["status"], "release")
        self.assertEqual(rel_data[unit_0]["status"], "release")
        self.assertEqual(rel_data[self.harness.model.app][str(unit_1)], "idle")
        self.assertEqual(rel_data[self.harness.model.app][str(unit_0)], "idle")
