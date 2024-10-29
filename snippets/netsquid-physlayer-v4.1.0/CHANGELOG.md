CHANGELOG
=========

2021-04-06 (v4.1.0)
-------------------
- added multiplexed detection to both `BSMDetector` and `QKDDetector`

2021-02-24 (v4.0.3)
-------------------
- changed maintainer
- updated requirements to accept NetSquid v1.0
- added `.netsquid-physlayer.classical_connection.ClassicalConnectionWithLength`

2020-08-21 (v4.0.2)
-------------------
- Fixed some minor bugs in and made small improvements of detectors.

2020-08-25 (v4.0.1)
-------------------
- Removed usage of deprecated code and fixed bug in unit test.

2020-08-12 (v4.0.0)
-------------------
- Added TwinDetector and QKDDetector classes and moved these, as well
as the BSMDetector to a single file. All three detectors subclass from the
new QuantumDetector component introduced in NetSquid 0.10.

2020-08-06 (v3.2.0)
-------------------
- Added back an updated version of the absorption connection.

2020-08-03 (v3.1.0)
--------
- Use NetSquid BellIndex.

2020-07-30 (v3.0.0)
-------------------
- Major refactor, multiple old modules removed, see https://gitlab.com/softwarequtech/netsquid-snippets/netsquid-physlayer/-/issues/11 for details.
- Added BSMDetector which perform optical Bell-state measurement.
- Changed HeraldedConnection to be a NetSquid Connection and use the BSMDetector.

2020-06-26 (v2.0.0)
-------------------
- Connections now take node IDs instead of node objects to align with NetSquid and allow for network configuration.

2020-05-26 (v1.0.0)
-------------------
- Fixed issue with photon emission since dephasing noise was applied to all qubits "in use" including the communication qubit.
  This was wrong for two reasons:
  - The noise should not depend on if the qubits where inuse or not.
  - The dephasing noise during photon emission should not be applied to the communication qubit.
    This was not a big issue since the state was added after the noise.
    However, the first values of `delta_w` and `tau_decay` where then used for the
    communication qubit and not the first memory qubit as it might have been intendend.

2020-04-01 (v0.1.8)
-------------------
- Allow for netsquid < 1.0

2020-04-01 (v0.1.7)
-------------------
- Updated information on who the maintainer of this snippet is

2020-03-18 (v0.1.6)
-------------------
- Allow for netsquid 0.8

2020-01-22 (v0.1.5)
-------------------
- Now working with netsquid 0.7

2020-01-20 (v0.1.4)
-------------------
- Fixed bug that does not use the qubit types from config file

2019-11-04 (v0.1.3)
-------------------
- Created this snippet
