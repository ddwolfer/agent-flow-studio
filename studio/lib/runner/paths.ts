import { join } from "node:path";
import { fileURLToPath } from "node:url";
export const STUDIO_ROOT = fileURLToPath(new URL("../../", import.meta.url)); // studio/
export const RUNS_ROOT = join(STUDIO_ROOT, "runs");
