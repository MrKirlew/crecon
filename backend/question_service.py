"""
Question Service - Manages questions, schedules, and conversation state
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from location_service import LocationService
from recurrence_service import RecurrenceService

logger = logging.getLogger(__name__)


class Question:
    """Question model"""
    def __init__(
        self,
        id: str,
        location_id: str,
        question_text: str,
        question_type: str = "sequential",
        order: int = 0,
        recurrence: Optional[Dict[str, Any]] = None,
        throttle: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.location_id = location_id
        self.question_text = question_text
        self.question_type = question_type
        self.order = order
        self.recurrence = recurrence or {}
        self.throttle = throttle or {}
        self.enabled = enabled
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.last_triggered: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "location_id": self.location_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "order": self.order,
            "recurrence": self.recurrence,
            "throttle": self.throttle,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class Schedule:
    """Schedule model"""
    def __init__(
        self,
        id: str,
        location_id: str,
        questions: List[Question],
        name: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.location_id = location_id
        self.questions = questions
        self.name = name
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "location_id": self.location_id,
            "name": self.name,
            "questions": [q.to_dict() for q in sorted(self.questions, key=lambda x: x.order)],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class ConversationSession:
    """Conversation session state"""
    def __init__(
        self,
        session_id: str,
        location_id: str,
        schedule_id: str,
        questions: List[Question]
    ):
        self.session_id = session_id
        self.location_id = location_id
        self.schedule_id = schedule_id
        self.questions = sorted(questions, key=lambda x: x.order)
        self.current_question_index = 0
        self.answers: Dict[str, str] = {}
        self.conversation_active = True
        self.created_at = datetime.utcnow()
    
    def get_current_question(self) -> Optional[Question]:
        """Get current question"""
        if self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    def get_next_question(self) -> Optional[Question]:
        """Get next question"""
        if self.current_question_index + 1 < len(self.questions):
            return self.questions[self.current_question_index + 1]
        return None
    
    def answer_current_question(self, answer: str) -> bool:
        """Answer current question and move to next"""
        current = self.get_current_question()
        if current:
            self.answers[current.id] = answer
            self.current_question_index += 1
            return True
        return False
    
    def is_complete(self) -> bool:
        """Check if all questions are answered"""
        return self.current_question_index >= len(self.questions)


class QuestionService:
    """Service for managing questions and schedules"""
    
    def __init__(
        self,
        location_service: LocationService,
        recurrence_service: RecurrenceService
    ):
        self.location_service = location_service
        self.recurrence_service = recurrence_service
        # In-memory storage (replace with database in production)
        self.questions: Dict[str, Question] = {}
        self.schedules: Dict[str, Schedule] = {}
        self.sessions: Dict[str, ConversationSession] = {}
        self.answer_history: List[Dict[str, Any]] = []
        logger.info("QuestionService initialized")
    
    def create_question(
        self,
        location_id: str,
        question_text: str,
        question_type: str = "sequential",
        order: int = 0,
        recurrence: Optional[Dict[str, Any]] = None,
        throttle: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> Question:
        """Create a new question"""
        question_id = str(uuid4())
        question = Question(
            id=question_id,
            location_id=location_id,
            question_text=question_text,
            question_type=question_type,
            order=order,
            recurrence=recurrence,
            throttle=throttle,
            enabled=enabled
        )
        self.questions[question_id] = question
        logger.info(f"Created question: {question_id}")
        return question
    
    def create_schedule(
        self,
        location_id: str,
        questions: List[Question],
        name: Optional[str] = None
    ) -> Schedule:
        """Create a new schedule"""
        schedule_id = str(uuid4())
        schedule = Schedule(
            id=schedule_id,
            location_id=location_id,
            questions=questions,
            name=name
        )
        self.schedules[schedule_id] = schedule
        logger.info(f"Created schedule: {schedule_id} with {len(questions)} questions")
        return schedule
    
    def get_schedules_for_location(self, location_id: str) -> List[Schedule]:
        """Get all schedules for a location"""
        return [s for s in self.schedules.values() if s.location_id == location_id]
    
    def get_questions_for_location(
        self,
        location_id: str,
        enabled_only: bool = True
    ) -> List[Question]:
        """Get all questions for a location"""
        questions = [q for q in self.questions.values() if q.location_id == location_id]
        if enabled_only:
            questions = [q for q in questions if q.enabled]
        return sorted(questions, key=lambda x: x.order)
    
    def queue_questions_for_location(
        self,
        location_id: str,
        current_time: Optional[datetime] = None
    ) -> List[Question]:
        """
        Queue questions that should be asked for a location
        Checks recurrence and throttling rules
        """
        questions = self.get_questions_for_location(location_id, enabled_only=True)
        queued = []
        
        for question in questions:
            # Check recurrence
            should_trigger = self.recurrence_service.should_trigger_now(
                recurrence=question.recurrence,
                last_triggered=question.last_triggered,
                current_time=current_time
            )
            
            if not should_trigger:
                continue
            
            # Check throttle
            should_ask = self.recurrence_service.check_throttle(
                throttle=question.throttle,
                question_id=question.id,
                answer_history=self.answer_history
            )
            
            if should_ask:
                queued.append(question)
        
        return sorted(queued, key=lambda x: x.order)
    
    def create_conversation_session(
        self,
        location_id: str,
        schedule_id: str,
        questions: List[Question]
    ) -> ConversationSession:
        """Create a new conversation session"""
        session_id = str(uuid4())
        session = ConversationSession(
            session_id=session_id,
            location_id=location_id,
            schedule_id=schedule_id,
            questions=questions
        )
        self.sessions[session_id] = session
        logger.info(f"Created conversation session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get conversation session by ID"""
        return self.sessions.get(session_id)
    
    def process_conversation_message(
        self,
        session_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Process a conversation message and return next state
        Detects "next topic" command to move to next question
        """
        session = self.sessions.get(session_id)
        if not session:
            return {
                "error": "Session not found",
                "conversation_active": False
            }
        
        # Check for "next topic" command
        message_lower = message.lower().strip()
        next_topic_phrases = [
            "next topic",
            "next question",
            "move on",
            "skip",
            "next"
        ]
        
        is_next_command = any(phrase in message_lower for phrase in next_topic_phrases)
        
        if is_next_command:
            # Move to next question
            current = session.get_current_question()
            if current:
                # Save empty answer for skipped question
                session.answer_current_question("")
            
            next_q = session.get_current_question()
            if next_q:
                return {
                    "session_id": session_id,
                    "current_question_id": next_q.id,
                    "next_question": {
                        "question_id": next_q.id,
                        "question_text": next_q.question_text,
                        "question_type": next_q.question_type,
                        "order": next_q.order,
                        "location_id": session.location_id,
                        "schedule_id": session.schedule_id
                    },
                    "conversation_active": True,
                    "message": next_q.question_text,
                    "should_continue": True
                }
            else:
                # No more questions
                session.conversation_active = False
                return {
                    "session_id": session_id,
                    "current_question_id": None,
                    "next_question": None,
                    "conversation_active": False,
                    "message": "No more scheduled questions for this location.",
                    "should_continue": False
                }
        else:
            # Regular answer
            current = session.get_current_question()
            if current:
                session.answer_current_question(message)
                
                # Check if conversation type
                if current.question_type == "conversation":
                    # Continue conversation until "next topic"
                    return {
                        "session_id": session_id,
                        "current_question_id": current.id,
                        "next_question": None,
                        "conversation_active": True,
                        "message": f"Thank you for sharing. Continue the conversation or say 'next topic' to move on.",
                        "should_continue": True
                    }
                else:
                    # Sequential - move to next
                    next_q = session.get_current_question()
                    if next_q:
                        return {
                            "session_id": session_id,
                            "current_question_id": next_q.id,
                            "next_question": {
                                "question_id": next_q.id,
                                "question_text": next_q.question_text,
                                "question_type": next_q.question_type,
                                "order": next_q.order,
                                "location_id": session.location_id,
                                "schedule_id": session.schedule_id
                            },
                            "conversation_active": True,
                            "message": next_q.question_text,
                            "should_continue": True
                        }
                    else:
                        session.conversation_active = False
                        return {
                            "session_id": session_id,
                            "current_question_id": None,
                            "next_question": None,
                            "conversation_active": False,
                            "message": "No more scheduled questions for this location.",
                            "should_continue": False
                        }
            else:
                session.conversation_active = False
                return {
                    "session_id": session_id,
                    "current_question_id": None,
                    "next_question": None,
                    "conversation_active": False,
                    "message": "All questions have been answered.",
                    "should_continue": False
                }
    
    def record_answer(
        self,
        question_id: str,
        location_id: str,
        answer_text: str,
        delivery_channel: str = "app",
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Record an answer"""
        answer_record = {
            "id": str(uuid4()),
            "question_id": question_id,
            "location_id": location_id,
            "answer_text": answer_text,
            "timestamp": timestamp or datetime.utcnow(),
            "delivery_channel": delivery_channel
        }
        self.answer_history.append(answer_record)
        
        # Update question last_triggered
        question = self.questions.get(question_id)
        if question:
            question.last_triggered = answer_record["timestamp"]
        
        logger.info(f"Recorded answer for question {question_id}")
        return answer_record

