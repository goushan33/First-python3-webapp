
import asyncio
from day5_web_frame import get, post

from day4_models import User, Comment, Blog, next_id

@get('/')
async def index(request):
    users =await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }