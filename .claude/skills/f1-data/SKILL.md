---
name: f1-data
description: FastF1 and OpenF1 data access patterns, lap dataframe semantics, track status codes, and data quirks discovered while building BOXBOX. Use when ingesting, debugging, or extending F1 timing data code.
---

# F1 Data Access (FastF1 + OpenF1)

## FastF1 session loading pattern
```python
import fastf1
fastf1.Cache.enable_cache("data/fastf1_cache")  # dir must exist
session = fastf1.get_session(2025, "Monaco", "R")   # year, event name fragment, "R"=race
session.load(laps=True, telemetry=False, weather=True, messages=True)
laps = session.laps              # fastf1.core.Laps (DataFrame subclass)
total_laps = session.total_laps  # scheduled laps
results = session.results        # classification; .Abbreviation, .Status, .Position
weather = session.weather_data   # AirTemp, TrackTemp, Rainfall (bool), per ~1min
```
- `telemetry=False` keeps loads fast; we never need car telemetry for strategy.
- Event resolution is fuzzy: "Monaco", "Miami", "Australia" all resolve. Use
  `fastf1.get_event_schedule(year)` to list events if a name fails.
- Loads hit the network on first call, then the on-disk cache. Cache dir:
  `data/fastf1_cache/`.

## Lap dataframe columns (the ones we use)
| Column | Meaning | Quirks |
|---|---|---|
| `Driver` | 3-letter abbreviation | |
| `LapNumber` | 1-indexed float | cast to int |
| `LapTime` | timedelta | NaT on first lap / red flag / no time |
| `Compound` | SOFT/MEDIUM/HARD/INTERMEDIATE/WET | sometimes UNKNOWN |
| `TyreLife` | laps on this set incl. current | float; includes pre-race usage for used sets |
| `Stint` | stint counter from 1 | float |
| `Position` | position at end of lap | NaN occasionally — fall back to cumulative-time ranking |
| `PitInTime` | session time entering pit at END of this lap | non-NaT ⇒ this is an in-lap |
| `PitOutTime` | session time leaving pit at START of this lap | non-NaT ⇒ out-lap |
| `TrackStatus` | concatenated status codes during lap, e.g. '2645' | see below |
| `IsAccurate` | FastF1's own clean-lap flag | use as AND with our filters |
| `LapStartTime` / `Time` | session time at lap start / end | basis for gaps |
| `Team` | team name | used for team-mate fallback in fits |

## Track status codes
'1' green · '2' yellow · '4' Safety Car · '5' red flag · '6' VSC deployed · '7' VSC ending.
A lap is an SC lap if '4' in TrackStatus, VSC if '6' or '7' in it. Priority for a
single label: red(5) > SC(4) > VSC(6/7) > yellow(2) > green.

## Gaps between cars
Gap of car X to car ahead at end of lap t = `Time_X(lap t) − Time_ahead(lap t)`
(session-time difference at lap completion). This is the standard interval
approximation; it ignores the ahead-car's movement during the delta. Good to ~0.5s.

## OpenF1 (https://api.openf1.org/v1) endpoint map
No auth for historic data. Filters are query params; comparison ops like `date>=...` work.
- `/sessions?year=2026&session_name=Race` → session_key, meeting_key, circuit
- `/laps?session_key=K&driver_number=N` → lap_number, lap_duration, duration_sector_*,
  is_pit_out_lap, date_start
- `/pit?session_key=K` → pit_duration (pit-lane time, NOT time lost), lap_number, driver_number
- `/stints?session_key=K` → compound, lap_start, lap_end, tyre_age_at_start
- `/intervals?session_key=K` → gap_to_leader, interval (to car ahead), date (~4s cadence; race only)
- `/race_control?session_key=K` → SC/VSC/flag messages with date + category
- `/position?session_key=K` → position changes stream
- `/drivers?session_key=K` → driver_number ↔ name_acronym ↔ team_name
- `/weather?session_key=K` → air_temperature, track_temperature, rainfall

## Quirks discovered tonight (update as found)
- (2026-06-11) fastf1 3.8.3 on Python 3.13 works; suppress its chatty INFO logging via
  `logging.getLogger("fastf1").setLevel(logging.WARNING)`.
- FastF1 `TyreLife` already counts the current lap (out-lap of a new set = 1.0).
- Lap 1 has no `LapStartTime` gap basis; we exclude laps 1-3 from decision points anyway.
- 2026 season: Bahrain + Saudi cancelled. Completed by 2026-06-11: Australia, China,
  Japan, Miami, Canada, Monaco. Barcelona GP is 2026-06-14.
- `session.total_laps` can be fewer than scheduled if the race was shortened — trust it
  over the schedule.
- Several 2026 races (Australia, China, Canada) fail FastF1's lap-accuracy check for
  individual drivers ("all laps marked as inaccurate") — do not gate clean-lap filters
  on `IsAccurate`; use green-flag/no-in-out + MAD outlier filtering instead.
- Miami 2026: `weather_data.Rainfall` has 3 True samples but they are AFTER the race
  ended (session clock 02:39+; race ends ~02:28). `weather.rain=True` for the race is
  technically right but no race lap was wet. Check lap-window overlap, not the session flag.
- When a driver's clean laps on a compound all come from ONE stint, tyre_age and
  lap_number are collinear → 3-param lstsq explodes (predicts ~0s laps). Drop the
  fuel term in that case (handled in `boxbox.sim.degradation._fit`).
- Monaco 2026 race had 89 pit-in records (heavy attrition/stop count) — sanity-check
  stop-derived metrics against this kind of outlier race.
- Windows console (cp1252) cannot print '→' (U+2192): rich console output crashes in
  redirected/legacy terminals. Keep console strings ASCII; files are written UTF-8.
