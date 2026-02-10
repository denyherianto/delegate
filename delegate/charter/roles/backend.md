## Backend Engineering Practices

- Read existing code patterns before writing. Match error handling style,
  naming conventions, and project structure.
- Write the interface first: define the function signature, the API contract,
  or the data model before implementing the logic.
- Every public endpoint or function gets input validation and error handling.
  Never trust the caller.
- Write tests alongside implementation. At minimum: one happy path,
  one error case, one edge case per function.
- At the same time, don't write unnecessarily repetitive tests - aim for 
  mutually disjoint tests that together cover all the invariants.
- If you add or change an API, update the contract in shared/specs/.
  Others depend on this.
- Don't swallow errors. Log them with context (what was attempted,
  what input caused it), then return a meaningful error.
- If you need to add a dependency, check if something already in the
  project solves the problem. Fewer dependencies is better.
- Think about what happens at 10x scale. You don't need to build for it,
  but flag it if your approach won't survive it.