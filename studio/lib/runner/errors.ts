export class ConfigError extends Error { constructor(m: string) { super(m); this.name = "ConfigError"; } }
export class ClaudeRunError extends Error { constructor(m: string) { super(m); this.name = "ClaudeRunError"; } }
export class PostProcessError extends Error { constructor(m: string) { super(m); this.name = "PostProcessError"; } }
