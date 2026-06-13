"""Pydantic v2 schemas - the single source of truth for every data shape in BOXBOX.

Unit conventions: seconds as float everywhere; laps are 1-indexed ints.
A DecisionPoint at lap t contains information through the END of lap t-1 only,
plus the track status current during lap t (real-time knowledge). The question
it poses is: "do you pit at the end of lap t?"
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"]
TrackStatusLabel = Literal["GREEN", "YELLOW", "SC", "VSC", "RED"]
Action = Literal["PIT", "STAY"]
DRY_COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")
WET_COMPOUNDS: tuple[str, ...] = ("INTERMEDIATE", "WET")


# --------------------------------------------------------------------------- ingestion


class LapRecord(BaseModel):
    """One completed (or attempted) lap by one car, normalized across data sources."""

    driver: str
    team: str = ""
    lap_number: int
    lap_time_s: Optional[float] = None
    start_time_s: Optional[float] = None  # session time at lap start
    end_time_s: Optional[float] = None  # session time at lap end (basis for gaps)
    compound: Compound = "UNKNOWN"
    tyre_age: Optional[int] = None  # laps on this set INCLUDING the current lap
    stint: Optional[int] = None
    position: Optional[int] = None  # position at end of lap
    pit_in: bool = False  # car entered the pit at the END of this lap
    pit_out: bool = False  # car left the pit at the START of this lap
    track_status: TrackStatusLabel = "GREEN"  # worst status during the lap
    is_accurate: bool = True  # source's own clean-lap flag
    rain_affected: bool = False  # rainfall recorded during this lap's time window


class PitStop(BaseModel):
    driver: str
    lap: int  # the in-lap number
    old_compound: Compound = "UNKNOWN"
    new_compound: Compound = "UNKNOWN"
    under_sc: bool = False  # in-lap ran under SC/VSC


class Weather(BaseModel):
    air_temp_c: Optional[float] = None
    track_temp_c: Optional[float] = None
    rain: bool = False


class RaceData(BaseModel):
    """Normalized race container - identical shape from the FastF1 and OpenF1 paths."""

    race_id: str  # e.g. "2026-monaco"
    season: int
    track: str
    total_laps: int
    weather: Weather = Weather()
    laps: list[LapRecord] = Field(default_factory=list)
    pit_stops: list[PitStop] = Field(default_factory=list)
    classified: list[str] = Field(default_factory=list)
    retirements: dict[str, int] = Field(default_factory=dict)  # driver -> last completed lap
    teams: dict[str, str] = Field(default_factory=dict)  # driver -> team name
    source: Literal["fastf1", "openf1"] = "fastf1"


# ----------------------------------------------------------------------- decision points


class RivalInfo(BaseModel):
    driver: str
    gap_s: Optional[float] = None  # positive seconds between the two cars
    compound: Compound = "UNKNOWN"
    tyre_age: Optional[int] = None


class FocalCar(BaseModel):
    driver: str
    position: int
    compound: Compound
    tyre_age: int  # age entering the current lap
    compounds_used: list[Compound] = Field(default_factory=list)
    compounds_available: list[Compound] = Field(default_factory=list)
    last_lap_times_s: list[float] = Field(default_factory=list)  # up to last 3, oldest first
    car_ahead: Optional[RivalInfo] = None
    car_behind: Optional[RivalInfo] = None


class TopNRow(BaseModel):
    position: int
    driver: str
    compound: Compound = "UNKNOWN"
    tyre_age: Optional[int] = None
    gap_to_leader_s: Optional[float] = None


class RaceState(BaseModel):
    """The full prompt payload - everything a strategist knows at the decision lap.

    Every field is derived ONLY from laps <= current_lap - 1, except track_status,
    which is the status current during the lap in progress (real-time knowledge).
    """

    race_id: str
    track: str
    total_laps: int
    current_lap: int
    weather: Weather
    track_status: TrackStatusLabel
    pit_loss_s: float
    focal: FocalCar
    top10: list[TopNRow] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    dp_id: str  # "<race_id>-L<lap:03d>-<driver>-<type>"
    race_id: str
    season: int
    lap: int
    driver: str
    dp_type: Literal["A", "B", "C"]
    question: str
    state: RaceState
    # ---- hindsight fields below: used for scoring, NEVER serialized into prompts ----
    team_action: Action
    team_compound: Optional[Compound] = None
    trigger: str = ""  # human-readable reason this DP was emitted
    # Conditions-only flag (NEVER from score/delta): the decision sits in a wet/
    # changeable phase the dry-only v1 simulator cannot model (no wet->dry crossover).
    # Excluded from the headline metric. See extract.decision_points.is_changeable.
    changeable_conditions: bool = False


# ----------------------------------------------------------------------------- harness


class ModelDecision(BaseModel):
    """The strict JSON answer schema models must produce."""

    action: Action
    compound: Optional[Compound] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = ""


class CallResult(BaseModel):
    """One model call (real or mock) on one decision point."""

    dp_id: str
    model_name: str  # config short name, e.g. "claude-fable-5"
    model_id: str  # resolved OpenRouter id, or "mock"
    prompt_version: str
    temperature: float
    repeat_index: int
    raw_response: str = ""
    decision: Optional[ModelDecision] = None
    invalid: bool = False
    error: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    timestamp_utc: str = ""


# ----------------------------------------------------------------------------- scoring


class StrategyOption(BaseModel):
    """One candidate strategy evaluated by the simulator."""

    stop_lap: Optional[int] = None  # None = no further stop
    compound: Optional[Compound] = None
    total_time_s: float = 0.0
    legal: bool = True


class Score(BaseModel):
    dp_id: str
    race_id: str
    season: int
    dp_type: str
    model_name: str
    repeat_index: int
    invalid: bool
    action: Optional[Action] = None
    compound: Optional[Compound] = None
    sim_model_s: Optional[float] = None
    sim_optimal_s: float  # hindsight oracle (knows future SC/VSC)
    sim_exante_optimal_s: float  # realized time of the ex-ante (no-future-SC) plan
    sim_team_s: float
    delta_exante_s: Optional[float] = None  # PRIMARY: sim(model) - sim(exante optimal)
    delta_hindsight_s: Optional[float] = None  # secondary: sim(model) - sim(optimal), >= 0
    delta_vs_team_s: Optional[float] = None  # sim(model) - sim(team)
    beat_team: Optional[bool] = None  # strictly faster than the real team call
    agree_team_action: Optional[bool] = None  # PIT/STAY matches the team
    agree_team_exact: Optional[bool] = None  # action AND compound match
    team_action: Action
    optimal_action: Action
    optimal_compound: Optional[Compound] = None
    optimal_stop_lap: Optional[int] = None
    exante_action: Action  # the ex-ante oracle's call at lap t
    exante_compound: Optional[Compound] = None
    exante_stop_lap: Optional[int] = None
    changeable_conditions: bool = False  # carried from the DP; excluded from headline
