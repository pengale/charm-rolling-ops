# Manual QA

This file outlines tests that can be performed manually, either because they have not yet been automated, or because the automation is difficult enough to warrant human hands running the test.

## Test Leader Loss

The rolling op should execute successfully, even if the leader goes down at an inopportune time (perhaps due to a hardware fault, or some other event outside of the Juju model).

More formally:

Assume that there exist three units of our app, designated A, B and C. Unit A is the leader.

A human operator kicks off a rolling restart.

Unit B successfully restarts, and reports the success to unit A. However, after receiving the relation changed hook, A drops offline.

B or C will pick up leadership. This test verifies that the rolling operation will complete successfully.

### Test Steps

0. Bootstrap a lxd cloud and create a model to host this test.

See [Bootstrap an lxd cloud](#Bootstrap-an-lxd-cloud) below.

1. Build the charm and deploy three units.

```
charmcraft pack
juju deploy ./rolling-ops*.charm -n 3
```

2. Wait for the cloud to settle.

```
watch --color 'juju status --color'
```

3. In three separate terminal windows, start three separate debug sessions.

```
juju debug-hooks rolling-ops/0
# Switch terminal
juju debug-hooks rolling-ops/1
# Switch terminal
juju debug-hooks rolling-ops/2

```

4. Kick off the restart.

```
juju run-action rolling-ops/0 rolling-ops/1 rolling-ops/2 restart delay=0
```

5. Step through the first restart.

After you execute the action above, each of your terminals should jump into a debug environment in a hook. Run the following in each environment:

```
./dispatch
exit
```

6. Repeat until at least one unit (not the leader) completes a restart and sets its status back to active.

7. Yeet the leader

The leader will be marked with a `*` in the output of `juju status`. Note the `Instance id` (`juju-<a hash>-<unit number>`).

This id is also the name of the lxd container. Delete it with the lxc CLI:

```
lxc delete <Inst id> --force
```

8. Finish the rolling op

On each of the remaining units, run ./dispatch, then exit the tmux session.

```
./dispatch
CTRL+a D
```

9. Verify that the relation data is in good shape:

(The commands below assume that unit 2 was the leader that we removed.)

Inspect the relation data, using `relation-get` directly, or using your tool of choice. (E.g. `show-relation` in [JHack](https://github.com/PietroPasotti/jhack))

The application data bag should show all units as idle:
```
$> juju run --unit rolling-ops/0 "relation-get -r restart:0 - rolling-ops"

<ops.model.Unit rolling-ops/0>: idle
<ops.model.Unit rolling-ops/1>: idle
<ops.model.Unit rolling-ops/2>: idle
```

And the relation data for each individual unit should have `state: release`.

```
$> juju run --unit rolling-ops/0 "relation-get -r restart:0 - rolling-ops/1"
egress-subnets: <some subnet>
ingress-address: <some ip>
private-address: <some ip>
state: release

$> juju run --unit rolling-ops/0 "relation-get -r restart:0 - rolling-ops/2"
egress-subnets: <some subnet>
ingress-address: <some ip>
private-address: <some ip>
state: release

$> juju run --unit rolling-ops/1 "relation-get -r restart:0 - rolling-ops/0"

egress-subnets: <some subnet>
ingress-address: <some ip>
private-address: <some ip>
state: release
```

10. Verify that subsequent restarts will work.

We are not necessarily in a 100% okay state. There is a unit missing. It has left data in the peer relation, and it will show up with a state of `unknown` in juju status. But this will not affect the ability of the other units to run a restart. To test this (assuming that unit 2 is the one that went away), run the following:

`juju run-action rolling-ops/0 rolling-ops/1 restart delay=0`

If you watch Juju status, you should see the units restart successfully, with the expected statuses.

### Copypasta

One liners to copy and paste for convenience:

- Assumptions
```
export TEST_MODEL="rolling-ops-test"
alias wj="watch --color 'juju status --color'"
```

- Reset
```
juju destroy-model -y --force $TEST_MODEL && juju add-model $TEST_MODEL
```

- Deploy
```
charmcraft pack && juju deploy ./rolling-ops*.charm -n 3 && wj
```

## Additional Notes

### Bootstrap an lxd cloud

Assuming an ubuntu box, do the following:

```
lxd init --auto
juju bootstrap localhost localhost
juju add-model rolling-ops-test
```

(No Ubuntu box? No problem! Create an Ubuntu virtual machine, on Mac or Windows, with [Multipass](https://multipass.run))
