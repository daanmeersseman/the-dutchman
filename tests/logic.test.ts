import { describe, expect, test } from 'claude-code/testing'

import { idleBeforeExpiry, money, noticeText, older, reached } from '../hooks/logic'

describe('reached', () => {
  test('a reminder with a step fires at each step', () => {
    expect(reached(200_000, 250_000, 150_000)).toBe(0)
    expect(reached(260_000, 250_000, 150_000)).toBe(250_000)
    expect(reached(410_000, 250_000, 150_000)).toBe(400_000)
  })
  test('a reminder without a step fires once', () => {
    expect(reached(260_000, 250_000)).toBe(250_000)
    expect(reached(900_000, 250_000)).toBe(250_000)
  })
})

test('the cache reminder follows the cache setting of the moment', () => {
  expect(idleBeforeExpiry(undefined, 60_000)).toBe(240_000)
  expect(idleBeforeExpiry('1h', 60_000)).toBe(3_540_000)
})

test('older compares major.minor.patch', () => {
  expect(older('2.1.9', '2.1.242')).toBe(true)
  expect(older('2.2.0', '2.1.242')).toBe(false)
  expect(older('2.1.242', '2.1.242')).toBe(false)
})

test('the notice keeps a saving and a cost at stake apart', () => {
  expect(money(5.5)).toBe('$5.50')
  expect(noticeText(57, 145, 6)).toBe('~$57/mo to save, $145/mo at stake. 6 tips: type /dutchman.')
  expect(noticeText(0, 20, 1)).toBe('$20/mo of your Claude Code bill at stake. 1 tip: type /dutchman.')
})
