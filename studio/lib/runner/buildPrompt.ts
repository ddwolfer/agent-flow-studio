import type { Channel } from "../config/schema";

export interface BuildPromptArgs {
  promptTemplate: string;
  references: readonly string[];
  channel: Channel;
  calendarText: string;
  htmlPath?: string;
  logPath?: string;
  dateIso?: string;
  reportCss?: string;
}

export function buildPrompt(a: BuildPromptArgs): string {
  let body = a.promptTemplate
    .replaceAll("{{channel.handle}}", a.channel.handle)
    .replaceAll("{{channel.name}}", a.channel.name)
    .replaceAll("{{channel.search_query}}", a.channel.search_query)
    .replaceAll("{{calendar}}", a.calendarText)
    .replaceAll("{{report_css}}", a.reportCss ?? "")
    .replaceAll("${HTML_FILE}", a.htmlPath ?? "")
    .replaceAll("${DATE}", a.dateIso ?? "")
    .replaceAll("${LOG_FILE}", a.logPath ?? "");
  if (a.references.length > 0)
    body += "\n\n---\n# Reference material (authoritative)\n\n" +
      a.references.join("\n\n---\n\n");
  return body;
}
