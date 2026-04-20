from __future__ import annotations

import json


class PromptEngine:
    """Build standardized reasoning prompts for Sopotek Quant System's reasoning engine."""

    PROMPT_VERSION = "sopotek-reasoning-v1"

    def build_messages(self, context, *, mode="assistive"):
        """Build a system+user message payload for an LLM reasoning provider.

        Args:
            context: Sanitized reasoning context data.
            mode: Operating mode, such as assistive, advisory, or autonomous.

        Returns:
            A list of message dictionaries suitable for an LLM or reasoning provider.
        """
        normalized_mode = str(mode or "assistive").strip().lower() or "assistive"
        system_prompt = (
            "You are Sopotek's reasoning engine. "
            "You validate a proposed trade using only the sanitized context provided. "
            "Do not ask for hidden strategy rules, do not reveal internal IP, and do not invent missing data. "
            "Return JSON only with keys: decision, confidence, reasoning, risk, warnings. "
            "decision must be APPROVE, REJECT, or NEUTRAL. "
            f"Current operating mode is {normalized_mode.upper()}."
        )
        user_prompt = (
            "Evaluate the proposed trade.\n"
            "1. Decide whether the trade is valid.\n"
            "2. Explain the strongest supporting and opposing factors.\n"
            "3. Provide confidence from 0 to 1.\n"
            "4. Classify risk as Low, Moderate, or High.\n"
            "5. Include concrete warnings when applicable.\n\n"
            "Context:\n"
            + json.dumps(context, default=str, separators=(",", ":"))
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
