"""
Safety Manager: confirmation gates and capability gating for dangerous operations.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Optional


class SafetyManager:
    def __init__(self) -> None:
        # Dangerous commands that require confirmation
        self.dangerous_patterns = [
            r'\brm\b.*-rf',
            r'\bkillall\b',
            r'\bshutdown\b',
            r'\breboot\b',
            r'\bsudo\b.*\brm\b',
            r'\bdd\b.*if=',
            r'\bmkfs\b',
            r'\bformat\b',
        ]
        
        # Commands that are always blocked
        self.blocked_commands = {
            'rm -rf /',
            'sudo rm -rf /',
            'format c:',
        }

    def requires_confirmation(self, commands: List[List[str]]) -> bool:
        """Check if any command requires user confirmation"""
        for cmd in commands:
            cmd_str = ' '.join(cmd).lower()
            
            # Check blocked commands
            if cmd_str in self.blocked_commands:
                return True
                
            # Check dangerous patterns
            for pattern in self.dangerous_patterns:
                if re.search(pattern, cmd_str, re.IGNORECASE):
                    return True
                    
        return False

    def get_confirmation_prompt(self, commands: List[List[str]]) -> str:
        """Generate confirmation prompt for dangerous commands"""
        cmd_list = '\n'.join(f"  {' '.join(cmd)}" for cmd in commands)
        return f"""
⚠️  DANGEROUS OPERATION DETECTED ⚠️

The following commands will be executed:
{cmd_list}

This could potentially harm your system or data.
Type 'yes' to confirm, or anything else to cancel: """

    def filter_safe_commands(self, commands: List[List[str]]) -> List[List[str]]:
        """Remove obviously dangerous commands"""
        safe_commands = []
        for cmd in commands:
            cmd_str = ' '.join(cmd).lower()
            if cmd_str not in self.blocked_commands:
                is_dangerous = any(re.search(pattern, cmd_str, re.IGNORECASE) 
                                 for pattern in self.dangerous_patterns)
                if not is_dangerous:
                    safe_commands.append(cmd)
        return safe_commands
