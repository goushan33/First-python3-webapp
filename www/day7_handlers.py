
import asyncio,time
from day5_web_frame import get, post

from day4_models import User, Comment, Blog, next_id

'''
@get('/')
async def index(request):
    users =await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }
'''

@get('/')
async def index(request):
    summary='used for test summary1'
    blogs=[Blog(id='1',name='blog1',summary=summary,created_at=time.time()-120),
           Blog(id='2',name='blog2',summary=summary,created_at=time.time()-3600),
           Blog(id='3',name='blog3',summary=summary,created_at=time.time()-7200)]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }
