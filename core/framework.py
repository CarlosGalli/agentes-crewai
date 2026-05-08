"""
CrewAI-inspired multi-agent framework usando Anthropic SDK.
Compatible con Python 3.14+.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
import anthropic


MODEL = "claude-sonnet-4-6"
_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


@dataclass
class Agent:
    """Representa un agente especializado con rol, objetivo y contexto."""
    role: str
    goal: str
    backstory: str
    verbose: bool = True
    max_tokens: int = 4096

    def _system_prompt(self) -> str:
        return (
            f"Sos un agente especializado con el siguiente rol: {self.role}\n\n"
            f"Tu objetivo principal: {self.goal}\n\n"
            f"Tu contexto y experiencia: {self.backstory}\n\n"
            "Respondé siempre en español rioplatense, de manera clara y profesional."
        )

    def execute(self, task_description: str, context: str = "") -> str:
        """Ejecuta una tarea y retorna el resultado."""
        if self.verbose:
            print(f"\n[Agente: {self.role}] Procesando tarea...")

        user_content = task_description
        if context:
            user_content = f"Contexto adicional:\n{context}\n\nTarea:\n{task_description}"

        response = get_client().messages.create(
            model=MODEL,
            max_tokens=self.max_tokens,
            system=self._system_prompt(),
            messages=[{"role": "user", "content": user_content}],
        )

        result = response.content[0].text
        if self.verbose:
            print(f"[Agente: {self.role}] Tarea completada. ({response.usage.output_tokens} tokens)")
        return result


@dataclass
class Task:
    """Define una tarea con su descripción, salida esperada y agente asignado."""
    description: str
    expected_output: str
    agent: Agent
    context_tasks: list["Task"] = field(default_factory=list)
    _output: str = field(default="", init=False, repr=False)

    @property
    def output(self) -> str:
        return self._output

    def execute(self) -> str:
        context = ""
        if self.context_tasks:
            parts = []
            for t in self.context_tasks:
                if t.output:
                    parts.append(f"--- Resultado previo ({t.agent.role}) ---\n{t.output}")
            context = "\n\n".join(parts)

        full_description = (
            f"{self.description}\n\n"
            f"Salida esperada: {self.expected_output}"
        )
        self._output = self.agent.execute(full_description, context)
        return self._output


@dataclass
class Crew:
    """Orquesta un conjunto de agentes y tareas en secuencia."""
    agents: list[Agent]
    tasks: list[Task]
    verbose: bool = True

    def kickoff(self, inputs: Optional[dict] = None) -> str:
        """Ejecuta todas las tareas en orden y retorna el resultado final."""
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Iniciando Crew con {len(self.tasks)} tarea(s) y {len(self.agents)} agente(s)")
            print(f"{'='*60}")

        start = time.time()
        sections: list[str] = []

        for i, task in enumerate(self.tasks, 1):
            if self.verbose:
                print(f"\n[Tarea {i}/{len(self.tasks)}] {task.description[:80]}...")

            # Sustituir variables en la descripción si se pasan inputs
            if inputs:
                for key, value in inputs.items():
                    task.description = task.description.replace(f"{{{key}}}", str(value))

            output = task.execute()
            sections.append(
                f"# Tarea {i} — {task.agent.role}\n\n{output}"
            )

        elapsed = time.time() - start
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Crew finalizado en {elapsed:.1f}s")
            print(f"{'='*60}\n")

        return "\n\n---\n\n".join(sections)
