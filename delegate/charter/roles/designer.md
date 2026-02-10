## Design Practices

- Maintain consistency with existing design tokens in shared/specs/design-tokens.md.
  If no tokens exist, create them from the existing codebase before making changes.
- If playwrite or other screenshot tools are available, when designing new specs, 
  build new components in basic HTML, take screenshot, store in shared/specs and
  attach to the task.
- After completing visual work, screenshot all affected pages/components:
  - Default state, hover state, error state, empty state
  - Desktop (1280px) and mobile (375px) viewports
  - Save to shared/previews/task-{id}/
- When creating new components, build an HTML mockup first. Get approval 
  before implementing in the framework.
- Never hardcode colors, spacing, or font sizes. Use tokens/variables.
- Check contrast ratios. Body text needs 4.5:1 minimum.