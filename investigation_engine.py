import json
import os
import sys

from google import genai
from google.genai import types
from google.cloud import bigquery
from google.cloud import secretmanager


# ============================================================
# CONFIGURATION
# ============================================================

SECRET_ID = "watertwin-gemini-api-key"

MODEL_NAME = "gemini-3.6-flash"

DATASET = "water_twin"
EVIDENCE_TABLE = "water_evidence_features"


# ============================================================
# WATER TWIN SYSTEM INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTIONS = """You are the WaterTwin AI Evidence Investigation Engine.

ROLE
Investigate abnormal water-usage events using ONLY the supplied evidence.
Your stage is INVESTIGATE within:
DETECT → INVESTIGATE → EXPLAIN → SIMULATE → PRIORITIZE → ACT

OBJECTIVES
- Compare relevant competing hypotheses.
- Synthesize observed, calculated and contextual evidence.
- Identify supporting and meaningful conflicting evidence.
- Select the best-supported hypothesis only when justified.
- Identify uncertainty and relevant missing information.
- Choose NO_ACTION, EXPLAIN, RECOMMEND or ABSTAIN.

EVIDENCE RULES
- Use only evidence supplied in the request.
- Never use hidden ground truth, scenario labels or expected answers.
- Never invent or modify measurements, counts, percentages, costs, savings,
  sensor readings or other facts.
- Deterministic SQL/code is the source of truth for calculations.
- Distinguish observed data, calculated metrics, contextual signals,
  hypotheses, assumptions and missing information.
- Do not infer causality merely because two signals occur together.
- Do not infer a specific physical failure mechanism unless supported.

LANGUAGE CALIBRATION
Use calibrated evidence language such as:
supports, is consistent with, provides evidence for, makes more likely,
weakens, strongly weakens, is less consistent with.

Avoid absolute causal language such as:
proves, confirms, rules out, definitively establishes, guarantees,
demonstrates beyond doubt, or equivalent wording.

Even when evidence is strong, describe what the evidence supports rather
than claiming certainty about physical causation.

HYPOTHESIS ENUM
Use only the exact primary_hypothesis enum values supplied by the response
schema.

If the evidence indicates a physical leak or continuous-flow loss, use:
LEAK

Do not create alternative labels or synonyms such as:
PHYSICAL_LEAKAGE, SYSTEM_LEAK, LEAK_DETECTED, LEAKAGE,
SENSOR_ISSUE, PRESSURE_ISSUE, OCCUPANCY_INCREASE or WEATHER_EFFECT.

CONFLICT CHECK
Before EXPLAIN or RECOMMEND, consider:
1. Is another independent signal materially abnormal?
2. Does it materially conflict with the leading hypothesis?
3. Is the relationship demonstrated or only assumed?
4. Could multiple hypotheses reasonably explain the observations?
5. Would additional information materially change the decision?

Do not treat every secondary threshold crossing as a material conflict.
A contextual or hydraulic signal may coexist with another explanation.

ABSTENTION
ABSTAIN when evidence is insufficient, materially conflicting, unreliable,
competing hypotheses remain unresolved, a material independent anomaly
remains unexplained, causal relationships are uncertain, or additional
information is needed before action.

When abstaining:
- primary_hypothesis should normally be AMBIGUOUS or the relevant
  uncertainty hypothesis.
- confidence_level should normally be LOW.
- missing_information must identify relevant information that would
  materially resolve the uncertainty.

DECISION GUIDANCE
NO_ACTION: normal behavior with no meaningful abnormal evidence.
EXPLAIN: abnormal consumption has a credible contextual explanation and
no stronger unresolved infrastructure or data-quality issue exists.
RECOMMEND: sufficient coherent evidence supports an actionable issue.
ABSTAIN: the evidence does not justify a reliable explanation or action.

CONFIDENCE
HIGH requires strong, persistent and consistent evidence with little
material conflict.
MEDIUM means a leading hypothesis is supported but meaningful uncertainty
remains.
LOW means evidence is weak, incomplete, conflicting or unreliable.
Do not assign HIGH merely because one hypothesis is plausible.

OUTPUT
Return only the JSON object defined by the response schema.
Do not include markdown or text outside the JSON.
"""


# ============================================================
# GEMINI RESPONSE SCHEMA
# ============================================================

INVESTIGATION_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "scenario_id": types.Schema(
            type="STRING"
        ),

        "decision": types.Schema(
            type="STRING",
            enum=[
                "NO_ACTION",
                "EXPLAIN",
                "RECOMMEND",
                "ABSTAIN",
            ],
        ),

        "primary_hypothesis": types.Schema(
            type="STRING",
            enum=[
                "NORMAL",
                "LEAK",
                "PRESSURE_ANOMALY",
                "OCCUPANCY_DRIVEN",
                "WEATHER_DRIVEN",
                "SENSOR_ANOMALY",
                "AMBIGUOUS",
            ],
        ),

        "explanation": types.Schema(
            type="STRING"
        ),

        "supporting_evidence": types.Schema(
            type="ARRAY",
            items=types.Schema(
                type="STRING"
            ),
        ),

        "conflicting_evidence": types.Schema(
            type="ARRAY",
            items=types.Schema(
                type="STRING"
            ),
        ),

        "missing_information": types.Schema(
            type="ARRAY",
            items=types.Schema(
                type="STRING"
            ),
        ),

        "confidence_level": types.Schema(
            type="STRING",
            enum=[
                "HIGH",
                "MEDIUM",
                "LOW",
            ],
        ),
    },

    required=[
        "scenario_id",
        "decision",
        "primary_hypothesis",
        "explanation",
        "supporting_evidence",
        "conflicting_evidence",
        "missing_information",
        "confidence_level",
    ],
)


# ============================================================
# GOOGLE CLOUD HELPERS
# ============================================================

def get_project_id():
    """
    Determine the active Google Cloud project using the runtime
    Google credentials.

    No project credential or API key is stored in source code.
    """

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if project_id:
        return project_id

    try:
        import google.auth

        _, project_id = google.auth.default()

        if project_id:
            return project_id

    except Exception as exc:
        raise RuntimeError(
            "Unable to determine Google Cloud project."
        ) from exc

    raise RuntimeError(
        "Google Cloud project could not be determined."
    )


def get_gemini_api_key(project_id):
    """
    Retrieve the Gemini API key from Google Cloud Secret Manager.

    The API key is never hard-coded in this application.
    """

    client = secretmanager.SecretManagerServiceClient()

    secret_name = (
        f"projects/{project_id}/secrets/"
        f"{SECRET_ID}/versions/latest"
    )

    response = client.access_secret_version(
        request={"name": secret_name}
    )

    api_key = response.payload.data.decode(
        "UTF-8"
    ).strip()

    if not api_key:
        raise RuntimeError(
            "Gemini API key secret exists but contains no value."
        )

    return api_key


# ============================================================
# BIGQUERY EVIDENCE RETRIEVAL
# ============================================================

def get_evidence(project_id, scenario_id):
    """
    Retrieve deterministic WaterTwin evidence from BigQuery.

    All evidence calculations are performed in BigQuery.
    Gemini receives the resulting evidence only.
    """

    client = bigquery.Client(
        project=project_id
    )

    query = f"""
    WITH scenario_data AS (
      SELECT *
      FROM `{project_id}.{DATASET}.{EVIDENCE_TABLE}`
      WHERE scenario_id = @scenario_id
    ),

    summary AS (
      SELECT
        scenario_id,

        COUNT(*) AS observation_count,

        MIN(timestamp) AS event_start,
        MAX(timestamp) AS event_end,

        ROUND(
          AVG(actual_consumption_litres),
          2
        ) AS avg_actual_consumption_litres,

        ROUND(
          AVG(consumption_deviation_pct),
          2
        ) AS avg_consumption_deviation_pct,

        ROUND(
          MAX(consumption_deviation_pct),
          2
        ) AS max_consumption_deviation_pct,

        COUNTIF(consumption_anomaly)
          AS significant_consumption_observations,

        ROUND(
          SAFE_DIVIDE(
            COUNTIF(consumption_anomaly),
            COUNT(*)
          ) * 100,
          2
        ) AS consumption_anomaly_rate_pct,

        ROUND(
          AVG(occupancy_deviation_pct),
          2
        ) AS avg_occupancy_deviation_pct,

        ROUND(
          MAX(occupancy_deviation_pct),
          2
        ) AS max_occupancy_deviation_pct,

        COUNTIF(significant_occupancy_increase)
          AS significant_occupancy_observations,

        ROUND(
          AVG(temperature_delta_c),
          2
        ) AS avg_temperature_delta_c,

        ROUND(
          MAX(temperature_delta_c),
          2
        ) AS max_temperature_delta_c,

        COUNTIF(significant_temperature_increase)
          AS significant_temperature_observations,

        ROUND(
          AVG(flow_deviation_pct),
          2
        ) AS avg_flow_deviation_pct,

        ROUND(
          MAX(flow_deviation_pct),
          2
        ) AS max_flow_deviation_pct,

        COUNTIF(significant_flow_increase)
          AS significant_flow_observations,

        ROUND(
          AVG(pressure_delta_psi),
          2
        ) AS avg_pressure_delta_psi,

        ROUND(
          MIN(pressure_delta_psi),
          2
        ) AS min_pressure_delta_psi,

        COUNTIF(significant_pressure_drop)
          AS significant_pressure_observations,

        COUNTIF(data_quality_issue)
          AS data_quality_issue_count,

        COUNTIF(reading_quality = 'POOR')
          AS poor_quality_readings,

        COUNTIF(meter_status != 'OK')
          AS non_ok_meter_readings

      FROM scenario_data
      GROUP BY scenario_id
    ),

    night_metrics AS (
      SELECT
        scenario_id,

        COUNTIF(
          is_night
          AND significant_flow_increase
        ) AS night_flow_anomaly_hours,

        ROUND(
          AVG(
            IF(
              is_night,
              flow_deviation_pct,
              NULL
            )
          ),
          2
        ) AS avg_night_flow_deviation_pct,

        ROUND(
          MAX(
            IF(
              is_night,
              flow_deviation_pct,
              NULL
            )
          ),
          2
        ) AS max_night_flow_deviation_pct

      FROM scenario_data
      GROUP BY scenario_id
    )

    SELECT
      s.*,
      n.night_flow_anomaly_hours,
      n.avg_night_flow_deviation_pct,
      n.max_night_flow_deviation_pct

    FROM summary s

    JOIN night_metrics n
      USING (scenario_id)
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "scenario_id",
                "STRING",
                scenario_id
            )
        ]
    )

    rows = list(
        client.query(
            query,
            job_config=job_config
        ).result()
    )

    if not rows:
        raise ValueError(
            f"No BigQuery evidence found for scenario "
            f"{scenario_id}."
        )

    row = rows[0]

    return dict(row)


# ============================================================
# GEMINI INVESTIGATION
# ============================================================

def investigate_with_gemini(
    api_key,
    evidence
):
    """
    Send deterministic evidence to Gemini for investigation,
    hypothesis comparison and evidence synthesis.

    Gemini performs qualitative reasoning.
    BigQuery remains the source of truth for numerical evidence.
    """

    client = genai.Client(
        api_key=api_key
    )

    evidence_text = json.dumps(
        evidence,
        indent=2,
        default=str
    )

    prompt = f"""
Investigate this WaterTwin event.

Use ONLY the supplied evidence.

Do not use hidden ground truth.

Do not invent measurements.

Compare relevant competing hypotheses before deciding.

Use the exact enum values defined by the response schema.

Explicitly consider whether contextual signals such as occupancy or
temperature actually explain the observed consumption and flow behavior.

Also inspect pressure behavior independently.

Do not automatically treat every secondary anomaly as a decisive conflict.

However, if a material independent infrastructure anomaly remains
unresolved and causality is not established, ABSTAIN.

Use calibrated evidence language. Avoid absolute causal wording such as
"confirms" or "proves" when the evidence only supports a hypothesis.

Return only the schema-defined JSON object.

SUPPLIED EVIDENCE:

{evidence_text}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "system_instruction": SYSTEM_INSTRUCTIONS,
            "response_mime_type": "application/json",
            "response_schema": INVESTIGATION_RESPONSE_SCHEMA,
        },
    )

    text = response.text.strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini returned invalid JSON."
        ) from exc

    return result


# ============================================================
# DETERMINISTIC WATER TWIN DECISION GUARD
# ============================================================

def evidence_item_mentions(item, keyword):
    """
    Safely inspect an evidence item regardless of whether Gemini
    returns a structured dictionary or a plain string.
    """

    keyword = keyword.lower()

    if isinstance(item, dict):
        searchable_text = " ".join(
            str(value)
            for value in item.values()
        ).lower()
    else:
        searchable_text = str(item).lower()

    return keyword in searchable_text


def apply_deterministic_guard(
    result,
    evidence
):
    """
    Deterministic safety/policy layer.

    Gemini performs the investigation and hypothesis comparison.

    This guard protects WaterTwin from two important failure modes:

    1. Recommending physical intervention when data quality is poor.
    2. Explaining an event through context when a material,
       independently unresolved infrastructure anomaly is present.

    No scenario_id-specific logic is used.
    No hidden ground truth is used.
    """

    decision = result.get(
        "decision"
    )

    primary_hypothesis = result.get(
        "primary_hypothesis"
    )

    observation_count = int(
        evidence.get(
            "observation_count"
        ) or 0
    )

    pressure_anomaly_hours = int(
        evidence.get(
            "significant_pressure_observations"
        ) or 0
    )

    min_pressure_delta = float(
        evidence.get(
            "min_pressure_delta_psi"
        ) or 0
    )

    flow_anomaly_hours = int(
        evidence.get(
            "significant_flow_observations"
        ) or 0
    )

    night_flow_anomaly_hours = int(
        evidence.get(
            "night_flow_anomaly_hours"
        ) or 0
    )

    occupancy_anomaly_hours = int(
        evidence.get(
            "significant_occupancy_observations"
        ) or 0
    )

    temperature_anomaly_hours = int(
        evidence.get(
            "significant_temperature_observations"
        ) or 0
    )

    data_quality_issue_count = int(
        evidence.get(
            "data_quality_issue_count"
        ) or 0
    )

    poor_quality_readings = int(
        evidence.get(
            "poor_quality_readings"
        ) or 0
    )

    non_ok_meter_readings = int(
        evidence.get(
            "non_ok_meter_readings"
        ) or 0
    )

    # ========================================================
    # GUARD 1: DATA QUALITY
    # ========================================================

    data_quality_compromised = (
        data_quality_issue_count > 0
        or poor_quality_readings > 0
        or non_ok_meter_readings > 0
    )

    if data_quality_compromised:

        if decision == "RECOMMEND":

            result["decision"] = (
                "ABSTAIN"
            )

            result["primary_hypothesis"] = (
                "SENSOR_ANOMALY"
            )

            result["confidence_level"] = (
                "LOW"
            )

            missing_information = list(
                result.get(
                    "missing_information"
                ) or []
            )

            if not missing_information:
                missing_information.append(
                    "Meter diagnostic and calibration "
                    "information to verify measurement "
                    "reliability"
                )

            result[
                "missing_information"
            ] = missing_information

            result["explanation"] = (
                result.get(
                    "explanation",
                    ""
                )
                + " WaterTwin applied a deterministic "
                "data-quality guard because affected "
                "measurements cannot support a reliable "
                "physical intervention."
            )

        return result

    # ========================================================
    # GUARD 2: MATERIAL PRESSURE CONFLICT
    # ========================================================

    material_pressure_anomaly = (
        observation_count > 0
        and pressure_anomaly_hours >= max(
            24,
            int(
                observation_count * 0.10
            )
        )
        and min_pressure_delta <= -5.0
    )

    contextual_explanation_present = (
        occupancy_anomaly_hours > 0
        or temperature_anomaly_hours > 0
    )

    no_flow_anomaly = (
        flow_anomaly_hours == 0
    )

    no_night_flow_anomaly = (
        night_flow_anomaly_hours == 0
    )

    conflicting_evidence = (
        result.get(
            "conflicting_evidence"
        ) or []
    )

    gemini_pressure_conflict = any(
        evidence_item_mentions(
            item,
            "pressure"
        )
        for item in conflicting_evidence
    )

    unresolved_pressure_conflict = (
        material_pressure_anomaly
        and contextual_explanation_present
        and no_flow_anomaly
        and no_night_flow_anomaly
        and decision == "EXPLAIN"
        and primary_hypothesis in {
            "OCCUPANCY_DRIVEN",
            "WEATHER_DRIVEN",
        }
        and gemini_pressure_conflict
    )

    if unresolved_pressure_conflict:

        result["decision"] = (
            "ABSTAIN"
        )

        result["primary_hypothesis"] = (
            "AMBIGUOUS"
        )

        result["confidence_level"] = (
            "LOW"
        )

        conflicting = list(
            result.get(
                "conflicting_evidence"
            ) or []
        )

        pressure_conflict = {
            "signal": (
                "Persistent pressure anomaly"
            ),
            "value": (
                f"{pressure_anomaly_hours} significant "
                f"pressure observations, minimum "
                f"pressure delta "
                f"{min_pressure_delta} psi"
            ),
            "interpretation": (
                "A material pressure anomaly remains "
                "unresolved. The supplied evidence does "
                "not establish that the contextual demand "
                "increase caused the pressure degradation."
            ),
        }

        if not any(
            evidence_item_mentions(
                item,
                "pressure"
            )
            for item in conflicting
        ):
            conflicting.append(
                pressure_conflict
            )

        result[
            "conflicting_evidence"
        ] = conflicting

        missing = list(
            result.get(
                "missing_information"
            ) or []
        )

        if not missing:
            missing.append(
                "Upstream supply pressure logs and "
                "pump or PRV operational data to "
                "determine the source of the pressure "
                "degradation"
            )

        result[
            "missing_information"
        ] = missing

        result["explanation"] = (
            "The supplied evidence supports a contextual "
            "demand hypothesis, but a separate material "
            "pressure anomaly remains unresolved. The "
            "evidence does not establish that occupancy "
            "or weather caused the pressure degradation. "
            "WaterTwin therefore abstains pending "
            "additional hydraulic evidence."
        )

    return result


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_result(
    result,
    scenario_id
):
    """
    Validate the required WaterTwin JSON contract.
    """

    required_fields = [
        "scenario_id",
        "decision",
        "primary_hypothesis",
        "explanation",
        "supporting_evidence",
        "conflicting_evidence",
        "missing_information",
        "confidence_level",
    ]

    for field in required_fields:

        if field not in result:
            raise RuntimeError(
                f"Gemini result is missing required field: "
                f"{field}"
            )

    allowed_decisions = {
        "NO_ACTION",
        "EXPLAIN",
        "RECOMMEND",
        "ABSTAIN",
    }

    allowed_hypotheses = {
        "NORMAL",
        "LEAK",
        "PRESSURE_ANOMALY",
        "OCCUPANCY_DRIVEN",
        "WEATHER_DRIVEN",
        "SENSOR_ANOMALY",
        "AMBIGUOUS",
    }

    allowed_confidence = {
        "HIGH",
        "MEDIUM",
        "LOW",
    }

    if result[
        "scenario_id"
    ] != scenario_id:

        result[
            "scenario_id"
        ] = scenario_id

    if result[
        "decision"
    ] not in allowed_decisions:

        raise RuntimeError(
            f"Invalid decision returned: "
            f"{result['decision']}"
        )

    if result[
        "primary_hypothesis"
    ] not in allowed_hypotheses:

        raise RuntimeError(
            "Invalid primary_hypothesis returned: "
            f"{result['primary_hypothesis']}"
        )

    if result[
        "confidence_level"
    ] not in allowed_confidence:

        raise RuntimeError(
            "Invalid confidence_level returned: "
            f"{result['confidence_level']}"
        )

    if not isinstance(
        result[
            "supporting_evidence"
        ],
        list
    ):
        raise RuntimeError(
            "supporting_evidence must be a list."
        )

    if not isinstance(
        result[
            "conflicting_evidence"
        ],
        list
    ):
        raise RuntimeError(
            "conflicting_evidence must be a list."
        )

    if not isinstance(
        result[
            "missing_information"
        ],
        list
    ):
        raise RuntimeError(
            "missing_information must be a list."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    scenario_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "S2"
    )

    print(
        f"Investigating WaterTwin scenario: "
        f"{scenario_id}"
    )

    print(
        "Determining Google Cloud project..."
    )

    project_id = get_project_id()

    print(
        f"Using Google Cloud project: "
        f"{project_id}"
    )

    print(
        "Retrieving Gemini API key from "
        "Secret Manager..."
    )

    api_key = get_gemini_api_key(
        project_id
    )

    print(
        "Secret Manager access successful."
    )

    print(
        "Retrieving evidence from BigQuery..."
    )

    evidence = get_evidence(
        project_id,
        scenario_id
    )

    print(
        "BigQuery evidence retrieved successfully."
    )

    print(
        "Sending evidence to Gemini..."
    )

    result = investigate_with_gemini(
        api_key,
        evidence
    )

    validate_result(
        result,
        scenario_id
    )

    print(
        "\nGemini Investigation Result:"
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )

    print(
        "\nApplying deterministic WaterTwin "
        "decision guard..."
    )

    final_result = (
        apply_deterministic_guard(
            result,
            evidence
        )
    )

    validate_result(
        final_result,
        scenario_id
    )

    print(
        "\nFinal WaterTwin Decision:"
    )

    print(
        json.dumps(
            final_result,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
