from enum import Enum


class AuraState(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVATED = "activated"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    PAUSED = "paused"
    ERROR = "error"


LABELS = {
    AuraState.INITIALIZING: "Inicializando",
    AuraState.IDLE: "Em espera",
    AuraState.ACTIVATED: "Ativada",
    AuraState.LISTENING: "Escutando",
    AuraState.THINKING: "Pensando",
    AuraState.SPEAKING: "Falando",
    AuraState.PAUSED: "Pausada",
    AuraState.ERROR: "Erro",
}

_ALLOWED: dict[AuraState, set[AuraState]] = {
    AuraState.INITIALIZING: {AuraState.IDLE, AuraState.ERROR},
    AuraState.IDLE: {
        AuraState.ACTIVATED, AuraState.LISTENING, AuraState.THINKING,
        AuraState.SPEAKING, AuraState.PAUSED, AuraState.ERROR,
    },
    AuraState.ACTIVATED: {AuraState.LISTENING, AuraState.IDLE, AuraState.ERROR},
    AuraState.LISTENING: {AuraState.THINKING, AuraState.IDLE, AuraState.ERROR},
    AuraState.THINKING: {AuraState.SPEAKING, AuraState.IDLE, AuraState.ERROR},
    AuraState.SPEAKING: {
        AuraState.IDLE, AuraState.LISTENING, AuraState.ACTIVATED,
        AuraState.ERROR, AuraState.PAUSED,
    },
    AuraState.PAUSED: {AuraState.IDLE, AuraState.ERROR},
    AuraState.ERROR: {AuraState.IDLE, AuraState.PAUSED},
}


class TransitionError(ValueError):
    pass


class StateMachine:
    def __init__(self) -> None:
        self.state = AuraState.INITIALIZING

    def can(self, target: AuraState) -> bool:
        return target in _ALLOWED[self.state]

    def go(self, target: AuraState) -> AuraState:
        if target is self.state:
            return self.state
        if not self.can(target):
            raise TransitionError(f"{self.state.value} → {target.value}")
        self.state = target
        return self.state
