"""
Update Agent - LLM-based Code Generation for EntityGraph Node Updates

Uses LLM to generate Python code for updating EntityGraph nodes based on:
- Node type (metric, symptom, time_decay)
- Database records from health_metric_records and patient.symptoms
- Time-based confidence decay

Workflow:
1. Classify node type using NodeTypeMatcher
2. Load appropriate prompt template WITH dynamic metadata
3. Generate Python code with LLM (with retry loop)
4. Execute code in sandbox environment
5. Apply result variables to EntityGraph

Key Design:
- patient_id is NOT in the prompt - it's injected by the environment
- Supports 3 retry attempts with error feedback
- Uses real LLM API calls for code generation
- Code uses result variables, NOT direct entity_graph access
- Async parallel updates for multiple nodes

Logging:
- All operations are logged for debugging
- Generated code is logged (first 200 chars)
- Execution results are logged
"""

import re
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime

from langchain.schema import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from backend.config.config_manager import get_config
from backend.services.node_type_matcher import NodeTypeMatcher
from backend.services.metric_crud import MetricCRUD
from backend.database.crud import patient_crud
from drhyper.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================
# Metric Name Mapping
# ============================================

# Map DrHyper entity node names to database metric names
# This resolves the mismatch between DrHyper-generated node names
# and actual metric names stored in the database
NODE_TO_METRIC_MAPPING = {
    # Systolic Blood Pressure variants
    "systolic blood pressure": "Systolic BP",
    "systolic": "Systolic BP",
    "systolic bp": "Systolic BP",
    "systolic blood pressure value": "Systolic BP",
    
    # Diastolic Blood Pressure variants
    "diastolic blood pressure": "Diastolic BP",
    "diastolic": "Diastolic BP",
    "diastolic bp": "Diastolic BP",
    "diastolic blood pressure value": "Diastolic BP",
    
    # Blood Pressure (combined)
    "blood pressure": "Blood Pressure",
    "bp": "Blood Pressure",
    "blood pressure value": "Blood Pressure",
    "blood pressure values": "Blood Pressure",
    "blood pressure readings": "Blood Pressure",
    
    # Heart Rate variants
    "heart rate": "Heart Rate",
    "hr": "Heart Rate",
    "pulse": "Heart Rate",
    "pulse rate": "Heart Rate",
    
    # Glucose variants
    "glucose": "Glucose",
    "blood glucose": "Glucose",
    "blood sugar": "Glucose",
    "fasting glucose": "Glucose",
    "fasting blood glucose": "Glucose",
    
    # Weight variants
    "weight": "Weight",
    "body weight": "Weight",
    "patient weight": "Weight",
    
    # BMI variants
    "bmi": "BMI",
    "body mass index": "BMI",
    
    # Cholesterol variants
    "total cholesterol": "Total Cholesterol",
    "cholesterol": "Total Cholesterol",
    "ldl": "LDL Cholesterol",
    "ldl cholesterol": "LDL Cholesterol",
    "hdl": "HDL Cholesterol",
    "hdl cholesterol": "HDL Cholesterol",
    "triglycerides": "Triglycerides",
    
    # Lab values
    "hba1c": "HbA1c",
    "hba1c": "HbA1c",
    "glycated hemoglobin": "HbA1c",
    "creatinine": "Creatinine",
    "egfr": "eGFR",
    "estimated gfr": "eGFR",
    
    # Thyroid
    "tsh": "TSH",
    "thyroid stimulating hormone": "TSH",
    
    # Symptoms (map to symptom type)
    "headache": "头痛",
    "dizziness": "头晕",
    "fatigue": "疲劳",
    "palpitations": "心悸",
    "shortness of breath": "气短",
    "chest pain": "胸痛",
    "nausea": "恶心",
    "vision changes": "视力模糊",
}

# Abstract nodes that don't have direct database records
# These should be handled specially or skipped
ABSTRACT_NODE_PATTERNS = [
    r"number of.*readings",
    r"time period of.*measurements",
    r"count of.*",
    r"frequency of.*",
    r"duration of.*",
    r"trend of.*",
    r"pattern of.*",
    r"current medications.*",
    r"medication compliance",
    r"lifestyle factors",
    r"risk factors",
]


class UpdateAgent:
    """
    Update Agent using LLM code generation
    
    Generates and executes Python code to update EntityGraph nodes
    based on latest database records.

    Features:
    - LLM-based code generation with retry loop
    - patient_id injected by environment (not in prompt)
    - Supports metric nodes, symptom nodes, and time decay
    - Metric name mapping for DrHyper node names to database names
    - Abstract node detection and handling
    """

    # System message for code generation
    SYSTEM_MESSAGE = """You are generating Python code to update EntityGraph nodes.

IMPORTANT: The execution environment provides these variables:
- `patient_id`: The patient identifier (DO NOT hardcode, use this variable)
- `sandbox`: Database session for all operations
- `MetricCRUD`: CRUD operations for health metrics (includes get_latest_record, get_metric_metadata)
- `patient_crud`: CRUD operations for patients
- `node_id`: The ID of the node to update
- `datetime`: datetime module for timestamp operations
- `result`: Dictionary to store results (USE THIS to pass values back)

CRITICAL RULES:
1. DO NOT use 'return' statements - this code runs in exec(), not a function
2. DO NOT access entity_graph directly (no entity_graph.nodes or entity_graph.entity_graph.nodes)
3. ALWAYS use result variables to pass values back:
   - For metric updates: result["node_value"] = new_value, result["updated"] = True
   - For symptom updates: result["node_status"] = new_status, result["node_value"] = value
   - For time decay: result["new_confidence"] = calculated_value
4. Handle errors gracefully with result["updated"] = False and result["reason"]

The system will automatically apply the result values to the entity graph.
You only need to set the appropriate result variables.

Generate code that:
1. Uses `patient_id` to query the database
2. Extracts the appropriate value
3. Sets result variables (result["node_value"], result["updated"], etc.)
4. Handles errors gracefully

Return ONLY the Python code without markdown code blocks."""
    
    def __init__(self, db_session: Session, config_path: Optional[str] = None):
        """
        Initialize Update Agent
        
        Args:
            db_session: Database session for operations
            config_path: Optional path to config file
        """
        self.db = db_session
        self.config = get_config(config_path)
        self.max_retries = 3
        
        # Initialize LLM model
        model_name = self.config.get("main_agent.model", self.config.get_model())
        temperature = self.config.get("main_agent.temperature", 0.7)
        
        self.model = ChatOpenAI(
            model=model_name,
            api_key=self.config.get_api_key(),
            base_url=self.config.get_base_url(),
            temperature=temperature
        )
        
        logger.info(f"UpdateAgent initialized with model={model_name}")
        
        # Load prompt templates
        self.prompt_templates = self._load_prompt_templates()
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load prompt templates from files"""
        templates = {}
        template_names = ["metric", "symptom", "time_decay"]
        
        for name in template_names:
            template_path = Path(__file__).parent.parent / "prompts" / f"update_agent_{name}.txt"
            try:
                if template_path.exists():
                    templates[name] = template_path.read_text(encoding="utf-8")
                    logger.debug(f"Loaded prompt template: {name}")
                else:
                    logger.warning(f"Prompt template not found: {template_path}")
                    templates[name] = self._get_default_prompt(name)
            except Exception as e:
                logger.error(f"Error loading prompt template {name}: {e}")
                templates[name] = self._get_default_prompt(name)
        
        return templates
    
    def _get_default_prompt(self, prompt_type: str) -> str:
        """Get default prompt if file not found"""
        if prompt_type == "metric":
            return "Query latest metric using MetricCRUD.get_latest_record(sandbox, patient_id, metric_name) and update node value."
        elif prompt_type == "symptom":
            return "Query symptoms using patient_crud.get_symptoms(sandbox, patient_id) and update node status."
        else:
            return "Apply time decay to node confidence based on last_updated timestamp."
    
    def update_all_nodes(
        self,
        entity_graph,
        patient_id: str
    ) -> Dict[str, int]:
        """
        Update all nodes in EntityGraph

        Args:
            entity_graph: EntityGraph instance
            patient_id: Patient identifier

        Returns:
            Dictionary with update counts:
            - metric_updated: Number of metric nodes updated
            - symptom_updated: Number of symptom nodes updated
            - time_decay_applied: Number of nodes with time decay applied
        """
        stats = {
            "metric_updated": 0,
            "symptom_updated": 0,
            "time_decay_applied": 0
        }

        logger.info(f"[SYNC] Starting update for {entity_graph.entity_graph.number_of_nodes()} nodes")

        # Store patient_id for use in _normalize_metric_name
        self._current_patient_id = patient_id
        
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            # Classify node type
            node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
            
            if node_type == "metric":
                success = self._update_metric_node(
                    entity_graph, node_id, metric_name, patient_id
                )
                if success:
                    stats["metric_updated"] += 1
            
            elif node_type == "symptom":
                success = self._update_symptom_node(
                    entity_graph, node_id, patient_id
                )
                if success:
                    stats["symptom_updated"] += 1
            
            # Always apply time decay
            self._apply_time_decay(entity_graph, node_id, node_type)
            stats["time_decay_applied"] += 1
        
        logger.info(
            f"Update complete: {stats['metric_updated']} metrics, "
            f"{stats['symptom_updated']} symptoms, "
            f"{stats['time_decay_applied']} time decay applied"
        )
        
        return stats

    def _normalize_metric_name(self, node_name: str) -> Tuple[str, bool]:
        """
        Normalize DrHyper node name to database metric name

        Args:
            node_name: Node name from DrHyper EntityGraph

        Returns:
            Tuple of (normalized_name, is_abstract)
            - normalized_name: Database metric name or original if no mapping
            - is_abstract: True if this is an abstract node without direct DB records
        """
        node_name_lower = node_name.lower().strip()

        # Check direct mapping first
        if node_name_lower in NODE_TO_METRIC_MAPPING:
            return NODE_TO_METRIC_MAPPING[node_name_lower], False

        # Check for abstract node patterns
        for pattern in ABSTRACT_NODE_PATTERNS:
            if re.match(pattern, node_name_lower, re.IGNORECASE):
                return node_name, True

        # Try fuzzy matching with available metrics
        # Get available metrics from database
        try:
            metadata = MetricCRUD.get_metric_metadata(self.db, self._current_patient_id)
            if metadata.get("available"):
                available_metrics = metadata.get("unique_metrics", [])

                # Simple fuzzy match - check if node name contains metric name
                for metric in available_metrics:
                    metric_lower = metric.lower()
                    if metric_lower in node_name_lower or node_name_lower in metric_lower:
                        return metric, False

                    # Check word-by-word matching
                    node_words = set(node_name_lower.split())
                    metric_words = set(metric_lower.split())
                    if len(node_words & metric_words) >= 2:  # At least 2 common words
                        return metric, False
        except Exception as e:
            logger.debug(f"Error during fuzzy matching: {e}")

        # No match found, return original
        return node_name, False

    def _is_abstract_node(self, node_name: str) -> bool:
        """
        Check if node is an abstract concept without direct database records

        Args:
            node_name: Node name to check

        Returns:
            True if abstract node
        """
        _, is_abstract = self._normalize_metric_name(node_name)
        return is_abstract

    async def update_all_nodes_async(
        self,
        entity_graph,
        patient_id: str,
        max_concurrency: int = 5
    ) -> Dict[str, int]:
        """
        Update all nodes in EntityGraph using async parallel execution

        Args:
            entity_graph: EntityGraph instance
            patient_id: Patient identifier
            max_concurrency: Maximum concurrent updates (default 5)

        Returns:
            Dictionary with update counts
        """
        stats = {
            "metric_updated": 0,
            "symptom_updated": 0,
            "time_decay_applied": 0
        }

        logger.info(f"[ASYNC] Starting parallel update for {entity_graph.entity_graph.number_of_nodes()} nodes")

        # Store patient_id for use in _normalize_metric_name
        self._current_patient_id = patient_id

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrency)

        # Create tasks for all nodes
        tasks = []
        node_types = []

        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            # Classify node type
            node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
            node_types.append((node_id, node_type, metric_name))

        # Execute all updates in parallel with concurrency limit
        results = await self._update_nodes_in_parallel(
            entity_graph, node_types, patient_id, semaphore
        )

        # Aggregate results
        for node_id, success, node_type in results:
            if success:
                if node_type == "metric":
                    stats["metric_updated"] += 1
                elif node_type == "symptom":
                    stats["symptom_updated"] += 1
            stats["time_decay_applied"] += 1

        logger.info(
            f"[ASYNC] Update complete: {stats['metric_updated']} metrics, "
            f"{stats['symptom_updated']} symptoms, "
            f"{stats['time_decay_applied']} time decay applied"
        )

        return stats

    async def _update_nodes_in_parallel(
        self,
        entity_graph,
        node_types: List[Tuple[str, str, Optional[str]]],
        patient_id: str,
        semaphore: asyncio.Semaphore
    ) -> List[Tuple[str, bool, str]]:
        """
        Execute node updates in parallel with concurrency control

        Args:
            entity_graph: EntityGraph instance
            node_types: List of (node_id, node_type, metric_name) tuples
            patient_id: Patient identifier
            semaphore: Asyncio semaphore for concurrency control

        Returns:
            List of (node_id, success, node_type) tuples
        """
        async def update_single_node(node_id: str, node_type: str, metric_name: Optional[str]):
            async with semaphore:
                try:
                    if node_type == "metric" and metric_name:
                        success = await asyncio.to_thread(
                            self._update_metric_node,
                            entity_graph, node_id, metric_name, patient_id
                        )
                    elif node_type == "symptom":
                        success = await asyncio.to_thread(
                            self._update_symptom_node,
                            entity_graph, node_id, patient_id
                        )
                    else:
                        success = True  # Skip unknown node types

                    # Apply time decay
                    self._apply_time_decay(entity_graph, node_id, node_type)

                    return (node_id, success, node_type)

                except Exception as e:
                    logger.error(f"[ASYNC] Error updating node {node_id}: {e}")
                    return (node_id, False, node_type)

        # Create and run all tasks
        tasks = [
            update_single_node(node_id, node_type, metric_name)
            for node_id, node_type, metric_name in node_types
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            node_id, node_type, _ = node_types[i]
            if isinstance(result, Exception):
                logger.error(f"[ASYNC] Task failed for node {node_id}: {result}")
                processed_results.append((node_id, False, node_type))
            else:
                processed_results.append(result)

        return processed_results
    
    def _update_metric_node(
        self,
        entity_graph,
        node_id: str,
        metric_name: str,
        patient_id: str
    ) -> bool:
        """
        Update metric node with latest database record

        Uses metric name mapping to resolve DrHyper node names to database metric names.

        Args:
            entity_graph: EntityGraph instance
            node_id: Node ID to update
            metric_name: Name of the metric (from DrHyper)
            patient_id: Patient identifier

        Returns:
            True if update successful
        """
        node_data = entity_graph.entity_graph.nodes[node_id]
        node_name = node_data.get("name", "")
        current_value = node_data.get("value", "")

        # Normalize metric name using mapping
        normalized_metric_name, is_abstract = self._normalize_metric_name(metric_name)

        if is_abstract:
            logger.info(
                f"[UPDATE METRIC] Skipping abstract node: {metric_name} -> {normalized_metric_name}"
            )
            # Mark abstract nodes as successfully skipped (not a failure)
            node_data["value"] = f"[Abstract: {metric_name}]"
            node_data["last_updated"] = datetime.now()
            return True

        logger.info(
            f"[UPDATE METRIC] node_id={node_id}, metric_name={metric_name} -> {normalized_metric_name}, "
            f"current_value={current_value}, patient_id={patient_id}"
        )

        # Get metric metadata for dynamic context
        metric_metadata = MetricCRUD.get_metric_metadata(self.db, patient_id, normalized_metric_name)
        metadata_text = self._format_metadata_for_prompt(metric_metadata)

        logger.debug(
            f"[UPDATE METRIC] Retrieved metadata for {normalized_metric_name}: "
            f"{metric_metadata.get('record_count', 0)} records"
        )

        # Format prompt with node information AND metadata
        prompt = self.prompt_templates["metric"].format(
            node_id=node_id,
            node_name=node_name,
            metric_name=normalized_metric_name,  # Use normalized name
            current_value=current_value,
            metric_metadata=metadata_text
        )

        logger.debug(f"[UPDATE METRIC] Prompt template filled for {node_id}")

        return self._generate_and_execute_code(
            entity_graph, node_id, patient_id, "metric", prompt
        )

    def _format_metadata_for_prompt(self, metadata: Dict[str, Any]) -> str:
        """
        Format metric metadata for inclusion in prompt

        Args:
            metadata: Metadata dictionary from MetricCRUD.get_metric_metadata

        Returns:
            Formatted string for prompt
        """
        if not metadata.get("available"):
            return "No metric records available for this patient."

        lines = [
            f"- Record count: {metadata['record_count']} records",
            f"- Date range: {metadata['date_range']['earliest']} to {metadata['date_range']['latest']}",
            f"- Available fields: {', '.join(metadata['available_fields'])}",
            f"- Value types: {', '.join(metadata['value_types'])}",
        ]

        if metadata.get('unique_metrics'):
            lines.append(f"- Available metrics: {', '.join(metadata['unique_metrics'][:5])}")

        return "\n".join(lines)
    
    def _update_symptom_node(
        self,
        entity_graph,
        node_id: str,
        patient_id: str
    ) -> bool:
        """
        Update symptom node from patient symptoms
        
        Args:
            entity_graph: EntityGraph instance
            node_id: Node ID to update
            patient_id: Patient identifier
        
        Returns:
            True if update successful
        """
        node_data = entity_graph.entity_graph.nodes[node_id]
        node_name = node_data.get("name", "")
        current_status = node_data.get("status", 0)
        current_value = node_data.get("value", "")
        
        # Format prompt with node information
        prompt = self.prompt_templates["symptom"].format(
            node_id=node_id,
            node_name=node_name,
            current_status=current_status,
            current_value=current_value
        )
        
        logger.debug(f"Updating symptom node {node_id} ({node_name})")
        
        return self._generate_and_execute_code(
            entity_graph, node_id, patient_id, "symptom", prompt
        )
    
    def _apply_time_decay(
        self,
        entity_graph,
        node_id: str,
        node_type: str
    ) -> float:
        """
        Apply time decay to node confidence
        
        Args:
            entity_graph: EntityGraph instance
            node_id: Node ID
            node_type: Type of node
        
        Returns:
            New confidence value
        """
        from backend.services.time_decay_executor import TimeDecayExecutor
        
        decay_executor = TimeDecayExecutor()
        new_confidence = decay_executor.apply_decay(entity_graph, node_id, node_type)
        
        return new_confidence
    
    def _generate_and_execute_code(
        self,
        entity_graph,
        node_id: str,
        patient_id: str,
        node_type: str,
        prompt: str
    ) -> bool:
        """
        Generate code with LLM and execute with retry loop
        
        Args:
            entity_graph: EntityGraph instance
            node_id: Node ID to update
            patient_id: Patient identifier (injected by environment)
            node_type: Type of node (metric/symptom)
            prompt: Prompt template with node information
        
        Returns:
            True if code generation and execution successful
        """
        logger.info(f"[LLM CODE GEN] Starting code generation for node {node_id} (type={node_type})")
        logger.debug(f"[LLM CODE GEN] Prompt length: {len(prompt)} chars")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"[LLM CODE GEN] Attempt {attempt + 1}/{self.max_retries} for node {node_id}")
                
                # Generate code using LLM
                logger.debug("[LLM CODE GEN] Invoking LLM API...")
                response = self.model.invoke([
                    SystemMessage(content=self.SYSTEM_MESSAGE),
                    HumanMessage(content=prompt)
                ])
                
                # Extract code from response
                code = self._extract_code(response.content)
                
                if not code:
                    logger.warning(f"[LLM CODE GEN] No code extracted from LLM response (attempt {attempt + 1})")
                    logger.debug(f"[LLM CODE GEN] Raw response: {response.content[:500]}...")
                    prompt += "\n\nPlease generate valid Python code."
                    continue
                
                logger.info(f"[LLM CODE GEN] Code extracted ({len(code)} chars)")
                logger.info(f"[LLM CODE GEN] Generated code (first 300 chars):\n{code[:300]}...")
                logger.debug(f"[LLM CODE GEN] Full generated code:\n{code}")

                # Validate code before execution
                logger.debug(f"[LLM CODE GEN] Validating code for node {node_id}...")
                is_valid, error_msg = self._validate_code(code, node_id)

                if not is_valid:
                    logger.warning(f"[LLM CODE GEN] ❌ VALIDATION FAILED: {error_msg}")
                    prompt += f"\n\nPrevious error: {error_msg}\nPlease fix and regenerate code."
                    continue

                logger.debug(f"[LLM CODE GEN] Code validation passed")

                # Execute code
                logger.info(f"[LLM CODE GEN] Executing generated code for node {node_id}...")
                success, result = self._execute_code(
                    code, patient_id, entity_graph, node_id, node_type
                )
                
                if success:
                    logger.info(f"[LLM CODE GEN] ✅ SUCCESS: Node {node_id} updated on attempt {attempt + 1}")
                    logger.info(f"[LLM CODE GEN] Result: {result}")
                    return True
                
                # Execution failed - retry with error feedback
                error_message = result.get("error", "Unknown error")
                logger.warning(f"[LLM CODE GEN] ❌ FAILED: {error_message}")
                prompt += f"\n\nPrevious error: {error_message}\nPlease fix and regenerate code."
                
            except Exception as e:
                logger.error(f"[LLM CODE GEN] ❌ EXCEPTION: {e}", exc_info=True)
                prompt += f"\n\nPrevious exception: {str(e)}\nPlease fix and regenerate code."
        
        logger.error(f"[LLM CODE GEN] ❌ FAILED: Node {node_id} not updated after {self.max_retries} attempts")
        return False
    
    def _extract_code(self, response_content: str) -> str:
        """
        Extract Python code from LLM response

        Handles responses with or without markdown code blocks.

        Args:
            response_content: Raw LLM response

        Returns:
            Extracted Python code
        """
        content = response_content.strip()

        # Try to extract from markdown code blocks
        code_block_pattern = r"```python\s*(.*?)\s*```"
        match = re.search(code_block_pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        # Try generic code block
        code_block_pattern = r"```\s*(.*?)\s*```"
        match = re.search(code_block_pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        # No code blocks found - return content as-is (might be plain code)
        return content

    def _validate_code(self, code: str, node_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate generated code before execution

        Checks for common errors:
        - 'return' statements (not allowed in exec)
        - Direct entity_graph access (not allowed)
        - Syntax errors

        Args:
            code: Code to validate
            node_id: Node ID for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for 'return' statements
        if re.search(r'\breturn\b', code):
            return False, f"Code contains 'return' statement (not allowed in exec) for node {node_id}"

        # Check for direct entity_graph access (NOT ALLOWED)
        # LLM should use result variables only
        if re.search(r'entity_graph\.nodes\[', code):
            return False, f"Direct entity_graph access not allowed (use result variables) for node {node_id}"
        
        if re.search(r'entity_graph\.entity_graph\.nodes\[', code):
            return False, f"Direct entity_graph access not allowed (use result variables) for node {node_id}"

        # Check for syntax errors
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            return False, f"Syntax error in generated code for node {node_id}: {str(e)}"

        return True, None
    
    def _execute_code(
        self,
        code: str,
        patient_id: str,
        entity_graph,
        node_id: str,
        node_type: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute generated code in controlled environment

        CRITICAL:
        - patient_id is injected into exec_globals, NOT in the prompt
        - Code should use result variables, NOT access entity_graph directly
        - This method applies the result to the entity graph

        Args:
            code: Python code to execute
            patient_id: Patient identifier (injected by environment)
            entity_graph: EntityGraph instance
            node_id: Node ID to update
            node_type: Type of node

        Returns:
            Tuple of (success, result_dict)
        """
        logger.info(f"[CODE EXEC] Preparing execution environment for node {node_id}")
        logger.debug(f"[CODE EXEC] patient_id={patient_id}, node_type={node_type}")

        try:
            # Create execution environment
            # patient_id is injected HERE, not in the prompt!
            exec_globals = {
                "patient_id": patient_id,  # ← INJECTED BY ENVIRONMENT
                "sandbox": self.db,
                "MetricCRUD": MetricCRUD,
                "patient_crud": patient_crud,
                "node_id": node_id,
                "datetime": datetime,
                "result": {},  # ← Code sets result variables here
            }

            logger.info(f"[CODE EXEC] Executing code in sandbox environment...")

            # Execute code
            exec(code, exec_globals)

            # Get result from code
            result = exec_globals.get("result", {})

            logger.debug(f"[CODE EXEC] Execution result: {result}")

            # Apply result to entity graph
            success = self._apply_result_to_graph(entity_graph, node_id, node_type, result)

            if success:
                logger.info(f"[CODE EXEC] ✅ SUCCESS: Node {node_id} updated successfully")
                return True, result

            # Code executed but update failed
            logger.warning(f"[CODE EXEC] ❌ Code executed but updated=False: {result.get('reason', 'Unknown')}")
            return False, {
                "error": result.get("reason", "Update returned updated=False")
            }

        except Exception as e:
            logger.error(f"[CODE EXEC] ❌ EXCEPTION: {e}", exc_info=True)
            logger.error(f"[CODE EXEC] Code that failed:\n{code}")
            return False, {"error": str(e)}

    def _apply_result_to_graph(
        self,
        entity_graph,
        node_id: str,
        node_type: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Apply result variables to entity graph

        Args:
            entity_graph: EntityGraph instance
            node_id: Node ID to update
            node_type: Type of node (metric/symptom/time_decay)
            result: Result dictionary from code execution

        Returns:
            True if update successful
        """
        if not result.get("updated") and node_type != "time_decay":
            # For metric/symptom updates, check updated flag
            return False

        # Get node data
        node_data = entity_graph.entity_graph.nodes[node_id]

        # Apply value update
        if "node_value" in result:
            old_value = node_data.get("value")
            node_data["value"] = result["node_value"]
            logger.info(
                f"[APPLY RESULT] Node {node_id} value updated: "
                f"{old_value} → {result['node_value']}"
            )

        # Apply status update with string-to-numeric conversion
        if "node_status" in result:
            old_status = node_data.get("status")
            new_status = result["node_status"]
            
            # Status mapping for string-to-numeric conversion
            STATUS_MAP = {
                "updated": 2,
                "active": 2,
                "confirmed": 2,
                "verified": 2,
                "high_confidence": 2,
                "resolved": 0,
                "inactive": 0,
                "unconfirmed": 0,
                "unknown": 0,
                "no_data": 0,
            }
            
            # Convert string status to numeric
            if isinstance(new_status, str):
                new_status = STATUS_MAP.get(new_status.lower(), 1)  # Default to 1 if unknown
                logger.debug(
                    f"[APPLY RESULT] Converted status '{result['node_status']}' → {new_status}"
                )
            
            # Validate status is numeric 0, 1, or 2
            if not isinstance(new_status, (int, float)) or new_status not in (0, 1, 2):
                logger.warning(
                    f"[APPLY RESULT] Invalid status {new_status} for node {node_id}, "
                    f"defaulting to 1"
                )
                new_status = 1
            
            node_data["status"] = int(new_status)
            logger.info(
                f"[APPLY RESULT] Node {node_id} status updated: "
                f"{old_status} → {int(new_status)}"
            )

        # Apply confidence update (for time decay)
        if "new_confidence" in result:
            old_confidence = node_data.get("confidence", 1.0)
            node_data["confidence"] = result["new_confidence"]
            logger.info(
                f"[APPLY RESULT] Node {node_id} confidence updated: "
                f"{old_confidence} → {result['new_confidence']}"
            )

        # Apply measured_at timestamp if provided
        if "measured_at" in result:
            try:
                node_data["last_updated"] = datetime.fromisoformat(result["measured_at"])
            except (ValueError, TypeError):
                node_data["last_updated"] = datetime.now()
        else:
            # Update timestamp to now
            node_data["last_updated"] = datetime.now()

        return True
    
    def __repr__(self):
        return f"UpdateAgent(model={self.config.get_model()}, db_session={type(self.db).__name__})"
