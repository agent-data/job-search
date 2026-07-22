// Registers the bundled Job Search skills with OpenCode.

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const pluginDirectory = dirname(fileURLToPath(import.meta.url));
const skillsPath = join(pluginDirectory, "..", "..", "skills");

export const JobSearchPlugin = async () => ({
  config(config) {
    config.skills ??= {};
    config.skills.paths ??= [];
    if (!config.skills.paths.includes(skillsPath)) {
      config.skills.paths.push(skillsPath);
    }
  },
});
