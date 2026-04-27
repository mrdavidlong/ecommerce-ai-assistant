# Capstone Rubric: BYOP (Build Your Own Project) — Agentic AI 2.0

Source: `Agentic AI 2.0 - EM Capstone Projects Rubrics BYOP.xlsx`

**Total: 100 points**

---

## 1. Problem Definition & Use Case Clarity (20 pts)

### 1.1 Problem Clarity & Real-World Relevance (8 pts)
| Score | Criteria |
|---|---|
| 7–8 | Clearly defined, high-impact real-world problem with strong motivation and specificity |
| 5–6 | Problem is clear but motivation or scope is somewhat vague |
| 3–4 | Problem is defined but lacks clarity or real-world grounding |
| 0–2 | Problem is unclear, trivial, or not well-articulated |

### 1.2 User / Stakeholder Definition (6 pts)
| Score | Criteria |
|---|---|
| 5–6 | Well-defined user persona with clear needs, context, and role |
| 3–4 | User is described but lacks specificity or context |
| 1–2 | User is vaguely mentioned |
| 0 | No user definition |

### 1.3 Success Criteria & Measurable Outcomes (6 pts)
| Score | Criteria |
|---|---|
| 5–6 | Clear, measurable metrics defined (quality, cost, time, accuracy, etc.) |
| 3–4 | Some metrics defined but not fully measurable |
| 1–2 | Success criteria are vague or qualitative only |
| 0 | No success criteria defined |

---

## 2. Agentic Design & System Architecture (25 pts)

### 2.1 Agent Decomposition & Role Clarity (8 pts)
| Score | Criteria |
|---|---|
| 7–8 | Clear multi-agent design with one job per agent; roles are well-justified |
| 5–6 | Multiple agents present but roles overlap or aren't clearly justified |
| 3–4 | Agent roles are defined but decomposition lacks clarity |
| 0–2 | Single agent or no clear agent decomposition |

### 2.2 Orchestration & Workflow Design (7 pts)
| Score | Criteria |
|---|---|
| 6–7 | Well-structured workflow with justified orchestration pattern (e.g., supervisor, pipeline, parallel) |
| 4–5 | Orchestration exists but pattern choice isn't well-justified |
| 2–3 | Basic orchestration; workflow is hard to follow |
| 0–1 | No clear orchestration design |

### 2.3 End-to-End System Completeness (5 pts)
| Score | Criteria |
|---|---|
| 5 | Full pipeline working: input → agents → outputs → user interface |
| 3–4 | Most of the pipeline works; minor gaps |
| 1–2 | Partial pipeline; significant gaps |
| 0 | System is not functional end-to-end |

### 2.4 Modularity & Extensibility (5 pts)
| Score | Criteria |
|---|---|
| 5 | System is modular; adding a new agent or tool requires minimal changes |
| 3–4 | Mostly modular; some coupling exists |
| 1–2 | Limited modularity; changes require significant refactoring |
| 0 | Monolithic; no modularity |

---

## 3. Quality, Grounding & Output Reliability (20 pts)

### 3.1 Output Quality & Usefulness (8 pts)
| Score | Criteria |
|---|---|
| 7–8 | Outputs are highly relevant, actionable, and valuable to the user |
| 5–6 | Outputs are useful but occasionally off-target or verbose |
| 3–4 | Outputs are partially relevant; quality is inconsistent |
| 0–2 | Outputs are frequently irrelevant or low quality |

### 3.2 Grounding (RAG / Data-Backed Outputs) (6 pts)
| Score | Criteria |
|---|---|
| 5–6 | Outputs are grounded in a knowledge base or data source with clear traceability |
| 3–4 | Some grounding present; not consistent across all outputs |
| 1–2 | Minimal grounding; outputs rely heavily on LLM parametric knowledge |
| 0 | No grounding; outputs are purely LLM-generated |

### 3.3 Output Structure & Consistency (3 pts)
| Score | Criteria |
|---|---|
| 3 | Structured outputs with defined schemas/validation (e.g., Pydantic, JSON schema) |
| 2 | Mostly structured; some inconsistency |
| 1 | Loosely structured; no schema enforcement |
| 0 | Unstructured outputs |

### 3.4 Guardrails & Hallucination Control (3 pts)
| Score | Criteria |
|---|---|
| 3 | Strong safeguards: input validation, output constraints, fallback logic |
| 2 | Some guardrails present but not comprehensive |
| 1 | Minimal guardrails |
| 0 | No guardrails |

---

## 4. Evaluation, Iteration & Improvement (15 pts)

### 4.1 Evaluation Framework (5 pts)
| Score | Criteria |
|---|---|
| 5 | Clear eval strategy with dataset + metrics + evaluation methods defined |
| 3–4 | Evaluation present but incomplete (missing dataset, metrics, or method) |
| 1–2 | Ad hoc evaluation only |
| 0 | No evaluation |

### 4.2 Use of Evaluation Signals (5 pts)
| Score | Criteria |
|---|---|
| 5 | Eval results used to drive meaningful improvements to the system |
| 3–4 | Some improvements made based on eval but not systematic |
| 1–2 | Eval performed but results not acted on |
| 0 | No use of evaluation signals |

### 4.3 Evidence of Improvement (5 pts)
| Score | Criteria |
|---|---|
| 5 | Clear before/after improvements with measurable deltas shown |
| 3–4 | Some iteration evident but improvements not clearly measured |
| 1–2 | Minor changes made; no clear improvement story |
| 0 | No evidence of iteration |

---

## 5. Technical Implementation & Integration (10 pts)

### 5.1 Tool Integration & System Connectivity (5 pts)
| Score | Criteria |
|---|---|
| 5 | Smooth integration across APIs, tools, databases, and LLMs |
| 3–4 | Most integrations work; minor issues |
| 1–2 | Partial integrations; significant issues |
| 0 | Little to no integration |

### 5.2 Reliability & Error Handling (5 pts)
| Score | Criteria |
|---|---|
| 5 | Handles failures, edge cases, and variability robustly; graceful degradation |
| 3–4 | Some error handling present; not comprehensive |
| 1–2 | Minimal error handling; system is brittle |
| 0 | No error handling |

---

## 6. Usability, UX & Decision Support (5 pts)

### 6.1 User Experience & Accessibility (3 pts)
| Score | Criteria |
|---|---|
| 3 | Interface or interaction is intuitive, clear, and easy to use |
| 2 | Usable but requires some guidance |
| 1 | Difficult to use; confusing flow |
| 0 | No usable interface |

### 6.2 Decision Support / Automation Value (2 pts)
| Score | Criteria |
|---|---|
| 2 | System clearly improves decision-making or automates meaningful work |
| 1 | Some automation value but limited impact |
| 0 | No clear decision support or automation value |

---

## 7. Documentation, Communication & Delivery (5 pts)

### 7.1 Documentation Completeness (3 pts)
| Score | Criteria |
|---|---|
| 3 | Covers architecture, agents, design decisions, setup instructions clearly |
| 2 | Mostly documented; some gaps |
| 1 | Minimal documentation |
| 0 | No documentation |

### 7.2 Clarity of Explanation & Demo (2 pts)
| Score | Criteria |
|---|---|
| 2 | Clear articulation of system, trade-offs, and outcomes; strong demo |
| 1 | Explanation is adequate but lacks depth or clarity |
| 0 | Poor or no explanation/demo |

---

## Scoring Strategy for This Project

| Category | Target | Key Evidence |
|---|---|---|
| Problem Definition | 18–20 | Clear problem statement, user personas (shoppers), measurable KPIs |
| Agentic Design | 23–25 | LangGraph star topology, supervisor + 4 specialists, justified orchestration |
| Quality & Grounding | 18–20 | ChromaDB RAG, Pydantic structured outputs, tool-grounded responses |
| Evaluation | 13–15 | 25-query LangSmith dataset, 4 evaluators, v1 vs v2 comparison |
| Technical | 9–10 | 8 tools, FastAPI, error handling, /v1 and /v2 endpoints |
| UX | 4–5 | Chat UI, AgentBadge, "Thinking" accordion with supervisor step |
| Documentation | 4–5 | architecture.md, evaluation_results.md, CLAUDE.md updated |
| **Total** | **89–100** | |
