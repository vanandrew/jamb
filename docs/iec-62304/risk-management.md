# Risk Management Integration

## ISO 14971 Relationship

IEC 62304 requires integration with the risk management process defined by ISO 14971.
Software-related hazards must be identified, risks evaluated, and risk controls
implemented as part of the software development lifecycle.

Key requirements include identifying software items that could contribute to hazardous situations, defining risk control measures for identified hazards, verifying that risk controls are implemented and effective, and tracing from hazards through risk controls to software requirements and their tests.

The risk management process runs in parallel with software development. As new hazards are
identified or risks change, the software requirements and design must be updated
accordingly.

## HAZ and RC Documents in jamb

The default jamb document hierarchy includes document types specifically for risk
management:

**HAZ (Hazards)** documents capture identified hazards. HAZ items describe potential hazardous situations and their causes, and they link to project requirements (PRJ) to show which aspects of the system give rise to each hazard. **RC (Risk Controls)** documents define the measures taken to reduce risk. RC items describe how each hazard is controlled and link to the HAZ items they mitigate.

This structure mirrors the ISO 14971 process: identify hazards, then define controls for
those hazards.

## Derived Requirements and `derived: true`

Some software requirements do not originate from user needs. Instead, they derive from
risk analysis -- they exist because a risk control requires a specific software behavior.
These are called **derived requirements**.

In jamb, mark derived requirements with `derived: true` in the item metadata. This tells
jamb that the item does not need a parent link in the normal traceability chain (UN or SYS).
Instead, it traces to an RC (risk control) item.

Without the `derived: true` flag, `jamb validate` would flag these items as unlinked
because they lack the expected parent link. The flag signals that the item's provenance
is the risk management process rather than the requirements decomposition chain.

## Risk Controls to Software Requirements Tracing

The complete risk management traceability chain in jamb is:

1. **HAZ** items identify hazards and link to PRJ items.
2. **RC** items define risk controls and link to HAZ items.
3. **SRS** items (marked `derived: true`) implement risk controls and link to RC items.
4. **Tests** verify the derived SRS items using `@pytest.mark.requirement`.

This creates a complete chain from hazard identification through risk control definition
to software implementation and verification:

> Hazard (HAZ) --> Risk Control (RC) --> Software Requirement (SRS) --> Test

This chain satisfies IEC 62304 Clause 7.4 (risk control verification) by demonstrating
that every identified hazard has a defined control, that control is implemented as a
software requirement, and that requirement is verified by a test.
