import { useEffect, useMemo, useRef } from "react";
import { Layer, Rect, Stage, Text, Transformer } from "react-konva";
import type Konva from "konva";

import type { FieldDefinition } from "../lib/schema";
import type { PdfViewport } from "./PdfViewer";

type PlacementLayerProps = {
  fields: FieldDefinition[];
  viewport: PdfViewport | null;
  selectedFieldId: string | null;
  onSelect: (fieldId: string) => void;
  onUpdatePlacement: (
    fieldId: string,
    placement: Partial<FieldDefinition["placement"]>,
  ) => void;
};

type RectMetrics = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const MIN_WIDTH_PX = 20;

export default function PlacementLayer({
  fields,
  viewport,
  selectedFieldId,
  onSelect,
  onUpdatePlacement,
}: PlacementLayerProps) {
  const shapeRefs = useRef<Record<string, Konva.Rect>>({});
  const transformerRef = useRef<Konva.Transformer>(null);

  const visibleFields = useMemo(
    () =>
      fields.filter(
        (field) => field.placement.page_index === 0 && viewport,
      ),
    [fields, viewport],
  );

  useEffect(() => {
    if (!transformerRef.current) {
      return;
    }
    if (!selectedFieldId) {
      transformerRef.current.nodes([]);
      transformerRef.current.getLayer()?.batchDraw();
      return;
    }
    const node = shapeRefs.current[selectedFieldId];
    if (node) {
      transformerRef.current.nodes([node]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [selectedFieldId]);

  if (!viewport) {
    return null;
  }

  const boxHeightPx = (field: FieldDefinition) =>
    Math.max(10, field.placement.font_policy.size * viewport.scale * 1.3);

  const toRectMetrics = (field: FieldDefinition): RectMetrics => {
    const height = boxHeightPx(field);
    const width = Math.max(MIN_WIDTH_PX, field.placement.max_width * viewport.scale);
    const x = field.placement.x * viewport.scale;
    const y = viewport.height - field.placement.y * viewport.scale - height;
    return { x, y, width, height };
  };

  const updateFromRect = (field: FieldDefinition, rect: RectMetrics) => {
    const newX = rect.x / viewport.scale;
    const newY = (viewport.height - rect.y - rect.height) / viewport.scale;
    const newMaxWidth = rect.width / viewport.scale;
    onUpdatePlacement(field.id, { x: newX, y: newY, max_width: newMaxWidth });
  };

  return (
    <Stage width={viewport.width} height={viewport.height}>
      <Layer>
        {visibleFields.map((field) => {
          const rect = toRectMetrics(field);
          const isSelected = field.id === selectedFieldId;
          return (
            <Rect
              key={field.id}
              ref={(node) => {
                if (node) {
                  shapeRefs.current[field.id] = node;
                }
              }}
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              stroke={isSelected ? "#2563eb" : "#94a3b8"}
              strokeWidth={2}
              fill={
                isSelected
                  ? "rgba(37, 99, 235, 0.12)"
                  : "rgba(148, 163, 184, 0.15)"
              }
              draggable
              onClick={() => onSelect(field.id)}
              onTap={() => onSelect(field.id)}
              onDragEnd={(event) => {
                const node = event.target;
                updateFromRect(field, {
                  x: node.x(),
                  y: node.y(),
                  width: rect.width,
                  height: rect.height,
                });
              }}
              onTransformEnd={() => {
                const node = shapeRefs.current[field.id];
                if (!node) {
                  return;
                }
                const width = Math.max(
                  MIN_WIDTH_PX,
                  node.width() * node.scaleX(),
                );
                node.scaleX(1);
                node.scaleY(1);
                updateFromRect(field, { ...rect, width });
              }}
            />
          );
        })}
        {visibleFields.map((field) => {
          const rect = toRectMetrics(field);
          const isSelected = field.id === selectedFieldId;
          return (
            <Text
              key={`${field.id}-label`}
              x={rect.x + 4}
              y={rect.y + 2}
              text={field.label}
              fontSize={Math.max(10, rect.height * 0.6)}
              fill={isSelected ? "#1d4ed8" : "#475569"}
              listening={false}
            />
          );
        })}
        <Transformer
          ref={transformerRef}
          rotateEnabled={false}
          enabledAnchors={["middle-left", "middle-right"]}
          boundBoxFunc={(oldBox, newBox) => ({
            ...newBox,
            y: oldBox.y,
            height: oldBox.height,
          })}
        />
      </Layer>
    </Stage>
  );
}
