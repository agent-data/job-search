// job-search opencode plugin
// Registers the shared skills/ tree and injects a bootstrap system message.
// PIN: verify hook names (config, experimental.chat.messages.transform) on the installed opencode version.

import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
// Resolve skills/ relative to the repo root (two levels up from .opencode/plugins/).
const skillsPath = join(__dirname, "..", "..", "skills");

// Tool-map adapter: see shared/references/platform/opencode.md for the full opencode tool map.
const BOOTSTRAP = `\
You are running inside opencode. Read AGENTS.md first — it is the instruction map for this workspace.

Tool map (opencode): see shared/references/platform/opencode.md for the complete action→tool mapping,
scheduling, headless invocation, and all PIN items that must be verified on the running instance.

agent-data CLI must be on PATH. Authenticate with:
  agent-data init --api-key <KEY> -y
`;

export default {
  // PIN: confirm config hook signature and config.skills.paths format on the installed opencode version.
  config(config) {
    if (!config.skills) config.skills = {};
    if (!Array.isArray(config.skills.paths)) config.skills.paths = [];
    config.skills.paths.push(skillsPath);
    return config;
  },

  experimental: {
    chat: {
      // PIN: ground truth over any README that says system.transform — messages.transform is correct.
      messages: {
        transform(messages) {
          const bootstrap = { role: "system", content: BOOTSTRAP };
          return [bootstrap, ...messages];
        },
      },
    },
  },
};
