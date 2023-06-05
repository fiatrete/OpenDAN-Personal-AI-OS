import random

all_jokes = [
    """- Do you have a girl friend?
- yeah
- nice! Where is she from?
- A different nation
- Oh really? Which nation?
- Imagination""",
    """Q: Why is the letter B so cool?
A: Because it's sitting in the middle of the AC.""",
    """Teacher: Make a sentence using the word "I"
Student: I is..
Teacher: No that is not correct, you should say I am
Student: Ok. I am the ninth letter in the alphabet!""",
    """Teacher: Did your father help you with your homework?
Sam: No, he did it all by himself!"""
]


def random_joke():
    return all_jokes[random.randint(0, len(all_jokes) - 1)]
