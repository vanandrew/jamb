# Risk Management Integration

## ISO 14971 Relationship

IEC 62304 requires integration with the risk management process defined by ISO 14971.
Software-related hazards must be identified, risks evaluated, and risk controls
implemented as part of the software development lifecycle.

Key requirements include identifying software items that could contribute to hazardous situations, defining risk control measures for identified hazards, verifying that risk controls are implemented and effective, and tracing from hazards through risk controls to software requirements and their tests.

:::{note}
jamb supports **risk-to-requirement traceability** — linking hazards to risk controls to software requirements and their tests. It does not provide the full ISO 14971 risk management process (hazard analysis worksheets, probability/severity estimation, risk evaluation, overall residual risk evaluation, or benefit-risk assessment). These must be handled by your risk management process and tools.
:::

The risk management process runs in parallel with software development. As new hazards are
identified or risks change, the software requirements and design must be updated
accordingly.

## HAZ and RC Documents in jamb

The default jamb document hierarchy includes document types specifically for risk
management:

**HAZ (Hazards)** documents capture identified hazards. HAZ items describe potential hazardous situations and their causes, and they link to project requirements (PRJ) to show which aspects of the system give rise to each hazard. **RC (Risk Controls)** documents define the measures taken to reduce risk. RC items describe how each hazard is controlled and link to the HAZ items they mitigate.

This structure mirrors the ISO 14971 process: identify hazards, then define controls for
those hazards.

## Risk Controls to Software Requirements Tracing

The complete risk management traceability chain in jamb is:

1. **HAZ** items identify hazards and link to PRJ items.
2. **RC** items define risk controls and link to HAZ items.
3. **SRS** items implement risk controls and link to RC items.
4. **Tests** verify the SRS items using `@pytest.mark.requirement`.

This creates a complete chain from hazard identification through risk control definition
to software implementation and verification:

> Hazard (HAZ) --> Risk Control (RC) --> Software Requirement (SRS) --> Test

This chain satisfies IEC 62304 Clause 7.3 (verification of risk control measures) by demonstrating
that every identified hazard has a defined control, that control is implemented as a
software requirement, and that requirement is verified by a test.
