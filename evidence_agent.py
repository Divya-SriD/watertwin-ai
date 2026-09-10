import json
import os
import sys

from google.cloud import bigquery


# ============================================================
# CONFIGURATION
# ============================================================

DATASET = "water_twin"
EVIDENCE_TABLE = "water_evidence_features"


# ============================================================
# GOOGLE CLOUD PROJECT
# ============================================================

def get_project_id():
    """
    Determine the active Google Cloud project.

    No API keys are stored in this file.
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


# ============================================================
# BIGQUERY EVIDENCE RETRIEVAL
# ============================================================

def get_evidence(project_id, scenario_id):
    """
    Retrieve deterministic evidence from BigQuery.

    Gemini is NOT used here.

    This layer only retrieves and calculates evidence.
    """

    client = bigquery.Client(project=project_id)

    query = f"""
    SELECT
      scenario_id,

      COUNT(*) AS observation_count,

      -- ======================================================
      -- CONSUMPTION
      -- ======================================================

      ROUND(
        AVG(actual_consumption_litres),
        2
      ) AS avg_actual_consumption_litres,

      ROUND(
        AVG(expected_consumption_litres),
        2
      ) AS avg_expected_consumption_litres,

      ROUND(
        AVG(consumption_deviation_pct),
        2
      ) AS avg_consumption_deviation_pct,

      ROUND(
        MAX(consumption_deviation_pct),
        2
      ) AS max_consumption_deviation_pct,

      ROUND(
        MIN(consumption_deviation_pct),
        2
      ) AS min_consumption_deviation_pct,

      COUNTIF(consumption_anomaly)
        AS significant_consumption_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(consumption_anomaly),
          COUNT(*)
        ) * 100,
        2
      ) AS consumption_anomaly_rate_pct,

      -- ======================================================
      -- OCCUPANCY
      -- ======================================================

      ROUND(
        AVG(occupancy_deviation_pct),
        2
      ) AS avg_occupancy_deviation_pct,

      ROUND(
        MAX(occupancy_deviation_pct),
        2
      ) AS max_occupancy_deviation_pct,

      ROUND(
        MIN(occupancy_deviation_pct),
        2
      ) AS min_occupancy_deviation_pct,

      COUNTIF(significant_occupancy_increase)
        AS significant_occupancy_observations,

      -- ======================================================
      -- WEATHER
      -- ======================================================

      ROUND(
        AVG(temperature_delta_c),
        2
      ) AS avg_temperature_delta_c,

      ROUND(
        MAX(temperature_delta_c),
        2
      ) AS max_temperature_delta_c,

      ROUND(
        MIN(temperature_delta_c),
        2
      ) AS min_temperature_delta_c,

      COUNTIF(significant_temperature_increase)
        AS significant_temperature_observations,

      ROUND(
        AVG(rainfall_mm),
        2
      ) AS avg_rainfall_mm,

      ROUND(
        MAX(rainfall_mm),
        2
      ) AS max_rainfall_mm,

      -- ======================================================
      -- FLOW
      -- ======================================================

      ROUND(
        AVG(flow_deviation_pct),
        2
      ) AS avg_flow_deviation_pct,

      ROUND(
        MAX(flow_deviation_pct),
        2
      ) AS max_flow_deviation_pct,

      ROUND(
        MIN(flow_deviation_pct),
        2
      ) AS min_flow_deviation_pct,

      COUNTIF(significant_flow_increase)
        AS significant_flow_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_flow_increase),
          COUNT(*)
        ) * 100,
        2
      ) AS flow_anomaly_rate_pct,

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
      ) AS max_night_flow_deviation_pct,

      -- ======================================================
      -- PRESSURE
      -- ======================================================

      ROUND(
        AVG(pressure_delta_psi),
        2
      ) AS avg_pressure_delta_psi,

      ROUND(
        MAX(pressure_delta_psi),
        2
      ) AS max_pressure_delta_psi,

      ROUND(
        MIN(pressure_delta_psi),
        2
      ) AS min_pressure_delta_psi,

      COUNTIF(significant_pressure_drop)
        AS significant_pressure_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_pressure_drop),
          COUNT(*)
        ) * 100,
        2
      ) AS pressure_anomaly_rate_pct,

      -- ======================================================
      -- DATA QUALITY
      -- ======================================================

      COUNTIF(data_quality_issue = TRUE)
        AS data_quality_issue_count,

      COUNTIF(reading_quality = 'POOR')
        AS poor_quality_readings,

      COUNTIF(meter_status != 'OK')
        AS non_ok_meter_readings,

      COUNTIF(reading_quality = 'GOOD')
        AS good_quality_readings,

      COUNTIF(meter_status = 'OK')
        AS ok_meter_readings

    FROM
      `{project_id}.{DATASET}.{EVIDENCE_TABLE}`

    WHERE
      scenario_id = @scenario_id

    GROUP BY
      scenario_id
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
            f"No evidence found for scenario {scenario_id}."
        )

    return dict(rows[0])


# ============================================================
# EVIDENCE CLASSIFICATION
# ============================================================

def classify_evidence(evidence):
    """
    Deterministically classify evidence.

    No Gemini call is made here.

    Categories:
      observed
      calculated
      contextual
      supporting
      conflicting
      missing
    """

    observed = []
    calculated = []
    contextual = []
    supporting = []
    conflicting = []
    missing = []

    # ========================================================
    # OBSERVED
    # ========================================================

    observed.append({
        "signal": "actual_consumption",
        "value": evidence["avg_actual_consumption_litres"],
        "source": "BigQuery"
    })

    observed.append({
        "signal": "flow_deviation",
        "value": evidence["avg_flow_deviation_pct"],
        "source": "BigQuery"
    })

    observed.append({
        "signal": "pressure_delta",
        "value": evidence["avg_pressure_delta_psi"],
        "source": "BigQuery"
    })

    observed.append({
        "signal": "occupancy_deviation",
        "value": evidence["avg_occupancy_deviation_pct"],
        "source": "BigQuery"
    })

    observed.append({
        "signal": "temperature_delta",
        "value": evidence["avg_temperature_delta_c"],
        "source": "BigQuery"
    })

    # ========================================================
    # CALCULATED
    # ========================================================

    calculated.append({
        "metric": "consumption_anomaly_rate_pct",
        "value": evidence["consumption_anomaly_rate_pct"]
    })

    calculated.append({
        "metric": "flow_anomaly_rate_pct",
        "value": evidence["flow_anomaly_rate_pct"]
    })

    calculated.append({
        "metric": "pressure_anomaly_rate_pct",
        "value": evidence["pressure_anomaly_rate_pct"]
    })

    calculated.append({
        "metric": "significant_consumption_observations",
        "value": evidence[
            "significant_consumption_observations"
        ]
    })

    calculated.append({
        "metric": "significant_flow_observations",
        "value": evidence[
            "significant_flow_observations"
        ]
    })

    calculated.append({
        "metric": "significant_pressure_observations",
        "value": evidence[
            "significant_pressure_observations"
        ]
    })

    calculated.append({
        "metric": "night_flow_anomaly_hours",
        "value": evidence[
            "night_flow_anomaly_hours"
        ]
    })

    # ========================================================
    # CONTEXTUAL
    # ========================================================

    contextual.append({
        "signal": "occupancy",
        "max_deviation_pct": evidence[
            "max_occupancy_deviation_pct"
        ],
        "significant_observations": evidence[
            "significant_occupancy_observations"
        ]
    })

    contextual.append({
        "signal": "temperature",
        "max_delta_c": evidence[
            "max_temperature_delta_c"
        ],
        "significant_observations": evidence[
            "significant_temperature_observations"
        ]
    })

    # ========================================================
    # SUPPORTING EVIDENCE
    # ========================================================

    if evidence[
        "significant_consumption_observations"
    ] > 0:

        supporting.append({
            "signal": "consumption_anomaly",
            "value": (
                f"{evidence['significant_consumption_observations']} "
                "observations"
            ),
            "reason": (
                "Consumption differs materially from the "
                "expected baseline."
            )
        })

    if evidence[
        "night_flow_anomaly_hours"
    ] > 0:

        supporting.append({
            "signal": "night_time_flow",
            "value": (
                f"{evidence['night_flow_anomaly_hours']} hours"
            ),
            "reason": (
                "Abnormal flow during low-demand hours can "
                "indicate continuous background flow."
            )
        })

    if evidence[
        "significant_occupancy_observations"
    ] > 0:

        supporting.append({
            "signal": "occupancy_increase",
            "value": (
                f"{evidence['significant_occupancy_observations']} "
                "observations"
            ),
            "reason": (
                "Higher occupancy can explain increased "
                "water demand."
            )
        })

    if evidence[
        "significant_temperature_observations"
    ] > 0:

        supporting.append({
            "signal": "temperature_increase",
            "value": (
                f"{evidence['significant_temperature_observations']} "
                "observations"
            ),
            "reason": (
                "Elevated temperature can increase "
                "water demand."
            )
        })

    if evidence[
        "significant_pressure_observations"
    ] > 0:

        supporting.append({
            "signal": "pressure_anomaly",
            "value": (
                f"{evidence['significant_pressure_observations']} "
                "observations"
            ),
            "reason": (
                "Persistent pressure deviation represents "
                "a material infrastructure signal."
            )
        })

    # ========================================================
    # CONFLICTING EVIDENCE
    # ========================================================

    if (
        evidence["night_flow_anomaly_hours"] > 0
        and (
            evidence[
                "significant_occupancy_observations"
            ] > 0
            or evidence[
                "significant_temperature_observations"
            ] > 0
        )
    ):

        conflicting.append({
            "signal": "context_vs_night_flow",
            "reason": (
                "Contextual demand signals coexist with "
                "abnormal night-time flow."
            )
        })

    if (
        evidence[
            "significant_pressure_observations"
        ] > 0
        and evidence[
            "significant_flow_observations"
        ] == 0
    ):

        conflicting.append({
            "signal": "pressure_without_flow",
            "reason": (
                "Pressure anomalies exist without a "
                "corresponding significant flow anomaly."
            )
        })

    if (
        evidence[
            "significant_consumption_observations"
        ] > 0
        and evidence[
            "data_quality_issue_count"
        ] > 0
    ):

        conflicting.append({
            "signal": "consumption_vs_data_quality",
            "reason": (
                "Consumption anomalies occur while "
                "measurement quality is degraded."
            )
        })

    # ========================================================
    # MISSING INFORMATION
    # ========================================================

    if evidence[
        "significant_pressure_observations"
    ] > 0:

        missing.append(
            "Upstream supply pressure and pump/PRV "
            "operational information."
        )

    if evidence[
        "night_flow_anomaly_hours"
    ] > 0:

        missing.append(
            "Sub-meter isolation or physical inspection "
            "information to localize abnormal flow."
        )

    if evidence[
        "significant_temperature_observations"
    ] > 0:

        missing.append(
            "Irrigation or cooling-system operational "
            "records for the affected period."
        )

    if evidence[
        "data_quality_issue_count"
    ] > 0:

        missing.append(
            "Meter diagnostic, calibration and telemetry "
            "information."
        )

    return {
        "observed": observed,
        "calculated": calculated,
        "contextual": contextual,
        "supporting": supporting,
        "conflicting": conflicting,
        "missing": missing
    }


# ============================================================
# BUILD FINAL EVIDENCE PACKAGE
# ============================================================

def build_evidence_package(
    evidence,
    classifications,
    project_id
):
    """
    Build the structured evidence package.

    The six evidence categories are intentionally exposed
    at the top level for downstream agents.
    """

    return {
        "scenario_id": evidence[
            "scenario_id"
        ],

        "observation_count": evidence[
            "observation_count"
        ],

        "source": {
            "system": "BigQuery",
            "table": (
                f"{project_id}."
                f"{DATASET}."
                f"{EVIDENCE_TABLE}"
            )
        },

        "raw_metrics": evidence,

        "observed": classifications[
            "observed"
        ],

        "calculated": classifications[
            "calculated"
        ],

        "contextual": classifications[
            "contextual"
        ],

        "supporting": classifications[
            "supporting"
        ],

        "conflicting": classifications[
            "conflicting"
        ],

        "missing": classifications[
            "missing"
        ]
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_evidence_package(
    package,
    scenario_id
):
    """
    Validate the final Evidence Agent package.
    """

    if package.get("scenario_id") != scenario_id:
        raise RuntimeError(
            "Evidence package contains the wrong scenario."
        )

    observation_count = int(
        package.get("observation_count") or 0
    )

    if observation_count <= 0:
        raise RuntimeError(
            "Evidence package contains zero observations."
        )

    required_sections = [
        "observed",
        "calculated",
        "contextual",
        "supporting",
        "conflicting",
        "missing"
    ]

    for section in required_sections:

        if section not in package:
            raise RuntimeError(
                f"Evidence package is missing "
                f"section: {section}"
            )

        if not isinstance(
            package[section],
            list
        ):
            raise RuntimeError(
                f"Evidence package section "
                f"{section} must be a list."
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
        f"Running WaterTwin Evidence Agent "
        f"for scenario: {scenario_id}"
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
        "Retrieving raw evidence from BigQuery..."
    )

    evidence = get_evidence(
        project_id,
        scenario_id
    )

    print(
        "BigQuery evidence retrieved successfully."
    )

    print(
        "Classifying evidence..."
    )

    classifications = classify_evidence(
        evidence
    )

    package = build_evidence_package(
        evidence,
        classifications,
        project_id
    )

    validate_evidence_package(
        package,
        scenario_id
    )

    print(
        "\nWaterTwin Evidence Agent Result:"
    )

    print(
        json.dumps(
            package,
            indent=2,
            default=str
        )
    )


if __name__ == "__main__":
    main()