"""
LiveKit voice agent entry point.

Configures the STT -> LLM -> TTS pipeline and launches the intake agent.
Supports both live voice mode and console text mode for development.

Usage:
    Live voice:   python main.py dev
    Console mode: python main.py console
"""

import logging
import sys

from src.config import settings

logger = logging.getLogger(__name__)


def _run_voice_mode() -> None:
    """Start the full LiveKit voice pipeline (requires API keys)."""
    from livekit.agents import AgentSession, WorkerOptions, cli
    from livekit.plugins import deepgram, openai, cartesia, silero

    from src.schemas.customer_schema import SessionData
    from src.agents.intake_agent import IntakeAgent

    def build_session() -> AgentSession:
        return AgentSession[SessionData](
            stt=deepgram.STT(
                model=settings.model.stt_model,
                language=settings.model.stt_language,
            ),
            llm=openai.LLM(
                model=settings.model.llm_model,
                temperature=settings.model.llm_temperature,
            ),
            tts=cartesia.TTS(
                model=settings.model.tts_model,
                voice=settings.model.tts_voice_id,
            ),
            vad=silero.VAD.load(),
            userdata=SessionData(),
        )

    async def entrypoint(ctx) -> None:
        session = build_session()
        await session.start(room=ctx.room, agent=IntakeAgent())
        logger.info("Voice agent session started in room: %s", ctx.room.name)

    worker = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=settings.agent_name,
    )
    cli.run_app(worker)


def _run_console_mode() -> None:
    """Start the offline console demo (no API keys required)."""
    from console_demo import ConsoleSession

    session = ConsoleSession()
    session.run()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "console":
        _run_console_mode()
    else:
        _run_voice_mode()
