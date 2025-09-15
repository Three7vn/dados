"""
Multi-task parser: breaks complex instructions into individual tasks with dependencies.
Handles "AND", "then", "while" connectors per system.md requirements.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    PARALLEL = "parallel"  # Can run concurrently
    SEQUENTIAL = "sequential"  # Must wait for previous task


@dataclass
class Task:
    id: str
    instruction: str
    task_type: TaskType
    depends_on: List[str]  # Task IDs this task depends on


class TaskParser:
    def __init__(self) -> None:
        # Patterns for splitting complex instructions
        self.parallel_connectors = [
            r'\band\b',
            r'\balso\b',
            r'\bwhile you\'?re doing that\b',
            r'\bat the same time\b',
            r'\bmeanwhile\b',
        ]
        
        self.sequential_connectors = [
            r'\bthen\b',
            r'\bafter\b',
            r'\bonce\b.*\bdone\b',
            r'\bwhen\b.*\bfinished\b',
            r'\bnext\b',
            r'\bfollowed by\b',
        ]

    def parse(self, instruction: str) -> List[Task]:
        """Parse instruction into tasks with dependencies"""
        # Clean up instruction
        text = instruction.strip()
        
        # Check if it's a complex multi-task instruction
        if not self._is_multi_task(text):
            return [Task(
                id="task_0",
                instruction=text,
                task_type=TaskType.PARALLEL,
                depends_on=[]
            )]
        
        # Split into segments based on connectors
        segments = self._split_instruction(text)
        tasks = []
        
        for i, (segment, connector_type) in enumerate(segments):
            task_id = f"task_{i}"
            depends_on = []
            
            if connector_type == TaskType.SEQUENTIAL and i > 0:
                # Sequential tasks depend on the previous task
                depends_on = [f"task_{i-1}"]
            elif connector_type == TaskType.PARALLEL and i > 0:
                # Parallel tasks can depend on the first task if it makes sense
                # For now, keep them independent unless explicitly sequential
                depends_on = []
            
            tasks.append(Task(
                id=task_id,
                instruction=segment.strip(),
                task_type=connector_type,
                depends_on=depends_on
            ))
        
        return tasks

    def _is_multi_task(self, text: str) -> bool:
        """Check if instruction contains multiple tasks"""
        all_connectors = self.parallel_connectors + self.sequential_connectors
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in all_connectors)

    def _split_instruction(self, text: str) -> List[tuple[str, TaskType]]:
        """Split instruction into segments with their connector types"""
        segments = []
        remaining = text
        
        # Find all connectors and their positions
        connectors_found = []
        
        for pattern in self.parallel_connectors:
            for match in re.finditer(pattern, remaining, re.IGNORECASE):
                connectors_found.append((match.start(), match.end(), TaskType.PARALLEL, match.group()))
        
        for pattern in self.sequential_connectors:
            for match in re.finditer(pattern, remaining, re.IGNORECASE):
                connectors_found.append((match.start(), match.end(), TaskType.SEQUENTIAL, match.group()))
        
        # Sort by position
        connectors_found.sort(key=lambda x: x[0])
        
        if not connectors_found:
            return [(text, TaskType.PARALLEL)]
        
        # Split text at connector positions
        last_end = 0
        for start, end, task_type, connector in connectors_found:
            # Add segment before connector
            if start > last_end:
                segment = remaining[last_end:start].strip()
                if segment:
                    segments.append((segment, TaskType.PARALLEL if not segments else task_type))
            last_end = end
        
        # Add final segment
        if last_end < len(remaining):
            final_segment = remaining[last_end:].strip()
            if final_segment:
                final_type = connectors_found[-1][2] if connectors_found else TaskType.PARALLEL
                segments.append((final_segment, final_type))
        
        return segments if segments else [(text, TaskType.PARALLEL)]
