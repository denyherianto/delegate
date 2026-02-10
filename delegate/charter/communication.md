# Communication Protocol

All agents communicate exclusively via messages. No agent directly modifies another agent's files.

## Messaging

Messages are stored in a shared SQLite database. The daemon delivers messages and tracks their lifecycle (delivered → seen → processed → read).

Your conversational text is NOT delivered to anyone — it only goes to an internal log. The ONLY way to communicate is the mailbox send command:

```
python -m delegate.mailbox send <home> <team> <your_name> <recipient> "<message>"
```

For every message you receive, respond by running the send command. Do not just compose a reply — actually execute the command.

Check inbox: `python -m delegate.mailbox inbox <home> <team> <your_name>`

## When to Message

- **Ask questions early.** Unclear requirements → message the manager. Ten-minute conversation saves a day of rework.
- **Report progress.** Finished a task or hit a blocker → message the manager.
- **Keep it brief.** Say what you need clearly and concisely.
- **Respond promptly.** If you need something, be specific about what and by when.
- **Don't wait silently.** If blocked on someone, say so explicitly.

## Long-Running Work

When working on a task that takes more than a few minutes and someone may be waiting for the result (especially the boss or manager), send a brief progress update every few minutes. A short "Still working on X — finished Y, now doing Z" keeps people informed and prevents the impression that messages were dropped. Don't wait until everything is done to communicate.
