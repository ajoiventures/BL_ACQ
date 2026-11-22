# Verify corporate research delivery

Open [test_corporate_service.py](../../tests/test_corporate_service.py). Run
`python -m unittest discover -s tests -p test_corporate_service.py -v` from the
repository root.

The suite starts a real loopback founder service with a temporary SQLite
database. All financial evidence comes from the checked-in historical case;
there are no remote data calls.

The tests cover both API routes' authentication, commercial role scope and
Origin restrictions. They evaluate all three actual case packets, verify
reported and forecast accounting checks and preserve the August-source/October-
model distinction. A deliberately stressed financing case with expensive debt
and no revolver must withhold IRR/MOIC when its financing conditions fail.

A source-ownership test rejects client-supplied replacement facts. It then
changes server review metadata after the initial GET and verifies the POST's
export bundle contains exactly the new server facts and matching calculation
digest. Other tests exercise malformed nested cases, invalid JSON, nonfinite
financial inputs, deep JSON nesting, and the exact 65,536-byte request boundary.

Calculations and unsupported mutation paths must leave existing research runs,
decisions, evidence, task queues and founder actions unchanged. Missing source files fail closed
with a generic unavailable message. Static-file and DOM-reference checks verify
that the page's assets and referenced elements exist.

These HTTP and static checks do not run a browser or validate visual layout.
The browser gate remains separate and must pass in a supported environment.
