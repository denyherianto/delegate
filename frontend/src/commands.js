/**
 * Command registry for magic commands.
 * Magic commands are slash-prefixed commands typed in the chat input
 * that execute directly, bypassing the manager agent.
 */

export const COMMANDS = {
  shell: {
    name: 'shell',
    description: 'Run a shell command (e.g. /shell -d ~/Documents ls)',
    usage: '/shell [command]',
  },
  status: {
    name: 'status',
    description: 'Show system status',
    usage: '/status',
  },
  diff: {
    name: 'diff',
    description: 'Show task diff (e.g. /diff 42 or /diff T0042)',
    usage: '/diff [task_id]',
  },
  cost: {
    name: 'cost',
    description: 'Show cost summary',
    usage: '/cost',
  },
  agent: {
    name: 'agent',
    description: 'Add an agent to the team (e.g. /agent add alice --role engineer)',
    usage: '/agent add [name] [--role <role>] [--seniority junior|senior] [--bio \'...\']',
  },
};

/**
 * Parse a potential command input.
 * @param {string} input - The input text
 * @returns {{ name: string, args: string, raw: string } | null}
 */
export function parseCommand(input) {
  if (!input || !input.startsWith('/')) return null;

  const trimmed = input.slice(1).trim();
  if (!trimmed) return null;

  const spaceIdx = trimmed.indexOf(' ');
  const name = spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx);
  const args = spaceIdx === -1 ? '' : trimmed.slice(spaceIdx + 1).trim();

  return {
    name: name.toLowerCase(),
    args,
    raw: input
  };
}

/**
 * Filter commands by query prefix.
 * @param {string} query - The query string (without the / prefix)
 * @returns {Array} - Filtered command objects
 */
export function filterCommands(query) {
  const lowerQuery = query.toLowerCase();
  return Object.values(COMMANDS).filter(c =>
    c.name.startsWith(lowerQuery)
  );
}
