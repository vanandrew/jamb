# Software Development Lifecycle

## The Eight Process Areas

IEC 62304 defines eight process areas that together constitute the software development
lifecycle:

1. **Software development planning** -- establish a plan for conducting the development
   activities, including the methods, tools, and deliverables for each phase.
2. **Software requirements analysis** -- define and document what the software must do,
   including functional requirements, performance requirements, and interface requirements.
3. **Software architectural design** -- define the major structural components (software
   units and software items) and their interfaces. Decompose the system into manageable
   pieces.
4. **Software detailed design** -- specify each software unit in enough detail that it can
   be implemented and verified. This includes algorithms, data structures, and interfaces.
5. **Software unit implementation** -- write the source code for each software unit
   according to the detailed design.
6. **Software unit verification** -- verify that each software unit meets its detailed
   design specification. This typically involves unit testing and code review.
7. **Software integration testing** -- test the integrated software items and software
   units to verify that they work together as specified in the architectural design.
8. **Software system testing** -- test the complete integrated software system to verify
   that it meets the software requirements.

## The V-Model

IEC 62304 follows a V-model where each development phase on the left side of the "V" has
a corresponding verification phase on the right side:

```
Planning
  \                                      / System Testing
   Requirements Analysis                /
     \                                / Integration Testing
      Architectural Design           /
        \                          / Unit Verification
         Detailed Design          /
           \                    /
            Unit Implementation
```

The key principle is that each level of specification is verified by a corresponding level
of testing:

- **Requirements** are verified by **system testing**
- **Architecture** is verified by **integration testing**
- **Detailed design** is verified by **unit verification**

This structure ensures that every design decision has a corresponding verification
activity, creating a closed loop from specification to proof.
