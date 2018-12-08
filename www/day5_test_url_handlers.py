from day5_web_frame import get,post

@get('/')
def handler_url_blog(request):
    body='<h1>Awesome</h1>'
    return body

@get('/greeting')
def handler_url_blog(request):
    body='<h1>Awesome:/greeting</h1>'
    return body


@post('/greeting')
def handler_url_comment(*,name,request):
    body='<h1>Awesome:/greeting%s</h1>'%name
    return body
