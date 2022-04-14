# rolling-ops

## Description

This charm contains the `rollingops` library, along with an example
implementation against it.

## Usage

Operators may use charm as a reference when including the `rollingops`
lib in their own charms. This repo also contains tests for the
library, using the reference charm.


## Relations
peers:
    rolling_ops:
        interface: rolling_ops


## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines
on enhancements to this charm following best practice guidelines, and
`CONTRIBUTING.md` for developer guidance.
