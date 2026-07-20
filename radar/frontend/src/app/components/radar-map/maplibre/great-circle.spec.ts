import { describe, expect, it } from 'vitest';
import {
  greatCircle,
  MAP_ZOOM_PIN_HYSTERESIS,
  MAP_ZOOM_PIN_THRESHOLD,
  resolvePinMode,
} from './great-circle';

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
  it('matches day-view pin enter threshold of 4', () => {
    expect(MAP_ZOOM_PIN_THRESHOLD).toBe(4);
    expect(MAP_ZOOM_PIN_HYSTERESIS).toBe(0.4);
  });
});

describe('resolvePinMode', () => {
  it('enters pin mode only at or above threshold when currently hatching', () => {
    expect(resolvePinMode(3.9, false)).toBe(false);
    expect(resolvePinMode(4, false)).toBe(true);
    expect(resolvePinMode(4.2, false)).toBe(true);
  });

  it('stays in pin mode through globe pan jitter below threshold until hysteresis floor', () => {
    const exitBelow = MAP_ZOOM_PIN_THRESHOLD - MAP_ZOOM_PIN_HYSTERESIS;
    expect(resolvePinMode(3.9, true)).toBe(true);
    expect(resolvePinMode(exitBelow, true)).toBe(true);
    expect(resolvePinMode(exitBelow - 0.01, true)).toBe(false);
  });
});
