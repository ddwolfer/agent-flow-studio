import { z } from "zod";

export const Channel = z.object({
  id: z.string().regex(/^[a-z0-9-]+$/),
  handle: z.string().min(1),
  name: z.string().min(1),
  search_query: z.string().min(1),
  pipeline: z.string().min(1),
  enabled: z.boolean(),
});
export const ChannelsFile = z.object({ channels: z.array(Channel) });

export const PipelineFile = z.object({
  name: z.string().min(1),
  model: z.string().min(1),
  max_turns: z.number().int().positive(),
  prompt: z.object({
    template: z.string().min(1),
    references: z.array(z.string()).default([]),
  }),
  post: z.object({
    pdf: z.boolean(),
    notify: z.boolean(),
    picks: z.object({ model: z.string().min(1), prompt: z.string().min(1) }),
  }),
  quality_judge: z.object({ model: z.string().min(1), rubric: z.string().min(1) }),
});

export type Channel = z.infer<typeof Channel>;
export type PipelineConfig = z.infer<typeof PipelineFile>;
