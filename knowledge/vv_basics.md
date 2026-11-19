# Verification and Validation (V&V): course notes

Starter notes for Jarvis. Add your own lecture notes as extra .md files in
this folder. Start each topic with a "## " heading so Jarvis can find it.

## Overview: what V&V is and why it matters

Verification and validation (V&V) is the set of checking activities that run
through the whole software process. Its goal is to build confidence that the
software is fit for purpose. It cannot prove that software has zero defects.
How much confidence is needed depends on what the software is for (a medical
device needs more than a hobby app), on what users expect, and on market
pressure. V&V starts with requirements reviews and continues through design
reviews, code inspections and testing.

## Verification vs validation: the two questions

Verification asks: "Are we building the product right?" It checks that the
software conforms to its specification, meaning the stated functional and
non-functional requirements.

Validation asks: "Are we building the right product?" It checks that the
software does what the customer really needs and expects.

Both are needed because a specification can be incomplete or simply wrong
about what users need. Software can pass every specification-based test
(verification succeeds) and still be useless to its users (validation fails).

Everyday comparison: a chef follows the recipe perfectly (verification), but
the guest wanted pizza, not soup (validation).

Common mix-up: students often think "verification = testing by developers,
validation = testing by users". The real difference is what you compare
against: the specification (verification) or the customer's real needs
(validation).

## Static vs dynamic techniques

Static techniques examine the software or its documents without running the
program. Examples: requirements reviews, design reviews, code inspections,
automated static analysis tools.

Dynamic techniques execute the program with test data and observe how it
behaves. Examples: unit testing, system testing, performance testing,
acceptance testing.

Static techniques work on any readable artefact, so they can be used early,
before runnable code exists. Dynamic techniques need an executable version.
Only running the system shows its real behaviour, such as actual response
time under load.

Comparison: static is proofreading a recipe. Dynamic is cooking the dish and
tasting it.

## Reviews and inspections

In an inspection, a small team carefully reads a document or source code to
find defects, often using a checklist of common errors. The program is not
executed.

Advantages of inspections:
- One session can find many defects. In testing, one failure can hide other
  defects behind it. An inspection looks at the static text, so errors do not
  mask each other.
- Incomplete versions can be inspected. No test harness is needed.
- They can check wider quality attributes: standards compliance, portability,
  maintainability, poor programming style.
- They apply to requirements, designs, code, test plans and other documents.

Limits of inspections:
- They cannot show how the system really behaves when it runs: performance,
  usability with real users, unexpected interactions between components.
- They are weak for validation with customers, because they check against the
  specification, not against what the customer really wants.

Inspections and testing are complementary. Good V&V uses both.

## Automated static analysis

Static analysis tools scan source code without running it and flag likely
problems: variables used before they are initialised, unreachable code,
unused variables, possible null references, coding standard violations.
They support inspections but do not replace them, because a tool cannot judge
whether the code does what the user needs.

## Testing levels

- Unit testing: individual functions, methods or classes are tested in
  isolation. Usually written by developers.
- Integration (component) testing: units are combined, and tests focus on the
  interfaces and interactions between them.
- System testing: the complete, integrated system is tested, including
  emergent properties such as performance and reliability.
- Acceptance testing: customers test the system with their own data to decide
  whether it is ready to be accepted and deployed.

Comparison: unit = checking each brick, integration = checking the mortar
between bricks, system = checking the whole house, acceptance = the buyer
walking through before taking the keys.

## Development, release and user testing

- Development testing: the team that builds the system tests it during
  development (unit, component and system testing).
- Release testing: a separate team tests a complete version before release to
  check that it meets its requirements and is good enough for external use.
- User testing: real or potential users test the system in their own
  environment. Alpha testing: selected users work with the development team
  on early versions. Beta testing: a release is made available to a larger
  group of users who report problems. Acceptance testing: the customer decides
  whether to accept the system.

## Two goals of testing: validation testing and defect testing

Validation testing shows the developer and the customer that the software
meets its requirements. A successful test shows the system working as
intended.

Defect testing tries to expose faults: incorrect, undesirable or
non-conforming behaviour. A successful defect test is one that makes the
system fail.

Testing can show the presence of errors, not their absence (Dijkstra).

## Regression testing and test-driven development

Regression testing re-runs earlier tests after a change, to check that the
change has not broken something that used to work. Automated tests make this
cheap.

In test-driven development (TDD), the test is written before the code. You
write a failing test, write just enough code to pass it, then clean up the
code. The growing test suite doubles as a regression suite.

## How to classify an activity

Ask two questions:
1. Is the program executed? No = static. Yes = dynamic.
2. What is it checked against? The specification = verification. The
   customer's real needs = validation.

Examples:
- Code inspection against a checklist: verification, static.
- Unit tests derived from the specification: verification, dynamic.
- Requirements review with end users: validation, static.
- Prototype demo to the customer: validation.
- Customer acceptance testing with real data: mainly validation, dynamic.

Many activities contribute to both. System testing against the requirements
is verification, and when real users are involved it also validates.
