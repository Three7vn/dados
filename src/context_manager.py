"""
Context Manager: orchestrates task graphs with dependencies and concurrency.
Manages parallel shell tasks and serialized GUI interactions per system.md.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

from task_parser import Task, TaskType


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskExecution:
    task: Task
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ContextManager:
    def __init__(self, max_parallel_tasks: int = 3) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max_parallel_tasks)
        self.gui_lock = threading.Lock()  # Serialize GUI interactions
        self.executions: Dict[str, TaskExecution] = {}
        
    def execute_tasks(
        self, 
        tasks: List[Task], 
        shell_executor: Any,
        gui_executor: Any, 
        text_injector: Any,
        command_router: Any,
        vlm_client: Any
    ) -> Dict[str, TaskExecution]:
        """Execute task graph with proper dependencies and concurrency"""
        
        # Initialize task executions
        for task in tasks:
            self.executions[task.id] = TaskExecution(task=task, status=TaskStatus.PENDING)
        
        # Submit tasks respecting dependencies
        futures: Dict[str, Future] = {}
        
        for task in tasks:
            # Wait for dependencies
            self._wait_for_dependencies(task)
            
            # Submit task for execution
            future = self.executor.submit(
                self._execute_single_task,
                task,
                shell_executor,
                gui_executor,
                text_injector,
                command_router,
                vlm_client
            )
            futures[task.id] = future
        
        # Wait for all tasks to complete
        for task_id, future in futures.items():
            try:
                result = future.result(timeout=300)  # 5 minute timeout per task
                self.executions[task_id].result = result
                self.executions[task_id].status = TaskStatus.COMPLETED
            except Exception as e:
                self.executions[task_id].error = str(e)
                self.executions[task_id].status = TaskStatus.FAILED
        
        return self.executions

    def _wait_for_dependencies(self, task: Task) -> None:
        """Wait for task dependencies to complete"""
        while True:
            all_deps_done = True
            for dep_id in task.depends_on:
                if dep_id in self.executions:
                    dep_status = self.executions[dep_id].status
                    if dep_status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        all_deps_done = False
                        break
            
            if all_deps_done:
                break
            
            time.sleep(0.1)  # Check every 100ms

    def _execute_single_task(
        self,
        task: Task,
        shell_executor: Any,
        gui_executor: Any,
        text_injector: Any,
        command_router: Any,
        vlm_client: Any
    ) -> Dict[str, Any]:
        """Execute a single task with proper routing"""
        
        execution = self.executions[task.id]
        execution.status = TaskStatus.RUNNING
        execution.started_at = time.time()
        
        try:
            # Route the task instruction
            route_info = command_router.route(task.instruction)
            path = route_info.get("path", "dictation")
            
            result = {"path": path, "success": False}
            
            if path == "dictation":
                text_injector.type_text(task.instruction)
                result["success"] = True
                
            elif path == "shell":
                commands = route_info.get("commands", [])
                if commands:
                    # Shell tasks can run in parallel (no GUI lock needed)
                    ok, details = shell_executor.run(commands)
                    result["success"] = ok
                    result["details"] = details
                    
            elif path == "gui":
                # GUI tasks must be serialized to avoid conflicts
                with self.gui_lock:
                    gui_result = gui_executor.execute(
                        instruction=task.instruction, 
                        vlm_client=vlm_client
                    )
                    result["success"] = gui_result.get("success", False)
                    result["gui_details"] = gui_result
            
            execution.completed_at = time.time()
            return result
            
        except Exception as e:
            execution.completed_at = time.time()
            raise e

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get current status of a task"""
        execution = self.executions.get(task_id)
        return execution.status if execution else None

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all task executions"""
        summary = {
            "total_tasks": len(self.executions),
            "completed": sum(1 for e in self.executions.values() if e.status == TaskStatus.COMPLETED),
            "failed": sum(1 for e in self.executions.values() if e.status == TaskStatus.FAILED),
            "running": sum(1 for e in self.executions.values() if e.status == TaskStatus.RUNNING),
            "pending": sum(1 for e in self.executions.values() if e.status == TaskStatus.PENDING),
        }
        
        if summary["completed"] > 0:
            total_time = sum(
                (e.completed_at or 0) - (e.started_at or 0) 
                for e in self.executions.values() 
                if e.completed_at and e.started_at
            )
            summary["total_execution_time"] = total_time
        
        return summary

    def cleanup(self) -> None:
        """Clean up resources"""
        self.executor.shutdown(wait=True)
