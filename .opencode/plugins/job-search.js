// job-search opencode plugin
// Registers the shared skills/ tree and injects a bootstrap message at session start.
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

// Stable sentinel used by the dedup guard below. It must be a substring of BOOTSTRAP that no
// ordinary message would contain, so the guard can recognize an already-injected bootstrap by
// content regardless of opencode's exact message-object shape.
const BOOTSTRAP_MARKER = "You are running inside opencode.";

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
      // Injection lifecycle (AAS-PORT-08). opencode's transform fires on EVERY agent step, so
      // unconditionally prepending the bootstrap would re-inject it each step — token bloat, and
      // repeated system messages break some models. So:
      //   - inject as a USER-role message, not system (system messages bloat tokens when repeated
      //     and multiple system messages break some models);
      //   - DEDUP-GUARD: skip injection when the current messages already carry the bootstrap
      //     (recognized by BOOTSTRAP_MARKER), so a per-step/per-turn callback does not duplicate it;
      //   - COMPACTION RE-INJECT: the same guard re-adds the bootstrap when compaction has dropped
      //     it (marker absent -> inject once more), so the instruction survives a compacted context.
      // PIN: ground truth over any README that says system.transform — messages.transform is correct;
      // and confirm opencode's exact message-object shape on a running instance.
      messages: {
        transform(messages) {
          if (!Array.isArray(messages)) return messages;
          const hasBootstrap = messages.some((m) => {
            const c = m && m.content;
            return typeof c === "string" && c.includes(BOOTSTRAP_MARKER);
          });
          if (hasBootstrap) return messages;
          return [{ role: "user", content: BOOTSTRAP }, ...messages];
        },
      },
    },
  },
};
