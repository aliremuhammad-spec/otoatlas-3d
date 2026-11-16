import { formatMillimetres } from './format';

describe('millimetre formatting', () => {
  it('uses two decimals below 5 mm and one decimal from 5 mm', () => {
    expect(formatMillimetres(2.934)).toBe('2.93');
    expect(formatMillimetres(0.5)).toBe('0.50');
    expect(formatMillimetres(4.996)).toBe('5.00');
    expect(formatMillimetres(5)).toBe('5.0');
    expect(formatMillimetres(31.47)).toBe('31.5');
  });

  it('renders Eastern Arabic digits with the Arabic decimal separator', () => {
    expect(formatMillimetres(2.93, 'eastern')).toBe('٢٫٩٣');
    expect(formatMillimetres(12.5, 'eastern')).toBe('١٢٫٥');
  });

  it('shows a dash for undefined values', () => {
    expect(formatMillimetres(Number.NaN)).toBe('—');
  });
});
