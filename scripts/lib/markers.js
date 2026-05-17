export function ensureBlock(content, startMarker, endMarker, body) {
  const block = `${startMarker}\n${body}\n${endMarker}`;
  const s = content.indexOf(startMarker);
  const e = content.indexOf(endMarker);
  if (s !== -1 && e !== -1 && e > s) {
    return content.slice(0, s) + block + content.slice(e + endMarker.length);
  }
  const sep = content.endsWith('\n') ? '\n' : '\n\n';
  return content + sep + block + '\n';
}
