## Architecture Practices

- Before proposing a design, understand the existing system. Read before 
  writing. Check shared/specs/ and shared/decisions/ for prior art.

- Write specs in shared/specs/ before implementation begins. Include:
  - Data models, API contracts, component interfaces
  - What's intentionally excluded and why

- When reviewing others' work, focus on structural concerns:
  - Does this create coupling that will hurt later?
  - Is the abstraction at the right level?
  - Will this scale to 10x the current usage?

- Document key decisions in shared/decisions/ specifying:
  - Context: what situation prompted this decision
  - Assumptions: what assumptions underpin this decision
  - Decision: what we chose
  - Consequences: what follows from this choice

- Flag tech debt proactively. Don't wait to be asked.