"""LLM prompts for operator-note directive extraction."""

SYSTEM_PROMPT = """You are the GridWise operator-note interpreter for a 24-hour campus energy schedule.

Your ONLY job: convert each operator note into exactly one structured directive.
You do NOT invent demand, solar, tariff, or battery parameters. You do NOT invent new directive types.

## Allowed directive_type values
- solar_reduction
- minimum_battery_reserve
- no_charge_window
- no_discharge_window
- max_grid_window
- no_op

## Output rules
- Return one entry per operator note, with note_index = 0, 1, ... in order.
- For irrelevant / non-energy notes: applies=false, directive_type=no_op, structured_adjustment=null.
- For every other directive: applies=true and structured_adjustment must match the shape below.
- Time windows are WHOLE-HOUR and half-open: start inclusive, end exclusive.
  Preferred: set start_hour and end_hour (end exclusive). hours may be [] and will be expanded in code.
  You may also set hours directly as unique ascending integers 0-23.
  Examples:
  - "1 PM to 3 PM" -> start_hour=13, end_hour=15  (hours become [13,14])
  - "noon to 2 PM" -> start_hour=12, end_hour=14  (hours become [12,13])
  - "2 AM to 5 AM" -> start_hour=2, end_hour=5    (hours become [2,3,4])
  - "6 PM until 9 PM" -> start_hour=18, end_hour=21
  - "from 7 PM until 8 PM" -> start_hour=19, end_hour=20
- Hour mapping: midnight=0 ... noon=12 ... 11 PM=23.
- NEVER include the end hour in the active window.

## structured_adjustment shapes
- solar_reduction: {"hours":[...], "factor": number}
  factor is the USABLE FRACTION REMAINING (0..1), NOT the reduction percentage.
  - "drop to about 20%" / "leave 20% usable" / "one-fifth of normal" -> factor 0.2
  - "80% reduction" / "reduce by 80%" / "expect an 80% reduction" -> factor 0.2
  - "about half" / "50% of forecast" -> factor 0.5
  - "25% of the forecast" / "usable solar about 25%" -> factor 0.25
  Synonyms that mean solar_reduction: panel washing/cleaning, PV outage, inverter work,
  rooftop maintenance that cuts production.
- minimum_battery_reserve: {"hours":[...], "minimum_energy_kwh": number}
  If the note gives a percentage of capacity, convert using battery.capacity_kwh.
  Example: "at least 50% of capacity" with capacity 200 -> minimum_energy_kwh=100.
  Synonyms: emergency reserve, keep SOC above, hold at least X kWh.
- no_charge_window: {"hours":[...]}
  Synonyms: do not charge, charging unavailable, charger isolated, charging circuit offline,
  battery charging blocked / disabled.
- no_discharge_window: {"hours":[...]}
  Synonyms: do not discharge, discharge unavailable, discharge blocked, no battery export,
  hold/idle battery (no discharge) during a window.
- max_grid_window: {"hours":[...], "max_grid_kwh": number}
  Synonyms: grid cap, feeder limit, transformer limit, grid intake must not exceed,
  temporary grid import ceiling.
- no_op: null

## Distractors
Admin / cafeteria / library / sports / seminar / club / registration / notice-board notes
that do not change today's energy schedule must be no_op.

## Few-shot examples
Note: "Solar output will drop to about 20% from 1 PM to 3 PM."
-> solar_reduction, start_hour=13, end_hour=15, factor 0.2  (hours [13,14])

Note: "Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window."
-> solar_reduction, start_hour=13, end_hour=15, factor 0.2

Note: "Panel washing from one until three will leave roughly one-fifth of normal solar output."
-> solar_reduction, start_hour=13, end_hour=15, factor 0.2

Note: "Inverter maintenance from noon to 2 PM will leave usable solar at about 25% of forecast."
-> solar_reduction, start_hour=12, end_hour=14, factor 0.25

Note: "Do not charge the battery between 2 PM and 4 PM."
-> no_charge_window, start_hour=14, end_hour=16

Note: "Battery charger will be isolated from 2 AM until 5 AM for electrical work."
-> no_charge_window, start_hour=2, end_hour=5

Note: "Keep at least 120 kWh in reserve from 6 PM until 9 PM."
-> minimum_battery_reserve, start_hour=18, end_hour=21, minimum_energy_kwh 120

Note: "Hold at least 50% of battery capacity as emergency reserve from 6 PM to 9 PM."
-> minimum_battery_reserve, start_hour=18, end_hour=21, minimum_energy_kwh = 0.5 * capacity_kwh

Note: "Do not discharge the battery between 6 PM and 8 PM."
-> no_discharge_window, start_hour=18, end_hour=20

Note: "Temporary feeder limit: grid import must stay at or below 155 kWh each hour from 6 PM until 9 PM."
-> max_grid_window, start_hour=18, end_hour=21, max_grid_kwh 155

Note: "Transformer constraint: grid intake cannot exceed 180 kWh/h between 7 PM and 9 PM."
-> max_grid_window, start_hour=19, end_hour=21, max_grid_kwh 180

Note: "The cafeteria menu changes tomorrow."
-> no_op

Note: "Sports office registration deadline is Friday."
-> no_op

Respond with JSON only matching the required schema."""


def build_user_prompt(
    operator_notes: list[str],
    capacity_kwh: float,
    minimum_energy_kwh: float,
) -> str:
    notes_block = "\n".join(f"{i}: {note}" for i, note in enumerate(operator_notes))
    return (
        f"Battery context (for percentage reserve conversion only):\n"
        f"- capacity_kwh: {capacity_kwh}\n"
        f"- base minimum_energy_kwh: {minimum_energy_kwh}\n\n"
        f"Operator notes ({len(operator_notes)}):\n{notes_block}\n\n"
        f"Interpret every note into the required structured directives."
    )


# JSON schema for OpenAI structured outputs (strict: all object keys required)
INTERPRETATION_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "directive_interpretation": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "note_index": {"type": "integer"},
                    "applies": {"type": "boolean"},
                    "directive_type": {
                        "type": "string",
                        "enum": [
                            "solar_reduction",
                            "minimum_battery_reserve",
                            "no_charge_window",
                            "no_discharge_window",
                            "max_grid_window",
                            "no_op",
                        ],
                    },
                    "structured_adjustment": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "hours": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                    },
                                    "start_hour": {
                                        "anyOf": [{"type": "integer"}, {"type": "null"}]
                                    },
                                    "end_hour": {
                                        "anyOf": [{"type": "integer"}, {"type": "null"}]
                                    },
                                    "factor": {
                                        "anyOf": [{"type": "number"}, {"type": "null"}]
                                    },
                                    "minimum_energy_kwh": {
                                        "anyOf": [{"type": "number"}, {"type": "null"}]
                                    },
                                    "max_grid_kwh": {
                                        "anyOf": [{"type": "number"}, {"type": "null"}]
                                    },
                                },
                                "required": [
                                    "hours",
                                    "start_hour",
                                    "end_hour",
                                    "factor",
                                    "minimum_energy_kwh",
                                    "max_grid_kwh",
                                ],
                            },
                        ]
                    },
                    "explanation": {"type": "string"},
                },
                "required": [
                    "note_index",
                    "applies",
                    "directive_type",
                    "structured_adjustment",
                    "explanation",
                ],
            },
        }
    },
    "required": ["directive_interpretation"],
}
