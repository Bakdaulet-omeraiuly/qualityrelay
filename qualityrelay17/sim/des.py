"""Minimal deterministic discrete-event core (generator processes), stdlib only.

A process is a generator that yields commands:
  ('timeout', seconds)
  ('acquire', {Resource: units, ...})   -- atomic multi-resource acquire, FIFO among waiters
  ('release', {Resource: units, ...})
  ('wait', Signal)                      -- resumes when the signal fires
Ties are broken by insertion order, so a seeded model replays bit-identically.
Same role as SimPy here; SimPy is not a CI dependency, so this file is the CPU baseline.
"""
from __future__ import annotations
import heapq


class Resource:
    def __init__(self, name: str, capacity: int):
        if capacity < 1:
            raise ValueError(f'{name}: capacity >= 1')
        self.name, self.capacity, self.in_use = name, capacity, 0
        self.busy_time = 0.0
        self._last = 0.0

    def _account(self, now):
        self.busy_time += self.in_use * (now - self._last)
        self._last = now


class Signal:
    def __init__(self):
        self.waiters = []
        self.fired = False


class Env:
    def __init__(self):
        self.now = 0.0
        self._heap = []
        self._seq = 0
        self._waiting = []      # FIFO of (proc, request dict)
        self.resources: list[Resource] = []

    def resource(self, name, capacity):
        r = Resource(name, capacity)
        self.resources.append(r)
        return r

    def _schedule(self, t, proc, value=None):
        self._seq += 1
        heapq.heappush(self._heap, (t, self._seq, proc, value))

    def process(self, gen):
        self._schedule(self.now, gen)
        return gen

    def fire(self, sig: Signal):
        sig.fired = True
        for p in sig.waiters:
            self._schedule(self.now, p)
        sig.waiters = []

    def _can(self, req):
        return all(r.in_use + u <= r.capacity for r, u in req.items())

    def _grant(self, req):
        for r, u in req.items():
            r._account(self.now)
            r.in_use += u

    def _try_waiters(self):
        still = []
        for proc, req in self._waiting:
            if self._can(req):
                self._grant(req)
                self._schedule(self.now, proc)
            else:
                still.append((proc, req))
        self._waiting = still

    def _step(self, proc, value):
        try:
            cmd = proc.send(value)
        except StopIteration:
            return
        kind, arg = cmd
        if kind == 'timeout':
            if arg < 0:
                raise ValueError('negative timeout')
            self._schedule(self.now + arg, proc)
        elif kind == 'acquire':
            if not self._waiting and self._can(arg):
                self._grant(arg)
                self._schedule(self.now, proc)
            else:
                self._waiting.append((proc, arg))
                self._try_waiters()
        elif kind == 'release':
            for r, u in arg.items():
                if r.in_use < u:
                    raise RuntimeError(f'{r.name}: release without acquire')
                r._account(self.now)
                r.in_use -= u
            self._schedule(self.now, proc)
            self._try_waiters()
        elif kind == 'wait':
            if arg.fired:
                self._schedule(self.now, proc)
            else:
                arg.waiters.append(proc)
        else:
            raise ValueError(f'unknown command {kind}')

    def run(self, until=float('inf')):
        while self._heap and self._heap[0][0] <= until:
            t, _, proc, value = heapq.heappop(self._heap)
            self.now = t
            self._step(proc, value)
        for r in self.resources:
            r._account(self.now)
        return self.now
