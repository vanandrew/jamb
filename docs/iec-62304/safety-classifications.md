# Software Safety Classifications

## Three Classes

IEC 62304 defines three software safety classifications based on the potential for harm. **Class A** means no injury or damage to health is possible — the software cannot contribute to a hazardous situation, or the hazardous situation cannot result in harm. **Class B** means non-serious injury is possible — the software can contribute to a hazardous situation that could result in non-serious injury. **Class C** means death or serious injury is possible — the software can contribute to a hazardous situation that could result in death or serious injury.

The classification is determined through the risk management process (ISO 14971). A higher
classification means more lifecycle activities are required, increasing the documentation
and verification burden.

## Required Activities by Class

The following table shows which lifecycle activities IEC 62304 requires for each safety
class:

| Activity | Class A | Class B | Class C |
|----------|---------|---------|---------|
| Development planning | Required | Required | Required |
| Requirements analysis | Required | Required | Required |
| Architectural design | --- | Required | Required |
| Detailed design | --- | --- | Required |
| Unit implementation | Required | Required | Required |
| Unit verification | --- | Required | Required |
| Integration testing | --- | Required | Required |
| System testing | Required | Required | Required |
| Release | Required | Required | Required |

Class A software has the lightest requirements: planning, requirements, implementation,
system testing, and release. Class C software requires the full set of activities including
architectural design, detailed design, unit verification, and integration testing.

## How jamb Supports All Classes

jamb's document hierarchy and traceability features can be configured for any safety class.

For **Class A**, a simpler document hierarchy may suffice. You might use only PRJ and UN documents with system-level tests linking to user needs. The reduced set of required activities means fewer documents and links are needed.

For **Class B**, the intermediate level requires architectural design and unit verification. A hierarchy such as PRJ, UN, SYS, and SRS with corresponding test coverage provides the necessary traceability through architecture and into verification.

For **Class C**, the full PRJ, UN, SYS, SRS, and test chain provides complete bidirectional traceability. Detailed design items in SRS link to architectural items in SYS, which link to user needs in UN. Every level is verified by tests linked through `@pytest.mark.requirement`. This satisfies the most demanding lifecycle requirements.

Regardless of the class, jamb's `validate` command checks for completeness at whatever
level of traceability you have configured, and suspect link detection ensures that changes
are tracked across all levels.
