import time,uuid
from day3_orm import Model,StringField,IntegerField,BooleanField,FloatField,TextField

def next_id():
    #%015d:以数字形式输出，不足15的话右边补0.
    #%s000:结尾补000
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
#在编写ORM时，给一个Field增加一个default参数可以让ORM自己填入缺省值，非常方便。
## 并且，缺省值可以作为函数对象传入，在调用save()时自动计算。
#例如，主键id的缺省值是函数next_id，创建时间created_at的缺省值是函数time.time，
# #可以自动设置当前日期和时间。
class User(Model):
    __table__='users'

    id=StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    name=StringField(ddl='varchar(50)')
    email=StringField(ddl='varchar(50)')
    passwd=StringField(ddl='varchar(50)')
    admin=BooleanField()
    image=StringField(ddl='varchar(500)')
    created_at=FloatField(default=time.time)

class Blog(Model):
    __table__='blogs'

    id=StringField(primary_key=True,default=next_id,ddl='varchar(50)')
    name=StringField(ddl='varchar(50)')
    user_id=StringField(ddl='varchar(50)')
    user_name=StringField(ddl='varchar(50)')
    user_image=StringField(ddl='varchar(500)')
    summary=StringField(ddl='varchar(200)')
    content=TextField()
    created_at=FloatField(default=time.time)


class Comment(Model):
    __table__='comments'

    id=StringField(primary_key=True,default=next_id,ddl='varchar(50)')
    user_id=StringField(ddl='varchar(50)')
    user_name=StringField(ddl='varchar(50)')
    user_image=StringField(ddl='varchar(500)')
    blog_id=StringField(ddl='varchar(50)')
    content=TextField()
    # 把函数名time.time当作参数传递。在save()时才调用time.time()来计算
    #日期和时间用float类型存储在数据库中，而不是datetime类型，eg:1541759926.1508577
    created_at=FloatField(default=time.time)



