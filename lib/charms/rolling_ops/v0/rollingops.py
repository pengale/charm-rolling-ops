"""A library to enable charms to implement "rolling" or "serialized" operations. E.g., a
rolling restart.

You may use this library directly, or extend it to customize behavior.

For example, in order to implement a rolling restart, a charm author would need to add the
following lines of code, to the following files (note the consistent use of the name "restart")
to namespace this particular rolling op:

Add a peer relation to `metadata.yaml`:
```yaml
peers:
    restart:
        interface: rolling_op
```

To enable a human operator to trigger the restat, add an action to `actions.yaml`:
```yaml
restart:
  description: Restarts a service
  params: {}
```

Import the library, and enable it by doing the following:

1. Override the Charm's `on` property with the RollingEvents class from the library.
2. Add a method containing code to be executed to the Charm object. Here, we call this
method `_restart`.
3. Initialize a RollingOpsManager class, passing in the Charm, name of the peer relation,
restart handler, and action.

src/charm.py
```python
# ...
from charms.rolling_ops.v0.rollingops import RollingOpsManager, RollingEvents
# ...

class SomeCharm(...):
    # ...
    on = RollingEvents
    # ...

    def __init__(...)
        # ...
        self.restart = RollingOpsManager(self, 'restart', self._restart, self.on.restart_action)
        # ...

    def _restart(self, event):
        systemd.service_restart('foo')
```

"""
import logging
from ops.charm import CharmBase, RelationChangedEvent, CharmEvents, ActionEvent
from ops.framework import EventBase, EventSource, Object

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "20b7777f58fe421e9a223aefc2b4d3a4"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


class LockErrorNoRelation(Exception):
    pass


class Lock:
    """A class that keeps track of a single asynchronous lock.

    Warning: a Lock has permission to update relation data, which means that there are
    side effects to invoking the .acquire, .release and .grant methods. Running any one of
    them will trigger a RelationChanged event, once per transition from one internal
    status to another.

    This class tracks state across the cloud by implementing a peer relation
    interface. There are two parts to the interface:

    1) The data on a unit's peer relation (defined in metadata.yaml.) Each unit can update
       this data. The only meaningful values are "acquire", and "release", which represent
       a request to acquire the lock, and a request to release the lock, respectively.

    2) The application data in the relation. This tracks whether the lock has been
       "granted", Or has been released (and reverted to idle). There are two valid states:
       "granted" or None.  If a lock is in the "granted" state, a unit should emit a
       RunWithLocks event and then release the lock.

       If a lock is in "None", this means that a unit has not yet requested the lock, or
       that the request has been completed.

    In more detail, here is the relation structure:

    relation.data:
        <unit n>:
            status: 'acquire|release'
        <application>:
           <unit n>: 'granted|None'

    Note that this class makes no attempts to timestamp the locks and thus handle multiple
    requests in a row. If a unit re-requests a lock before being granted the lock, the
    lock will simply stay in the "acquire" state. If a unit wishes to clear its lock, it
    simply needs to call lock.release().

    """

    # Track lock requests from units.
    ACQUIRE = 'acquire'
    RELEASE = 'release'

    # Track responses from the leader.
    GRANTED = 'granted'
    IDLE = 'idle'

    def __init__(self, rel_name, charm, unit=None):
        self.relation = charm.model.relations[rel_name][0]
        if not self.relation:
            # TODO: defer caller in this case (probably just fired too soon).
            raise LockErrorNoRelation()

        self.unit = unit or charm.framework.model.unit
        self.app = charm.framework.model.app

    @property
    def status(self):
        """Return an appropriate status.

        Note that the state exists in the unit's relation data, and the application
        relation data, so we have to be careful about what our states mean.

        Unit status can only be in "acquire", "release", "None" (None means unset)
        Application status can only be in "granted" or "None" (None means unset or released)

        """
        unit_status = self.relation.data[self.unit].get('status', None)
        app_status = self.relation.data[self.app].get(str(self.unit), self.IDLE)

        if app_status == self.GRANTED and unit_status == self.RELEASE:
            # Active release request.
            return self.RELEASE

        if app_status == self.IDLE and unit_status == self.ACQUIRE:
            # Active acquire request.
            return self.ACQUIRE

        return app_status  # Granted or unset/released

    @status.setter
    def status(self, status):
        """Set the given status.

        Since we update the relation data, this may fire off a RelationChanged event.
        """
        if status == self.ACQUIRE:
            self.relation.data[self.unit].update({"status": status})

        if status == self.RELEASE:
            self.relation.data[self.unit].update({"status": status})

        if status == self.GRANTED:
            self.relation.data[self.app].update({str(self.unit): status})

        if status is self.IDLE:
            self.relation.data[self.app].update({str(self.unit): status})

    def acquire(self):
        self.status = self.ACQUIRE

    def release(self):
        self.status = self.RELEASE

    def clear(self):
        self.status = self.IDLE

    def grant(self):
        self.status = self.GRANTED

    def is_held(self):
        return self.status == self.GRANTED

    def release_requested(self):
        return self.status == self.RELEASE

    def is_pending(self):
        return self.status == self.ACQUIRE


class Locks:
    """Generator that returns a list of locks."""
    def __init__(self, rel_name, charm):
        self.rel_name = rel_name
        self.charm = charm

        # Gather all the units.
        relation = charm.model.relations[rel_name][0]
        units = [unit for unit in relation.units]

        # Plus our unit ...
        units.append(charm.framework.model.unit)

        self.units = units

    def __iter__(self):

        for unit in self.units:
            yield Lock(self.rel_name, self.charm, unit=unit)


class RollingEvent(EventBase):
    def __init__(self, handle, name):
        super().__init__(handle)
        self._name = name

    def snapshot(self):
        return {"name": self._name}

    def restore(self, snapshot):
        self._name = snapshot["name"]

    @property
    def name(self):
        """The `name` property allows us to namespace Rolling Operations."""
        return self._name


class RunWithLock(RollingEvent):
    pass


class AcquireLock(RollingEvent):
    pass


class ProcessLocks(RollingEvent):
    pass


class RollingEvents(CharmEvents):
    run_with_lock = EventSource(RunWithLock)
    acquire_lock = EventSource(AcquireLock)
    process_locks = EventSource(ProcessLocks)


class RollingOpsManager(Object):
    """Emitters and handlers for rolling ops."""

    def __init__(self, charm, rel_name, func_run, event_acquire):
        """
        params:
            charm: the charm we are attaching this to.
            rel_name: an identifier, by convention based on the name of the relation in the
                metadata.yaml, which identifies this instance of RollingOperatorsFactory,
                distinct from other instances that may be hanlding other events.
            func_run: a closure to run when we have a lock. (It must take a CharmBase object and
                EventBase object as args.)
            event_acquire: The event that will prompt us to acquire a lock.
        """
        super().__init__(charm, None)

        self.charm = charm
        self.name = rel_name
        self._func_run = func_run

        self.framework.observe(event_acquire, self._on_acquire_lock)
        self.framework.observe(charm.on[self.name].relation_changed, self._on_relation_changed)
        self.framework.observe(charm.on.run_with_lock, self._on_run_with_lock)
        self.framework.observe(charm.on.process_locks, self._on_process_locks)

    def _func_run(self: CharmBase, event: EventBase) -> None:
        """Placeholder for the function that actually runs our event.

        Usually overridden in the init.
        """
        raise NotImplementedError

    def _on_relation_changed(self: CharmBase, event: RelationChangedEvent):
        """Process relation changed.

        First, determine whether this unit has been granted a lock. If so, emit a RunWithLock
        event.

        Then, if we are the leader, fire off a process locks event.

        """
        if not event.relation.name == self.name:
            # This is not relevant to us.
            return

        if Lock(self.name, self.charm).is_held():
            self.charm.on.run_with_lock.emit(name=self.name)

        if self.framework.model.unit.is_leader():
            self.charm.on.process_locks.emit(name=self.name)

    def _on_process_locks(self: CharmBase, event: ProcessLocks):
        """Process locks.

        Runs only on the leader. Updates the status of all locks.

        """
        if not event.name == self.name:
            return

        if not self.framework.model.unit.is_leader():
            return

        pending = []

        for lock in Locks(self.name, self.charm):
            if lock.is_held():
                # One of our units has the lock -- return without further processing.
                return

            if lock.release_requested():
                lock.clear()  # Updates relation data

            if lock.is_pending():
                if lock.unit == self.charm.model.unit:
                    # Always run on the leader last.
                    pending.insert(0, lock)
                else:
                    pending.append(lock)

        # If we reach this point, and we have pending units, we want to grant a lock to
        # one of them.
        if pending:
            lock = pending[-1]
            lock.grant()
            if lock.unit == self.charm.model.unit:
                # It's time for the leader to run with lock.
                self.charm.on.run_with_lock.emit(name=self.name)

    def _on_acquire_lock(self: CharmBase, event: ActionEvent):
        """Request a lock."""
        if not event.params.get('name') == self.name:
            return

        Lock(self.name, self.charm).acquire()  # Updates relation data

    def _on_run_with_lock(self: CharmBase, event: RunWithLock):
        if not event.name == self.name:
            return

        lock = Lock(self.name, self.charm)
        self._func_run(event)
        lock.release()  # Updates relation data
        if lock.unit == self.charm.model.unit:
            self.charm.on.process_locks.emit(name=self.name)
