/**
 * Example tool — a starting point, not the point (mirrors lg_agent's example
 * tool convention). Returns the current server time in a given IANA timezone.
 */

import { tool } from "ai";
import { z } from "zod";

export const getTime = tool({
  description: "Get the current date and time, optionally in a specific IANA timezone.",
  inputSchema: z.object({
    timezone: z
      .string()
      .optional()
      .describe('IANA timezone, e.g. "America/New_York". Defaults to UTC.'),
  }),
  execute: async ({ timezone }) => {
    const now = new Date();
    const iso = timezone
      ? now.toLocaleString("en-US", { timeZone: timezone })
      : now.toISOString();
    return { now: iso, timezone: timezone ?? "UTC" };
  },
});
