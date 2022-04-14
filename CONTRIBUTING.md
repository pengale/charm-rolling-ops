# charm-rolling-ops

## Developing

Create and activate a virtualenv with the development requirements:

```
pip install tox
tox
source .tox/unit/bin/activate
```

## Code overview

The rolling ops library lives in
`lib/charms/rolling_ops/v0/rollingops.py`. The example charm lives in
`src/charm.py`.

## Intended use case

The charm herein has no production use -- it serves simply to host,
test, and document the `rollingops` library.

Charm authors may include the Rolling Ops library in the [same way
that any charm library](https://juju.is/docs/sdk/libraries) may be
included.

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Simply run `tox`.

Prior to publishing an update to this library, developers should be
sure additionally run `tox -e integration`. This will run a separate
set of tests against a live environment. Note that `juju` must be
installed, and a bare metal or vm controller must be bootstrapped.

Manual tests may be run by following the instructions in test/QA.md.
