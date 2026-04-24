"""IGV Integration Module.
======================

Integration with IGV (Integrative Genomics Viewer) for visualization.
"""

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class IGVTrack:
    """Represents an IGV track."""

    name: str
    path: str
    format: str  # bam, vcf, bed, bigwig, etc.
    color: str | None = None
    height: int = 50
    visible: bool = True


@dataclass
class IGVSession:
    """Represents an IGV session."""

    genome: str
    tracks: list[IGVTrack] = field(default_factory=list)
    locus: str | None = None
    session_file: Path | None = None


class IGVController:
    """Controller for IGV (Integrative Genomics Viewer).

    Communicates with IGV via its HTTP port control interface.
    Supports:
    - Loading genomes and tracks
    - Navigation to loci
    - Capturing screenshots
    - Session management
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 60151,
        timeout: float = 10.0,
    ):
        """Initialize IGV controller.

        Args:
            host: IGV host
            port: IGV port (default 60151)
            timeout: Connection timeout

        """
        self.host = host
        self.port = port
        self.timeout = timeout

    def _send_command(self, command: str) -> str:
        """Send a command to IGV."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                sock.sendall(f"{command}\n".encode())
                response = sock.recv(4096).decode().strip()
                return response
        except OSError as e:
            logger.error(f"IGV connection error: {e}")
            raise ConnectionError(f"Could not connect to IGV at {self.host}:{self.port}")

    async def _send_command_async(self, command: str) -> str:
        """Send a command asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_command, command)

    def is_running(self) -> bool:
        """Check if IGV is running and accessible."""
        try:
            self._send_command("echo")
            return True
        except ConnectionError:
            return False

    async def load_genome(self, genome: str) -> bool:
        """Load a genome.

        Args:
            genome: Genome ID (e.g., "hg38", "hg19", "mm10")

        Returns:
            Success status

        """
        response = await self._send_command_async(f"genome {genome}")
        return response == "OK"

    async def load_track(self, track: IGVTrack) -> bool:
        """Load a track into IGV.

        Args:
            track: Track to load

        Returns:
            Success status

        """
        command = f"load {track.path}"
        if track.name:
            command += f" name={track.name}"

        response = await self._send_command_async(command)
        return response == "OK"

    async def goto(self, locus: str) -> bool:
        """Navigate to a genomic locus.

        Args:
            locus: Locus string (e.g., "chr1:10000-20000", "BRCA1")

        Returns:
            Success status

        """
        response = await self._send_command_async(f"goto {locus}")
        return response == "OK"

    async def snapshot(
        self,
        output_path: Path,
        region: str | None = None,
    ) -> bool:
        """Capture a screenshot.

        Args:
            output_path: Output file path
            region: Optional region to capture

        Returns:
            Success status

        """
        if region:
            await self.goto(region)

        # Set snapshot directory
        await self._send_command_async(f"snapshotDirectory {output_path.parent}")

        # Take snapshot
        response = await self._send_command_async(f"snapshot {output_path.name}")
        return response == "OK"

    async def load_session(self, session_file: Path) -> bool:
        """Load an IGV session file."""
        response = await self._send_command_async(f"load {session_file}")
        return response == "OK"

    async def save_session(self, session_file: Path) -> bool:
        """Save current session to file."""
        response = await self._send_command_async(f"saveSession {session_file}")
        return response == "OK"

    async def new_session(self) -> bool:
        """Start a new session."""
        response = await self._send_command_async("new")
        return response == "OK"

    async def zoom_in(self) -> bool:
        """Zoom in."""
        response = await self._send_command_async("zoomIn")
        return response == "OK"

    async def zoom_out(self) -> bool:
        """Zoom out."""
        response = await self._send_command_async("zoomOut")
        return response == "OK"

    async def set_track_height(self, track_name: str, height: int) -> bool:
        """Set track height."""
        response = await self._send_command_async(f"setTrackHeight {track_name} {height}")
        return response == "OK"

    async def collapse_track(self, track_name: str) -> bool:
        """Collapse a track."""
        response = await self._send_command_async(f"collapse {track_name}")
        return response == "OK"

    async def expand_track(self, track_name: str) -> bool:
        """Expand a track."""
        response = await self._send_command_async(f"expand {track_name}")
        return response == "OK"

    async def setup_session(self, session: IGVSession) -> bool:
        """Setup a complete IGV session.

        Args:
            session: Session configuration

        Returns:
            Success status

        """
        # Start new session
        await self.new_session()

        # Load genome
        await self.load_genome(session.genome)

        # Load tracks
        for track in session.tracks:
            await self.load_track(track)

        # Navigate to locus
        if session.locus:
            await self.goto(session.locus)

        return True

    def create_session_xml(
        self,
        session: IGVSession,
        output_path: Path,
    ) -> Path:
        """Create an IGV session XML file.

        Args:
            session: Session configuration
            output_path: Output file path

        Returns:
            Path to session file

        """
        xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Session genome="{session.genome}" version="8">
    <Resources>
"""

        for track in session.tracks:
            xml_content += f'        <Resource path="{track.path}" name="{track.name}"/>\n'

        xml_content += """    </Resources>
</Session>
"""

        output_path.write_text(xml_content)
        return output_path
