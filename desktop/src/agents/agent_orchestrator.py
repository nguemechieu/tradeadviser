"""Pipeline orchestrator for sequential agent execution.

This module provides a small coordinator for running a list of agents in a
defined order. Each agent receives a shared working context and may modify it
or signal pipeline control by returning `None` or setting `halt_pipeline`.
"""


class AgentOrchestrator:
    """Sequential agent pipeline manager.

    The orchestrator is responsible for running each agent in order and
    tracking the shared working context between them. Agents are expected to
    implement an asynchronous `process(context)` method that returns a dict.
    """

    def __init__(self, agents=None):
        """Initialize the orchestrator with an ordered agent list.

        Parameters:
            agents: Optional iterable of agent instances implementing `process`.

        The provided iterable is copied into an internal list so the orchestrator
        retains its own ordered agent sequence without mutating the original.
        """
        self.agents = list(agents or [])

    async def run(self, context):
        """Run the orchestrator and return the finalized working context.

        Parameters:
            context: Initial context data provided to the first agent.

        Returns:
            The final working context after all agents run, or an empty dict if
            execution is aborted because an agent returned `None`.

        The pipeline uses the returned value from each agent as the next working
        context. Agents may set `halt_pipeline` in the working context to stop
        execution gracefully after the current agent completes.
        """
        working = dict(context or {})
        # Copy the input data to avoid mutating the caller's original context.
        for agent in self.agents:
            working = await agent.process(working)
            if working is None:
                # Agent signaled a hard stop; return a safe empty context.
                return {}
            if working.get("halt_pipeline"):
                # Agent requested graceful pipeline termination.
                break
        return working
