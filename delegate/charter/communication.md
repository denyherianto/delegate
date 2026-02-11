# Communication Protocol

All agents communicate exclusively via messages. No agent directly modifies another agent's files.

## Messaging

Messages are stored in a shared SQLite database. The daemon delivers messages and tracks their lifecycle (delivered → seen → processed → read).

Your conversational text is NOT delivered to anyone — it only goes to an internal log. The ONLY way to communicate is the mailbox send command:

```
python -m delegate.mailbox send <home> <team> <your_name> <recipient> "<message>"
```

Do not just compose a reply — actually execute the send command. But ONLY send a message when you have substantive content. Do NOT send acknowledgment-only messages. The system shows delivery/read status automatically.

Check inbox: `python -m delegate.mailbox inbox <home> <team> <your_name>`

## When to Message

- **Ask questions early.** Unclear requirements → message the manager.
- **Report results.** Finished a task or hit a blocker → message the manager with specifics.
- **Keep it brief.** Say what you need clearly and concisely.
- **Be specific.** If you need something, say exactly what and by when.
- **Don't wait silently.** If blocked on someone, say so explicitly.

## When NOT to Message

- **No pure acknowledgments.** "Got it", "Thanks", "Working on it", "Standing by" — these waste everyone's time. Just do the work.
- **No redundant status.** If you have nothing new to report, don't send a message.
- **No echoing back.** Don't repeat what someone told you. Confirm only if there's ambiguity.
- **Consolidate.** If you have multiple things to say to the same person, send one message, not three.
