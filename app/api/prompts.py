import random
from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

PROMPT_POOL = [
    "What made you smile today?",
    "Describe a moment you felt truly present.",
    "What's something you're grateful for right now?",
    "How did you take care of yourself today?",
    "What emotion showed up the most today?",
    "Write about a challenge you're facing.",
    "What would you tell your younger self?",
    "Describe your ideal day from start to finish.",
    "What's one thing you'd like to let go of?",
    "Who made a positive impact on you recently?",
    "What's a boundary you need to set or reinforce?",
    "Write about a fear you'd like to overcome.",
    "What does your inner critic say? How would you respond kindly?",
    "Describe a place where you feel completely safe.",
    "What's something new you learned about yourself?",
    "How do you feel in your body right now?",
    "What would you do if you knew you couldn't fail?",
    "Write a letter to someone you miss.",
    "What patterns do you notice in your mood lately?",
    "Describe a moment of unexpected joy.",
    "What does rest look like for you?",
    "What are you avoiding? Why?",
    "Write about a time you surprised yourself.",
    "What values are most important to you right now?",
    "How do you want to feel at the end of this week?",
    "What's a small win you can celebrate today?",
    "Describe your relationship with change.",
    "What song matches your mood right now and why?",
    "Write about a moment of connection with someone.",
    "What does your future self need to hear from you today?",
    "What are three things that bring you peace?",
    "Describe how you handle stress. What helps?",
]


@router.get("/")
async def get_prompts(
    current_user: User = Depends(get_current_active_user),
):
    """Return 5 shuffled inspiration prompts"""
    selected = random.sample(PROMPT_POOL, min(5, len(PROMPT_POOL)))
    return {"prompts": selected}
