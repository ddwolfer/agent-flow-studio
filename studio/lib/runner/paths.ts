import { join } from "node:path";

// Absolute path to the studio/ dir. All runtime entrypoints (Next server,
// vitest, the tsx launcher) execute with cwd = studio/, and webpack cannot
// bundle an import.meta.url URL specifier — so anchor on process.cwd().
export const STUDIO_ROOT = process.cwd();
export const RUNS_ROOT = join(STUDIO_ROOT, "runs");
