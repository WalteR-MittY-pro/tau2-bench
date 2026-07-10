from __future__ import annotations

from typing import Optional

from tau2.agent.llm_agent import AGENT_INSTRUCTION, LLMAgent, LLMAgentStateType
from tau2.environment.tool import Tool


SYSTEM_PROMPT_SKILL_INJECTED = """
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
<skill_injected_context>
{prompt_context}
</skill_injected_context>
""".strip()


class SkillInjectedAgent(LLMAgent[LLMAgentStateType]):
    def __init__(
        self,
        tools: list[Tool],
        domain_policy: str,
        llm: str,
        llm_args: Optional[dict] = None,
        tau2_prompt_context: dict | None = None,
    ) -> None:
        self.prompt_context = _load_prompt_context(tau2_prompt_context)
        super().__init__(
            tools=tools,
            domain_policy=domain_policy,
            llm=llm,
            llm_args=llm_args,
        )

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT_SKILL_INJECTED.format(
            agent_instruction=AGENT_INSTRUCTION,
            domain_policy=self.domain_policy,
            prompt_context=self.prompt_context,
        )


def create_skill_injected_agent(tools, domain_policy, **kwargs):
    return SkillInjectedAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
        tau2_prompt_context=kwargs.get("tau2_prompt_context"),
    )


def _load_prompt_context(context: dict | None) -> str:
    if not context:
        raise ValueError("skill_injected requires tau2_prompt_context")
    if context.get("kind") != "tau2_prompt_context":
        raise ValueError("skill_injected requires tau2_prompt_context")
    prompt_payload_path = context.get("prompt_payload_path")
    if not prompt_payload_path:
        raise ValueError("tau2_prompt_context requires prompt_payload_path")

    import json
    from pathlib import Path

    payload = json.loads(Path(prompt_payload_path).read_text(encoding="utf-8"))
    prompt = str(payload.get("prompt", ""))
    return prompt
