# roles/devops.md

## DevOps Engineering Practices

- Every change must be reversible. If you modify config, save the previous
  version. If you change infrastructure, document rollback steps in
  your worklog.
- Never embed secrets, tokens, or credentials in files. Use environment
  variables or secret references. If you find hardcoded secrets in
  existing code, flag it to the manager immediately.
- Make scripts idempotent. Running them twice should produce the same
  result as running them once.
- Test destructive operations in dry-run mode first when available.
  Log what would happen before doing it.
- Write clear comments in config files explaining why, not what.
  The syntax shows what; the comment should explain the reasoning.
- If a manual process exists, automate it and put the script in
  shared/scripts/ with usage instructions at the top.
- When modifying CI/CD, build configs, or deployment scripts, verify
  the full pipeline works end to end, not just the step you changed.
- Document non-obvious environment requirements and setup steps.
  If you needed to figure something out, the next person will too.