import { STATUS_COLORS, ROLE_COLORS, OCR_STATUS_COLORS } from '@/config/constants';
import './Badge.css';

type BadgeVariant = 'status' | 'role' | 'ocr' | 'custom';

interface BadgeProps {
  variant: BadgeVariant;
  value: string;
  color?: string;
}

export function Badge({ variant, value, color }: BadgeProps) {
  let badgeColor = color;

  if (!badgeColor) {
    switch (variant) {
      case 'status':
        badgeColor = STATUS_COLORS[value as keyof typeof STATUS_COLORS] || 'gray';
        break;
      case 'role':
        badgeColor = ROLE_COLORS[value as keyof typeof ROLE_COLORS] || 'gray';
        break;
      case 'ocr':
        badgeColor = OCR_STATUS_COLORS[value as keyof typeof OCR_STATUS_COLORS] || 'gray';
        break;
      default:
        badgeColor = 'gray';
    }
  }

  return <span className={`badge badge-${badgeColor}`}>{value}</span>;
}
