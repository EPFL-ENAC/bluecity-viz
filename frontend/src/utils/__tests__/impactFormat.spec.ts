import { describe, expect, it } from 'vitest'
import { formatCo2, formatCount, formatDistance, formatTime } from '../impactFormat'

describe('impact numbers', () => {
  it('picks the distance unit', () => {
    expect(formatDistance(-0.509)).toBe('-509 m')
    expect(formatDistance(2.34)).toBe('+2.3 km')
    expect(formatDistance(-6917.7)).toBe('-6.9k km')
    expect(formatDistance(0)).toBe('0 m')
  })

  it('picks the time unit', () => {
    expect(formatTime(0.25)).toBe('+15 s')
    expect(formatTime(1.9)).toBe('+1.9 min')
    expect(formatTime(26036)).toBe('+434 h')
  })

  it('picks the CO2 unit', () => {
    expect(formatCo2(-141)).toBe('-141 g')
    expect(formatCo2(16871)).toBe('+17 kg')
    expect(formatCo2(-1914500)).toBe('-1.9 t')
    expect(formatCo2(undefined)).toBe('—')
  })

  it('shortens counts', () => {
    expect(formatCount(500)).toBe('500')
    expect(formatCount(13584)).toBe('13.6k')
    expect(formatCount(76000)).toBe('76k')
  })
})
