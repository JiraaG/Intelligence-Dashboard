import { describe, expect, it } from 'vitest';
import { greatCircle, MAP_ZOOM_PIN_THRESHOLD } from './great-circle';

describe('greatCircle helper', () => {
  it('returns n+1 coordinate pairs from A to B', () => {
    const coords = greatCircle(41.9, 12.5, 48.8, 2.3, 10);
    expect(coords.length).toBe(11);
    expect(coords[0][0]).toBeCloseTo(12.5, 5);
    expect(coords[0][1]).toBeCloseTo(41.9, 5);
    expect(coords[10][0]).toBeCloseTo(2.3, 5);
    expect(coords[10][1]).toBeCloseTo(48.8, 5);
  });

  it('applies perpendicular curvature so midpoint is offset', () => {
    const straightMid = greatCircle(0, 0, 0, 10, 2, 0);
    const curvedMid = greatCircle(0, 0, 0, 10, 2, 0.2);
    expect(straightMid[1][1]).toBeCloseTo(0, 5);
    expect(Math.abs(curvedMid[1][1])).toBeGreaterThan(0.1);
  });
});

describe('MAP_ZOOM_PIN_THRESHOLD', () => {
  it('matches day-view pin/hatch threshold of 5', () => {
    expect(MAP_ZOOM_PIN_THRESHOLD).toBe(5);
    expect(3 < MAP_ZOOM_PIN_THRESHOLD).toBe(true);
    expect(5 < MAP_ZOOM_PIN_THRESHOLD).toBe(false);
  });
});
