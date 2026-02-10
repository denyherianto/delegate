## Frontend Engineering Practices

- Check for existing design tokens, component library, or style conventions
  before writing new styles. Match what's there.
- Build components in isolation before integrating. Test with mock data first.
- Handle loading, empty, and error states for every data-driven component.
  The happy path is half the work.
- Never hardcode colors, spacing, or breakpoints. Use variables/tokens.
- Test at 375px and 1280px minimum. If it breaks at either, it's not done.
- If playwright is available, screenshot your work, save to
  shared/previews/task-{id}/ and attach to the task. Include default, error, 
  and mobile states (if appropriate)
- Keep bundle impact in mind. Check the size of any dependency before adding it.
- Accessibility is not optional: semantic HTML, keyboard navigation,
  sufficient contrast, alt text.