# Spec: CoEvo Core and Benchmark Adapter Split

## Assumptions

1. The target development branch is `feature/split`.
2. The first implementation phase must preserve WildClawBench scoring behavior.
3. `coevo-core` should be open-source friendly and must not import benchmark runtimes.
4. WildClawBench and tau2 adapters are optional modules in the same repository for now.
5. tau2 integration optimizes prompt or agent behavior strategy, not executable task code.
6. tau2 evaluation criteria, gold actions, hidden assertions, and private benchmark answers must not be exposed to SG, Verifier, or Rubricator prompts except through sanitized oracle feedback.

## Objective

Split the current CoEvo implementation into a benchmark-independent algorithm core and benchmark-specific adapters. The split should make the system easier to open source, easier to reason about, and safer to extend with tau2 while preserving existing WildClawBench behavior.

The user is the repository maintainer and future open-source users who want to run the same CoEvo algorithm against different black-box benchmarks.

Success means:

- `coevo_core` owns algorithm orchestration, shared schemas, ranking, verification, receipt revision, persistence, reports, and cache policy.
- `coevo_adapters.wildclawbench` owns all WildClawBench runtime, task markdown, skill package materialization, `eval/run_batch.py`, score parsing, output discovery, and feedback extraction details.
- `coevo_adapters.tau2` owns all tau2 runtime, task selection, prompt injection, simulation execution, score mapping, trajectory sanitization, and feedback extraction details.
- Existing WildClawBench single-task runs produce the same score mapping and report fields after migration, modulo live LLM nondeterminism.
- tau2 can evaluate candidate prompt strategies as a black-box oracle and return `OracleScore` objects usable by the unchanged CoEvo ranking loop.

## Tech Stack

- Language: Python 3.12+ preferred, matching tau2; current AgentClawBench tests also run on Python 3.13.
- Test runner: `pytest`.
- Runtime LLM client: existing CoEvo `LLMClient` abstraction, later moved into `coevo_core.llm`.
- WildClawBench runtime: existing `eval/run_batch.py`.
- tau2 runtime: `/Users/user/Desktop/project/tau2-bench` package APIs:
  - `tau2.data_model.simulation.TextRunConfig`
  - `tau2.runner.build.build_environment`, `build_user`, and low-level orchestrator construction
  - `tau2.runner.simulation.run_simulation`
  - `tau2.evaluator.evaluator.EvaluationType`

## Commands

Install current AgentClawBench dependencies:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest
```

Run current CoEvo unit tests:

```bash
.venv/bin/python -m pytest tests/test_coevo_v2_schemas.py tests/test_coevo_v2_scoring_ranking.py tests/test_coevo_v2_prompts.py
```

Run current WildClawBench adapter tests:

```bash
.venv/bin/python -m pytest tests/test_coevo_v2_oracle_adapter.py tests/test_agentclawbench_algorithm_scripts.py
```

Run full local tests:

```bash
.venv/bin/python -m pytest tests
```

Run existing single-task WildClawBench flow:

```bash
.venv/bin/python scripts/run_agentclawbench_algorithm_task.py \
  --task tasks/03_Social_Interaction/03_Social_Interaction_task_2_chat_action_extraction.md \
  --exp-name 03_task2_chat_action_extraction_skill_evolution_v2
```

Run future split CLI:

```bash
.venv/bin/python -m coevo_cli run \
  --benchmark wildclawbench \
  --task tasks/03_Social_Interaction/03_Social_Interaction_task_2_chat_action_extraction.md \
  --exp-name 03_task2_chat_action_extraction_skill_evolution_v2
```

Run future tau2 adapter:

```bash
.venv/bin/python -m coevo_cli run \
  --benchmark tau2 \
  --tau2-root /Users/user/Desktop/project/tau2-bench \
  --domain airline \
  --task-ids 0,1,2,3,4 \
  --agent-llm gpt-4.1 \
  --user-llm gpt-4.1 \
  --exp-name tau2_airline_prompt_strategy
```

## Project Structure

Target layout:

```text
agentClawBench/
  coevo/                         # Compatibility layer during migration only
    __init__.py
    coordinator.py               # Re-export or delegate to coevo_core until removed
    oracle_adapter.py            # Re-export WildClawBench adapter until removed

  src/
    coevo_core/
      __init__.py
      candidates.py              # CandidateArtifact, CandidateKind, parsers
      config.py                  # CoevoConfig, OracleConfig, split config models
      errors.py                  # Typed core errors
      experiment.py              # Algorithm orchestration
      llm/
        __init__.py
        client.py                # LLMClient abstraction
        model_config.py
      ports.py                   # BenchmarkAdapter, PromptBuilder, Verifier ports
      prompts/
        __init__.py
        common.py
        openclaw_skill.py
        prompt_strategy.py
      ranking.py
      receipts.py                # Receipt schemas and validation
      reporting.py
      store.py                   # ExperimentStore and cache interfaces
      verifier.py

    coevo_adapters/
      __init__.py
      registry.py                # Adapter lookup by name
      wildclawbench/
        __init__.py
        adapter.py               # BenchmarkAdapter implementation
        feedback.py              # Existing experiment_trace logic
        score_reader.py          # score.json and public score mapping
        skill_runtime.py         # EvoSkill -> runtime dir
        task_loader.py           # markdown frontmatter loader/rewrite
      tau2/
        __init__.py
        adapter.py               # BenchmarkAdapter implementation
        config.py                # tau2 adapter config
        feedback.py              # Sanitized reward/trajectory summaries
        prompt_agent.py          # Prompt injection agent wrapper
        prompts.py               # tau2 SG/Verifier/Rubricator prompt builders
        score_mapper.py          # RewardInfo -> OracleScore
        task_loader.py           # tau2 task selection and safe task context

    coevo_cli/
      __init__.py
      main.py
      commands/
        run.py
        inspect.py

  tests/
    core/
    adapters/
      wildclawbench/
      tau2/
    contract/
```

During migration, imports from `coevo.*` remain supported by delegating to the new modules. That compatibility layer prevents existing scripts and tests from breaking while the internals move.

## Architecture

### Dependency Rule

Allowed dependencies:

```text
coevo_cli -> coevo_core
coevo_cli -> coevo_adapters.*

coevo_adapters.wildclawbench -> coevo_core
coevo_adapters.wildclawbench -> WildClawBench runtime files

coevo_adapters.tau2 -> coevo_core
coevo_adapters.tau2 -> tau2 runtime package

coevo_core -> Python stdlib and injected interfaces only
```

Forbidden dependencies:

```text
coevo_core -> coevo_adapters.*
coevo_core -> eval.run_batch
coevo_core -> tau2
coevo_core -> benchmark task directories
```

### Core Responsibility

`coevo_core` owns:

- Candidate group lifecycle.
- Mode A skill or prompt strategy updates.
- Mode B oracle evaluation orchestration.
- Receipt generation and revision.
- Verifier scoring against receipts.
- Rank alignment calculation.
- Candidate acceptance policy.
- Experiment state persistence.
- Cache key composition.
- Report model and generic report rendering.

`coevo_core` does not know how a benchmark executes.

### Adapter Responsibility

Each adapter owns:

- Loading benchmark tasks.
- Producing safe task context for prompts.
- Materializing candidates into benchmark runtime form.
- Running benchmark evaluations.
- Parsing benchmark outputs.
- Sanitizing public oracle feedback.
- Producing adapter-specific report sections.
- Validating benchmark-specific configuration.

Adapters do not own CoEvo mode scheduling, rank alignment, or receipt revision policy.

## Public Contracts

### CandidateArtifact

`CandidateArtifact` replaces benchmark-specific `EvoSkill` as the core candidate model.

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

CandidateKind = Literal["openclaw_skill", "prompt_strategy"]

@dataclass(frozen=True, order=True)
class CandidateKey:
    slot: int
    version: int

    def token(self) -> str:
        return f"s{self.slot:03d}_v{self.version:03d}"

@dataclass
class CandidateArtifact:
    key: CandidateKey
    kind: CandidateKind
    name: str
    files: dict[str, str] = field(default_factory=dict)
    prompt_block: str | None = None
    entrypoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Rules:

- `openclaw_skill` candidates must include `files["SKILL.md"]`, at least one `.py` file, and an `entrypoint`.
- `prompt_strategy` candidates must include a non-empty `prompt_block`.
- A candidate may carry adapter-specific metadata, but core acceptance logic cannot depend on adapter-specific metadata keys.

### BenchmarkTask

```python
@dataclass
class BenchmarkTask:
    task_id: str
    benchmark: str
    description: str
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Rules:

- `description` is safe to show to SG, Verifier, and Rubricator.
- `metadata` may contain private values, but prompt builders must use adapter-provided safe context rather than dumping metadata blindly.

### BenchmarkContext

```python
@dataclass
class BenchmarkContext:
    task: BenchmarkTask
    public_context: dict[str, Any]
    prompt_context: dict[str, Any]
    verifier_context: dict[str, Any]
    rubricator_context: dict[str, Any]
```

Rules:

- `public_context` is safe for reports.
- `prompt_context` is safe for SG prompts.
- `verifier_context` is safe for Verifier prompts.
- `rubricator_context` is safe for Rubricator prompts.
- Private oracle-only data must not appear in any of these dictionaries.

### BenchmarkAdapter

```python
from pathlib import Path
from typing import Protocol, Sequence

class BenchmarkAdapter(Protocol):
    name: str
    candidate_kind: CandidateKind

    def load_task(self, task_ref: str, config: AdapterConfig) -> BenchmarkTask:
        ...

    def build_context(
        self,
        task: BenchmarkTask,
        config: AdapterConfig,
    ) -> BenchmarkContext:
        ...

    def validate_candidate(self, candidate: CandidateArtifact) -> None:
        ...

    def materialize_candidate(
        self,
        task: BenchmarkTask,
        candidate: CandidateArtifact,
        work_dir: Path,
        config: AdapterConfig,
    ) -> MaterializedCandidate:
        ...

    def evaluate_batch(
        self,
        task: BenchmarkTask,
        candidates: Sequence[CandidateArtifact],
        config: OracleConfig,
        store: ExperimentStore,
    ) -> dict[CandidateKey, OracleScore]:
        ...

    def build_report_sections(
        self,
        task: BenchmarkTask,
        scores: dict[CandidateKey, OracleScore],
    ) -> list[ReportSection]:
        ...
```

Rules:

- `evaluate_batch` is batch-oriented for efficiency.
- Adapters may use internal concurrency.
- Core ranks the returned `OracleScore` objects after adapter evaluation.
- Adapter errors are raised as typed `AdapterError` subclasses with a stable `stage` field.

### OracleScore

```python
@dataclass
class OracleFeedback:
    summary: str = ""
    produced_artifacts: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    error_excerpt: str = ""
    trajectory_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class OracleScore:
    candidate: CandidateKey
    oracle_score: float
    oracle_pass: int
    rank: int = -1
    feedback: OracleFeedback = field(default_factory=OracleFeedback)
    output_dir: str = ""
```

Rules:

- `oracle_score` is normalized to `[0.0, 1.0]`.
- `oracle_pass` is `1` when `oracle_score >= oracle_threshold`, else `0`.
- `feedback` must be safe to pass to Rubricator and report rendering.
- Hidden labels, gold actions, ground-truth DB states, private assertions, and secrets must be redacted.

## WildClawBench Adapter

### Goal

Move the current `coevo/oracle_adapter.py`, task loader, skill package runtime, and score summarization behind `coevo_adapters.wildclawbench` without changing behavior.

### Behavior Preservation Requirements

The migrated adapter must preserve:

- `eval/run_batch.py` command shape.
- `--task`, `--model`, `--models-config`, `--rate-limit-retries`, `--rate-limit-wait-seconds`, and `--skill-dir` flags.
- `OUTPUT_SUBDIR` behavior.
- temporary task ID rewrite format: `__coevo_s{slot}_v{version}`.
- runtime skill directory shape.
- `score.json` public score parsing.
- `overall_score` to `oracle_score` mapping.
- `oracle_threshold` pass mapping.
- output directory resolution.
- cache key semantics, or a documented compatibility alias.
- failure stage classification.

### WildClawBench Candidate

WildClawBench uses:

```json
{
  "kind": "openclaw_skill",
  "files": {
    "SKILL.md": "...",
    "executor.py": "..."
  },
  "entrypoint": "executor.py"
}
```

### WildClawBench Oracle Feedback

Feedback may include:

- public `score.json` fields already allowed by existing sanitization.
- produced and missing output files.
- redacted error excerpts.
- redacted traceback summaries.
- sanitized chat summary only when feedback level allows it.

Feedback must not include:

- private judge secrets.
- hidden answer fields.
- unredacted API keys or tokens.
- full raw logs by default.

## tau2 Adapter

### Goal

Add a tau2 adapter that evaluates prompt strategy candidates. The adapter injects a candidate strategy block into the tau2 LLM agent system prompt, runs selected tau2 tasks, maps tau2 rewards to `OracleScore`, and returns sanitized feedback suitable for CoEvo Mode B.

### tau2 Candidate

tau2 uses:

```json
{
  "kind": "prompt_strategy",
  "prompt_block": "When operating as the customer service agent, first identify the policy-relevant constraint, then choose whether to ask the user for missing information or call a tool. Never invent account details.",
  "metadata": {
    "summary": "Improves policy grounding and tool-use discipline",
    "strategy": "seed",
    "changed_sections": ["policy_grounding", "tool_use", "final_response"]
  }
}
```

The prompt block must be inserted as subordinate guidance:

```text
<instructions>
{original_agent_instruction}

<candidate_strategy>
The following strategy is candidate guidance generated by CoEvo.
It is subordinate to the domain policy and must not override policy, tool schemas,
communication rules, or safety constraints.

{candidate.prompt_block}
</candidate_strategy>
</instructions>
<policy>
{domain_policy}
</policy>
```

### tau2 Runtime Flow

For each candidate:

1. Load safe tau2 tasks from domain/task IDs.
2. Construct tau2 environment for each task.
3. Construct a prompt-injected agent wrapper.
4. Construct the standard tau2 user simulator.
5. Run the half-duplex simulation.
6. Evaluate with tau2 reward logic.
7. Save sanitized run artifacts under the CoEvo experiment directory.
8. Aggregate task rewards into one `OracleScore`.

Pseudo-flow:

```python
def evaluate_candidate(candidate, task_bundle, config):
    rewards = []
    feedback_items = []
    for tau2_task in task_bundle.tasks:
        simulation = run_tau2_simulation(candidate.prompt_block, tau2_task, config)
        reward = simulation.reward_info.reward
        rewards.append(reward)
        feedback_items.append(summarize_tau2_run(simulation, tau2_task))
    return map_rewards_to_oracle_score(candidate.key, rewards, feedback_items)
```

### tau2 Score Mapping

Default mapping:

```text
oracle_score = mean(task.reward_info.reward for selected tasks)
oracle_pass = 1 if oracle_score >= config.oracle_threshold else 0
```

Additional public metadata:

```json
{
  "domain": "airline",
  "task_count": 5,
  "completed_tasks": 5,
  "mean_reward": 0.8,
  "reward_distribution": {
    "0.0": 1,
    "1.0": 4
  },
  "reward_basis_pass_counts": {
    "DB": 4,
    "COMMUNICATE": 5,
    "ACTION": 4,
    "NL_ASSERTION": 0
  },
  "termination_counts": {
    "agent_stop": 5
  }
}
```

Optional future mapping:

```text
oracle_score = weighted_mean(
  reward,
  weights = task_difficulty_or_domain_weights
)
```

Weighted mapping is out of scope for the first tau2 adapter unless existing tau2 task metadata already supplies stable weights.

### tau2 Feedback Sanitization

Allowed feedback:

- aggregate score and pass ratio.
- reward breakdown pass/fail counts.
- termination reason counts.
- number of tool errors.
- tool call names and error categories, without full arguments by default.
- short sanitized assistant/user transcript summary.
- policy category tags when derived from public domain policy.
- failure categories such as `db_mismatch`, `missing_communication`, `wrong_tool_sequence`, `premature_stop`, `protocol_violation`, `tool_error`, `timeout`.

Disallowed feedback:

- exact `evaluation_criteria.actions`.
- gold action arguments.
- gold or target DB states.
- hidden `env_assertions` details when they reveal target values.
- full raw task user scenario in SG update prompts.
- full trajectory with specific private values unless redacted.
- anything from `.env`.

### tau2 Task Context for Prompts

The adapter builds four contexts.

#### Public Report Context

Safe for reports:

```json
{
  "benchmark": "tau2",
  "domain": "airline",
  "task_ids": ["0", "1", "2", "3", "4"],
  "task_count": 5,
  "agent_mode": "half_duplex",
  "evaluation_type": "all",
  "candidate_kind": "prompt_strategy"
}
```

#### SG Prompt Context

Safe for Skill Generator:

```json
{
  "benchmark": "tau2",
  "candidate_kind": "prompt_strategy",
  "domain": "airline",
  "agent_instruction_template": "You are a customer service agent...",
  "domain_policy_summary": "Policy text or adapter-created summary.",
  "tool_schema_summary": [
    {
      "name": "get_reservation",
      "description": "Look up a reservation.",
      "required_args": ["reservation_id"]
    }
  ],
  "communication_rules": [
    "Each turn must be either a user-facing message or a tool call, not both.",
    "Always return valid JSON only when making model responses through tau2 tool interface."
  ],
  "optimization_goal": "Improve average tau2 reward without violating policy or hardcoding task-specific answers.",
  "known_failure_summary": {
    "reward_basis_fail_counts": {"DB": 2, "COMMUNICATE": 1},
    "failure_categories": ["missing_required_communication", "tool_error"],
    "oracle_summary": "avg_reward=0.6; common failures: DB and communication"
  }
}
```

SG must not receive:

- task-specific expected actions.
- exact private user data from task scenarios.
- hidden assertions.
- target final DB state.

#### Verifier Prompt Context

Safe for Verifier:

```json
{
  "candidate_kind": "prompt_strategy",
  "domain": "airline",
  "domain_policy_summary": "...",
  "tool_schema_summary": [...],
  "candidate_prompt_block": "...",
  "receipt": {...},
  "mode": "mode_a"
}
```

Verifier judges the prompt strategy as static evidence. It does not predict exact tau2 task success, and it does not see oracle results in Mode A.

#### Rubricator Prompt Context

Safe for Rubricator:

```json
{
  "benchmark": "tau2",
  "domain": "airline",
  "candidate_kind": "prompt_strategy",
  "domain_policy_summary": "...",
  "tool_schema_summary": [...],
  "oracle_scores": {
    "s000_v001": {
      "oracle_score": 0.8,
      "oracle_pass": 1,
      "feedback": {
        "summary": "avg_reward=0.8; failures: DB=1",
        "metadata": {
          "reward_basis_pass_counts": {"DB": 4, "COMMUNICATE": 5}
        }
      }
    }
  },
  "verifier_scores": {...},
  "rank_mismatches": [...]
}
```

Rubricator sees oracle ranks and sanitized aggregate feedback, not hidden oracle implementation details.

## tau2 Prompt Contracts

### tau2 SG Seed Prompt

System:

```text
You are an expert prompt-strategy engineer for tau2 customer-service agents.
Return exactly one JSON object and nothing else.
Do not wrap the JSON in markdown fences.
```

User:

```text
[Benchmark]
tau2

[Candidate Type]
prompt_strategy

[Safe Task Context]
{sg_prompt_context_json}

[Instruction]
Generate one candidate prompt strategy block for the tau2 agent.
The block will be inserted below the original tau2 agent instruction and above the domain policy.
It is subordinate to the domain policy, tool schemas, and communication protocol.

[Required JSON Schema]
{
  "package_mode": "full",
  "candidate_kind": "prompt_strategy",
  "prompt_block": "string",
  "metadata": {
    "summary": "short string",
    "strategy": "seed",
    "changed_sections": ["policy_grounding", "tool_use"]
  }
}

[Rules]
- Do not mention hidden evaluation criteria, gold actions, expected DB states, or benchmark-private labels.
- Do not hardcode task-specific user IDs, reservation IDs, order IDs, account IDs, or expected answers.
- Do not override the domain policy.
- Do not tell the agent to ignore user instructions, system instructions, tools, or policies.
- Emphasize reusable behavior: policy grounding, clarification, tool-use discipline, final communication, and error recovery.
- Keep prompt_block under 1200 words.
- The prompt_block must be directly usable as system-prompt guidance.
- Return JSON only.
```

### tau2 SG Variant Prompt

System:

```text
You are an expert prompt-strategy engineer for tau2 customer-service agents.
Generate one meaningful variant of the seed prompt strategy.
Return exactly one JSON object and nothing else.
```

User:

```text
[Safe Task Context]
{sg_prompt_context_json}

[Seed Candidate]
{candidate_json}

[Variant Slot]
{slot}

[Instruction]
Create a standalone prompt strategy variant with a genuinely different behavioral emphasis.

[Required JSON Schema]
{
  "package_mode": "full",
  "candidate_kind": "prompt_strategy",
  "prompt_block": "string",
  "metadata": {
    "summary": "short string",
    "strategy": "variant",
    "variant_focus": "clarification | tool_sequence | policy_grounding | communication",
    "changed_sections": ["string"]
  }
}

[Rules]
- Preserve safety and policy subordination.
- Do not simply rename or reorder the seed.
- Choose a distinct strategy focus.
- Do not include task-specific expected answers or hidden labels.
- Return JSON only.
```

### tau2 SG Mode A Update Prompt

System:

```text
You are the CoEvo Skill Generator for tau2 prompt strategies.
Improve one prompt strategy under a fixed receipt.
Return exactly one JSON object and nothing else.
```

User:

```text
[Safe Task Context]
{sg_prompt_context_json}

[Current Candidate]
{candidate_json}

[Fixed Receipt]
{receipt_json}

[Verifier Result Under Fixed Receipt]
{verifier_score_json}

[Update Objective]
Improve the candidate prompt strategy to address verifier misses under the fixed receipt.
This update will be accepted only if the same verifier score does not decrease.

[Required JSON Schema]
{
  "package_mode": "full",
  "candidate_kind": "prompt_strategy",
  "prompt_block": "string",
  "metadata": {
    "summary": "short update summary",
    "strategy": "mode_a_update",
    "targeted_rubrics": ["r1"],
    "changed_sections": ["string"],
    "expected_effect": "string"
  }
}

[Rubric Hit Semantics]
- Positive-point false: add the missing merit.
- Positive-point true: preserve it.
- Negative-point true: remove the flaw.
- Negative-point false: keep it absent.

[Rules]
- metadata.targeted_rubrics must contain at least one current miss or penalty.
- Do not change the receipt.
- Do not mention oracle scores.
- Do not hardcode hidden task answers, expected actions, or private values.
- Keep prompt_block under 1200 words.
- Return JSON only.
```

### tau2 Verifier Init/Scoring Prompt

The Verifier scores prompt strategies against a receipt. It is intentionally static and evidence-based: it reads the candidate prompt block and safe context, then judges whether the prompt likely encourages the required reusable behavior.

System:

```text
You are an expert evaluator of tau2 customer-service prompt strategies.
You receive safe benchmark context, one candidate prompt strategy, and binary signed-point rubrics.
Judge only observable evidence in the candidate prompt and safe context.
Return valid JSON only.
```

User:

```text
[Safe Verifier Context]
{verifier_context_json}

[Candidate Prompt Strategy]
{candidate_json}

[Receipt]
{receipt_json}

[Required JSON Schema]
{
  "criterion_hits": {"r1": true},
  "rationale": "short explanation",
  "raw_score": 0
}

[Rules]
- For positive-point criteria, true means the merit is present in the prompt strategy.
- For negative-point criteria, true means the flaw is present in the prompt strategy.
- Evaluate every rubric independently.
- Do not infer hidden oracle outcomes or private task labels.
- Do not use oracle scores in Mode A.
- Give credit only for concrete guidance likely to affect tau2 agent behavior.
- Penalize prompt strategies that override policy, expose hidden benchmark assumptions, ask the model to ignore tool schemas, or hardcode task-specific values.
- criterion_hits keys must exactly match receipt.rubrics[*].rubric_id.
- raw_score must equal the signed sum of all criteria judged true.
- rationale must be under 120 words.
```

### tau2 Initial Rubricator Prompt

The initial receipt should evaluate reusable prompt-strategy quality, not benchmark hidden answers.

System:

```text
You are an expert rubric designer for tau2 prompt-strategy candidates.
Generate binary signed-point rubrics that can evaluate reusable customer-service agent prompt strategies.
Return valid JSON only.
```

User:

```text
[Safe Rubricator Context]
{rubricator_context_json}

[Instruction]
Generate a receipt for ranking tau2 prompt_strategy candidates before oracle execution.

[Required JSON Schema]
{
  "metadata": {
    "benchmark": "tau2",
    "candidate_kind": "prompt_strategy",
    "domain": "airline"
  },
  "rubrics": [
    {
      "rubric_id": "r1",
      "category": "policy_grounding",
      "criterion": "binary evaluable criterion",
      "points": 1
    }
  ],
  "maximum_score": 1,
  "minimum_score": -1,
  "baseline_score": 0
}

[Rules]
- Generate 6 to 14 binary criteria.
- Points must be signed integers only: positive 1..5, negative -5..-1.
- Cover policy grounding, tool-use discipline, clarification behavior, communication completeness, protocol compliance, and anti-overfitting.
- Do not include hidden evaluation criteria, gold actions, private task data, or benchmark answers.
- Do not create multiple threshold variants for the same criterion.
- maximum_score and minimum_score must match the signed point bounds.
- Return JSON only.
```

### tau2 Rubricator Revision Prompt

The revision prompt aligns local verifier ranking with tau2 oracle ranking using sanitized aggregate evidence.

System:

```text
You are an expert rubric reviser for tau2 prompt-strategy candidates.
Improve the receipt so verifier ranking better matches public oracle evidence.
Return valid JSON only.
```

User:

```text
[Safe Rubricator Context]
{rubricator_context_json}

[Current Receipt]
{receipt_json}

[Candidate Evidence]
{candidate_evidence_json}

[Verifier Scores]
{verifier_scores_json}

[Oracle Scores]
{sanitized_oracle_scores_json}

[Rank Comparison]
{
  "verifier_rank": ["s001_v001", "s000_v001"],
  "oracle_rank": ["s000_v001", "s001_v001"],
  "rank_alignment": 0.5,
  "rank_mismatches": [...]
}

[Required JSON Schema]
{receipt_schema_json}

[Rules]
- Optimize rank alignment, not absolute oracle score values.
- Treat oracle scores as sparse public feedback, not hidden labels.
- Prefer reweighting existing criteria before adding new criteria.
- Add a criterion only when safe public evidence shows a missing reusable prompt-strategy factor.
- Remove criteria only when redundant, unsupported, not binary-evaluable, or contradicted by safe evidence.
- Do not infer hidden tau2 evaluator internals, gold actions, target DB states, or private assertions.
- Preserve binary evaluability.
- Do not overfit to one candidate or one task ID.
- Return a complete receipt, not a patch.
- Points must remain signed integers from -5..-1 or 1..5.
```

## tau2 Result Presentation

### Files

Each tau2 experiment writes:

```text
<exp_dir>/
  config.json
  task_spec.json
  summary.json
  summary.md
  report.md
  report.html
  events.jsonl
  candidates/
    initial/
    outer_000_mode_a_000/
  oracle_scores/
    outer_000_mode_b_batch.json
  tau2_runs/
    outer_000/
      s000_v001/
        task_<id>/
          simulation.json
          reward_info.json
          public_feedback.json
          llm_debug/              # optional, if enabled
  round_states/
```

### Summary JSON

```json
{
  "benchmark": "tau2",
  "domain": "airline",
  "candidate_kind": "prompt_strategy",
  "task_count": 5,
  "best_candidate": "s000_v002",
  "best_candidate_name": "tau2_airline_prompt_strategy_seed",
  "best_oracle_score": 0.8,
  "oracle_pass_ratio": 0.5,
  "final_receipt_version": 3,
  "last_rank_alignment": 0.75,
  "active_candidate_keys": ["s000_v002", "s001_v001"],
  "stop_reason": "outer_rounds_exhausted",
  "elapsed_seconds": 123.45
}
```

### Report Sections

The tau2 report adds:

- Benchmark configuration.
- Domain and task set.
- Candidate prompt strategy table.
- Oracle score table.
- Reward basis pass/fail table.
- Common failure categories.
- Rank alignment over rounds.
- Final best prompt block.
- Sanitization note explaining that hidden evaluation details were excluded.

Example table:

```markdown
| Candidate | Oracle | Pass | DB Pass | Comm Pass | Action Pass | Termination | Failure Summary |
|---|---:|---:|---:|---:|---:|---|---|
| s000_v002 | 0.80 | 1 | 4/5 | 5/5 | 4/5 | agent_stop=5 | db_mismatch=1 |
```

## Code Style

Use narrow dataclasses and injected collaborators. Keep parsing at boundaries and core logic on typed objects.

Example:

```python
class Tau2Adapter:
    name = "tau2"
    candidate_kind = "prompt_strategy"

    def __init__(self, runner: Tau2Runner, mapper: Tau2ScoreMapper) -> None:
        self._runner = runner
        self._mapper = mapper

    def validate_candidate(self, candidate: CandidateArtifact) -> None:
        if candidate.kind != "prompt_strategy":
            raise AdapterError("tau2 requires prompt_strategy candidates")
        if not candidate.prompt_block or not candidate.prompt_block.strip():
            raise AdapterError("tau2 prompt_block must be non-empty")

    def evaluate_batch(
        self,
        task: BenchmarkTask,
        candidates: Sequence[CandidateArtifact],
        config: OracleConfig,
        store: ExperimentStore,
    ) -> dict[CandidateKey, OracleScore]:
        scores = {}
        for candidate in candidates:
            self.validate_candidate(candidate)
            outputs = self._runner.run_candidate(task, candidate, config, store)
            scores[candidate.key] = self._mapper.to_oracle_score(candidate.key, outputs)
        return scores
```

Conventions:

- Protocols live in `coevo_core.ports`.
- Core dataclasses are benchmark-neutral.
- Adapter classes are named `<Benchmark>Adapter`.
- Functions that parse external data use `parse_` or `load_` prefixes.
- Functions that map safe internal structures use `to_` prefixes.
- No core function should reach into adapter-specific metadata.

## Testing Strategy

### Core Unit Tests

Location:

```text
tests/core/
```

Coverage:

- Candidate validation.
- Receipt validation.
- Rank alignment.
- Mode A acceptance.
- Cache key composition.
- Experiment state persistence.
- Prompt JSON parser and repair contracts.

### Adapter Contract Tests

Location:

```text
tests/contract/
```

Coverage:

- Every adapter implements `BenchmarkAdapter`.
- `evaluate_batch` returns stable `OracleScore` shape.
- `build_context` does not leak disallowed fields.
- Candidate kind mismatch raises typed errors.

### WildClawBench Regression Tests

Location:

```text
tests/adapters/wildclawbench/
```

Coverage:

- Migrated adapter command equals old command.
- Runtime skill directory equals old directory shape.
- Public score parsing equals old score parsing.
- Failure stage classification equals old classification.
- Existing tests from `tests/test_coevo_v2_oracle_adapter.py` still pass through compatibility imports.

### tau2 Unit Tests

Location:

```text
tests/adapters/tau2/
```

Coverage:

- Prompt injection preserves original tau2 policy and inserts candidate as subordinate guidance.
- SG prompt context excludes hidden evaluation fields.
- Verifier prompt includes candidate prompt and receipt but not oracle scores in Mode A.
- Rubricator revision prompt includes sanitized oracle ranks and aggregate feedback but not gold actions or target DB states.
- Reward mapping computes mean reward and pass threshold correctly.
- Feedback sanitizer redacts secrets and private values.
- Adapter validates `prompt_strategy` candidates.

### tau2 Integration Tests

Location:

```text
tests/adapters/tau2/test_tau2_integration.py
```

Coverage:

- Optional, gated by `TAU2_INTEGRATION_TEST_ENABLED=1`.
- Uses a tiny mock or tau2 `mock` domain run when available.
- Verifies one candidate can run end-to-end and produce `OracleScore`.

Command:

```bash
TAU2_INTEGRATION_TEST_ENABLED=1 .venv/bin/python -m pytest tests/adapters/tau2/test_tau2_integration.py
```

## Boundaries

### Always

- Keep `coevo_core` free of benchmark imports.
- Keep WildClawBench behavior unchanged in the first migration phase.
- Validate candidate shape at adapter boundaries.
- Redact tau2 feedback before passing it to SG, Verifier, Rubricator, or reports.
- Keep `evaluate_batch` as the oracle adapter entrypoint for efficiency.
- Preserve compatibility imports from `coevo.*` until scripts are migrated.
- Run focused tests after each migration slice.

### Ask First

- Changing WildClawBench scoring semantics.
- Changing `score.json` parsing rules.
- Changing `oracle_threshold` defaults.
- Changing cache key compatibility.
- Adding new runtime dependencies.
- Moving files out of the repository root in a way that breaks existing scripts.
- Exposing more tau2 trajectory detail to prompts.

### Never

- Expose tau2 gold actions, target DB state, hidden assertions, or private labels to SG, Verifier, Rubricator, or reports.
- Hardcode benchmark answers into generated candidates.
- Let `coevo_core` import `tau2` or `eval.run_batch`.
- Remove existing WildClawBench tests during migration.
- Commit `.env`, API keys, raw private benchmark outputs, or unredacted logs.
- Rewrite the CoEvo algorithm while doing the adapter split.

## Success Criteria

The split is complete when:

1. `feature/split` contains this spec and implementation follows it.
2. `coevo_core` imports no benchmark-specific modules.
3. WildClawBench runs through `coevo_adapters.wildclawbench` and produces the same `OracleScore` mapping as the old `coevo.oracle_adapter`.
4. Existing WildClawBench scripts keep working through compatibility imports or documented replacements.
5. tau2 runs through `coevo_adapters.tau2` with `prompt_strategy` candidates.
6. tau2 SG, Verifier, and Rubricator prompts use only adapter-provided safe contexts.
7. tau2 reports show score tables, rank alignment, best prompt block, and sanitized failure summaries.
8. Core, contract, WildClawBench regression, and tau2 unit tests pass.

## Implementation Plan

### Phase 1: Core Contract Extraction

1. Create `coevo_core` schemas and ports.
2. Add compatibility aliases from existing `coevo.schemas_v2` to new schemas where safe.
3. Add contract tests for `CandidateArtifact`, `OracleScore`, and `BenchmarkAdapter`.

Verification:

```bash
.venv/bin/python -m pytest tests/contract tests/core
```

### Phase 2: WildClawBench Adapter Move

1. Move current oracle logic into `coevo_adapters.wildclawbench`.
2. Keep old `coevo.oracle_adapter` as a delegating compatibility module.
3. Preserve command construction, score parsing, output resolution, failure classification, and cache behavior.
4. Run old adapter tests and compare representative serialized outputs.

Verification:

```bash
.venv/bin/python -m pytest tests/test_coevo_v2_oracle_adapter.py tests/test_agentclawbench_algorithm_scripts.py
```

### Phase 3: Core Coordinator Adapter Injection

1. Update experiment orchestration to receive a `BenchmarkAdapter`.
2. Replace direct `evaluate_skill_batch` call with `adapter.evaluate_batch`.
3. Keep WildClawBench as the default adapter for compatibility.
4. Add tests with a fake adapter to verify Mode B integration.

Verification:

```bash
.venv/bin/python -m pytest tests/core tests/test_coevo_v2_coordinator.py
```

### Phase 4: tau2 Adapter Foundation

1. Add tau2 adapter config and task loader.
2. Add prompt-injected tau2 agent wrapper.
3. Add reward mapper and feedback sanitizer.
4. Add tau2 prompt builders for SG, Verifier, and Rubricator.
5. Add tau2 unit tests for leakage prevention and score mapping.

Verification:

```bash
.venv/bin/python -m pytest tests/adapters/tau2
```

### Phase 5: tau2 End-to-End

1. Add CLI support for `--benchmark tau2`.
2. Run small tau2 domain/task set.
3. Persist tau2-specific artifacts under `tau2_runs`.
4. Render tau2 report sections.

Verification:

```bash
TAU2_INTEGRATION_TEST_ENABLED=1 .venv/bin/python -m pytest tests/adapters/tau2/test_tau2_integration.py
```

### Phase 6: Documentation and Open-Source Cleanup

1. Document architecture and adapter authoring guide.
2. Add sample fake adapter.
3. Add README section for WildClawBench and tau2 optional extras.
4. Confirm no private benchmark data or secrets are exposed.

## Task Breakdown

- [ ] Task: Add core contracts
  - Acceptance: `CandidateArtifact`, `BenchmarkTask`, `BenchmarkContext`, `OracleScore`, and `BenchmarkAdapter` exist in `coevo_core`.
  - Verify: `.venv/bin/python -m pytest tests/contract`
  - Files: `src/coevo_core/candidates.py`, `src/coevo_core/ports.py`, `src/coevo_core/scores.py`, `tests/contract/test_adapter_contract.py`

- [ ] Task: Add WildClawBench adapter wrapper without behavior changes
  - Acceptance: New adapter delegates to existing functions and old tests pass.
  - Verify: `.venv/bin/python -m pytest tests/test_coevo_v2_oracle_adapter.py`
  - Files: `src/coevo_adapters/wildclawbench/adapter.py`, `coevo/oracle_adapter.py`, `tests/adapters/wildclawbench/test_regression.py`

- [ ] Task: Inject adapter into coordinator
  - Acceptance: Mode B uses `BenchmarkAdapter.evaluate_batch`; WildClawBench remains default.
  - Verify: `.venv/bin/python -m pytest tests/test_coevo_v2_coordinator.py`
  - Files: `src/coevo_core/experiment.py`, `coevo/coordinator.py`, `tests/core/test_experiment_adapter.py`

- [ ] Task: Add tau2 prompt-strategy schema and parser
  - Acceptance: SG outputs parse into `prompt_strategy` candidates and invalid shapes fail explicitly.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_candidate_parser.py`
  - Files: `src/coevo_adapters/tau2/prompts.py`, `src/coevo_core/candidates.py`, `tests/adapters/tau2/test_candidate_parser.py`

- [ ] Task: Add tau2 prompt builders
  - Acceptance: SG, Verifier, and Rubricator prompt builders include required safe context and exclude disallowed fields.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_prompts.py`
  - Files: `src/coevo_adapters/tau2/prompts.py`, `tests/adapters/tau2/test_prompts.py`

- [ ] Task: Add tau2 prompt-injected agent wrapper
  - Acceptance: Candidate prompt block is subordinate to tau2 original instructions and policy remains intact.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_prompt_agent.py`
  - Files: `src/coevo_adapters/tau2/prompt_agent.py`, `tests/adapters/tau2/test_prompt_agent.py`

- [ ] Task: Add tau2 score mapper and feedback sanitizer
  - Acceptance: RewardInfo objects map to mean `OracleScore`; feedback redacts private fields.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_score_mapper.py tests/adapters/tau2/test_feedback.py`
  - Files: `src/coevo_adapters/tau2/score_mapper.py`, `src/coevo_adapters/tau2/feedback.py`, `tests/adapters/tau2/test_score_mapper.py`, `tests/adapters/tau2/test_feedback.py`

- [ ] Task: Add tau2 adapter evaluate_batch
  - Acceptance: Adapter can evaluate a fake tau2 runner in batch and return ranked-compatible `OracleScore` objects.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_adapter.py`
  - Files: `src/coevo_adapters/tau2/adapter.py`, `tests/adapters/tau2/test_adapter.py`

- [ ] Task: Add CLI benchmark selection
  - Acceptance: `--benchmark wildclawbench` uses old behavior; `--benchmark tau2` validates tau2-specific args.
  - Verify: `.venv/bin/python -m pytest tests/test_agentclawbench_algorithm_scripts.py tests/adapters/tau2/test_cli.py`
  - Files: `src/coevo_cli/main.py`, `src/coevo_cli/commands/run.py`, `scripts/run_agentclawbench_algorithm_task.py`, `tests/adapters/tau2/test_cli.py`

- [ ] Task: Add tau2 report sections
  - Acceptance: Report includes tau2 score table, reward basis summary, best prompt block, and sanitization note.
  - Verify: `.venv/bin/python -m pytest tests/adapters/tau2/test_report.py`
  - Files: `src/coevo_adapters/tau2/report.py`, `src/coevo_core/reporting.py`, `tests/adapters/tau2/test_report.py`

## Risks and Mitigations

### Risk: WildClawBench scoring changes accidentally

Mitigation:

- Start by delegating to existing functions.
- Add snapshot tests for command construction and score mapping.
- Preserve compatibility imports.

### Risk: Core abstraction becomes too broad

Mitigation:

- Keep `BenchmarkAdapter` narrow.
- Put prompt construction into adapter-specific prompt builders.
- Avoid adding methods until a second adapter requires them.

### Risk: tau2 prompt leaks hidden task answers

Mitigation:

- Build explicit safe contexts.
- Add leakage tests with sentinel private fields.
- Centralize redaction in `coevo_adapters.tau2.feedback`.

### Risk: tau2 execution is slow

Mitigation:

- Keep `evaluate_batch`.
- Reuse loaded tasks and static domain context.
- Cache candidate/task/model results.
- Allow adapter-local concurrency with conservative defaults.

### Risk: Report formats diverge

Mitigation:

- Keep common report schema in core.
- Let adapters contribute typed `ReportSection` objects.
- Preserve existing WildClawBench fields.

## Open Questions

1. Should tau2 adapter default to one domain (`airline`) or require `--domain` explicitly?
2. Should tau2 task selection use `task_ids`, `num_tasks`, `task_split_name`, or all three?
3. Should tau2 integration tests use the real tau2 `mock` domain or a fake runner by default?
4. Should reports include redacted per-task transcript summaries by default, or only at higher feedback levels?
5. Should `coevo_core` live under `src/` immediately, or should we first keep root-level packages to minimize packaging changes?
