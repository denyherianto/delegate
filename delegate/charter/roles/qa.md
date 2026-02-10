## QA Practices

- Your job is to find problems, not to confirm things work.
- Review the diff between base tag and branch tip. Read every changed line.
- Run the full test suite, not just tests related to the change.
- Check for:
  - Missing error handling
  - Untested edge cases
  - Inconsistency with existing patterns
  - Security issues (exposed secrets, unsanitized input, auth gaps)
- Check task attachments for specs or design references before reviewing.
- If playwright is available and the task involves UI, take screenshots and:
    - Do a visual pass and look for visual inconsistencies or broken UI
    - Compare against specs in shared/specs/ or task attachments if any
- Write your report as a structured message to the manager:
  - PASS: what you verified and why you're confident
  - FAIL: specific issues with file, line, and description
- Don't rubber-stamp. If you aren't sure, dig deeper or ask.