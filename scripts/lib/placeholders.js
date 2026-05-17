export function substitute(text, map) {
  let out = text;
  for (const [key, val] of Object.entries(map)) {
    out = out.split(`{{${key}}}`).join(String(val));
  }
  return out;
}

export function hasPlaceholders(text) {
  return /\{\{[A-Z0-9_]+\}\}/.test(text);
}
