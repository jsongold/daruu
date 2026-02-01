/**
 * Cost tracking display components.
 */

import { type CSSProperties } from 'react';
import type { CostSummary } from '../../types/api';
import { Card } from '../ui/Card';
import { formatCost, formatFileSize } from '../../utils/format';

export interface CostDisplayProps {
  cost: CostSummary;
  showDetails?: boolean;
}

export function CostDisplay({ cost, showDetails = false }: CostDisplayProps) {
  const containerStyles: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  };

  const totalStyles: CSSProperties = {
    textAlign: 'center',
    padding: '16px',
    backgroundColor: '#f9fafb',
    borderRadius: '8px',
  };

  const totalAmountStyles: CSSProperties = {
    fontSize: '28px',
    fontWeight: 700,
    color: '#111827',
    marginBottom: '4px',
  };

  const totalLabelStyles: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
  };

  const breakdownStyles: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '12px',
  };

  const breakdownItemStyles: CSSProperties = {
    padding: '12px',
    backgroundColor: '#f9fafb',
    borderRadius: '6px',
    textAlign: 'center',
  };

  const breakdownValueStyles: CSSProperties = {
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    marginBottom: '2px',
  };

  const breakdownLabelStyles: CSSProperties = {
    fontSize: '11px',
    color: '#6b7280',
    textTransform: 'uppercase',
  };

  return (
    <Card title="Cost Tracking" padding="md">
      <div style={containerStyles}>
        <div style={totalStyles}>
          <div style={totalAmountStyles}>{formatCost(cost.estimated_cost_usd)}</div>
          <div style={totalLabelStyles}>Estimated Total Cost</div>
        </div>

        <div style={breakdownStyles}>
          <div style={breakdownItemStyles}>
            <div style={breakdownValueStyles}>{formatCost(cost.breakdown.llm_cost_usd)}</div>
            <div style={breakdownLabelStyles}>LLM</div>
          </div>
          <div style={breakdownItemStyles}>
            <div style={breakdownValueStyles}>{formatCost(cost.breakdown.ocr_cost_usd)}</div>
            <div style={breakdownLabelStyles}>OCR</div>
          </div>
          <div style={breakdownItemStyles}>
            <div style={breakdownValueStyles}>{formatCost(cost.breakdown.storage_cost_usd)}</div>
            <div style={breakdownLabelStyles}>Storage</div>
          </div>
        </div>

        {showDetails && (
          <CostDetails cost={cost} />
        )}
      </div>
    </Card>
  );
}

function CostDetails({ cost }: { cost: CostSummary }) {
  const detailsStyles: CSSProperties = {
    fontSize: '13px',
    color: '#6b7280',
  };

  const rowStyles: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid #f3f4f6',
  };

  const labelStyles: CSSProperties = {
    color: '#6b7280',
  };

  const valueStyles: CSSProperties = {
    color: '#374151',
    fontWeight: 500,
  };

  return (
    <div style={detailsStyles}>
      <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#374151' }}>
        Usage Details
      </h4>

      <div style={rowStyles}>
        <span style={labelStyles}>Model</span>
        <span style={valueStyles}>{cost.model_name}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>LLM Calls</span>
        <span style={valueStyles}>{cost.llm_calls}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>Input Tokens</span>
        <span style={valueStyles}>{cost.llm_tokens_input.toLocaleString()}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>Output Tokens</span>
        <span style={valueStyles}>{cost.llm_tokens_output.toLocaleString()}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>OCR Pages</span>
        <span style={valueStyles}>{cost.ocr_pages_processed}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>OCR Regions</span>
        <span style={valueStyles}>{cost.ocr_regions_processed}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>Storage Upload</span>
        <span style={valueStyles}>{formatFileSize(cost.storage_bytes_uploaded)}</span>
      </div>

      <div style={rowStyles}>
        <span style={labelStyles}>Storage Download</span>
        <span style={valueStyles}>{formatFileSize(cost.storage_bytes_downloaded)}</span>
      </div>
    </div>
  );
}

/**
 * Compact cost indicator for headers.
 */
export function CostIndicator({ cost }: { cost: CostSummary }) {
  const indicatorStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    backgroundColor: '#f3f4f6',
    borderRadius: '16px',
    fontSize: '12px',
    fontWeight: 500,
  };

  const iconStyles: CSSProperties = {
    color: '#22c55e',
  };

  return (
    <div style={indicatorStyles}>
      <span style={iconStyles}>$</span>
      <span style={{ color: '#374151' }}>{formatCost(cost.estimated_cost_usd)}</span>
    </div>
  );
}
