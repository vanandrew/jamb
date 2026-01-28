# What is IEC 62304?

## Purpose

IEC 62304 defines the software development lifecycle processes required for medical device
software. It applies to both Software as a Medical Device (SaMD) and Software in a Medical
Device (SiMD). The standard establishes a common framework that software developers,
regulatory bodies, and quality teams use to ensure medical device software is developed
with appropriate rigor.

## Scope

IEC 62304 covers the full software lifecycle from development planning through maintenance.
It prescribes activities for development planning, requirements analysis, architectural and
detailed design, implementation and verification, integration and system testing, software
release, and software maintenance and problem resolution.

The standard does not prescribe specific methods or tools. Instead, it defines *what* must
be done at each lifecycle stage, leaving organizations free to choose *how* they accomplish
each activity.

## Regulatory Context

IEC 62304 is referenced by the **EU Medical Device Regulation (MDR)** and is recognized by
the **FDA** as a consensus standard. Compliance with IEC 62304 is often required for
**CE marking** under the EU MDR and for **FDA 510(k) clearance** or **PMA approval** in the
United States.

When manufacturers declare conformity to IEC 62304, regulatory reviewers can streamline
their assessment of the software development process. This makes IEC 62304 compliance
a practical necessity for most medical device software.

## Relationship to Related Standards

IEC 62304 does not exist in isolation. It assumes that **ISO 13485** (Quality Management Systems) provides the overarching quality management system within which software development occurs, and that **ISO 14971** (Risk Management) provides the risk management process with which IEC 62304 integrates — software hazards must be identified and controlled through this process. **IEC 62443** (Industrial Cybersecurity) is an industrial automation cybersecurity standard increasingly referenced for connected medical devices, as cybersecurity requirements intersect with software lifecycle activities.

IEC 62304 assumes a quality management system (ISO 13485) and risk management process
(ISO 14971) are in place. It references these standards rather than duplicating their
requirements.

## SaMD vs SiMD

IEC 62304 applies to two categories of medical device software. **SaMD (Software as a Medical Device)** is software that *is* the medical device — examples include diagnostic algorithms, clinical decision support tools, and standalone monitoring applications where the software itself performs the intended medical purpose. **SiMD (Software in a Medical Device)** is software embedded in a physical medical device, such as firmware controlling an infusion pump or software running on an imaging system, where the software is a component of a larger device.

IEC 62304 applies equally to both categories. The safety classification of the software
(Class A, B, or C) determines the rigor of the lifecycle activities required, regardless
of whether the software is SaMD or SiMD.
