import re
import logging
import time
import json
from day5_web_frame import get, post
from aiohttp import web
from day4_models import User, Comment, Blog, next_id
from day5_error_api import APIError,APIValueError
import hashlib
from day6_config import configs
import day6_config
import day3_orm

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
    cookie_str = request.cookies.get(COOKIE_NAME)
    print(cookie_str)
    user = ''
    summary = 'used for test summary1'
    blogs = [Blog(id='1', name='blog1', summary=summary, created_at=time.time() - 120),
             Blog(id='2', name='blog2', summary=summary, created_at=time.time() - 3600),
             Blog(id='3', name='blog3', summary=summary, created_at=time.time() - 7200)]
    if cookie_str:
        if 'deleted' in cookie_str:
            user = ''
        else:
            user = await cookiestr2user(cookie_str)

    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        #'__user__': request.__user__
    }


@get('/api/users')
async def api_get_users():
    users=await User.find_all(orderBy='created_at')
    for u in users:
        pass
    return dict(users=users)


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret#默认awesome



@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }

def user2cookiestr(user,max_life):
    #Generate cookie str by user
    expires=str(int(time.time()+max_life))
    s='%s-%s-%s-%s'%(user.id,user.passwd,expires,_COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

#提交注册信息
@post('/api/user/register')
async def api_register_user(*, email, name, passwd):
    '''
    通过验证邮箱进行唯一注册
    用户注册时输入的密码是通过sha1计算后的40位hash字符串，服务器也不会知道原始密码明文；
    用户头像是从gravatar网站抓取
    '''
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll(email=email)
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (name, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookiestr(user, 86400), max_age=86400, httponly=True)#86400s=24h
    user.passwd = '******'#返回的是cookie，所以把passwd用*代替
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


#登陆
@get('/signin')
async def signin():
    return {
        '__template__': 'signin.html'
    }
#提交登陆信息
@post('/api/user/authentication')
async def user_authentication(*,email,passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid null password.')
    user= await User.findAll(email=email)
    if len(user) == 0:
        raise APIError('signin:failed', 'no such email exist')
    user=user[0]#turn a list to a dict
    user=day6_config.toDict(user)# a dict to a special Dict
    input_passwd = '%s:%s' % (user.name, passwd)
    input_hash_passwd=hashlib.sha1(input_passwd.encode('utf-8')).hexdigest()
    db_passwd=user.passwd
    if input_hash_passwd!=db_passwd:
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookiestr(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


#解密cookie,显示当前登陆的用户
async def cookiestr2user(cookiestr):
    if not cookiestr:
        return None
    try:
        L=cookiestr.split('-')
        if len(L)!=3:
            return None
        uid, expires, hashed_s=L
        if int(expires)<time.time():
            return None
        user = await User.find(uid)#按主键查找
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if hashed_s!= hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('the hashed_s from cookie is invaild')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None




#退出登陆
@get('/signout')
async def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r
