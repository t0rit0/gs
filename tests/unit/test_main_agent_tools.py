"""
Unit tests for MainAgent tools

Following TDD approach, these tests are written before implementation.
All tests should fail initially and pass after tools are implemented.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Optional

# These will be imported from the actual implementation once created
# For now, we define placeholders to make the tests compile
from typing import TypedDict


class MainAgentState(TypedDict, total=False):
    """Placeholder for MainAgentState - will be imported from actual implementation"""
    messages: list
    conversation_id: str
    patient_id: str
    entity_graph: object  # Will be EntityGraph
    accomplish: bool
    report: Optional[dict]
    last_hint: str


class TestGetNextDiagnosticQuestion:
    """Tests for get_next_diagnostic_question tool"""

    @pytest.fixture
    def mock_entity_graph(self):
        """Create a mock EntityGraph"""
        graph = Mock()
        graph.get_hint_message = Mock(return_value=("Ask about blood pressure", False, []))
        return graph

    @pytest.fixture
    def sample_state(self, mock_entity_graph):
        """Create a sample state for testing"""
        return MainAgentState(
            messages=[],
            conversation_id="test_conv_123",
            patient_id="patient_456",
            entity_graph=mock_entity_graph,
            accomplish=False,
            report=None,
            last_hint=""
        )

    def test_returns_hint_message(self, sample_state, mock_entity_graph):
        """
        Test that tool returns hint from graph

        Should call graph.get_hint_message() and return the hint message.
        """
        # This test will fail until tool is implemented
        from backend.agents.main_agent.tools import get_next_diagnostic_question

        result = get_next_diagnostic_question(sample_state)

        # Verify graph.get_hint_message was called
        mock_entity_graph.get_hint_message.assert_called_once()

        # Verify hint is returned
        assert result == "Ask about blood pressure"

    def test_handles_accomplish_state(self, sample_state, mock_entity_graph):
        """
        Test that tool handles accomplish state correctly

        When graph indicates all data is collected (accomplish=True),
        tool should return a completion message.
        """
        from backend.agents.main_agent.tools import get_next_diagnostic_question

        # Mock graph to return accomplish=True
        mock_entity_graph.get_hint_message = Mock(
            return_value=("Data collection complete", True, [])
        )

        result = get_next_diagnostic_question(sample_state)

        # Verify completion message is returned
        assert "complete" in result.lower()

    def test_updates_state_with_last_hint(self, sample_state, mock_entity_graph):
        """
        Test that tool updates state with last_hint

        The hint should be stored in state for use in update_diagnosis_graph.
        """
        from backend.agents.main_agent.tools import get_next_diagnostic_question

        get_next_diagnostic_question(sample_state)

        # Verify state was updated with last_hint
        assert sample_state["last_hint"] == "Ask about blood pressure"

    def test_updates_accomplish_status(self, sample_state, mock_entity_graph):
        """
        Test that tool updates accomplish status in state

        When graph returns accomplish=True, state should be updated.
        """
        from backend.agents.main_agent.tools import get_next_diagnostic_question

        # Mock graph to return accomplish=True
        mock_entity_graph.get_hint_message = Mock(
            return_value=("Data collection complete", True, [])
        )

        get_next_diagnostic_question(sample_state)

        # Verify accomplish was updated in state
        assert sample_state["accomplish"] is True


class TestUpdateDiagnosisGraph:
    """Tests for update_diagnosis_graph tool"""

    @pytest.fixture
    def mock_entity_graph(self):
        """Create a mock EntityGraph"""
        graph = Mock()
        graph.accept_message = Mock(return_value=[])
        return graph

    @pytest.fixture
    def sample_state(self, mock_entity_graph):
        """Create a sample state for testing"""
        return MainAgentState(
            messages=[],
            conversation_id="test_conv_123",
            patient_id="patient_456",
            entity_graph=mock_entity_graph,
            accomplish=False,
            report=None,
            last_hint="Ask about blood pressure"
        )

    def test_updates_graph_nodes(self, sample_state, mock_entity_graph):
        """
        Test that tool updates graph with user response

        Should call graph.accept_message() with hint, query, and response.
        """
        from backend.agents.main_agent.tools import update_diagnosis_graph

        user_response = "My blood pressure is 120/80"
        query_message = "What is your blood pressure?"

        result = update_diagnosis_graph(
            state=sample_state,
            user_response=user_response,
            query_message=query_message
        )

        # Verify accept_message was called with correct parameters
        mock_entity_graph.accept_message.assert_called_once_with(
            hint="Ask about blood pressure",
            query=query_message,
            response=user_response
        )

    def test_returns_accomplish_status(self, sample_state, mock_entity_graph):
        """
        Test that tool correctly reports completion status

        Should return dict with accomplish status from graph.
        """
        from backend.agents.main_agent.tools import update_diagnosis_graph

        result = update_diagnosis_graph(
            state=sample_state,
            user_response="My blood pressure is 120/80",
            query_message="What is your blood pressure?"
        )

        # Verify result structure
        assert "accomplish" in result
        assert isinstance(result["accomplish"], bool)

    def test_returns_update_summary(self, sample_state, mock_entity_graph):
        """
        Test that tool returns summary of updates

        Should return dict with updated_nodes and new_nodes counts.
        """
        from backend.agents.main_agent.tools import update_diagnosis_graph

        result = update_diagnosis_graph(
            state=sample_state,
            user_response="My blood pressure is 120/80",
            query_message="What is your blood pressure?"
        )

        # Verify result structure
        assert "updated_nodes" in result
        assert "new_nodes" in result


class TestQueryPatientHistory:
    """Tests for query_patient_history tool"""

    @pytest.fixture
    def sample_state(self):
        """Create a sample state for testing"""
        return MainAgentState(
            messages=[],
            conversation_id="test_conv_123",
            patient_id="patient_456",
            entity_graph=Mock(),
            accomplish=False,
            report=None,
            last_hint=""
        )

    @pytest.mark.asyncio
    async def test_delegates_to_sql_agent(self, sample_state):
        """
        Test that tool delegates to SQLAgent for database queries

        Should use SQLAgent to query patient history.
        """
        from backend.agents.main_agent.tools import query_patient_history

        question = "What medications is the patient taking?"

        with patch('backend.agents.main_agent.tools.SQLAgent') as mock_sql_agent:
            mock_agent_instance = Mock()
            mock_agent_instance.process_request = Mock(
                return_value={
                    "success": True,
                    "final_answer": "Patient is taking lisinopril"
                }
            )
            mock_sql_agent.return_value = mock_agent_instance

            result = query_patient_history(state=sample_state, question=question)

            # Verify SQLAgent was called
            mock_agent_instance.process_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_formats_results(self, sample_state):
        """
        Test that tool returns formatted text results

        Should return query results as formatted string.
        """
        from backend.agents.main_agent.tools import query_patient_history

        with patch('backend.agents.main_agent.tools.SQLAgent') as mock_sql_agent:
            mock_agent_instance = Mock()
            mock_agent_instance.process_request = Mock(
                return_value={
                    "success": True,
                    "final_answer": "Patient is taking lisinopril"
                }
            )
            mock_sql_agent.return_value = mock_agent_instance

            result = query_patient_history(
                state=sample_state,
                question="What medications is the patient taking?"
            )

            # Verify formatted result
            assert isinstance(result, str)
            assert "lisinopril" in result

    @pytest.mark.asyncio
    async def test_passes_patient_id_from_state(self, sample_state):
        """
        Test that tool passes patient_id from state to SQLAgent

        Patient ID should come from state, not be a parameter.
        """
        from backend.agents.main_agent.tools import query_patient_history

        with patch('backend.agents.main_agent.tools.SQLAgent') as mock_sql_agent:
            mock_agent_instance = Mock()
            mock_agent_instance.process_request = Mock(
                return_value={"success": True, "final_answer": "Result"}
            )
            mock_sql_agent.return_value = mock_agent_instance

            query_patient_history(
                state=sample_state,
                question="What medications is the patient taking?"
            )

            # Verify patient_id from state was used
            call_args = mock_agent_instance.process_request.call_args
            assert "patient_456" in str(call_args)


class TestGenerateDiagnosticReport:
    """Tests for generate_diagnostic_report tool"""

    @pytest.fixture
    def mock_entity_graph(self):
        """Create a mock EntityGraph"""
        graph = Mock()
        graph._serialize_nodes_with_value = Mock(
            return_value="Blood Pressure: 120/80\nHeart Rate: 72 bpm"
        )
        return graph

    @pytest.fixture
    def sample_state(self, mock_entity_graph):
        """Create a sample state for testing"""
        return MainAgentState(
            messages=[],
            conversation_id="test_conv_123",
            patient_id="patient_456",
            entity_graph=mock_entity_graph,
            accomplish=True,
            report=None,
            last_hint=""
        )

    @pytest.mark.asyncio
    async def test_generates_report(self, sample_state, mock_entity_graph):
        """
        Test that tool creates structured report

        Should generate report with summary, findings, recommendations.
        """
        from backend.agents.main_agent.tools import generate_diagnostic_report

        with patch('backend.agents.main_agent.tools.ChatOpenAI') as mock_llm:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke = Mock(
                return_value=Mock(
                    content="Diagnostic report: Normal blood pressure, no issues."
                )
            )
            mock_llm.return_value = mock_llm_instance

            result = generate_diagnostic_report(sample_state)

            # Verify report structure
            assert isinstance(result, dict)
            assert "summary" in result

    @pytest.mark.asyncio
    async def test_saves_to_state(self, sample_state):
        """
        Test that tool saves report to state

        Report should be stored in state["report"] for checkpointer persistence.
        """
        from backend.agents.main_agent.tools import generate_diagnostic_report

        with patch('backend.agents.main_agent.tools.ChatOpenAI') as mock_llm:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke = Mock(
                return_value=Mock(content="Diagnostic report")
            )
            mock_llm.return_value = mock_llm_instance

            generate_diagnostic_report(sample_state)

            # Verify report was saved to state
            assert sample_state["report"] is not None
            assert isinstance(sample_state["report"], dict)

    @pytest.mark.asyncio
    async def test_serializes_graph_data(self, sample_state, mock_entity_graph):
        """
        Test that tool serializes collected data from graph

        Should call _serialize_nodes_with_value to get collected information.
        """
        from backend.agents.main_agent.tools import generate_diagnostic_report

        with patch('backend.agents.main_agent.tools.ChatOpenAI') as mock_llm:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke = Mock(return_value=Mock(content="Report"))
            mock_llm.return_value = mock_llm_instance

            generate_diagnostic_report(sample_state)

            # Verify graph serialization was called
            mock_entity_graph._serialize_nodes_with_value.assert_called_once()
