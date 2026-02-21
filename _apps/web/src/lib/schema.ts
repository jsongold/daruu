import { z } from "zod";

export const ValidationRuleSchema = z.object({
  min_length: z.number().int().nonnegative().optional(),
  max_length: z.number().int().nonnegative().optional(),
  regex: z.string().nullable().optional(),
});

export const FontPolicySchema = z
  .object({
    family: z.string().nullable().optional(),
    size: z.number().positive(),
    min_size: z.number().positive(),
  })
  .refine((value) => value.min_size <= value.size, {
    message: "min_size must be <= size",
    path: ["min_size"],
  });

export const PlacementSchema = z.object({
  page_index: z.number().int().nonnegative(),
  x: z.number(),
  y: z.number(),
  max_width: z.number().positive(),
  align: z.enum(["left", "center", "right"]).default("left"),
  font_policy: FontPolicySchema,
});

export const FieldDefinitionSchema = z.object({
  id: z.string().min(1),
  key: z.string().min(1),
  label: z.string().min(1),
  type: z.literal("string"),
  required: z.boolean(),
  validation: ValidationRuleSchema.nullable().optional(),
  placement: PlacementSchema,
});

export const TemplateSchemaSchema = z.object({
  version: z.literal("v1").default("v1"),
  name: z.string().min(1),
  fields: z.array(FieldDefinitionSchema),
});

export type TemplateSchema = z.infer<typeof TemplateSchemaSchema>;
export type FieldDefinition = z.infer<typeof FieldDefinitionSchema>;

export const defaultTemplateSchema: TemplateSchema = {
  version: "v1",
  name: "empty-template",
  fields: [],
};
