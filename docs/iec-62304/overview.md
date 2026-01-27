# What is IEC 62304?

## Purpose

IEC 62304 defines the software development lifecycle processes required for medical device
software. It applies to both Software as a Medical Device (SaMD) and Software in a Medical
Device (SiMD). The standard establishes a common framework that software developers,
regulatory bodies, and quality teams use to ensure medical device software is developed
with appropriate rigor.

## Scope

IEC 62304 covers the full software lifecycle from development planning through maintenance.
It prescribes activities for:

- Development planning
- Requirements analysis
- Architectural and detailed design
- Implementation and verification
- Integration and system testing
- Software release
- Software maintenance and problem resolution

The standard does not prescribe specific methods or tools. Instead, it defines *what* must
be done at each lifecycle stage, leaving organizations free to choose *how* they accomplish
each activity.

## Regulatory Context

IEC 62304 is referenced by the **EU Medical Device Regulation (MDR)** and is recognized by
the **FDA** as a consensus standard. Compliance with IEC 62304 is often required for:

- **CE marking** under the EU MDR
- **FDA 510(k) clearance** or **PMA approval** in the United States

When manufacturers declare conformity to IEC 62304, regulatory reviewers can streamline
their assessment of the software development process. This makes IEC 62304 compliance
a practical necessity for most medical device software.

## Relationship to Related Standards

IEC 62304 does not exist in isolation. It assumes that the following are already in place:

- **ISO 13485** (Quality Management Systems) -- provides the overarching quality management
  system within which software development occurs.
- **ISO 14971** (Risk Management) -- provides the risk management process that IEC 62304
  integrates with. Software hazards must be identified and controlled through this process.
- **IEC 62443** (Cybersecurity) -- addresses cybersecurity concerns for connected medical
  devices, which increasingly intersect with software lifecycle requirements.

IEC 62304 assumes a quality management system (ISO 13485) and risk management process
(ISO 14971) are in place. It references these standards rather than duplicating their
requirements.

## SaMD vs SiMD

IEC 62304 applies to two categories of medical device software:

- **SaMD (Software as a Medical Device)** -- software that *is* the medical device. Examples
  include diagnostic algorithms, clinical decision support tools, and standalone monitoring
  applications. The software itself performs the intended medical purpose.
- **SiMD (Software in a Medical Device)** -- software that is embedded in a physical medical
  device. Examples include firmware controlling an infusion pump or software running on an
  imaging system. The software is a component of a larger device.

IEC 62304 applies equally to both categories. The safety classification of the software
(Class A, B, or C) determines the rigor of the lifecycle activities required, regardless
of whether the software is SaMD or SiMD.
