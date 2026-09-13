# `delayEndTime` is a delay until the cycle *ends*

Raised by #427, which asked whether LocalThings exposes Samsung's native
"Delay End" and whether `delay_start_hours` maps to
`x.com.samsung.da.delayEndTime`. It does map to it, and that mapping was
built on the assumption that `delayEndTime` is just another name for
`delayStartTime`. It is not.

## What the two fields are

| Field | Meaning | Who reports it |
|---|---|---|
| `x.com.samsung.da.delayStartTime` | duration until the cycle **starts** | dishwashers |
| `x.com.samsung.da.delayEndTime` | duration until the cycle **ends** | washers, dryers, air dressers |

Both hold a duration, not a wall-clock time: `"01:00:00"` means one hour
from now, not 1 AM. That part of the original reading was right, and it is
worth keeping stated because the field names invite the other reading.

No dump in the corpus carries both fields, so the split is clean by family.

## Evidence that `delayEndTime` runs to the end

Measured on a WD80T634DBE/S7 in #427. With the appliance `Ready` and
reporting a `remainingTime` of `03:17:00`, a write of `05:00:00` followed by
pressing start gave, during `Delaywash`:

```
x.com.samsung.da.state         = 'Run'
x.com.samsung.da.progress      = 'Delaywash'
x.com.samsung.da.remainingTime = '05:00:00'
x.com.samsung.da.delayEndTime  = '05:00:00'
```

Five hours to finish, not five hours plus the course. A delay-until-*start*
write would have left `remainingTime` at roughly 5 h + ~2 h.

Three independent observations agree:

1. `tests/fixtures/washer_wf80h_device.json`, the only dump in the corpus
   caught mid-delay, reports `delayEndTime` and `remainingTime` as the same
   `09:26:00`.
2. A `DA_WM_TP2_20_COMMON` (WW90T65) dump in #427, captured at 11:57 with
   Delay End set from the SmartThings app for a 17:10 finish, reports both
   fields as `05:14:00` — 11:57 + 5:14 = 17:11.
3. The field is named `delayEnd`, and Samsung's own app calls the feature
   "Delay End" and asks for a finish time.

Once the cycle itself starts, `delayEndTime` drops to `00:00:00` and
`remainingTime` alone carries the countdown.

## Minute precision: yes

Also measured on the WD80T634DBE/S7. A deliberately odd `03:17:00` was
written and read back unchanged (`held: true`) — no rounding to whole hours.
`_format_delay` already emits `HH:MM:00`, so the wire format was never the
constraint; only the `delay_start_hours` slider's `step=1` was, and
`time.<device>_finish_by` now covers the minute-granular case.

## What is still open

**Whether an unreachable finish time is clamped.** #308 reported that a
delay set to 1 h on a `DA_WM_TP1_21_COMMON` washer/dryer came back as ~9 h
and would not go lower, with other values "off by one or two hours" — which
reads naturally as an appliance refusing to finish sooner than its cycle
takes. The WD80T634DBE/S7 does *not* clamp at write time: asked for
`01:00:00` while `Ready` with a `02:23:00` cycle estimate, it accepted and
held the 1 h. That test stopped short of pressing start, so it rules out a
clamp on the write, not one applied when the cycle begins. #308's own
hardware is the place to settle it.

**Converting delay-until-end into delay-until-start.** Making
`delay_start_hours` mean delay-until-start on laundry would require writing
`requested_delay + cycle_duration`. `remainingTime` while `Ready` looks like
the cycle estimate, but the appliance re-estimates after load sensing (#427
saw 143 min before start and 199 min after), and during `Delaywash`
`remainingTime` is no longer separable into delay and cycle. That conversion
is not safe to guess — and the finish-time entity below does not need it.

**`LaundryPlanner*` in `/course/vs/0`.** Setting Delay End from the
SmartThings app leaves two options behind that a local duration write does
not. Across the two samples in #427:

| requested finish | `LaundryPlannerUserSetTime_` | `LaundryPlannerMicomSetTime_` |
|---|---|---|
| 17:10, Friday | `51710` | `1712` |
| 13:30, Saturday | `61330` | `1332` |

The trailing four digits are the requested finish; the leading digit tracks
the weekday in both samples, and `MicomSetTime` reads as the appliance's own
post-load-sensing answer. Two samples is a hypothesis, not a decode, and
nothing here writes these.

## What changed here

- `_delay_field` now prefers `delayStartTime` and is used for **both** the
  read and the write. The number previously read `delayStartTime` while
  writing `delayEndTime`, so a device reporting both would have displayed a
  value the write never touched — a set that looks like it did nothing.
  Unreachable today (nothing reports both), but the two keys mean different
  things and must not be mixed inside one entity.
- The comments asserting the fields are interchangeable are corrected.
- A `time` entity, `delay_finish_at` ("Finish by"), answers #427's actual
  request: pick a clock time, and it writes the delay that reaches it. It
  exists only where `delayEndTime` does, so dishwashers do not get it.

`delay_start_hours` is unchanged. On laundry it is really "finish in N
hours", but renaming it would change every existing user's `entity_id` for a
wording fix, and the new entity gives that reading a home without the churn.

### The one wart in `delay_finish_at`

Before start, the appliance holds a duration and nothing else, so the clock
time it points at is only fixed once the countdown is running. Set "finish
by 13:30" at 09:30 and the entity reads 13:30; leave the machine idle and ten
minutes later it reads 13:40, one recorder row per minute until start.
That is what the appliance will actually do — it finishes `delayEndTime`
after whenever start is pressed — but it does surprise, and unlike
`finish_time` it churns while the machine is *idle*, which is a case the
existing hysteresis option does not cover. Recovering a stable target would
mean the device storing one, which is what `LaundryPlannerUserSetTime`
appears to be and which nothing here writes.
