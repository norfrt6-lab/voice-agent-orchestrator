"""
Offline console demo — runs a full booking conversation without any API keys.

This simulates the multi-agent orchestration pipeline using the real
state machine, slot manager, guardrails, and mock tools. No LLM, no
LiveKit, no network calls. Designed for live demo walkthroughs.

Usage:
    python console_demo.py
    python console_demo.py --scenario emergency
    python console_demo.py --scenario info
"""

import argparse
import sys
from typing import Optional

from src.config import settings
from src.schemas.customer_schema import SessionData
from src.conversation.state_machine import (
    ConversationStateMachine,
    ConversationState,
    TransitionTrigger,
)
from src.conversation.slot_manager import SlotManager
from src.conversation.guardrails import GuardrailPipeline
from src.tools.services import match_service, get_service_details, get_all_services
from src.tools.availability import check_availability, get_available_dates
from src.tools.booking import create_booking
from src.tools.customer import lookup_customer

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


class ConsoleSession:
    """Simulates a full multi-agent conversation in the terminal."""

    def __init__(self) -> None:
        self.sm = ConversationStateMachine()
        self.slots = SlotManager()
        self.guardrails = GuardrailPipeline()
        self.session = SessionData()
        self.current_agent = "IntakeAgent"
        self._awaiting_confirmation = False

    def agent_say(self, text: str) -> None:
        print(f"{GREEN}{BOLD}[{self.current_agent}]{RESET} {GREEN}{text}{RESET}")

    def system_log(self, text: str) -> None:
        print(f"{DIM}  >> {text}{RESET}")

    # Pre-scripted scenarios for --scenario flag
    SCENARIOS: dict[str, list[str]] = {
        "booking": [
            "I need to book a plumber",
            "John Smith",
            "0412345678",
            "2025-03-15",
            "10:00",
            "42 Wallaby Way, Sydney",
            "Leaking kitchen tap",
            "yes",
            "no thanks, bye",
        ],
        "info": [
            "How much does electrical work cost?",
            "What about plumbing?",
            "no thanks, that's all",
        ],
        "emergency": [
            "I have a gas leak!",
            "0400111222",
        ],
    }

    MAX_INPUT_LENGTH = 500

    def run_scenario(self, scenario: str) -> None:
        """Auto-play a pre-scripted scenario for demo purposes."""
        steps = self.SCENARIOS.get(scenario)
        if not steps:
            print(f"{RED}Unknown scenario: {scenario}{RESET}")
            return

        print()
        print(f"{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}  VOICE AGENT ORCHESTRATOR - Scenario: {scenario}{RESET}")
        print(f"{BOLD}  Business: {settings.business.name}{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")
        print()

        self.sm.transition(TransitionTrigger.GREETING_DELIVERED)
        self.agent_say(
            f"Good morning, thanks for calling {settings.business.name}. "
            f"How can I help you today?"
        )
        self.system_log(f"State: {self.sm.current_state.value}")

        for step in steps:
            if self.sm.is_terminal():
                break
            print(f"\n{BLUE}[Caller] {RESET}{step}")
            self._process_input(step)
            self.system_log(f"State: {self.sm.current_state.value}")

        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}  Scenario '{scenario}' complete.{RESET}")
        print(f"{DIM}  State trace: {' -> '.join(self.sm.get_state_trace())}{RESET}")
        print(f"{DIM}  Slot stats: {self.slots.get_stats()}{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")

    def run(self) -> None:
        print()
        print(f"{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}  VOICE AGENT ORCHESTRATOR - Console Demo{RESET}")
        print(f"{BOLD}  Business: {settings.business.name}{RESET}")
        print(f"{BOLD}  Type 'quit' to exit{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")
        print()

        # Greeting
        self.sm.transition(TransitionTrigger.GREETING_DELIVERED)
        self.agent_say(
            f"Good morning, thanks for calling {settings.business.name}. "
            f"How can I help you today?"
        )
        self.system_log(f"State: {self.sm.current_state.value}")

        while not self.sm.is_terminal():
            user_input = input(f"\n{BLUE}[Caller] {RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print(f"\n{DIM}Session ended.{RESET}")
                return

            if len(user_input) > self.MAX_INPUT_LENGTH:
                self.agent_say("That was quite long. Could you keep it brief for me?")
                continue

            self._process_input(user_input)
            self.system_log(f"State: {self.sm.current_state.value}")

        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}  Conversation complete.{RESET}")
        print(f"{DIM}  State trace: {' -> '.join(self.sm.get_state_trace())}{RESET}")
        print(f"{DIM}  Slot stats: {self.slots.get_stats()}{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")

    def _process_input(self, text: str) -> None:
        # Check guardrails first
        violations = self.guardrails.check_user_input(text, self.session.error_count)
        for v in violations:
            if v.severity == "escalate":
                self._handle_escalation(v.violation_type or "unknown", text)
                return
            if v.severity == "block":
                self.agent_say(
                    "I can only help with home services like plumbing, electrical, "
                    "and HVAC. Is there something along those lines I can help with?"
                )
                return

        state = self.sm.current_state

        if state == ConversationState.INTENT_DETECTION:
            self._handle_intent(text)
        elif state == ConversationState.SERVICE_SELECTION:
            self._handle_service_selection(text)
        elif state == ConversationState.SLOT_FILLING:
            self._handle_slot_filling(text)
        elif state == ConversationState.SLOT_CONFIRMATION:
            self._handle_confirmation(text)
        elif state == ConversationState.AVAILABILITY_CHECK:
            self._handle_availability(text)
        elif state == ConversationState.CONFIRMATION:
            self._handle_post_booking(text)
        elif state == ConversationState.INFO_RESPONSE:
            self._handle_info(text)
        elif state == ConversationState.ESCALATION:
            self._handle_escalation_response(text)
        elif state == ConversationState.ERROR_RECOVERY:
            self._handle_error_recovery(text)
        else:
            self.agent_say("I'm sorry, I didn't catch that. Could you repeat that?")

    # ------------------------------------------------------------------ #
    # Intent detection
    # ------------------------------------------------------------------ #

    def _handle_intent(self, text: str) -> None:
        lower = text.lower()
        booking_signals = ["book", "appointment", "schedule", "come out", "send someone",
                           "fix", "repair", "install", "leak", "broken", "blocked"]
        info_signals = ["how much", "price", "cost", "what services", "do you offer",
                        "hours", "area", "where"]
        emergency_signals = ["gas leak", "burst pipe", "flooding", "fire", "sparking",
                             "emergency", "urgent"]

        if any(s in lower for s in emergency_signals):
            self._handle_escalation("emergency", text)
            return

        if any(s in lower for s in booking_signals):
            self.sm.transition(TransitionTrigger.INTENT_BOOK)
            self.current_agent = "BookingAgent"
            self.system_log("Handoff: IntakeAgent -> BookingAgent")

            # Try to extract service from intent message
            matched = match_service(text)
            if matched:
                self.slots.set_slot("service_type", matched)
                self.session.service_type = matched
                self.sm.transition(TransitionTrigger.SERVICE_CONFIRMED)
                self.agent_say(
                    f"I can help you book a {matched} appointment. "
                    f"Could I get your full name please?"
                )
            else:
                self.agent_say(
                    "I can help you book that. What type of service do you need? "
                    "We offer plumbing, electrical, HVAC, drain cleaning, "
                    "and general handyman services."
                )
            return

        if any(s in lower for s in info_signals):
            self.sm.transition(TransitionTrigger.INTENT_INFO)
            self.current_agent = "InfoAgent"
            self.system_log("Handoff: IntakeAgent -> InfoAgent")
            self._handle_info(text)
            return

        # Unclear intent
        self.agent_say(
            "I'd be happy to help! Are you looking to book an appointment, "
            "or did you have a question about our services?"
        )

    # ------------------------------------------------------------------ #
    # Service selection
    # ------------------------------------------------------------------ #

    def _handle_service_selection(self, text: str) -> None:
        matched = match_service(text)
        if matched:
            self.slots.set_slot("service_type", matched)
            self.session.service_type = matched
            self.sm.transition(TransitionTrigger.SERVICE_CONFIRMED)
            self.system_log(f"Service matched: {matched}")
            self.agent_say(
                f"Got it — {matched} service. Could I get your full name please?"
            )
        else:
            services = get_all_services()
            names = [s["name"] for s in services]
            self.agent_say(
                f"I'm not sure what service that falls under. "
                f"We offer: {', '.join(names)}. Which would you need?"
            )

    # ------------------------------------------------------------------ #
    # Slot filling
    # ------------------------------------------------------------------ #

    def _handle_slot_filling(self, text: str) -> None:
        next_slot = self.slots.get_next_empty_slot()
        if next_slot is None:
            self.sm.transition(TransitionTrigger.ALL_SLOTS_FILLED)
            self._show_confirmation()
            return

        slot_name = next_slot.name
        ok, msg = self.slots.set_slot(slot_name, text)
        self.system_log(f"Slot '{slot_name}': {'OK' if ok else 'FAILED'} — {msg}")

        if ok:
            setattr(self.session, slot_name, self.slots.get_slot_value(slot_name))
            # Check if all required filled now
            if self.slots.all_required_filled():
                self.sm.transition(TransitionTrigger.ALL_SLOTS_FILLED)
                self._show_confirmation()
                return
            # Ask for next slot
            next_next = self.slots.get_next_empty_slot()
            if next_next:
                self.agent_say(f"Got it. And {next_next.prompt_hint.lower()}?")
            else:
                # Optional slot prompt
                self.agent_say("Can you briefly describe the issue? Or I can skip that.")
        else:
            if self.slots.has_exceeded_retries(slot_name):
                self.session.error_count += 1
                self.sm.transition(TransitionTrigger.MAX_RETRIES)
                self.agent_say(
                    "I'm having trouble with that. Let me connect you with a team member."
                )
                return
            self.agent_say(f"Sorry, {msg} Could you try again?")

    def _show_confirmation(self) -> None:
        summary = self.slots.get_confirmation_summary()
        self.agent_say(f"{summary}\n\nDoes everything sound correct?")

    # ------------------------------------------------------------------ #
    # Confirmation gate
    # ------------------------------------------------------------------ #

    def _handle_confirmation(self, text: str) -> None:
        lower = text.lower()

        if any(w in lower for w in ["yes", "correct", "right", "yep", "yeah", "looks good"]):
            self.slots.confirm_all()
            self.sm.transition(TransitionTrigger.CALLER_CONFIRMED)
            self.system_log("Caller confirmed. Checking availability...")
            self._do_availability_and_book()
            return

        if any(w in lower for w in ["no", "wrong", "change", "actually", "correction"]):
            self.sm.transition(TransitionTrigger.CALLER_CORRECTED)
            self.agent_say("No problem. Which detail needs to be changed?")
            return

        self.agent_say("Sorry, I just need a yes or no — does everything look right?")

    # ------------------------------------------------------------------ #
    # Availability + booking
    # ------------------------------------------------------------------ #

    def _do_availability_and_book(self) -> None:
        slot_data = self.slots.to_dict()
        service = slot_data.get("service_type", "general handyman")
        date = slot_data.get("preferred_date", "")
        time = slot_data.get("preferred_time")

        avail = check_availability(service, date, time)

        if not avail["available"]:
            alt_dates = get_available_dates(service, limit=3)
            if alt_dates:
                self.sm.transition(TransitionTrigger.NO_AVAILABILITY)
                options = ", ".join(
                    f"{d['date']} ({d['day_name']})" for d in alt_dates[:3]
                )
                self.agent_say(
                    f"Unfortunately {date} isn't available. "
                    f"I have openings on: {options}. Which works for you?"
                )
            else:
                self.sm.transition(TransitionTrigger.NO_AVAILABILITY_AT_ALL)
                self.agent_say(
                    "I'm sorry, we don't have any availability in the coming days. "
                    "Let me connect you with the team to find a solution."
                )
            return

        # Book it
        self.sm.transition(TransitionTrigger.TIME_SELECTED)
        selected = avail["slots"][0]
        result = create_booking(
            name=slot_data.get("customer_name", ""),
            phone=slot_data.get("customer_phone", ""),
            service=service,
            date=selected["date"],
            time=selected["time"],
            address=slot_data.get("customer_address", ""),
            description=slot_data.get("job_description"),
            technician=selected.get("technician"),
        )

        if result["success"]:
            self.session.booking_ref = result["booking_ref"]
            self.sm.transition(TransitionTrigger.BOOKING_SUCCESS)
            self.agent_say(
                f"Booking confirmed! Your reference number is {result['booking_ref']}. "
                f"{selected.get('technician', 'A technician')} will be at your address "
                f"on {selected['date']} at {selected['time']}. "
                f"Is there anything else I can help with?"
            )
        else:
            self.sm.transition(TransitionTrigger.BOOKING_FAILED)
            self.agent_say(
                "Something went wrong creating the booking. "
                "Let me connect you with our team."
            )

    def _handle_availability(self, text: str) -> None:
        # Caller selecting an alternative date
        self.slots.correct_slot("preferred_date", text)
        self.session.preferred_date = text
        self.sm.transition(TransitionTrigger.TIME_SELECTED)
        self._do_availability_and_book()

    # ------------------------------------------------------------------ #
    # Post-booking
    # ------------------------------------------------------------------ #

    def _handle_post_booking(self, text: str) -> None:
        lower = text.lower()
        if any(w in lower for w in ["no", "nothing", "that's all", "bye", "thanks", "thank"]):
            self.sm.transition(TransitionTrigger.GOODBYE)
            name = self.session.customer_name or "there"
            self.agent_say(
                f"Thanks for calling {settings.business.name}, {name}. Have a great day!"
            )
        else:
            self.agent_say("Is there anything else I can help you with?")

    # ------------------------------------------------------------------ #
    # Info flow
    # ------------------------------------------------------------------ #

    def _handle_info(self, text: str) -> None:
        lower = text.lower()

        # Try to match a specific service
        matched = match_service(text)
        if matched:
            details = get_service_details(matched)
            if details:
                self.agent_say(
                    f"Our {details['name']} covers {details['description']} "
                    f"Pricing typically runs {details['price_range']} with a "
                    f"{details['call_out_fee']} call-out fee. "
                    f"Most jobs take {details['typical_duration']}. "
                    f"Would you like to book an appointment?"
                )
                return

        if any(w in lower for w in ["all services", "what do you offer", "list"]):
            services = get_all_services()
            lines = [f"{s['name']} ({s['price_range']})" for s in services]
            self.agent_say(
                f"We offer: {', '.join(lines)}. "
                f"Would you like details on any of these, or to book?"
            )
            return

        # Check if they want to book now
        if any(w in lower for w in ["book", "appointment", "schedule", "yes"]):
            self.sm.transition(TransitionTrigger.WANTS_TO_BOOK)
            self.current_agent = "BookingAgent"
            self.system_log("Handoff: InfoAgent -> BookingAgent")
            self.agent_say(
                "I'll get you booked in. What type of service do you need?"
            )
            return

        if any(w in lower for w in ["no", "that's all", "bye", "thanks"]):
            self.sm.transition(TransitionTrigger.SATISFIED)
            self.agent_say(
                f"Thanks for calling {settings.business.name}. Have a great day!"
            )
            return

        self.agent_say(
            "I can help with pricing, service details, or booking. "
            "What would you like to know?"
        )

    # ------------------------------------------------------------------ #
    # Escalation
    # ------------------------------------------------------------------ #

    def _handle_escalation(self, reason: str, text: str) -> None:
        if self.sm.current_state != ConversationState.ESCALATION:
            if self.sm.current_state == ConversationState.INTENT_DETECTION:
                self.sm.transition(TransitionTrigger.INTENT_EMERGENCY)
            elif self.sm.current_state == ConversationState.SLOT_FILLING:
                self.sm.transition(TransitionTrigger.MAX_RETRIES)
                self.sm.transition(TransitionTrigger.RECOVERY_FAILED)
            elif self.sm.current_state == ConversationState.ERROR_RECOVERY:
                self.sm.transition(TransitionTrigger.RECOVERY_FAILED)
            else:
                self.system_log(
                    f"Cannot escalate from state {self.sm.current_state.value} "
                    f"- valid triggers: {[t.value for t in self.sm.get_valid_triggers()]}"
                )

        self.current_agent = "EscalationAgent"
        self.system_log(f"Escalation triggered: {reason}")

        if reason == "emergency":
            lower = text.lower()
            if "gas" in lower:
                self.agent_say(
                    "If you smell gas, leave the area immediately and don't operate "
                    "any electrical switches. Call our emergency line at "
                    f"{settings.business.emergency_line} from outside. "
                    "If the smell is strong, call 000."
                )
            elif "flood" in lower or "water" in lower or "burst" in lower:
                self.agent_say(
                    "Please turn off your main water supply if you can safely reach it. "
                    f"Then call our emergency line at {settings.business.emergency_line}. "
                    "We'll have someone out to you as quickly as possible."
                )
            else:
                self.agent_say(
                    f"I understand this is urgent. Please call our emergency line at "
                    f"{settings.business.emergency_line} for immediate assistance. "
                    f"A team member will also call you back within "
                    f"{settings.business.callback_sla_minutes} minutes."
                )
        else:
            self.agent_say(
                f"I understand. Let me connect you with a team member. "
                f"Someone will call you back within "
                f"{settings.business.callback_sla_minutes} minutes. "
                f"Can I confirm the best number to reach you?"
            )

    def _handle_escalation_response(self, text: str) -> None:
        self.sm.transition(TransitionTrigger.HANDOFF_COMPLETE)
        self.agent_say(
            f"We've noted your details. A team member from {settings.business.name} "
            f"will be in touch shortly. Stay safe and have a good day."
        )

    # ------------------------------------------------------------------ #
    # Error recovery
    # ------------------------------------------------------------------ #

    def _handle_error_recovery(self, text: str) -> None:
        self.sm.transition(TransitionTrigger.CORRECTION_RECEIVED)
        next_slot = self.slots.get_next_empty_slot()
        self.agent_say(
            "Let me try that again. " + (
                next_slot.prompt_hint if next_slot else "Let's continue."
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline console demo")
    parser.add_argument(
        "--scenario",
        choices=["booking", "info", "emergency"],
        default=None,
        help="Auto-play a pre-scripted scenario instead of interactive mode",
    )
    args = parser.parse_args()

    session = ConsoleSession()
    if args.scenario:
        session.run_scenario(args.scenario)
    else:
        session.run()


if __name__ == "__main__":
    main()
