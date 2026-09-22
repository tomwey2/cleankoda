import asyncio
import os
from pathlib import Path
from typing import Any, Dict

import docker
from docker.errors import DockerException

from cleankoda.sandbox.base_env import ExecutionEnvironment
from cleankoda.sandbox.config import SandboxImageOption

class DockerEnvironment(ExecutionEnvironment):
    """Isolated Docker execution environment for shell commands."""

    def __init__(
        self,
        image_id: str,
        workspace_path: Path,
        max_output_chars: int = 12000,
    ) -> None:
        super().__init__(image_id, workspace_path, max_output_chars)
        self.client = docker.from_env()
        self.container = None
        self._ready_event = asyncio.Event()

    def _sync_start(self) -> None:
        """Starts the workspace container synchronously."""
        if self.container is not None:
            return

        uid = os.getuid()
        gid = os.getgid()

        try:
            # Basis-Volumes (immer vorhanden)
            volumes = {
                str(self.workspace_path): {
                    "bind": "/workspace",
                    "mode": "rw",
                }
            }

            container_home = "/home/sandbox"

            # Optionaler Host-Cache für Maven: Nur mounten, wenn er existiert
            m2_host_dir = Path.home() / ".m2"
            if m2_host_dir.is_dir():
                volumes[str(m2_host_dir)] = {
                    "bind": f"{container_home}/.m2",
                    "mode": "rw",
                }

            # Optional: Genauso für Python/Pip-Cache verfahren
            pip_cache_dir = Path.home() / ".cache" / "pip"
            if pip_cache_dir.is_dir():
                volumes[str(pip_cache_dir)] = {
                    "bind": f"{container_home}/.cache/pip",
                    "mode": "rw",
                }

            environment = {
                "HOME": container_home,
                "CI": "true",
            }

            self.container = self.client.containers.run(
                image=self.image.id,
                command="tail -f /dev/null",  # Hält den Container am Leben
                detach=True,
                volumes=volumes,
                working_dir="/workspace",
                user=f"{uid}:{gid}",
                network_mode="bridge",  # Standard-Netzwerk
                dns=["8.8.8.8", "1.1.1.1"],  # Verhindert 'Temporary failure in name resolution'
                mem_limit="2g",
                nano_cpus=2 * 10**9,  # Max 2 CPUs
                remove=True,  # Container wird beim Stoppen automatisch gelöscht
            )
        except DockerException as exc:
            raise RuntimeError(f"Error starting Docker sandbox: {exc}") from exc

    def start(self) -> None:
        """Starts the workspace container synchronously in the background."""
        try:
            self._sync_start()
        finally:
            self._ready_event.set()

    async def start_async(self) -> None:
        """Starts the container asynchronously in a separate thread."""
        try:
            await asyncio.to_thread(self._sync_start)
        finally:
            self._ready_event.set()

    def _sync_exec(self, command: str) -> Dict[str, Any]:
        """Blocking exec call via the Docker Python SDK."""
        if not self.container:
            return {
                "success": False,
                "exit_code": -1,
                "output": "Error: The sandbox container is not running.",
            }

        wrapped_cmd = f"bash -c 'set -o pipefail; {command}'"

        exec_instance = self.client.api.exec_create(
            self.container.id,
            cmd=wrapped_cmd,
            workdir="/workspace",
            environment={"TERM": "dumb"},  # Deaktiviert ANSI-Steuercodes
        )

        raw_output = self.client.api.exec_start(exec_instance)
        inspect_data = self.client.api.exec_inspect(exec_instance["Id"])
        exit_code = inspect_data.get("ExitCode", 0)

        output_text = raw_output.decode("utf-8", errors="replace").strip()
        output_text = self._truncate_output(output_text)

        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "output": output_text or "(No output)",
        }

    async def run(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Executes a Bash command asynchronously with a timeout in the Docker sandbox."""
        if not self._ready_event.is_set():
            await self._ready_event.wait()

        if not self.container:
            await self.start_async()

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._sync_exec, command),
                timeout=float(timeout),
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "exit_code": 124,
                "output": f"Command timeout reached after {timeout} seconds.",
            }
        except Exception as exc:
            return {
                "success": False,
                "exit_code": -1,
                "output": f"Execution error: {str(exc)}",
            }

    def stop(self) -> None:
        """Finish and remove the container cleanly."""
        if self.container:
            try:
                self.container.kill()
            except Exception:
                pass
            self.container = None
        self._ready_event.clear()
