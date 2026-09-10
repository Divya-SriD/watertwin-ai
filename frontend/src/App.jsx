import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "/api";

const SCENARIOS = [
  { id: "S1", name: "Normal", description: "Normal campus consumption" },
  {
    id: "S2",
    name: "Leak / Continuous Flow",
    description: "Persistent abnormal water usage",
  },
  {
    id: "S3",
    name: "Pressure Anomaly",
    description: "Infrastructure pressure deviation",
  },
  {
    id: "S4",
    name: "Occupancy Change",
    description: "Demand change associated with occupancy variation",
  },
  {
    id: "S5",
    name: "Weather-driven demand change",
    description: "Weather-aligned demand increase",
  },
  {
    id: "S6",
    name: "Sensor Anomaly",
    description: "Poor-quality meter readings",
  },
  {
    id: "S7",
    name: "Ambiguous / Conflicting",
    description: "Insufficient or conflicting evidence",
  },
];

const SITUATION_OVERVIEW = [
  {
    id: "S1",
    situation: "Normal",
    summary: "Baseline consumption pattern",
    priority: "BASELINE",
    status: "NO ACTION",
    tone: "green",
    cost: null,
  },
  {
    id: "S2",
    situation: "Leak / Continuous Flow",
    summary: "Persistent abnormal water usage",
    priority: "HIGH PRIORITY",
    status: "RECOMMEND",
    tone: "red",
    cost: 4000,
  },
  {
    id: "S3",
    situation: "Pressure Anomaly",
    summary: "Infrastructure pressure deviation",
    priority: "HIGH PRIORITY",
    status: "RECOMMEND",
    tone: "red",
    cost: 2500,
  },
  {
    id: "S4",
    situation: "Occupancy Change",
    summary: "Demand change associated with occupancy variation",
    priority: "MEDIUM PRIORITY",
    status: "EXPLAIN",
    tone: "yellow",
    cost: null,
  },
  {
    id: "S5",
    situation: "Weather-driven demand change",
    summary: "Demand increase aligned with weather",
    priority: "MEDIUM PRIORITY",
    status: "EXPLAIN",
    tone: "yellow",
    cost: null,
  },
  {
    id: "S6",
    situation: "Sensor Anomaly",
    summary: "Poor-quality meter readings",
    priority: "EVIDENCE QUALITY",
    status: "ABSTAIN",
    tone: "red",
    cost: null,
  },
  {
    id: "S7",
    situation: "Ambiguous / Conflicting",
    summary: "Insufficient or conflicting evidence",
    priority: "EVIDENCE LIMITED",
    status: "ABSTAIN",
    tone: "red",
    cost: null,
  },
];

const INTERVENTION_CATALOG_COST = SITUATION_OVERVIEW.reduce(
  (total, item) => total + (item.cost || 0),
  0
);

/*
 * WT-16: Controlled seven-scenario evaluation summary.
 * These values represent the deterministic MVP validation baseline.
 * They are shown as controlled validation, not production accuracy.
 */
const EVALUATION_SUMMARY = {
  scenariosEvaluated: 7,
  anomalyDetection: { correct: 7, total: 7, percent: 100 },
  rootCauseAccuracy: { correct: 7, total: 7, percent: 100 },
  decisionAccuracy: { correct: 7, total: 7, percent: 100 },
  falsePositiveRate: { value: 0, normalCases: 1 },
  abstentionAccuracy: { correct: 2, total: 2, percent: 100 },
  unsafeNonAbstentions: 0,
  interventionQuality: { correct: 2, total: 2, percent: 100 },
  selectedInterventionCount: 2,
  selectedInterventionCost: 6500,
  estimatedSavingsLitresPerDay: 4210.21,
  estimatedSavingsLitresPerYear: 1536726.65,
};

const EVALUATION_SCENARIOS = [
  { id: "S1", expected: "NO_ACTION", outcome: "NO_ACTION", hypothesis: "NORMAL", status: "PASS" },
  { id: "S2", expected: "RECOMMEND", outcome: "RECOMMEND", hypothesis: "LEAK", status: "PASS" },
  { id: "S3", expected: "RECOMMEND", outcome: "RECOMMEND", hypothesis: "PRESSURE_ANOMALY", status: "PASS" },
  { id: "S4", expected: "EXPLAIN", outcome: "EXPLAIN", hypothesis: "OCCUPANCY_DRIVEN", status: "PASS" },
  { id: "S5", expected: "EXPLAIN", outcome: "EXPLAIN", hypothesis: "WEATHER_DRIVEN", status: "PASS" },
  { id: "S6", expected: "ABSTAIN", outcome: "ABSTAIN", hypothesis: "SENSOR_ANOMALY", status: "PASS" },
  { id: "S7", expected: "ABSTAIN", outcome: "ABSTAIN", hypothesis: "AMBIGUOUS", status: "PASS" },
];

const LOADING_STEPS = [
  {
    title: "Detecting abnormal usage patterns",
    detail:
      "Running deterministic consumption and infrastructure analytics.",
  },
  {
    title: "Collecting supporting evidence",
    detail:
      "Combining consumption, context and infrastructure signals.",
  },
  {
    title: "Comparing competing root causes",
    detail:
      "Gemini is evaluating the supplied evidence and uncertainty.",
  },
  {
    title: "Simulating intervention feasibility",
    detail:
      "Applying the selected budget constraint to candidate actions.",
  },
  {
    title: "Preparing the evidence-backed decision",
    detail:
      "Finalizing recommendation, confidence and abstention behavior.",
  },
];

function formatNumber(value, decimals = 0) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${formatNumber(value, 1)}%`;
}

function formatCurrency(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `₹${formatNumber(value, 0)}`;
}

function formatSource(source) {
  if (!source) {
    return "BigQuery";
  }

  if (typeof source === "string") {
    return source;
  }

  if (typeof source === "object") {
    if (source.system && source.table) {
      return `${source.system} · ${source.table}`;
    }

    if (source.system) {
      return String(source.system);
    }

    return Object.entries(source)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(" · ");
  }

  return String(source);
}

function getStatusClass(decision) {
  return decision === "RECOMMEND"
    ? "status-recommend"
    : "status-abstain";
}

function getConfidenceClass(confidence) {
  if (confidence === "HIGH") return "confidence-high";
  if (confidence === "MEDIUM") return "confidence-medium";
  return "confidence-low";
}

function formatEvidenceItem(item) {
  if (typeof item === "string") {
    return item;
  }

  if (!item || typeof item !== "object") {
    return String(item ?? "");
  }

  const parts = [];

  if (item.signal) {
    parts.push(String(item.signal).replace(/_/g, " "));
  }

  if (item.metric) {
    parts.push(String(item.metric).replace(/_/g, " "));
  }

  if (item.value !== undefined && item.value !== null) {
    if (typeof item.value === "object") {
      parts.push(formatSource(item.value));
    } else {
      parts.push(String(item.value));
    }
  }

  if (item.max_deviation_pct !== undefined) {
    parts.push(
      `max deviation ${formatPercent(item.max_deviation_pct)}`
    );
  }

  if (item.max_delta_c !== undefined) {
    parts.push(
      `max delta ${formatNumber(item.max_delta_c, 1)} °C`
    );
  }

  if (item.reason) {
    parts.push(String(item.reason));
  }

  if (item.source) {
    parts.push(`Source: ${formatSource(item.source)}`);
  }

  return parts.join(" — ");
}

/*
 * These are inline SVGs rather than text/unicode characters.
 * This prevents the broken/missing glyphs visible in the previous UI.
 */
function SummaryIcon({ type }) {
  if (type === "situations") {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <rect x="4" y="4" width="6" height="6" rx="1.5" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" />
      </svg>
    );
  }

  if (type === "action") {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M5 12.5l4.2 4.2L19 7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M12 3.5l7 3v5.2c0 4.3-2.9 7.8-7 9.3-4.1-1.5-7-5-7-9.3V6.5l7-3z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinejoin="round"
      />
      <path
        d="M9 12l2 2 4-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function EvidenceGroup({ title, items, tone }) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  return (
    <div className={`evidence-group ${tone || ""}`}>
      <div className="evidence-group-title">
        <span>{title}</span>
        <span className="evidence-count">{items.length}</span>
      </div>

      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>
            {formatEvidenceItem(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}


function EvidenceDetailCards({
  consumption,
  infrastructure,
}) {
  const timeseries = Array.isArray(
    consumption?.evidence_timeseries
  )
    ? consumption.evidence_timeseries
    : [];

  const firstTimestamp =
    timeseries[0]?.timestamp;
  const lastTimestamp =
    timeseries[timeseries.length - 1]?.timestamp;

  const measurementWindow =
    firstTimestamp && lastTimestamp
      ? `${String(firstTimestamp)} → ${String(lastTimestamp)}`
      : "Available in Consumption Agent output";

  const cards = [
    {
      title: "Consumption",
      eyebrow: "DIRECT USAGE SIGNAL",
      rows: [
        {
          label: "Average actual",
          value:
            consumption?.avg_actual_consumption_litres !==
            undefined
              ? `${formatNumber(
                  consumption.avg_actual_consumption_litres,
                  0
                )} L`
              : "—",
        },
        {
          label: "Expected baseline",
          value:
            consumption?.avg_expected_consumption_litres !==
            undefined
              ? `${formatNumber(
                  consumption.avg_expected_consumption_litres,
                  0
                )} L`
              : "—",
        },
        {
          label: "Average deviation",
          value: formatPercent(
            consumption?.avg_consumption_deviation_pct
          ),
        },
        {
          label: "Significant observations",
          value: formatNumber(
            consumption?.significant_consumption_observations
          ),
        },
      ],
    },
    {
      title: "Flow",
      eyebrow: "INFRASTRUCTURE SIGNAL",
      rows: [
        {
          label: "Average deviation",
          value: formatPercent(
            infrastructure?.avg_flow_deviation_pct
          ),
        },
        {
          label: "Maximum deviation",
          value: formatPercent(
            infrastructure?.max_flow_deviation_pct
          ),
        },
        {
          label: "Significant observations",
          value: formatNumber(
            infrastructure?.significant_flow_observations
          ),
        },
        {
          label: "Night-flow anomaly hours",
          value: formatNumber(
            infrastructure?.night_flow_anomaly_hours
          ),
        },
      ],
    },
    {
      title: "Pressure",
      eyebrow: "INFRASTRUCTURE CHECK",
      rows: [
        {
          label: "Average delta",
          value:
            infrastructure?.avg_pressure_delta_psi !==
            undefined
              ? `${formatNumber(
                  infrastructure.avg_pressure_delta_psi,
                  1
                )} psi`
              : "—",
        },
        {
          label: "Minimum delta",
          value:
            infrastructure?.min_pressure_delta_psi !==
            undefined
              ? `${formatNumber(
                  infrastructure.min_pressure_delta_psi,
                  1
                )} psi`
              : "—",
        },
        {
          label: "Significant observations",
          value: formatNumber(
            infrastructure?.significant_pressure_observations
          ),
        },
        {
          label: "Evidence type",
          value: "Deterministic infrastructure analytics",
        },
      ],
    },
    {
      title: "Meter data quality",
      eyebrow: "DATA RELIABILITY",
      rows: [
        {
          label: "Quality issues",
          value: formatNumber(
            infrastructure?.data_quality_issue_count
          ),
        },
        {
          label: "Reading quality",
          value:
            Array.isArray(
              infrastructure?.reading_quality_values
            )
              ? infrastructure.reading_quality_values.join(
                  ", "
                )
              : "—",
        },
        {
          label: "Meter status",
          value:
            Array.isArray(
              infrastructure?.meter_status_values
            )
              ? infrastructure.meter_status_values.join(", ")
              : "—",
        },
        {
          label: "Measurement window",
          value: measurementWindow,
        },
      ],
    },
  ];

  return (
    <div
      className="evidence-detail-section"
      style={{
        marginTop: "22px",
        marginBottom: "22px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: "16px",
          marginBottom: "12px",
        }}
      >
        <div>
          <div className="section-kicker">
            EVIDENCE DETAILS
          </div>
          <h3
            style={{
              margin: "5px 0 0",
              fontSize: "21px",
              lineHeight: 1.25,
              color: "#153f38",
            }}
          >
            Where the evidence comes from
          </h3>
        </div>

        <div
          style={{
            fontSize: "12px",
            color: "#71827d",
            textAlign: "right",
            maxWidth: "340px",
            lineHeight: 1.45,
          }}
        >
          Deterministic values from the Consumption and
          Infrastructure Agents.
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(2, minmax(0, 1fr))",
          gap: "12px",
        }}
      >
        {cards.map((card) => (
          <div
            key={card.title}
            style={{
              border: "1px solid #dfe9e5",
              borderRadius: "14px",
              background: "#f8fbfa",
              padding: "16px 18px",
              boxSizing: "border-box",
            }}
          >
            <div
              style={{
                fontSize: "11px",
                fontWeight: 800,
                letterSpacing: "0.12em",
                color: "#347c70",
                marginBottom: "5px",
              }}
            >
              {card.eyebrow}
            </div>

            <div
              style={{
                fontSize: "17px",
                fontWeight: 800,
                color: "#183f38",
                marginBottom: "10px",
              }}
            >
              {card.title}
            </div>

            <div
              style={{
                display: "grid",
                gap: "7px",
              }}
            >
              {card.rows.map((row) => (
                <div
                  key={row.label}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: "14px",
                    borderTop: "1px solid #e6eeeb",
                    paddingTop: "7px",
                  }}
                >
                  <span
                    style={{
                      color: "#71827d",
                      fontSize: "13px",
                      lineHeight: 1.4,
                    }}
                  >
                    {row.label}
                  </span>

                  <strong
                    style={{
                      color: "#214c43",
                      fontSize: "13px",
                      lineHeight: 1.4,
                      textAlign: "right",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {row.value}
                  </strong>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: "10px",
          padding: "10px 12px",
          borderRadius: "10px",
          background: "#f2f7f5",
          color: "#70817c",
          fontSize: "12px",
          lineHeight: 1.5,
        }}
      >
        Values shown here are taken from the existing
        deterministic agent outputs. WaterTwin does not
        infer physical building, pipe or sensor locations
        that are not represented in the synthetic MVP data.
      </div>
    </div>
  );
}

function ConsumptionEvidenceChart({ data }) {
  if (!Array.isArray(data) || data.length === 0) {
    return null;
  }

  const points = data.filter(
    (point) =>
      point &&
      Number.isFinite(
        Number(point.actual_consumption_litres)
      ) &&
      Number.isFinite(
        Number(point.expected_consumption_litres)
      )
  );

  if (!points.length) {
    return null;
  }

  const width = 900;
  const height = 300;

  const padding = {
    top: 24,
    right: 24,
    bottom: 52,
    left: 72,
  };

  const chartWidth =
    width - padding.left - padding.right;

  const chartHeight =
    height - padding.top - padding.bottom;

  const values = points.flatMap((point) => [
    Number(point.actual_consumption_litres),
    Number(point.expected_consumption_litres),
  ]);

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  const range =
    maxValue - minValue ||
    Math.max(maxValue * 0.05, 1);

  const chartMin =
    minValue - range * 0.08;

  const chartMax =
    maxValue + range * 0.08;

  const getX = (index) =>
    points.length === 1
      ? padding.left + chartWidth / 2
      : padding.left +
        (index / (points.length - 1)) *
          chartWidth;

  const getY = (value) =>
    padding.top +
    ((chartMax - value) /
      (chartMax - chartMin)) *
      chartHeight;

  const createPath = (field) =>
    points
      .map((point, index) => {
        const x = getX(index);
        const y = getY(Number(point[field]));

        return `${
          index === 0 ? "M" : "L"
        } ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");

  const actualPath = createPath(
    "actual_consumption_litres"
  );

  const expectedPath = createPath(
    "expected_consumption_litres"
  );

  const xIndexes = [
    0,
    Math.floor((points.length - 1) / 3),
    Math.floor(((points.length - 1) * 2) / 3),
    points.length - 1,
  ].filter(
    (value, index, array) =>
      array.indexOf(value) === index
  );

  const formatTime = (timestamp) => {
    if (!timestamp) return "";

    const timePart = String(timestamp)
      .split(" ")[1];

    return timePart
      ? timePart.slice(0, 5)
      : String(timestamp);
  };

  return (
    <div className="consumption-chart">
      <div className="chart-header">
        <div>
          <div className="chart-title">
            Consumption evidence
          </div>

          <div className="chart-subtitle">
            Actual consumption compared with the
            expected baseline
          </div>
        </div>

        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-line legend-actual" />
            Actual
          </span>

          <span className="legend-item">
            <span className="legend-line legend-expected" />
            Expected
          </span>
        </div>
      </div>

      <div className="chart-container">
        <svg
          className="consumption-chart-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Actual consumption compared with expected consumption baseline"
        >
          {Array.from(
            { length: 5 },
            (_, index) => {
              const ratio = index / 4;

              const y =
                padding.top +
                ratio * chartHeight;

              const value =
                chartMax -
                ratio *
                  (chartMax - chartMin);

              return (
                <g key={`y-${index}`}>
                  <line
                    x1={padding.left}
                    x2={
                      width -
                      padding.right
                    }
                    y1={y}
                    y2={y}
                    className="chart-grid-line"
                  />

                  <text
                    x={padding.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    className="chart-axis-label"
                  >
                    {formatNumber(value)}
                  </text>
                </g>
              );
            }
          )}

          <path
            d={expectedPath}
            className="chart-line chart-line-expected"
          />

          <path
            d={actualPath}
            className="chart-line chart-line-actual"
          />

          {points.map((point, index) => (
            <circle
              key={`actual-${index}`}
              cx={getX(index)}
              cy={getY(
                Number(
                  point.actual_consumption_litres
                )
              )}
              r="3.5"
              className="chart-point-actual"
            />
          ))}

          {xIndexes.map((index) => (
            <text
              key={`x-${index}`}
              x={getX(index)}
              y={
                height -
                padding.bottom +
                28
              }
              textAnchor="middle"
              className="chart-axis-label"
            >
              {formatTime(
                points[index].timestamp
              )}
            </text>
          ))}

          <text
            x="18"
            y={height / 2}
            textAnchor="middle"
            transform={`rotate(-
              90 18 ${height / 2}
            )`}
            className="chart-axis-title"
          >
            Litres
          </text>
        </svg>
      </div>

      <div className="chart-footnote">
        {points.length} hourly observations from
        the Consumption Agent. Values are sourced from
        BigQuery deterministic analytics.
      </div>
    </div>
  );
}

function InterventionDecisionExplanation({ decision, investigation, recommendation, intervention, simulation, budget }) {
  const type = decision?.decision;

  if (type === "RECOMMEND" && intervention) {
    const cost = Number(intervention.estimated_cost);
    const daily = Number(intervention.estimated_water_savings_litres_per_day);
    const yearly = Number(intervention.estimated_water_savings_litres_per_year);
    const costPer1000 = Number(simulation?.cost_per_1000_litres_saved ?? decision?.impact?.cost_per_1000_litres_saved);
    const remaining = Number(intervention.budget_remaining ?? decision?.impact?.budget_remaining);
    const basis = recommendation?.decision_basis || investigation?.explanation || "The selected intervention is aligned with the evidence-backed decision.";
    const path = `Evidence → ${decision?.primary_hypothesis || "leading hypothesis"} → ${intervention.category || "intervention"} action → simulation → ${simulation?.simulation_status || "ACTION_FEASIBLE"}`;
    return <div style={{marginTop:"18px",padding:"16px",borderRadius:"14px",border:"1px solid #d9e8e3",background:"#f7fbf9"}}>
      <div style={{fontSize:"11px",fontWeight:800,letterSpacing:"0.12em",color:"#347c70",marginBottom:"10px"}}>WHY THIS ACTION IS RECOMMENDED</div>
      <div style={{display:"grid",gap:"14px"}}>
        <div><strong style={{display:"block",color:"#183f38",fontSize:"14px",marginBottom:"4px"}}>Why this action?</strong><p style={{margin:0,color:"#566c66",fontSize:"13px",lineHeight:1.55}}>{basis}</p></div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:"12px"}}>
          <div style={{padding:"12px",borderRadius:"10px",background:"#fff",border:"1px solid #e3ece9"}}><span style={{display:"block",color:"#71827d",fontSize:"12px",marginBottom:"4px"}}>Estimated intervention cost</span><strong style={{color:"#214c43",fontSize:"18px"}}>{formatCurrency(cost)}</strong></div>
          <div style={{padding:"12px",borderRadius:"10px",background:"#fff",border:"1px solid #e3ece9"}}><span style={{display:"block",color:"#71827d",fontSize:"12px",marginBottom:"4px"}}>What the cost represents</span><strong style={{color:"#214c43",fontSize:"13px",lineHeight:1.4}}>Estimated operational effort for the selected {String(intervention.category || "intervention").toLowerCase()} action.</strong></div>
        </div>
        <div><strong style={{display:"block",color:"#183f38",fontSize:"14px",marginBottom:"7px"}}>Expected impact of this action</strong><div style={{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:"10px"}}>
          <div><span style={{display:"block",color:"#71827d",fontSize:"11px"}}>Expected water savings</span><strong style={{color:"#214c43",fontSize:"14px"}}>{Number.isFinite(daily)?`${formatNumber(daily)} L/day`:"—"}</strong></div>
          <div><span style={{display:"block",color:"#71827d",fontSize:"11px"}}>Estimated annual savings</span><strong style={{color:"#214c43",fontSize:"14px"}}>{Number.isFinite(yearly)?`${formatNumber(yearly)} L/year`:"—"}</strong></div>
          <div><span style={{display:"block",color:"#71827d",fontSize:"11px"}}>Cost per 1,000 L saved</span><strong style={{color:"#214c43",fontSize:"14px"}}>{Number.isFinite(costPer1000)?`₹${formatNumber(costPer1000,2)} / 1,000 L`:"—"}</strong></div>
        {Number.isFinite(daily) && daily === 0 ? <p style={{margin:"10px 0 0",color:"#71827d",fontSize:"11px",lineHeight:1.5}}>No direct water savings are estimated at this stage because this is a diagnostic action. Any savings would depend on confirming and correcting the underlying infrastructure issue.</p> : null}</div></div>
        <div style={{padding:"11px 12px",borderRadius:"10px",background:"#eef6f3",color:"#4e6861",fontSize:"12px",lineHeight:1.5}}><strong>Decision path:</strong> {path}{Number.isFinite(remaining)?` The simulation leaves ${formatCurrency(remaining)} within the supplied ${formatCurrency(budget)} budget.`:""}</div>
        <div style={{paddingTop:"10px",borderTop:"1px solid #e3ece9",color:"#71827d",fontSize:"11px",lineHeight:1.5}}>These are synthetic MVP simulation estimates from the intervention catalog and deterministic simulator. They are not field quotations or measured real-world savings.</div>
      </div>
    </div>;
  }

  if (type === "NO_ACTION" && (recommendation?.status === "BUDGET_CONSTRAINED" || simulation?.simulation_status === "BUDGET_CONSTRAINED")) {
    const required = Number(decision?.impact?.required_intervention_cost ?? recommendation?.minimum_intervention_cost ?? simulation?.required_intervention_cost);
    const available = Number(budget);
    const shortfall = Number(decision?.impact?.budget_shortfall ?? (Number.isFinite(required) ? Math.max(required-available,0) : NaN));
    return <div style={{marginTop:"18px",padding:"16px",borderRadius:"14px",border:"1px solid #e7dfc8",background:"#fffaf0"}}>
      <div style={{fontSize:"11px",fontWeight:800,letterSpacing:"0.12em",color:"#8a6a2d",marginBottom:"6px"}}>BUDGET-CONSTRAINED SIMULATION</div>
      <strong style={{display:"block",color:"#5e4b27",fontSize:"14px",marginBottom:"5px"}}>The diagnosis did not change; the action was not feasible under this budget.</strong>
      <p style={{margin:"0 0 12px",color:"#6f6248",fontSize:"13px",lineHeight:1.5}}>WaterTwin identified the intervention candidate, then applied the supplied budget constraint deterministically.</p>
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:"10px"}}><div><span style={{display:"block",color:"#88795c",fontSize:"11px"}}>Required</span><strong style={{color:"#5e4b27"}}>{formatCurrency(required)}</strong></div><div><span style={{display:"block",color:"#88795c",fontSize:"11px"}}>Available</span><strong style={{color:"#5e4b27"}}>{formatCurrency(available)}</strong></div><div><span style={{display:"block",color:"#88795c",fontSize:"11px"}}>Shortfall</span><strong style={{color:"#5e4b27"}}>{formatCurrency(shortfall)}</strong></div></div>
      <div style={{marginTop:"12px",color:"#76694f",fontSize:"11px",lineHeight:1.5}}>Increase the simulation budget only to test whether the identified action becomes feasible. This simulation does not authorize physical work.</div>
    </div>;
  }

  if (type === "EXPLAIN") return <div style={{marginTop:"18px",padding:"16px",borderRadius:"14px",border:"1px solid #d9e8e3",background:"#f7fbf9",color:"#566c66",fontSize:"13px",lineHeight:1.55}}><strong style={{color:"#183f38"}}>No infrastructure intervention is recommended.</strong> The observed demand change is explained by available contextual evidence, so WaterTwin does not assign intervention spend.</div>;

  if (type === "ABSTAIN") return <div style={{marginTop:"18px",padding:"16px",borderRadius:"14px",border:"1px solid #eadfdf",background:"#fff8f8",color:"#6f5d5d",fontSize:"13px",lineHeight:1.55}}><strong style={{color:"#6a4747"}}>Do not authorize an intervention.</strong> WaterTwin is intentionally abstaining because the evidence is insufficient or conflicting. Collect the missing information above and reassess.</div>;
  if (type === "NO_ACTION") return <div style={{marginTop:"18px",padding:"16px",borderRadius:"14px",border:"1px solid #dfe9e5",background:"#f7fbf9",color:"#566c66",fontSize:"13px",lineHeight:1.55}}><strong style={{color:"#183f38"}}>No intervention cost is applied.</strong> The evidence does not currently support a physical action, so the simulator does not assign intervention spend.</div>;
  return null;
}

function WaterZoneSituationOverview({
  budget,
  selectedScenarioId,
  onSelectScenario,
}) {
  const numericBudget = Math.max(
    Number(budget) || 0,
    0
  );

  const coverage = Math.min(
    (numericBudget /
      INTERVENTION_CATALOG_COST) *
      100,
    100
  );

  const shortfall = Math.max(
    INTERVENTION_CATALOG_COST -
      numericBudget,
    0
  );

  return (
    <section className="situation-overview">
      <div className="overview-header">
        <div className="overview-heading-copy">
          <div className="section-kicker">
            WATER ZONE SITUATION OVERVIEW
          </div>

          <h2>
            What is happening across the
            controlled water zone?
          </h2>

          <p>
            A lightweight view of the seven
            controlled synthetic situations.
            Select a situation below to
            investigate it with the full
            WaterTwin decision workflow.
          </p>
        </div>

        <div className="overview-summary">
          <div className="overview-summary-item">
            <span className="overview-summary-icon">
              <SummaryIcon type="situations" />
            </span>

            <div>
              <strong>7</strong>
              <span>Situations</span>
            </div>
          </div>

          <div className="overview-summary-item">
            <span className="overview-summary-icon overview-summary-icon-action">
              <SummaryIcon type="action" />
            </span>

            <div>
              <strong>2</strong>
              <span>Action-capable</span>
            </div>
          </div>

          <div className="overview-summary-item">
            <span className="overview-summary-icon overview-summary-icon-abstain">
              <SummaryIcon type="abstain" />
            </span>

            <div>
              <strong>2</strong>
              <span>Abstention cases</span>
            </div>
          </div>
        </div>
      </div>

      <div className="budget-layout">
        <div className="budget-coverage">
          <div className="budget-coverage-header">
            <div>
              <div className="overview-card-label">
                BUDGET COVERAGE
              </div>

              <strong>
                {formatCurrency(
                  numericBudget
                )}{" "}
                available
              </strong>

              <span>
                {formatCurrency(
                  INTERVENTION_CATALOG_COST
                )}{" "}
                intervention catalog cost
              </span>
            </div>

            <div className="budget-coverage-value">
              {formatNumber(coverage, 0)}%
            </div>
          </div>

          <div
            className="budget-coverage-track"
            aria-label={`Budget coverage ${formatNumber(
              coverage,
              0
            )} percent`}
          >
            <div
              className="budget-coverage-fill"
              style={{
                width: `${coverage}%`,
              }}
            />
          </div>
        </div>

        <div className="budget-summary-card">
          <div className="budget-summary-heading">
            <span>Coverage</span>

            <strong>
              {formatNumber(
                coverage,
                0
              )}%
            </strong>
          </div>

          <div className="budget-summary-row">
            <span>Available</span>

            <strong>
              {formatCurrency(
                numericBudget
              )}
            </strong>
          </div>

          <div className="budget-summary-row">
            <span>Cataloged need</span>

            <strong>
              {formatCurrency(
                INTERVENTION_CATALOG_COST
              )}
            </strong>
          </div>

          <div className="budget-summary-row budget-summary-row-last">
            <span>Shortfall</span>

            <strong>
              {formatCurrency(shortfall)}
            </strong>
          </div>
        </div>
      </div>

      <div className="situation-section-header">
        <div>
          <div className="overview-card-label">
            PRIORITY / SITUATION
          </div>

          <span>
            Priority is a deterministic scenario
            profile; final decisions are produced
            only after evidence analysis.
          </span>

          <div
            className="situation-legend"
            aria-label="Situation priority legend"
          >
            <span>
              <i className="legend-dot legend-dot-green" />
              Baseline
            </span>

            <span>
              <i className="legend-dot legend-dot-yellow" />
              Monitor
            </span>

            <span>
              <i className="legend-dot legend-dot-red" />
              High attention
            </span>
          </div>
        </div>
      </div>

      <div className="situation-grid">
        {SITUATION_OVERVIEW.map(
          (item) => {
            const selected =
              item.id ===
              selectedScenarioId;

            return (
              <button
                key={item.id}
                type="button"
                className={`situation-card situation-card-${item.tone} ${
                  selected
                    ? "situation-card-selected"
                    : ""
                }`}
                onClick={() =>
                  onSelectScenario(
                    item.id
                  )
                }
              >
                <div className="situation-card-topline">
                  <span className="situation-id">
                    {item.id}
                  </span>

                  <span
                    className={`situation-status situation-status-${item.tone}`}
                  >
                    {item.status}
                  </span>
                </div>

                <div className="situation-name">
                  {item.situation}
                </div>

                <div className="situation-summary">
                  {item.summary}
                </div>

                <div className="situation-card-footer">
                  <span
                    className={`situation-priority situation-priority-${item.tone}`}
                  >
                    <i
                      className={`priority-dot priority-dot-${item.tone}`}
                    />
                    {item.priority}
                  </span>

                  <strong>
                    {item.cost === null
                      ? "—"
                      : formatCurrency(
                          item.cost
                        )}
                  </strong>
                </div>
              </button>
            );
          }
        )}
      </div>

      <div className="overview-note">
        Intervention costs shown here are synthetic MVP catalog estimates for simulation — not field quotations. Final intervention cost comes from the selected backend intervention and is tested against the supplied budget. An abstention does not authorize an intervention.
      </div>
    </section>
  );
}


function EvaluationSummary() {
  const metrics = [
    {
      label: "Anomaly detection",
      value: `${EVALUATION_SUMMARY.anomalyDetection.percent}%`,
      meta: `${EVALUATION_SUMMARY.anomalyDetection.correct}/${EVALUATION_SUMMARY.anomalyDetection.total} scenarios`,
    },
    {
      label: "Root-cause accuracy",
      value: `${EVALUATION_SUMMARY.rootCauseAccuracy.percent}%`,
      meta: `${EVALUATION_SUMMARY.rootCauseAccuracy.correct}/${EVALUATION_SUMMARY.rootCauseAccuracy.total} scenarios`,
    },
    {
      label: "Decision accuracy",
      value: `${EVALUATION_SUMMARY.decisionAccuracy.percent}%`,
      meta: `${EVALUATION_SUMMARY.decisionAccuracy.correct}/${EVALUATION_SUMMARY.decisionAccuracy.total} scenarios`,
    },
    {
      label: "Correct abstention",
      value: `${EVALUATION_SUMMARY.abstentionAccuracy.percent}%`,
      meta: `${EVALUATION_SUMMARY.abstentionAccuracy.correct}/${EVALUATION_SUMMARY.abstentionAccuracy.total} abstention cases`,
    },
    {
      label: "False-positive rate (normal cases)",
      value: `${formatNumber(EVALUATION_SUMMARY.falsePositiveRate.value, 0)}%`,
      meta: `0/${EVALUATION_SUMMARY.falsePositiveRate.normalCases} normal cases incorrectly flagged`,
    },
    {
      label: "Unsafe non-abstentions",
      value: formatNumber(EVALUATION_SUMMARY.unsafeNonAbstentions),
      meta: "unsafe action cases",
    },
    {
      label: "Intervention quality",
      value: `${EVALUATION_SUMMARY.interventionQuality.percent}%`,
      meta: `${EVALUATION_SUMMARY.interventionQuality.correct}/${EVALUATION_SUMMARY.interventionQuality.total} recommend cases`,
    },
    {
      label: "Estimated water savings",
      value: `${formatNumber(EVALUATION_SUMMARY.estimatedSavingsLitresPerDay, 0)} L/day`,
      meta: `${formatNumber(EVALUATION_SUMMARY.estimatedSavingsLitresPerYear, 0)} L/year`,
    },
  ];

  return (
    <section className="evaluation-panel">
      <div className="evaluation-header">
        <div>
          <div className="section-kicker">WT-16 · CONTROLLED VALIDATION</div>
          <h2>Does WaterTwin make the right decision?</h2>
          <p>
            Seven controlled synthetic scenarios with known ground truth were
            evaluated without calling Gemini during scoring.
          </p>
        </div>

        <div className="evaluation-badge">
          <strong>{EVALUATION_SUMMARY.scenariosEvaluated}/7</strong>
          <span>scenarios passed</span>
        </div>
      </div>

      <div className="evaluation-metrics">
        {metrics.map((metric) => (
          <div className="evaluation-metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.meta}</small>
          </div>
        ))}
      </div>

      <div className="evaluation-table-wrap">
        <div className="evaluation-table-title">
          Scenario-level validation
        </div>

        <div className="evaluation-table">
          <div className="evaluation-row evaluation-row-header">
            <span>Scenario</span>
            <span>Expected</span>
            <span>WaterTwin</span>
            <span>Hypothesis</span>
            <span>Result</span>
          </div>

          {EVALUATION_SCENARIOS.map((scenario) => (
            <div className="evaluation-row" key={scenario.id}>
              <strong>{scenario.id}</strong>
              <span>{scenario.expected}</span>
              <span>{scenario.outcome}</span>
              <span>{scenario.hypothesis}</span>
              <b className="evaluation-pass">{scenario.status}</b>
            </div>
          ))}
        </div>
      </div>

      <div className="evaluation-footnote">
        <strong>Interpretation:</strong> this is controlled MVP validation, not
        a claim of production-level accuracy. The dataset is synthetic and
        intentionally covers the seven defined scenarios. Estimated savings
        are deterministic simulator outputs; they are not measured field
        savings.
      </div>
    </section>
  );
}

function App() {
  const [view, setView] =
    useState("overview");

  const [scenarioId, setScenarioId] =
    useState("S2");

  const [budget, setBudget] =
    useState(20000);

  const [result, setResult] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [loadingStep, setLoadingStep] =
    useState(0);

  const [error, setError] =
    useState("");

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return undefined;
    }

    const interval =
      window.setInterval(() => {
        setLoadingStep((current) =>
          Math.min(
            current + 1,
            LOADING_STEPS.length - 1
          )
        );
      }, 4500);

    return () =>
      window.clearInterval(interval);
  }, [loading]);


  function selectScenario(nextScenarioId, openInvestigation = true) {
    if (loading) return;

    setScenarioId(nextScenarioId);
    setResult(null);
    setError("");

    if (openInvestigation) {
      setView("investigation");
    }
  }

  function returnToOverview() {
    if (loading) return;

    setView("overview");
    setResult(null);
    setError("");
  }

  async function analyzeScenario() {
    setView("investigation");
    setLoading(true);
    setLoadingStep(0);
    setResult(null);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            scenario_id: scenarioId,
            budget: Number(budget),
          }),
        }
      );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail?.message ||
            data?.detail ||
            "WaterTwin analysis failed."
        );
      }

      setResult(data);
    } catch (err) {
      setError(
        err.message ||
          "Unable to connect to the WaterTwin decision engine."
      );
    } finally {
      setLoading(false);
    }
  }

  const decision =
    result?.final_decision || {};

  const agents =
    result?.agents || {};

  const consumption =
    agents.consumption_agent || {};

  const infrastructure =
    agents.infrastructure_agent || {};

  const context =
    agents.context_agent || {};

  const evidence =
    agents.evidence_agent || {};

  const investigation =
    agents.investigation_engine || {};

  const recommendation =
    agents.recommendation_engine || {};

  const simulator =
    agents.intervention_simulator || {};

  const intervention =
    decision.recommended_intervention;

  const simulation =
    simulator.simulation || {};

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            W
          </div>

          <div>
            <div className="brand-name">
              WaterTwin AI
            </div>

            <div className="brand-subtitle">
              Evidence-Based Water Infrastructure Decision Intelligence
            </div>
          </div>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          Decision Engine Online
        </div>
      </header>

      <main className="dashboard">
        {view === "investigation" && (
          <div className="investigation-hero">
        <section className="hero">
          <div>
            <div className="eyebrow">
              WATER INFRASTRUCTURE DECISION
              CONSOLE
            </div>

            <h1>
              From abnormal usage
              <br />
              to evidence-backed action.
            </h1>

            <p>
              WaterTwin combines consumption,
              context, infrastructure signals
              and evidence to recommend an
              intervention — or abstain when the
              evidence is insufficient.
            </p>
          </div>

          <div className="workflow">
            <span className="workflow-active">
              DETECT
            </span>
            <span>→</span>
            <span>INVESTIGATE</span>
            <span>→</span>
            <span>EXPLAIN</span>
            <span>→</span>
            <span>SIMULATE</span>
            <span>→</span>
            <span>PRIORITIZE</span>
            <span>→</span>
            <span>ACT</span>
          </div>
        </section>
          </div>
        )}


        {view === "overview" && (
          <>
        <WaterZoneSituationOverview
          budget={budget}
          selectedScenarioId={
            scenarioId
          }
          onSelectScenario={(nextScenarioId) =>
            selectScenario(nextScenarioId, true)
          }
        />

            <EvaluationSummary />

            <section className="overview-cta">
              <div>
                <div className="section-kicker">READY TO INVESTIGATE</div>
                <h2>
                  Start with {scenarioId} —{" "}
                  {
                    SCENARIOS.find(
                      (scenario) => scenario.id === scenarioId
                    )?.name
                  }
                </h2>
                <p>
                  Set the intervention budget and run the complete
                  evidence-backed decision workflow.
                </p>
              </div>

              <button
                className="primary-overview-button"
                type="button"
                onClick={analyzeScenario}
                disabled={loading}
              >
                Investigate {scenarioId} <span>→</span>
              </button>
            </section>
          </>
        )}

        {view === "investigation" && (
          <>
            <div className="view-backbar">
              <button
                type="button"
                className="back-button"
                onClick={returnToOverview}
                disabled={loading}
              >
                ← Back to overview
              </button>

              <div>
                <strong>
                  {scenarioId} —{" "}
                  {
                    SCENARIOS.find(
                      (scenario) => scenario.id === scenarioId
                    )?.name
                  }
                </strong>
                <span>Evidence-backed decision investigation</span>
              </div>
            </div>

        <section className="control-panel">
          <div className="control-field">
            <label htmlFor="scenario">
              Scenario
            </label>

            <select
              id="scenario"
              value={scenarioId}
              disabled={loading}
              onChange={(event) =>
                selectScenario(event.target.value, false)
              }
            >
              {SCENARIOS.map(
                (scenario) => (
                  <option
                    key={scenario.id}
                    value={scenario.id}
                  >
                    {scenario.id} —{" "}
                    {scenario.name}
                  </option>
                )
              )}
            </select>

            <small>
              {
                SCENARIOS.find(
                  (scenario) =>
                    scenario.id ===
                    scenarioId
                )?.description
              }
            </small>
          </div>

          <div className="control-field">
            <label htmlFor="budget">
              Intervention budget
            </label>

            <div className="budget-input">
              <span>₹</span>

              <input
                id="budget"
                type="number"
                min="0"
                step="100"
                value={budget}
                onChange={(event) =>
                  setBudget(
                    event.target.value
                  )
                }
              />
            </div>

            <small>
              Simulation constraint
            </small>
          </div>

          <button
            className="analyze-button"
            onClick={analyzeScenario}
            disabled={loading}
          >
            {loading
              ? "Analyzing…"
              : "Analyze Scenario"}

            {!loading && (
              <span>→</span>
            )}
          </button>
        </section>

          </>
        )}

        {view === "investigation" && error && (
          <div className="error-banner">
            <strong>
              Unable to analyze:
            </strong>{" "}
            {error}
          </div>
        )}

        {view === "investigation" &&
          !result &&
          !loading &&
          !error && (
            <section className="empty-state">
              <div className="empty-icon">
                ◈
              </div>

              <h2>
                Ready to investigate
              </h2>

              <p>
                Select a scenario and
                budget, then run
                WaterTwin&apos;s
                evidence-based decision
                workflow.
              </p>

              <button
                className="secondary-button"
                onClick={
                  analyzeScenario
                }
              >
                Analyze {scenarioId}
              </button>
            </section>
          )}

        {view === "investigation" && loading && (
          <section className="loading-state">
            <div className="loading-header">
              <div className="loader" />

              <div>
                <div className="section-kicker">
                  ANALYSIS IN PROGRESS
                </div>

                <strong>
                  {
                    LOADING_STEPS[
                      loadingStep
                    ].title
                  }
                </strong>

                <span>
                  {
                    LOADING_STEPS[
                      loadingStep
                    ].detail
                  }
                </span>
              </div>
            </div>

            <div
              className="loading-progress"
              aria-label="WaterTwin analysis processing focus"
            >
              {LOADING_STEPS.map(
                (step, index) => (
                  <div
                    key={step.title}
                    className={`loading-step ${
                      index ===
                      loadingStep
                        ? "loading-step-active"
                        : ""
                    }`}
                  >
                    <span className="loading-step-marker">
                      {index + 1}
                    </span>

                    <span className="loading-step-label">
                      {step.title}
                    </span>
                  </div>
                )
              )}
            </div>

            <div className="loading-note">
              Processing focus is
              informational; the current API
              does not stream individual agent
              completion events.
            </div>
          </section>
        )}

        {view === "investigation" &&
          result &&
          !loading && (
            <>
              <section className="kpi-grid">
                <div className="kpi-card">
                  <div className="kpi-label">
                    Consumption deviation
                  </div>

                  <div className="kpi-value">
                    {formatPercent(
                      consumption.avg_consumption_deviation_pct
                    )}
                  </div>

                  <div className="kpi-meta">
                    {formatNumber(
                      consumption.significant_consumption_observations
                    )}{" "}
                    significant
                    observations
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">
                    Flow deviation
                  </div>

                  <div className="kpi-value">
                    {formatPercent(
                      infrastructure.avg_flow_deviation_pct
                    )}
                  </div>

                  <div className="kpi-meta">
                    {formatNumber(
                      infrastructure.night_flow_anomaly_hours
                    )}{" "}
                    night-flow anomaly
                    hours
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">
                    Pressure delta
                  </div>

                  <div className="kpi-value">
                    {formatNumber(
                      infrastructure.avg_pressure_delta_psi,
                      1
                    )}{" "}
                    psi
                  </div>

                  <div className="kpi-meta">
                    {formatNumber(
                      infrastructure.significant_pressure_observations
                    )}{" "}
                    pressure
                    observations
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-label">
                    Data quality issues
                  </div>

                  <div className="kpi-value">
                    {formatNumber(
                      infrastructure.data_quality_issue_count
                    )}
                  </div>

                  <div className="kpi-meta">
                    {infrastructure.reading_quality_values?.join(
                      ", "
                    ) ||
                      "No flags"}
                  </div>
                </div>
              </section>

              <section className="decision-layout">
                <div
                  className={`decision-card ${getStatusClass(
                    decision.decision
                  )}`}
                >
                  <div className="decision-topline">
                    <span className="section-kicker">
                      FINAL DECISION
                    </span>

                    <span className="scenario-pill">
                      {result.scenario_id}
                    </span>
                  </div>

                  <div className="decision-main">
                    <div>
                      <div className="decision-status">
                        {
                          decision.decision
                        }
                      </div>

                      <div className="hypothesis">
                        {
                          decision.primary_hypothesis
                        }
                      </div>
                    </div>

                    <div
                      className={`confidence ${getConfidenceClass(
                        decision.confidence_level
                      )}`}
                    >
                      <span>
                        CONFIDENCE
                      </span>

                      <strong>
                        {
                          decision.confidence_level
                        }
                      </strong>
                    </div>
                  </div>

                  <div className="decision-explanation">
                    <div className="subsection-title">
                      Why?
                    </div>

                    <p>
                      {investigation.explanation ||
                        "The investigation did not return an explanation."}
                    </p>
                  </div>

                  {decision.decision ===
                    "ABSTAIN" && (
                    <div className="abstention-box">
                      <div className="abstention-title">
                        ⚠ Evidence is
                        insufficient for a
                        reliable action
                      </div>

                      <p>
                        WaterTwin is
                        intentionally
                        abstaining rather than
                        presenting a
                        low-confidence
                        recommendation.
                      </p>

                      {Array.isArray(
                        decision.missing_information
                      ) &&
                        decision
                          .missing_information
                          .length >
                          0 && (
                          <>
                            <div className="subsection-title">
                              Additional
                              information
                              required
                            </div>

                            <ul>
                              {decision.missing_information.map(
                                (
                                  item,
                                  index
                                ) => (
                                  <li
                                    key={
                                      index
                                    }
                                  >
                                    {typeof item ===
                                    "object"
                                      ? formatSource(
                                          item
                                        )
                                      : item}
                                  </li>
                                )
                              )}
                            </ul>
                          </>
                        )}
                    </div>
                  )}
                </div>

                <div className="signal-card">
                  <div className="section-kicker">
                    CONTEXT SIGNALS
                  </div>

                  <div className="signal-row">
                    <span>
                      Occupancy deviation
                    </span>

                    <strong>
                      {formatPercent(
                        context.avg_occupancy_deviation_pct
                      )}
                    </strong>
                  </div>

                  <div className="signal-row">
                    <span>
                      Temperature delta
                    </span>

                    <strong>
                      {formatNumber(
                        context.avg_temperature_delta_c,
                        1
                      )}{" "}
                      °C
                    </strong>
                  </div>

                  <div className="signal-row">
                    <span>
                      Night consumption
                      anomalies
                    </span>

                    <strong>
                      {formatNumber(
                        consumption.night_consumption_anomaly_hours
                      )}
                    </strong>
                  </div>

                  <div className="signal-row">
                    <span>
                      Meter quality
                    </span>

                    <strong>
                      {Array.isArray(
                        infrastructure.reading_quality_values
                      )
                        ? infrastructure.reading_quality_values.join(
                            ", "
                          )
                        : formatSource(
                            infrastructure.reading_quality_values
                          ) ||
                          "GOOD"}
                    </strong>
                  </div>

                  <div className="signal-footer">
                    Context is considered
                    alongside direct
                    infrastructure evidence.
                  </div>
                </div>
              </section>

              <section className="content-grid">
                <div className="panel evidence-panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">
                        EVIDENCE
                      </div>

                      <h2>
                        What supports the
                        decision?
                      </h2>
                    </div>

                    <span className="source-badge">
                      {formatSource(
                        evidence.source
                      )}
                    </span>
                  </div>

                  <ConsumptionEvidenceChart
                    data={
                      consumption.evidence_timeseries
                    }
                  />

                  <EvidenceDetailCards
                    consumption={consumption}
                    infrastructure={infrastructure}
                  />

                  <div className="evidence-grid">
                    <EvidenceGroup
                      title="Observed"
                      items={
                        evidence.observed
                      }
                      tone="observed"
                    />

                    <EvidenceGroup
                      title="Calculated"
                      items={
                        evidence.calculated
                      }
                      tone="calculated"
                    />

                    <EvidenceGroup
                      title="Contextual"
                      items={
                        evidence.contextual
                      }
                      tone="contextual"
                    />

                    <EvidenceGroup
                      title="Supporting"
                      items={
                        evidence.supporting
                      }
                      tone="supporting"
                    />

                    <EvidenceGroup
                      title="Conflicting"
                      items={
                        evidence.conflicting
                      }
                      tone="conflicting"
                    />

                    <EvidenceGroup
                      title="Missing"
                      items={
                        evidence.missing
                      }
                      tone="missing"
                    />
                  </div>
                </div>

                <div className="panel recommendation-panel">
                  <div className="section-kicker">
                    INTERVENTION
                  </div>

                  <h2>
                    {intervention
                      ? "Recommended action"
                      : "No action recommended"}
                  </h2>

                  {intervention ? (
                    <>
                      <div className="intervention-name">
                        {
                          intervention.action
                        }
                      </div>

                      <div className="intervention-category">
                        {
                          intervention.category
                        }
                      </div>

                      <div className="impact-grid">
                        <div>
                          <span>
                            Estimated cost
                          </span>

                          <strong>
                            {formatCurrency(
                              intervention.estimated_cost
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Water savings
                          </span>

                          <strong>
                            {formatNumber(
                              intervention.estimated_water_savings_litres_per_day
                            )}{" "}
                            L/day
                          </strong>
                        </div>

                        <div>
                          <span>
                            Payback
                          </span>

                          <strong>
                            {formatNumber(
                              intervention.payback_days,
                              1
                            )}{" "}
                            days
                          </strong>
                        </div>

                        <div>
                          <span>
                            Feasibility
                          </span>

                          <strong>
                            {
                              intervention.feasibility
                            }
                          </strong>
                        </div>
                      </div>

                      <div className="simulation-box">
                        <div className="simulation-title">
                          Intervention
                          simulation
                        </div>

                        <div className="simulation-row">
                          <span>
                            Budget
                          </span>

                          <strong>
                            {formatCurrency(
                              result.simulation_budget
                            )}
                          </strong>
                        </div>

                        <div className="simulation-row">
                          <span>
                            Intervention
                            cost
                          </span>

                          <strong>
                            {formatCurrency(
                              intervention.estimated_cost
                            )}
                          </strong>
                        </div>

                        <div className="simulation-row">
                          <span>
                            Remaining
                            budget
                          </span>

                          <strong>
                            {formatCurrency(
                              intervention.budget_remaining
                            )}
                          </strong>
                        </div>

                        {simulation.simulation_status && (
                          <div className="simulation-status">
                            {
                              simulation.simulation_status
                            }
                          </div>
                        )}
                      </div>
                      <InterventionDecisionExplanation decision={decision} investigation={investigation} recommendation={recommendation} intervention={intervention} simulation={simulation} budget={result.simulation_budget} />
                    </>
                  ) : (
                    <div className="no-action">
                      <div className="no-action-icon">
                        !
                      </div>

                      <p>
                        {(recommendation?.status === "BUDGET_CONSTRAINED" || simulation?.simulation_status === "BUDGET_CONSTRAINED")
                          ? "An evidence-supported intervention was identified, but it is not feasible under the supplied budget."
                          : "No physical intervention is recommended because the available evidence does not support one."}
                      </p>
                    </div>
                  )}

                  {!intervention && (
                    <InterventionDecisionExplanation decision={decision} investigation={investigation} recommendation={recommendation} intervention={intervention} simulation={simulation} budget={result.simulation_budget} />
                  )}
                </div>
              </section>

              <section className="reasoning-panel">
                <div>
                  <div className="section-kicker">
                    DECISION BASIS
                  </div>

                  <h2>
                    Evidence before action
                  </h2>
                </div>

                <p>
                  {typeof recommendation.decision_basis ===
                  "string"
                    ? recommendation.decision_basis
                    : recommendation.decision_basis
                    ? formatSource(
                        recommendation.decision_basis
                      )
                    : "The recommendation is based on the evidence and deterministic intervention simulation."}
                </p>
              </section>

              <footer className="footer">
                <span>
                  WaterTwin AI
                </span>

                <span>
                  DETECT → INVESTIGATE →
                  EXPLAIN → SIMULATE →
                  PRIORITIZE → ACT
                </span>

                <span>
                  Evidence + Confidence +
                  Abstention
                </span>
              </footer>
            </>
          )}
      </main>

    </div>
  );
}

export default App;