export type FieldType = "string";
export type TextAlign = "left" | "center" | "right";

export type ValidationRule = {
  min_length?: number;
  max_length?: number;
  regex?: string;
};

export type FontPolicy = {
  family?: string;
  size: number;
  min_size: number;
};

export type Placement = {
  page_index: number;
  x: number;
  y: number;
  max_width: number;
  align: TextAlign;
  font_policy: FontPolicy;
};

export type FieldDefinition = {
  id: string;
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  validation?: ValidationRule;
  placement: Placement;
};

export type TemplateSchema = {
  version: "v1";
  name: string;
  fields: FieldDefinition[];
};
