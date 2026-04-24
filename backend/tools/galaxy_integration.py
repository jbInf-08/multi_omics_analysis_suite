"""
Galaxy Integration Module
=========================

Integration with Galaxy workflow platform for bioinformatics analysis.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import aiohttp


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    """Galaxy job states."""
    NEW = "new"
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    PAUSED = "paused"
    DELETED = "deleted"


@dataclass
class GalaxyConfig:
    """Configuration for Galaxy connection."""
    url: str = "https://usegalaxy.org"
    api_key: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3


@dataclass
class GalaxyWorkflow:
    """Represents a Galaxy workflow."""
    id: str
    name: str
    owner: str
    published: bool
    inputs: Dict[str, Any]
    steps: List[Dict]
    tags: List[str] = field(default_factory=list)


@dataclass
class GalaxyHistory:
    """Represents a Galaxy history."""
    id: str
    name: str
    state: str
    size: int
    datasets: List[Dict] = field(default_factory=list)


@dataclass
class GalaxyJob:
    """Represents a Galaxy job."""
    id: str
    tool_id: str
    state: JobState
    inputs: Dict
    outputs: Dict
    create_time: datetime
    update_time: datetime


class GalaxyClient:
    """
    Galaxy API client for workflow execution.
    
    Provides:
    - Workflow import/export
    - Job submission and monitoring
    - Data upload/download
    - History management
    """
    
    def __init__(self, config: Optional[GalaxyConfig] = None):
        """
        Initialize Galaxy client.
        
        Args:
            config: Galaxy configuration
        """
        self.config = config or GalaxyConfig()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["x-api-key"] = self.config.api_key
            
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout,
            )
        return self._session
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Dict:
        """Make API request."""
        session = await self._get_session()
        url = f"{self.config.url}/api/{endpoint}"
        
        if params is None:
            params = {}
        if self.config.api_key:
            params["key"] = self.config.api_key
        
        async with session.request(
            method, url, params=params, json=data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_workflows(self) -> List[GalaxyWorkflow]:
        """Get list of available workflows."""
        data = await self._request("GET", "workflows")
        
        workflows = []
        for item in data:
            workflows.append(GalaxyWorkflow(
                id=item["id"],
                name=item["name"],
                owner=item.get("owner", ""),
                published=item.get("published", False),
                inputs={},
                steps=[],
                tags=item.get("tags", []),
            ))
        return workflows
    
    async def get_workflow(self, workflow_id: str) -> GalaxyWorkflow:
        """Get workflow details."""
        data = await self._request("GET", f"workflows/{workflow_id}")
        
        return GalaxyWorkflow(
            id=data["id"],
            name=data["name"],
            owner=data.get("owner", ""),
            published=data.get("published", False),
            inputs=data.get("inputs", {}),
            steps=data.get("steps", []),
            tags=data.get("tags", []),
        )
    
    async def import_workflow(
        self,
        workflow_dict: Dict,
    ) -> GalaxyWorkflow:
        """Import a workflow from dictionary."""
        data = await self._request(
            "POST",
            "workflows",
            data={"workflow": workflow_dict}
        )
        return await self.get_workflow(data["id"])
    
    async def run_workflow(
        self,
        workflow_id: str,
        history_id: str,
        inputs: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Run a workflow.
        
        Args:
            workflow_id: Workflow ID
            history_id: History ID for outputs
            inputs: Input datasets mapping
            parameters: Tool parameters
            
        Returns:
            Invocation response
        """
        payload = {
            "workflow_id": workflow_id,
            "history_id": history_id,
            "inputs": inputs,
        }
        if parameters:
            payload["parameters"] = parameters
        
        return await self._request("POST", "workflows/invocations", data=payload)
    
    async def get_invocation_status(
        self,
        workflow_id: str,
        invocation_id: str,
    ) -> Dict:
        """Get workflow invocation status."""
        return await self._request(
            "GET",
            f"workflows/{workflow_id}/invocations/{invocation_id}"
        )
    
    async def create_history(self, name: str) -> GalaxyHistory:
        """Create a new history."""
        data = await self._request("POST", "histories", data={"name": name})
        return GalaxyHistory(
            id=data["id"],
            name=data["name"],
            state=data.get("state", "new"),
            size=data.get("size", 0),
        )
    
    async def get_histories(self) -> List[GalaxyHistory]:
        """Get list of histories."""
        data = await self._request("GET", "histories")
        
        histories = []
        for item in data:
            histories.append(GalaxyHistory(
                id=item["id"],
                name=item["name"],
                state=item.get("state", ""),
                size=item.get("size", 0),
            ))
        return histories
    
    async def upload_file(
        self,
        history_id: str,
        file_path: str,
        file_type: str = "auto",
    ) -> Dict:
        """
        Upload a file to Galaxy.
        
        Args:
            history_id: History ID
            file_path: Local file path
            file_type: Galaxy file type
            
        Returns:
            Upload response
        """
        payload = {
            "history_id": history_id,
            "targets": [{
                "destination": {"type": "hdas"},
                "items": [{
                    "src": "path",
                    "path": file_path,
                    "ext": file_type,
                }]
            }]
        }
        return await self._request("POST", "tools/fetch", data=payload)
    
    async def download_dataset(
        self,
        history_id: str,
        dataset_id: str,
    ) -> bytes:
        """Download a dataset."""
        session = await self._get_session()
        url = f"{self.config.url}/api/histories/{history_id}/contents/{dataset_id}/display"
        
        params = {}
        if self.config.api_key:
            params["key"] = self.config.api_key
        
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.read()
    
    async def get_tools(self) -> List[Dict]:
        """Get list of available tools."""
        return await self._request("GET", "tools")
    
    async def run_tool(
        self,
        history_id: str,
        tool_id: str,
        inputs: Dict[str, Any],
    ) -> GalaxyJob:
        """
        Run a Galaxy tool.
        
        Args:
            history_id: History ID
            tool_id: Tool ID
            inputs: Tool inputs
            
        Returns:
            GalaxyJob
        """
        payload = {
            "history_id": history_id,
            "tool_id": tool_id,
            "inputs": inputs,
        }
        
        data = await self._request("POST", "tools", data=payload)
        
        return GalaxyJob(
            id=data["jobs"][0]["id"],
            tool_id=tool_id,
            state=JobState(data["jobs"][0]["state"]),
            inputs=inputs,
            outputs=data.get("outputs", {}),
            create_time=utc_now(),
            update_time=utc_now(),
        )
    
    async def get_job_status(self, job_id: str) -> GalaxyJob:
        """Get job status."""
        data = await self._request("GET", f"jobs/{job_id}")
        
        return GalaxyJob(
            id=data["id"],
            tool_id=data.get("tool_id", ""),
            state=JobState(data["state"]),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            create_time=datetime.fromisoformat(data.get("create_time", "").replace("Z", "+00:00")),
            update_time=datetime.fromisoformat(data.get("update_time", "").replace("Z", "+00:00")),
        )
    
    async def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
    ) -> GalaxyJob:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID
            poll_interval: Polling interval in seconds
            timeout: Maximum wait time in seconds
            
        Returns:
            Completed GalaxyJob
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            job = await self.get_job_status(job_id)
            
            if job.state in [JobState.OK, JobState.ERROR, JobState.DELETED]:
                return job
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            
            await asyncio.sleep(poll_interval)
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
