from cleankoda.sandbox import AVAILABLE_IMAGES
from cleankoda.sandbox.config import SandboxImageOption
from pathlib import Path

from cleankoda.sandbox.base_env import ExecutionEnvironment
from cleankoda.sandbox.config import DEFAULT_IMAGE, get_standbox_image
from cleankoda.sandbox.docker_env import DockerEnvironment
from cleankoda.sandbox.host_env import HostEnvironment
from cleankoda.state import clear_status, set_status


class Sandbox:
    """Manages workspace execution environment lifecycle (host/docker)."""

    def __init__(
        self,
        workspace: Path,
        default_image_id: str | None = DEFAULT_IMAGE,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace_path = self.workspace
        self.is_starting: bool = False

        self.current_env: ExecutionEnvironment = HostEnvironment(self.workspace)
        if default_image_id and default_image_id != "host":
            self.current_env = DockerEnvironment(default_image_id, self.workspace)

    async def switch_environment(self, image_id: str | None) -> str:
        """Stops the active environment and asynchronously switches to host or docker image."""
        self.current_env.stop()

        if image_id and image_id != "host":
            self.is_starting = True
            set_status("sandbox", f"Sandbox: starting ({image_id})...")
            try:
                new_env = DockerEnvironment(image_id, self.workspace)
                await new_env.start_async()
                self.current_env = new_env
                return f"Sandbox enabled: Image [{image_id}]"
            except Exception as exc:
                self.current_env = HostEnvironment(self.workspace)
                return f"Error starting sandbox ({exc}). Fallback to host system."
            finally:
                self.is_starting = False
                clear_status("sandbox")
        else:
            self.is_starting = False
            clear_status("sandbox")
            self.current_env = HostEnvironment(self.workspace)
            return "Sandbox disabled: Commands run directly on the host."

    async def switch_runner(self, use_sandbox_param: bool, image_id: str | None = None) -> str:
        """Safely switch environment in sandbox."""
        if use_sandbox_param and image_id and image_id != "host":
            return await self.switch_environment(image_id)
        else:
            return await self.switch_environment("host")

    def get_sandbox_image(self) -> SandboxImageOption:
        """Returns the image of the current sandbox"""
        return self.current_env.image

    async def toggle_sandbox(self, enabled: bool) -> str:
        """Toggles sandbox execution environment on or off."""
        if enabled:
            image_id = self.get_sandbox_image().id
            return await self.switch_runner(True, image_id)
        else:
            return await self.switch_runner(False)

    def stop(self) -> None:
        """Cleanly shuts down active execution environment."""
        self.current_env.stop()
