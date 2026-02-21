## 1. Core Goal

You are designing a **PDF auto-filling AI system** where the primary objectives are:

* **Accuracy**
* **Speed**
* **Ease of use**

You want to introduce *agentic behavior* only where it meaningfully improves usability, without sacrificing reliability.

---

## 2. Fundamental Design Position (Final Consensus)

### ✅ Deterministic by default

### ✅ Agentic only on uncertainty or failure

> The system should be **deterministic as a baseline**, and the **Orchestrator consults an Agent only when validation fails or ambiguity exists**.

This hybrid design is the correct, production-grade approach.

---

## 3. What Is Dynamic vs Deterministic in Your System

### Dynamic (Agentic)

* **Labeling**: what a field represents (semantic classification)
* **Positioning**: bounding boxes / alignment when layout varies
* **Recovery suggestions** when validation fails

### Deterministic

* Preprocessing (rendering, OCR selection)
* Validation (geometry, schema, required fields)
* Value binding
* PDF writing
* State management
* Auditing, retries, stop conditions

---

## 4. Roles and Responsibilities (Clear Separation)

### Orchestrator (Use Case / Control Plane)

* Owns execution flow and state
* Runs deterministic steps
* Validates results
* Decides *when* to ask an Agent
* Applies agent proposals through Services
* Enforces limits (retries, cost, time)

### Agent

* **Only thinks / proposes**
* Never commits side effects
* Outputs **structured proposals**, not final data
* Used for:

  * Field detection & labeling proposals
  * Positioning fixes
  * Recovery actions after validation failure

### Service

* Owns **domain correctness**
* Validates, normalizes, and commits data
* Returns **canonical domain data**
* Uses Tools internally
* Is deterministic and testable

### Tool

* Performs **mechanical operations**
* No business rules
* No decision logic
* Examples: OCR, PDF writer, storage, API calls

---

## 5. Correct Call Relationship (Not a Simple Chain)

❌ Incorrect mental model:

```
Orchestrator → Agent → Service → Tool
```

✅ Correct model:

```
Orchestrator
 ├─ consults Agent (proposal only)
 ├─ validates proposal
 └─ invokes Service (execution)
        └─ Service uses Tool
```

> **Agents are not in the execution chain.**
> They are consulted decision helpers.

---

## 6. Why Service and Tool Must Be Separate (Encapsulation)

This is **not over-engineering**, it is **responsibility encapsulation**:

* **Tool** encapsulates *power* (can do things)
* **Service** encapsulates *responsibility* (should it be done, is it correct)

This separation is mandatory because:

* Agents are probabilistic and untrusted
* Side effects must be guarded
* Validation, rollback, and audit must be deterministic

**Rule of thumb**:

> If a Service adds no semantic value beyond calling a Tool, don’t create it.

---

## 7. Validation-Driven Agent Invocation (Key Pattern)

The Orchestrator follows this loop:

1. Run deterministic step
2. Validate result
3. If valid → proceed
4. If invalid → ask Agent:

   * *Why did this fail?*
   * *What safe recovery action should be attempted?*
5. Validate proposal
6. Apply fix deterministically
7. Re-validate
8. Stop on success, user confirmation, or bounded failure

This keeps latency, cost, and risk bounded.

---

## 8. Accuracy, Speed, and Agentic Trade-offs (Scientific View)

* **Deterministic flows**

  * Faster
  * Lower variance
  * Higher accuracy on known templates
* **Agentic flows**

  * Higher flexibility
  * Higher variance
  * Slower
  * Better recall on unseen documents

**Optimal strategy**:

* Use agentic logic only where input entropy is high
* Cache templates and revert to deterministic mode once stabilized

---

## 9. Final Architecture Principle

> **Dynamic components propose.
> Deterministic components decide and commit.**

This design:

* maximizes accuracy
* minimizes latency
* keeps the system easy to use
* scales safely in production

