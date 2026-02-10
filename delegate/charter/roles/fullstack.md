## Fullstack Engineering Practices

- Separate concerns cleanly. Don't leak backend logic into frontend
  components or embed presentation decisions in API responses.
- Define the API contract before building either side. Write it to
  shared/specs/ so both sides have a source of truth.
- Build backend first, verify with tests, then build frontend against it.
  Don't build both simultaneously and debug the gap.
- Use the same validation rules on both sides. Extract shared constants
  or schemas where possible.
- Handle loading, empty, and error states on the frontend for every
  endpoint you create on the backend.
- Test the full flow, not just each side in isolation. An endpoint that
  returns 200 and a component that renders data are both useless if the
  response shape doesn't match what the component expects.
- Keep frontend and backend changes in the same commit when they're
  coupled. Don't leave one side broken between commits.
- If playwright is available, screenshot completed UI work and save to
  shared/previews/task-{id}/ and attach to the task.